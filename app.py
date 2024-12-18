from flask import Flask, request, jsonify, render_template, url_for, redirect, session, send_file, abort, Response, send_file, make_response, render_template_string
from flask_cors import CORS
from text_processing import format_text
from flask_login import LoginManager, current_user, login_required
from logging.handlers import RotatingFileHandler


from dotenv import load_dotenv
load_dotenv()

# Dependencies for database
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

import openai
import os
import logging
import sys
import anthropic
import tiktoken 
import google.generativeai as genai
import subprocess # imported to support Scrapy

import requests
import json

import uuid # imported to generate unique IDs for files

from models import db, Folder, Conversation, User, SystemMessage, Website, UploadedFile
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler # for log file rotation
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename # for secure file uploads
from google.generativeai import GenerativeModel

# Imports for file uploads
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from file_processing import FileProcessor
from embedding_store import EmbeddingStore
from pinecone import Pinecone

from file_utils import (
    get_user_folder, get_system_message_folder, get_uploads_folder,
    get_processed_texts_folder, get_llmwhisperer_output_folder, ensure_folder_exists, get_file_path
)

# Imports for web search with footnotes
import asyncio
from asyncio import Queue
from functools import lru_cache
import aiohttp
from aiohttp import ClientSession
import asyncio
import time
from asyncio import Queue
from aiolimiter import AsyncLimiter
from bs4 import BeautifulSoup
from typing import List, Dict  
import re 
from concurrent.futures import ThreadPoolExecutor
from tenacity import retry, stop_after_attempt, wait_exponential
from async_timeout import timeout

from openai import OpenAI
client = OpenAI()

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")
if openai.api_key is None:
    raise ValueError("OPENAI_API_KEY environment variable not set")

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
db_url = os.getenv('DATABASE_URL')

BRAVE_SEARCH_API_KEY = os.getenv('BRAVE_SEARCH_API_KEY')

# Set debug directly here. Switch to False for production.
debug_mode = True

# Custom Unicode Formatter
class UnicodeFormatter(logging.Formatter):
    def format(self, record):
        try:
            return super().format(record)
        except UnicodeEncodeError:
            # If encoding fails, replace problematic characters
            return super().format(record).encode('utf-8', 'replace').decode('utf-8')

# Application Setup
app = Flask(__name__)
CORS(app)  # Cross-Origin Resource Sharing
app.config['DEBUG'] = debug_mode

# Configure logging
logging.basicConfig(level=logging.DEBUG if debug_mode else logging.INFO)

# Create custom formatter
unicode_formatter = UnicodeFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# File handler
file_handler = RotatingFileHandler("app.log", maxBytes=100000, backupCount=3, encoding='utf-8')
file_handler.setFormatter(unicode_formatter)
file_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(unicode_formatter)
console_handler.setLevel(logging.INFO if debug_mode else logging.WARNING)

# Control httpcore logging
httpcore_logger = logging.getLogger('httpcore')
httpcore_logger.setLevel(logging.WARNING)  # or logging.ERROR to be even quieter

# Add handlers to the app's logger
app.logger.addHandler(file_handler)
app.logger.addHandler(console_handler)

# Ensure that all log messages are propagated to the app's logger
app.logger.propagate = False

# Set the overall logger level
app.logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

from auth import auth as auth_blueprint  # Import the auth blueprint
app.register_blueprint(auth_blueprint)  # Registers auth with Flask application

# Set up database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Secret key for session handling
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') 

# Initialize database
db.init_app(app)
migrate = Migrate(app, db)

app.logger.info("Logging is set up.")

# Update the file storage configuration
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['BASE_UPLOAD_FOLDER'] = os.path.join(base_dir, 'user_files')
ensure_folder_exists(app.config['BASE_UPLOAD_FOLDER'])

embedding_store = EmbeddingStore(db_url)
from file_processing import FileProcessor
file_processor = FileProcessor(embedding_store, app)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}

# Initialize the login manager
login_manager = LoginManager()
login_manager.init_app(app)


# Enable auto-reload of templates
app.config['TEMPLATES_AUTO_RELOAD'] = True

from typing import List, Dict

# Begining of web search 

#### Common helper functions for both standard and intelligent web search

@app.route('/api/system-messages/<int:system_message_id>/toggle-search', methods=['POST'])
@login_required
def toggle_search(system_message_id):
    data = request.json
    enable_web_search = data.get('enableWebSearch')
    enable_intelligent_search = data.get('enableIntelligentSearch')
    
    system_message = SystemMessage.query.get_or_404(system_message_id)
    system_message.enable_web_search = enable_web_search
    # Note: We're not storing enable_intelligent_search in the database
    db.session.commit()
    
    return jsonify({
        'message': 'Search settings updated successfully',
        'enableWebSearch': system_message.enable_web_search,
        'enableIntelligentSearch': enable_intelligent_search
    }), 200

async def understand_query(client, model: str, messages: List[Dict[str, str]], user_query: str, is_standard_search: bool = True) -> str:
    app.logger.info(f"Starting query understanding for user query: '{user_query[:50]}...'")
    
    system_message = """Analyze the conversation history and the latest user query. 
    Provide a concise interpretation of what information the user is seeking, 
    considering the full context of the conversation."""

    # Only include the conversation history, excluding the latest user query
    conversation_history = "\n".join([f"{msg['role'].capitalize()}: {msg['content'][:50]}..." for msg in messages[:-1]])
    
    # Add the latest user query separately
    conversation_history += f"\nUser: {user_query}"

    app.logger.debug(f"Constructed conversation history for query understanding: {conversation_history}")

    messages_for_model = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": conversation_history}
    ]

    # Use gpt-4o-mini-2024-07-18 for standard search, otherwise use the provided model
    query_model = "gpt-4o-mini-2024-07-18" if is_standard_search else model
    app.logger.info(f"Sending request to model {query_model} for query interpretation")

    try:
        interpretation, _ = await get_response_from_model(client, query_model, messages_for_model, temperature=0.3)
        interpreted_query = interpretation.strip()
        app.logger.info(f"Query interpreted. Interpretation: '{interpreted_query[:100]}...'")
        return interpreted_query
    except Exception as e:
        app.logger.error(f"Error in understand_query: {str(e)}")
        raise WebSearchError(f"Failed to interpret query: {str(e)}")

class WebSearchError(Exception):
    """Custom exception for web search errors."""
    pass


async def perform_web_search(query: str) -> List[Dict[str, str]]:
    app.logger.info(f"Starting web search for query: '{query[:50]}...'")
    
    url = 'https://api.search.brave.com/res/v1/web/search'
    headers = {
        'Accept': 'application/json',
        'X-Subscription-Token': BRAVE_SEARCH_API_KEY
    }
    params = {
        'q': query,
        'count': 3
    }

    app.logger.info(f"Sending request to Brave Search API")

    try:
        async with ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=10) as response:
                app.logger.info(f"Received response from Brave Search API. Status: {response.status}")
                if response.status == 429:
                    raise WebSearchError("Rate limit reached. Please try again later.")
                response.raise_for_status()
                results = await response.json()
        
        if not results.get('web', {}).get('results', []):
            app.logger.warning(f'No results found for query: "{query[:50]}..."')
            return []
        
        formatted_results = [
            {
                "title": result['title'],
                "url": result['url'],
                "description": result['description'],
                "citation_number": i
            }
            for i, result in enumerate(results['web']['results'], 1)
        ]
        
        app.logger.info(f'Web search completed. Number of results: {len(formatted_results)}')
        
        # Log a summary of each result (title and URL)
        for i, result in enumerate(formatted_results, 1):
            app.logger.info(f"Result {i}: Title: '{result['title'][:30]}...', URL: {result['url']}")
        
        return formatted_results
    except aiohttp.ClientError as e:
        app.logger.error(f'Error performing Brave search: {str(e)}')
        raise WebSearchError(f"Failed to perform web search: {str(e)}")
    except Exception as e:
        app.logger.error(f'Unexpected error in perform_web_search: {str(e)}')
        raise WebSearchError(f"Unexpected error during web search: {str(e)}")

# Rate limiter: 3 requests per second
rate_limiter = AsyncLimiter(3, 1)

# Utility function that serves both standard and intelligent web search
async def perform_web_search_process(client, model: str, messages: List[Dict[str, str]], user_query: str, user_id: int, system_message_id: int, enable_intelligent_search: bool):
    app.logger.info(f"Starting web search process for query: '{user_query[:50]}...'")
    app.logger.info(f"Search type: {'Intelligent' if enable_intelligent_search else 'Standard'}")

    try:
        app.logger.info('Step 1: Understanding user query...')
        understood_query = await understand_query(client, model, messages, user_query, is_standard_search=not enable_intelligent_search)
        app.logger.info(f'Understood query: {understood_query}')

        if enable_intelligent_search:
            app.logger.info('Initiating intelligent web search...')
            return await intelligent_web_search_process(client, model, messages, understood_query, user_id, system_message_id)
        else:
            app.logger.info('Initiating standard web search...')
            return await standard_web_search_process(client, model, understood_query, user_id, system_message_id)

    except WebSearchError as e:
        app.logger.error(f'Web search process error: {str(e)}')
        return [], f"An error occurred during the web search process: {str(e)}"
    except Exception as e:
        app.logger.error(f'Unexpected error in web search process: {str(e)}')
        app.logger.exception("Full traceback:")
        return [], "An unexpected error occurred during the web search process."
    
#### Functions for intelligent web search

async def generate_search_queries(client, model: str, interpretation: str) -> List[str]:
    app.logger.info(f"Starting search query generation based on interpretation: '{interpretation[:50]}...'")
    
    system_message = """Generate three diverse search queries based on the given interpretation. 
    Respond with only valid JSON in the format: {"queries": ["query1", "query2", "query3"]}"""

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": interpretation}
    ]

    app.logger.info(f"Sending request to model {model} for search query generation")

    try:
        response, _ = await get_response_from_model(client, model, messages, temperature=0.3)
        app.logger.info(f"Received response from model: '{response[:100]}...'")
        
        queries = json.loads(response.strip())["queries"]
        
        app.logger.info("Generated search queries:")
        for i, query in enumerate(queries, 1):
            app.logger.info(f"Query {i}: '{query}'")
        
        return queries
    except json.JSONDecodeError as e:
        app.logger.error(f"Error decoding JSON in generate_search_queries: {str(e)}")
        app.logger.error(f"Raw response: {response}")
        raise WebSearchError(f"Failed to parse generated search queries: {str(e)}")
    except Exception as e:
        app.logger.error(f"Error in generate_search_queries: {str(e)}")
        raise WebSearchError(f"Failed to generate search queries: {str(e)}")

async def intelligent_web_search_process(client, model: str, messages: List[Dict[str, str]], understood_query: str, user_id: int, system_message_id: int):
    app.logger.info(f"Starting intelligent web search for understood query: '{understood_query[:50]}...'")

    try:
        # Step 1: Use the understood query to generate search queries
        app.logger.info("Step 1: Generating search queries based on understood query")
        generated_search_queries = await generate_search_queries(client, model, understood_query)
        app.logger.info(f"Generated {len(generated_search_queries)} search queries")

        if not generated_search_queries:
            app.logger.error("Failed to generate search queries")
            raise WebSearchError('Failed to generate search queries')

        # Step 2: Performing multiple web searches
        app.logger.info("Step 2: Performing multiple web searches")
        web_search_results = await perform_multiple_web_searches(generated_search_queries)
        app.logger.info(f"Received {len(web_search_results)} web search results")

        if web_search_results:
            # Step 3: Fetching full content for search results
            app.logger.info("Step 3: Fetching full content for search results")
            full_content_results = await fetch_full_content(web_search_results, app, user_id, system_message_id)
            app.logger.info(f"Fetched full content for {len(full_content_results)} results")

            # Step 4: Summarizing search results
            app.logger.info("Step 4: Summarizing search results")
            summarized_results = await summarize_search_results(client, model, full_content_results, understood_query)
            app.logger.info(f"Generated summary of length: {len(summarized_results)} characters")

            app.logger.info("Intelligent web search completed successfully")
            return generated_search_queries, summarized_results
        else:
            app.logger.warning("No relevant web search results were found")
            return generated_search_queries, "No relevant web search results were found."

    except WebSearchError as e:
        app.logger.error(f"WebSearchError in intelligent web search: {str(e)}")
        raise
    except Exception as e:
        app.logger.error(f"Unexpected error in intelligent web search: {str(e)}")
        app.logger.exception("Full traceback:")
        raise WebSearchError(f"Unexpected error during intelligent web search: {str(e)}")

# Create a rate limiter: 1 request per second
rate_limiter = AsyncLimiter(1, 1)

async def perform_multiple_web_searches(queries: List[str]) -> List[Dict[str, str]]:
    app.logger.info(f"Starting multiple web searches for {len(queries)} queries")
    all_results = []
    urls_seen = set()

    async def process_query(query):
        async with rate_limiter:
            app.logger.info(f"Processing query: '{query[:50]}...'")
            try:
                results = await perform_web_search(query)
                app.logger.info(f"Received {len(results)} results for query: '{query[:50]}...'")
                new_results_count = 0
                for result in results:
                    url = result.get("url")
                    if url and url not in urls_seen:
                        urls_seen.add(url)
                        all_results.append(result)
                        new_results_count += 1
                app.logger.info(f"Added {new_results_count} new results for query: '{query[:50]}...'")
            except WebSearchError as e:
                app.logger.error(f"Error searching for query '{query[:50]}...': {str(e)}")

    app.logger.info("Running web searches concurrently...")
    # Use asyncio.gather to run searches concurrently while respecting rate limits
    await asyncio.gather(*(process_query(query) for query in queries))

    app.logger.info(f"Multiple web searches completed. Total unique results: {len(all_results)}")
    app.logger.info(f"Unique URLs found: {len(urls_seen)}")

    return all_results


async def fetch_full_content(results: List[Dict[str, str]], app, user_id: int, system_message_id: int) -> List[Dict[str, str]]:
    app.logger.info(f"Starting to fetch full content for {len(results)} results")

    async def get_page_content(url: str) -> str:
        try:
            async with ClientSession() as session:
                app.logger.info(f"Fetching content from URL: {url}")
                async with session.get(url, timeout=10) as response:
                    app.logger.info(f"Received response from {url}. Status: {response.status}")
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    text_content = soup.get_text(strip=True, separator='\n')
                    app.logger.info(f"Extracted {len(text_content)} characters of text from {url}")
                    return text_content
        except Exception as e:
            app.logger.error(f"Error fetching content for {url}: {str(e)}")
            return ""

    tasks = [asyncio.create_task(get_page_content(result['url'])) for result in results]
    contents = await asyncio.gather(*tasks)

    full_content_results = []
    used_citation_numbers = set()

    for result, content in zip(results, contents):
        # Ensure unique citation numbers
        original_citation_number = result['citation_number']
        unique_citation_number = original_citation_number
        while unique_citation_number in used_citation_numbers:
            unique_citation_number += 1
        used_citation_numbers.add(unique_citation_number)

        full_result = {**result, "full_content": content, "citation_number": unique_citation_number}
        full_content_results.append(full_result)

        file_name = f"result_{unique_citation_number}.json"
        file_path = get_file_path(app, user_id, system_message_id, file_name, 'web_search_results')
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(full_result, f, ensure_ascii=False, indent=2)
            app.logger.info(f"Saved full content for result {unique_citation_number} to {file_path}")
        except Exception as e:
            app.logger.error(f"Error saving file for result {unique_citation_number}: {str(e)}")

    app.logger.info(f"Completed fetching full content for {len(full_content_results)} results")
    return full_content_results

async def summarize_page_content(client, content: str, query: str) -> str:
    app.logger.info("Starting summarize_page_content...")
    
    system_message = """Summarize the given content, focusing on information relevant to the query. 
    Be concise but include key points and any relevant code snippets."""

    user_message = f"""Summarize the following content, focusing on information relevant to the query: "{query}"

    Content: {content[:500]}...  # Truncated for logging purposes

    Provide a concise summary that captures the main points relevant to the query."""

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]

    try:
        summary, _ = await get_response_from_model(client, "gpt-4o-mini-2024-07-18", messages, temperature=0.3)
        summarized_content = summary.strip()
        app.logger.info(f"Page content summarized. Summary length: {len(summarized_content)} characters")
        return summarized_content
    except Exception as e:
        app.logger.error(f"Error in summarize_page_content: {str(e)}")
        raise WebSearchError(f"Failed to summarize page content: {str(e)}")

async def combine_summaries(client, summaries: List[Dict[str, str]], query: str) -> str:
    app.logger.info(f"Starting combine_summaries for query: '{query}'")
    
    system_message = """Combine the given summaries into a coherent overall summary. 
    Include relevant information from all sources and cite them using numbered footnotes [1], [2], etc. 
    At the end, include a 'Sources:' section with full URLs for each footnote."""

    # Truncate summaries for logging purposes
    truncated_summaries = [
        {
            "index": s["index"],
            "url": s["url"],
            "summary": s["summary"][:100] + "..." if len(s["summary"]) > 100 else s["summary"]
        }
        for s in summaries
    ]

    user_message = f"""Combine the following summaries into a coherent overall summary, focusing on information relevant to the query: "{query}"

    Summaries:
    {json.dumps(truncated_summaries, indent=2)}

    Provide a concise but comprehensive summary that addresses the query, citing sources with footnotes."""

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]

    try:
        app.logger.info(f"Sending request to combine {len(summaries)} summaries")
        final_summary, _ = await get_response_from_model(client, "gpt-4o-mini-2024-07-18", messages, temperature=0.3)
        combined_summary = final_summary.strip()
        app.logger.info(f"Summaries combined. Final summary length: {len(combined_summary)} characters")
        return combined_summary
    except Exception as e:
        app.logger.error(f"Error in combine_summaries: {str(e)}")
        raise WebSearchError(f"Failed to combine summaries: {str(e)}")

async def intelligent_summarize(client, model: str, content: str, query: str, max_tokens: int = 1000) -> str:
    app.logger.info(f"Starting intelligent summarization for query: '{query[:50]}...'")
    
    if not content:
        app.logger.warning("No content provided for summarization")
        return "No content available for summarization."
    
    system_message = """You are an advanced AI assistant tasked with intelligently summarizing web content. 
    Your summaries should be informative, relevant to the query, and include key information. 
    If the content contains code, especially for newer libraries, repos, or APIs, include it verbatim in your summary. 
    Adjust the level of detail based on the content's relevance and information density.
    Your summary should be comprehensive yet concise."""

    # Truncate content if it's too long
    max_content_length = 5000  # Adjust this value as needed
    truncated_content = content[:max_content_length]
    if len(content) > max_content_length:
        truncated_content += "... [Content truncated]"

    user_message = f"""Summarize the following content, focusing on information relevant to the query: "{query}"
    
    Content: {truncated_content}
    
    Remember to include any relevant code snippets verbatim, especially if they relate to new technologies or APIs."""

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]

    app.logger.info(f"Sending request to model {model} for intelligent summarization")
    app.logger.debug(f"Content length for summarization: {len(truncated_content)} characters")

    try:
        summary, _ = await get_response_from_model(client, model, messages, temperature=0.3)
        summarized_content = summary.strip()
        app.logger.info(f"Intelligent summarization completed. Summary length: {len(summarized_content)} characters")
        return summarized_content
    except Exception as e:
        app.logger.error(f"Error in intelligent_summarize: {str(e)}")
        raise WebSearchError(f"Failed to generate intelligent summary: {str(e)}")


# Controls the search results.  Lots of improvements can happen here to increase quality. (e.g. better summarization, better search results, etc.) 
async def summarize_search_results(client, model: str, results: List[Dict[str, str]], query: str) -> str:
    app.logger.info(f"Starting summarization of search results for query: '{query[:50]}...'")
    app.logger.info(f"Number of results to summarize: {len(results)}")

    summaries = []
    for index, result in enumerate(results, 1):
        app.logger.info(f"Summarizing result {index}/{len(results)} (URL: {result['url']})")
        
        # Log the first 100 characters of the full content for debugging
        app.logger.debug(f"Full content preview for result {index}: {result.get('full_content', '')[:100]}...")
        
        summary = await intelligent_summarize(client, model, result.get('full_content', ''), query)
        summaries.append({
            "index": result['citation_number'],
            "url": result['url'],
            "summary": summary
        })
        app.logger.info(f"Completed summary for result {index}")

    app.logger.info("All individual results summarized. Preparing combined summary prompt.")


    combined_summary_prompt = f"""Combine the following summaries into a coherent overall summary.
    Include relevant information from all sources and cite them using numbered footnotes [1], [2], etc.
    Include any code snippets that are present in the summaries, as they may be crucial for understanding new technologies.
    At the end, include a 'Sources:' section with full URLs for each footnote.
    Ensure all provided results are included in the summary and sources list.
    
    Query: {query}
    
    Summaries:
    {json.dumps(summaries, indent=2)}"""

    messages = [
        {"role": "system", "content": "You are an advanced AI assistant tasked with combining multiple summaries into a comprehensive, well-structured final summary."},
        {"role": "user", "content": combined_summary_prompt}
    ]

    app.logger.info(f"Sending request to model {model} for final summary combination")

    try:
        final_summary, _ = await get_response_from_model(client, model, messages, temperature=0.3)
        summarized_content = final_summary.strip()
        app.logger.info(f"Final summary generated. Length: {len(summarized_content)} characters")
        return summarized_content
    except Exception as e:
        app.logger.error(f"Error in summarize_search_results: {str(e)}")
        raise WebSearchError(f"Failed to combine summaries: {str(e)}")

##### Functions for standard web search

async def generate_single_search_query(client, model: str, messages: List[Dict[str, str]], user_query: str) -> str:
    app.logger.info("Starting generate_single_search_query...")
    
    system_message = """Generate a single, concise search query based on the conversation history and the latest user query. 
    The query should capture the main intent of the user's request."""

    conversation_history = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in messages[-5:]])
    conversation_history += f"\nUser: {user_query}"

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": conversation_history}
    ]

    try:
        query, _ = await get_response_from_model(client, "gpt-4o-mini-2024-07-18", messages, temperature=0.3)
        generated_query = query.strip()
        app.logger.info(f"Generated single search query: {generated_query}")
        return generated_query
    except Exception as e:
        app.logger.error(f"Error in generate_single_search_query: {str(e)}")
        raise WebSearchError(f"Failed to generate search query: {str(e)}")
    
async def standard_web_search_process(client, model: str, understood_query: str, user_id: int, system_message_id: int):
    app.logger.info(f"Starting standard web search process for understood query: '{understood_query[:50]}...'")
    try:
        app.logger.info('Step 2: Generating search query...')
        search_query = await generate_single_search_query(client, model, [], understood_query)
        app.logger.info(f'Generated search query: {search_query}')

        app.logger.info('Step 3: Performing web search...')
        web_search_results = await perform_web_search(search_query)
        app.logger.info(f'Web search completed. Results count: {len(web_search_results)}')

        if web_search_results:
            app.logger.info('Step 4: Fetching partial content for search results...')
            partial_content_results = await fetch_partial_content(web_search_results, app, user_id, system_message_id)
            app.logger.info(f'Partial content fetched for {len(partial_content_results)} results')
            
            app.logger.info('Step 5: Summarizing search results...')
            summarized_results = await standard_summarize_search_results(client, model, partial_content_results, understood_query)
            app.logger.info(f'Summarization completed. Summary length: {len(summarized_results)} characters')
        else:
            app.logger.warning('No web search results found.')
            summarized_results = "No relevant web search results were found."

        app.logger.info('Standard web search process completed successfully')
        return [search_query], summarized_results

    except WebSearchError as e:
        app.logger.error(f'Standard web search process error: {str(e)}')
        return None, f"An error occurred during the standard web search process: {str(e)}"
    except Exception as e:
        app.logger.error(f'Unexpected error in standard web search process: {str(e)}')
        app.logger.exception("Full traceback:")
        return None, "An unexpected error occurred during the standard web search process."

async def fetch_partial_content(results: List[Dict[str, str]], app, user_id: int, system_message_id: int) -> List[Dict[str, str]]:
    app.logger.info(f"Starting to fetch partial content for {len(results)} results")

    async def get_partial_page_content(url: str) -> str:
        try:
            async with ClientSession() as session:
                app.logger.info(f"Fetching partial content from URL: {url}")
                async with session.get(url, timeout=10) as response:
                    app.logger.info(f"Received response from {url}. Status: {response.status}")
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    text_content = soup.get_text(strip=True, separator='\n')
                    partial_content = text_content[:1000]  # Get first 1000 characters
                    app.logger.info(f"Extracted {len(partial_content)} characters of text from {url}")
                    return partial_content
        except Exception as e:
            app.logger.error(f"Error fetching content for {url}: {str(e)}")
            return ""

    tasks = [asyncio.create_task(get_partial_page_content(result['url'])) for result in results]
    contents = await asyncio.gather(*tasks)

    partial_content_results = []
    for result, content in zip(results, contents):
        partial_result = {**result, "partial_content": content}
        partial_content_results.append(partial_result)

        file_name = f"partial_result_{result['citation_number']}.json"
        file_path = get_file_path(app, user_id, system_message_id, file_name, 'web_search_results')
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(partial_result, f, ensure_ascii=False, indent=2)
            app.logger.info(f"Saved partial content for result {result['citation_number']} to {file_path}")
        except Exception as e:
            app.logger.error(f"Error saving file for result {result['citation_number']}: {str(e)}")

    app.logger.info(f"Completed fetching partial content for {len(partial_content_results)} results")
    return partial_content_results

async def standard_summarize_search_results(client, model: str, results: List[Dict[str, str]], query: str) -> str:
    app.logger.info(f"Starting standard summarization of search results for query: '{query[:50]}...'")
    
    combined_content = "\n\n".join([
        f"Title: {result['title']}\nURL: {result['url']}\nPartial Content: {result['partial_content']}"
        for result in results
    ])

    system_message = """Summarize the given search results, focusing on information relevant to the query. 
    Include key points from each result and cite them using numbered footnotes [1], [2], etc. 
    At the end, include a 'Sources:' section with full URLs for each footnote."""

    user_message = f"""Summarize the following search results, focusing on information relevant to the query: "{query}"

    Search Results:
    {combined_content}

    Provide a concise but comprehensive summary that addresses the query, citing sources with footnotes."""

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]

    try:
        summary, _ = await get_response_from_model(client, model, messages, temperature=0.3)
        summarized_content = summary.strip()
        app.logger.info(f"Search results summarized. Summary length: {len(summarized_content)} characters")
        return summarized_content
    except Exception as e:
        app.logger.error(f"Error in standard_summarize_search_results: {str(e)}")
        raise WebSearchError(f"Failed to summarize search results: {str(e)}")


# End of web search

@app.route('/query_documents', methods=['POST'])
@login_required
def query_documents():
    query = request.json.get('query')
    file_processor = FileProcessor(embedding_store, app)
    results = file_processor.query_index(query)
    return jsonify({'results': results})

# Routes to handle files and file uploads

from flask import make_response, send_file, abort

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/view_original_file/<file_id>')
@login_required
def view_original_file(file_id):
    file = UploadedFile.query.get_or_404(file_id)
    
    if file.user_id != current_user.id:
        abort(403)  # Unauthorized access
    
    if os.path.exists(file.file_path):
        try:
            # Create an HTML page that embeds the file
            html_content = f'''
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{file.original_filename}</title>
                <style>
                    html, body {{
                        margin: 0;
                        padding: 0;
                        height: 100%;
                        overflow: hidden;
                    }}
                    #file-embed {{
                        width: 100%;
                        height: 100%;
                        border: none;
                    }}
                </style>
            </head>
            <body>
                <embed id="file-embed" src="/serve_file/{file_id}" type="{file.mime_type}">
                <script>
                    function resizeEmbed() {{
                        var embed = document.getElementById('file-embed');
                        embed.style.height = window.innerHeight + 'px';
                    }}
                    window.onload = resizeEmbed;
                    window.onresize = resizeEmbed;
                </script>
            </body>
            </html>
            '''
            return render_template_string(html_content)
        except Exception as e:
            app.logger.error(f"Error serving file {file_id}: {str(e)}")
            abort(500)
    else:
        abort(404)  # File not found

@app.route('/serve_file/<file_id>')
@login_required
def serve_file(file_id):
    file = UploadedFile.query.get_or_404(file_id)
    
    if file.user_id != current_user.id:
        abort(403)  # Unauthorized access
    
    if os.path.exists(file.file_path):
        return send_file(
            file.file_path,
            mimetype=file.mime_type,
            as_attachment=False,
            download_name=file.original_filename
        )
    else:
        abort(404)  # File not found

@app.route('/view_processed_text/<file_id>')
@login_required
def view_processed_text(file_id):
    file = UploadedFile.query.get_or_404(file_id)
    
    if file.user_id != current_user.id:
        abort(403)  # Unauthorized access
    
    if file.processed_text_path and os.path.exists(file.processed_text_path):
        return send_file(
            file.processed_text_path,
            mimetype='text/plain',
            as_attachment=False,
            download_name=f"{file.original_filename}_processed.txt"
        )
    else:
        app.logger.error(f"Processed text not found for file ID: {file_id}")
        return jsonify({'error': 'Processed text not available'}), 404

@app.route('/upload_file', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'})
    
    file = request.files['file']
    system_message_id = request.form.get('system_message_id')
    
    app.logger.info(f"Received file upload request: {file.filename}, system_message_id: {system_message_id}")
    
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'})
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = get_file_path(app, current_user.id, system_message_id, filename, 'uploads')
        file.save(file_path)
        
        app.logger.info(f"File saved to: {file_path}")
        
        try:
            # Create a new UploadedFile record
            new_file = UploadedFile(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                original_filename=filename,
                file_path=file_path,
                system_message_id=system_message_id,
                file_size=os.path.getsize(file_path),
                mime_type=file.content_type
            )
            
            # Add and commit the new file to the database
            db.session.add(new_file)
            db.session.commit()
            
            app.logger.info(f"New file record created with ID: {new_file.id}")
            
            # Get the storage context for this system message
            storage_context = embedding_store.get_storage_context(system_message_id)
            
            # Process and index the file
            processed_text_path = file_processor.process_file(file_path, storage_context, new_file.id, current_user.id, system_message_id)
            
            app.logger.info(f"Processed text path returned: {processed_text_path}")
            
            # Update the processed_text_path
            if processed_text_path:
                new_file.processed_text_path = processed_text_path
                db.session.commit()
                app.logger.info(f"File {filename} processed successfully. Processed text path: {processed_text_path}")
            else:
                app.logger.warning(f"File {filename} processed, but no processed text path was returned.")
            
            return jsonify({'success': True, 'message': 'File uploaded and indexed successfully', 'file_id': new_file.id})
        except Exception as e:
            db.session.rollback()  # Rollback the session in case of error
            app.logger.error(f"Error processing file: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': f'Error processing file: {str(e)}'}), 500
    
    app.logger.error(f"File type not allowed: {file.filename}")
    return jsonify({'success': False, 'error': 'File type not allowed'}), 400

@app.route('/get_files/<int:system_message_id>')
@login_required
def get_files(system_message_id):
    try:
        files = UploadedFile.query.filter_by(system_message_id=system_message_id).all()
        file_list = [{
            'id': file.id,
            'name': file.original_filename,  
            'path': file.file_path,
            'size': file.file_size,  
            'type': file.mime_type,  
            'upload_date': file.upload_timestamp.isoformat() if file.upload_timestamp else None  # Add this for upload date
        } for file in files]
        return jsonify(file_list)
    except Exception as e:
        app.logger.error(f"Error fetching files: {str(e)}")
        return jsonify({'error': 'Error fetching files'}), 500
    
@app.route('/remove_file/<file_id>', methods=['DELETE'])
@login_required
def remove_file(file_id):
    file = UploadedFile.query.get_or_404(file_id)
    
    if file.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    try:
        # Delete vectors
        system_message_id = file.system_message_id
        storage_context = embedding_store.get_storage_context(system_message_id)
        vector_store = storage_context.vector_store
        namespace = embedding_store.generate_namespace(system_message_id)
        delete_vectors_for_file(vector_store, file.id, namespace)
        
        # Remove the original file
        if os.path.exists(file.file_path):
            os.remove(file.file_path)
            app.logger.info(f"Original file removed: {file.file_path}")
        else:
            app.logger.warning(f"Original file not found: {file.file_path}")
        
        # Remove the processed text file
        processed_file_name = f"{file.id}_processed.txt"
        processed_file_path = get_file_path(app, current_user.id, system_message_id, processed_file_name, 'processed_texts')
        
        if os.path.exists(processed_file_path):
            try:
                os.remove(processed_file_path)
                app.logger.info(f"Processed text file removed: {processed_file_path}")
            except Exception as e:
                app.logger.error(f"Error removing processed text file: {str(e)}")
                app.logger.error(f"File permissions: {oct(os.stat(processed_file_path).st_mode)[-3:]}")
        else:
            app.logger.warning(f"Processed text file not found: {processed_file_path}")
        
        # Remove the LLMWhisperer output file
        llmwhisperer_file_name = f"{file.id}_llmwhisperer_output.txt"
        llmwhisperer_file_path = get_file_path(app, current_user.id, system_message_id, llmwhisperer_file_name, 'llmwhisperer_output')
        
        if os.path.exists(llmwhisperer_file_path):
            try:
                os.remove(llmwhisperer_file_path)
                app.logger.info(f"LLMWhisperer output file removed: {llmwhisperer_file_path}")
            except Exception as e:
                app.logger.error(f"Error removing LLMWhisperer output file: {str(e)}")
                app.logger.error(f"File permissions: {oct(os.stat(llmwhisperer_file_path).st_mode)[-3:]}")
        else:
            app.logger.warning(f"LLMWhisperer output file not found: {llmwhisperer_file_path}")
        
        # Remove database entry
        db.session.delete(file)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'File, processed text, and LLMWhisperer output removed successfully'})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error removing file {file.original_filename} (ID: {file_id}): {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
def delete_vectors_for_file(vector_store, file_id, namespace):
    try:
        # Get the Pinecone index from the vector store
        pinecone_index = vector_store._pinecone_index

        # Query for vectors related to this file
        query_response = pinecone_index.query(
            namespace=namespace,
            vector=[0] * 1536,  # Dummy vector of zeros
            # This query is a workaround for Serverless and Starter Pinecone indexes, which don't support
            # metadata filtering during deletion. We're fetching a large number of vectors and filtering
            # them client-side to find those associated with the file we want to delete. (higher values may slow down the query).
            top_k=10000,  # Adjust this value based on your needs
            include_metadata=True
        )

        # Filter the results to only include vectors with matching file_id
        vector_ids = [
            match.id for match in query_response.matches 
            if match.metadata.get('file_id') == str(file_id)
        ]

        if vector_ids:
            # Delete the vectors
            delete_response = pinecone_index.delete(ids=vector_ids, namespace=namespace)
            app.logger.info(f"Deleted {len(vector_ids)} vectors for file ID: {file_id}. Delete response: {delete_response}")
        else:
            app.logger.warning(f"No vectors found for file ID: {file_id}")
    except Exception as e:
        app.logger.error(f"Error deleting vectors for file ID {file_id}: {str(e)}")
        raise

@app.route('/health')
def health_check():
    return 'OK', 200

@app.route('/get-website/<int:website_id>', methods=['GET'])
@login_required
def get_website(website_id):
    app.logger.debug(f"Attempting to fetch website with ID: {website_id}")
    try:
        query = Website.query.get(website_id)
        app.logger.debug(f"Query executed: {query}")  # Log the actual query object
        website = query
        if not website:
            app.logger.warning(f"No website found with ID: {website_id}")
            return jsonify({'error': 'Website not found'}), 404
        app.logger.debug(f"Website data: {website.to_dict()}")
        return jsonify({'website': website.to_dict()}), 200
    except Exception as e:
        app.logger.error(f"Exception occurred: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/test-website', methods=['GET'])
@login_required
def test_website():
    return jsonify({'message': 'Route is working'}), 200

@app.route('/index-website', methods=['POST'])
@login_required
def index_website():
    data = request.get_json()
    app.logger.debug(f"Received indexing request with data: {data}")
    url = data.get('url')
    if not url:
        app.logger.error("URL is missing from request data")
        return jsonify({'success': False, 'message': 'URL is required'}), 400

    allowed_domain = data.get('allowed_domain', '')
    custom_settings = data.get('custom_settings', {})

    # Run Scrapy spider
    process = subprocess.Popen(
        ['scrapy', 'runspider', 'webscraper/spiders/flexible_spider.py',
         '-a', f'url={url}', '-a', f'allowed_domain={allowed_domain}',
         '-a', f'custom_settings={json.dumps(custom_settings)}'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()

    stdout_decoded = stdout.decode('utf-8', errors='replace')
    stderr_decoded = stderr.decode('utf-8', errors='replace')
    app.logger.debug("STDOUT: %s", stdout_decoded)
    app.logger.debug("STDERR: %s", stderr_decoded)

    if process.returncode != 0:
        app.logger.error("Scraping failed with error: %s", stderr_decoded)
        return jsonify({'success': False, 'message': 'Error during scraping', 'error': stderr_decoded}), 500

    if stdout_decoded:
        try:
            scraped_content = json.loads(stdout_decoded)
            if 'content' in scraped_content:
                return jsonify({'success': True, 'message': 'Website indexed successfully', 'content': scraped_content['content']}), 200
            else:
                app.logger.error("Expected key 'content' not found in JSON output")
                return jsonify({'success': False, 'message': 'Expected data not found in the scraped output'}), 500
        except json.JSONDecodeError as e:
            app.logger.error("Error decoding JSON from scraping output: %s", str(e))
            return jsonify({'success': False, 'message': 'Invalid JSON data received', 'details': stdout_decoded}), 500
    else:
        app.logger.error("No data received from spider")
        return jsonify({'success': False, 'message': 'No data received from spider'}), 500

@app.route('/scrape', methods=['POST'])
@login_required
def scrape():
    data = request.get_json()
    url = data.get('url')
    allowed_domain = data.get('allowed_domain', '')

    command = [
        'scrapy', 'runspider', 'webscraper/spiders/flexible_spider.py',
        '-a', f'url={url}', '-a', f'allowed_domain={allowed_domain}'
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        app.logger.error(f"Spider error: {stderr.decode()}")
        return jsonify({'error': 'Failed to scrape the website'}), 500

    try:
        result = json.loads(stdout.decode())
        return jsonify({'data': result['content']}), 200
    except json.JSONDecodeError:
        app.logger.error("Failed to decode JSON from spider output")
        return jsonify({'error': 'Failed to decode JSON from spider output'}), 500

@app.route('/get-websites/<int:system_message_id>', methods=['GET'])
@login_required
def get_websites(system_message_id):
    websites = Website.query.filter_by(system_message_id=system_message_id).all()
    return jsonify({'websites': [website.to_dict() for website in websites]}), 200

@app.route('/add-website', methods=['POST'])
@login_required
def add_website():
    data = request.get_json()
    url = data.get('url')
    system_message_id = data.get('system_message_id')

    if not url:
        return jsonify({'success': False, 'message': 'URL is required'}), 400

    if not system_message_id:
        return jsonify({'success': False, 'message': 'System message ID is required'}), 400

    # Validate URL format here (optional, can be done in the frontend too)
    if not url.startswith('http://') and not url.startswith('https://'):
        return jsonify({'success': False, 'message': 'Invalid URL format'}), 400

    new_website = Website(url=url, system_message_id=system_message_id)
    db.session.add(new_website)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Website added successfully', 'website': new_website.to_dict()}), 201

@app.route('/remove-website/<int:website_id>', methods=['DELETE'])
@login_required
def remove_website(website_id):
    website = Website.query.get_or_404(website_id)
    db.session.delete(website)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Website removed successfully'}), 200

@app.route('/reindex-website/<int:website_id>', methods=['POST'])
@login_required
def reindex_website(website_id):
    website = Website.query.get_or_404(website_id)
    # Trigger re-indexing logic here (e.g., update indexed_at, change status)
    website.indexed_at = datetime.now(timezone.utc)
    website.indexing_status = 'In Progress'
    db.session.commit()

    return jsonify({'message': 'Re-indexing initiated', 'website': website.to_dict()}), 200

@app.route('/generate-image', methods=['POST'])
@login_required
def generate_image():
    data = request.json
    prompt = data.get('prompt', '')

    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400

    try:
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="256x256"
        )
        image_url = response['data'][0]['url']
        return jsonify({"image_url": image_url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/view-logs')
@login_required
def view_logs():
    logs_content = "<link rel='stylesheet' type='text/css' href='/static/css/styles.css'><div class='logs-container'>"
    try:
        with open('app.log', 'r') as log_file:
            logs_content += f"<div class='log-entry'><div class='log-title'>--- app.log ---</div><pre>"
            logs_content += log_file.read() + "</pre></div>\n"
    except FileNotFoundError:
        logs_content += "<div class='log-entry'><div class='log-title'>No log file found.</div></div>"
    logs_content += "</div>"
    return logs_content

# User loader function
@login_manager.user_loader
def load_user(user_id):
    from models import User  # Import here to avoid circular dependencies
    return User.query.get(int(user_id))

# Configure authentication using your API key
genai.configure(api_key=os.environ['GOOGLE_API_KEY'])

anthropic.api_key = os.environ.get('ANTHROPIC_API_KEY')
if anthropic.api_key is None:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set")

# Backup Admin user creation logic
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') # set this in your .env file
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
ADMIN_EMAIL = "admin@backup.com" # Change this to your own email address

def create_admin_user():
    admin_user = User.query.filter_by(username=ADMIN_USERNAME).first()
    if not admin_user and ADMIN_USERNAME and ADMIN_PASSWORD:
        hashed_password = generate_password_hash(ADMIN_PASSWORD)
        new_admin = User(
            username=ADMIN_USERNAME,
            email=ADMIN_EMAIL,
            password_hash=hashed_password,
            is_admin=True,
            status="Active"
        )
        try:
            db.session.add(new_admin)
            db.session.commit()
            print("Admin user created")
        except Exception as e:
            print(f"Error creating admin user: {e}")

# Move this to after app creation
# with app.app_context():
#    create_admin_user()

# Default System Message creation logic
DEFAULT_SYSTEM_MESSAGE = {
    "name": "Default System Message",
    "content": "You are a knowledgeable assistant that specializes in critical thinking and analysis.",
    "description": "Default entry for database",
    "model_name": "gpt-3.5-turbo",
    "temperature": 0.3
}

@app.cli.command("init_app")
def init_app():
    """Initialize the application."""
    with app.app_context():
        # Retrieve the admin user
        admin_user = User.query.filter_by(username=ADMIN_USERNAME).first()

        # Check if the default system message exists
        default_message = SystemMessage.query.filter_by(name=DEFAULT_SYSTEM_MESSAGE["name"]).first()

        if not default_message and admin_user:
            # Create a new default system message associated with the admin user
            new_default_message = SystemMessage(
                name=DEFAULT_SYSTEM_MESSAGE["name"],
                content=DEFAULT_SYSTEM_MESSAGE["content"],
                description=DEFAULT_SYSTEM_MESSAGE["description"],
                model_name=DEFAULT_SYSTEM_MESSAGE["model_name"],
                temperature=DEFAULT_SYSTEM_MESSAGE["temperature"],
                created_by=admin_user.id  # Associate with the admin user's ID
            )

            try:
                db.session.add(new_default_message)
                db.session.commit()
                print("Default system message created")
            except Exception as e:
                print(f"Error creating default system message: {e}")

@app.route('/api/system-messages/<int:system_message_id>/add-website', methods=['POST'])
@login_required
def add_website_to_system_message(system_message_id):
    data = request.json
    website_url = data.get('websiteURL')
    
    system_message = SystemMessage.query.get(system_message_id)
    if system_message:
        if not system_message.source_config:
            system_message.source_config = {'websites': []}
        system_message.source_config['websites'].append(website_url)
        db.session.commit()
        return jsonify({'message': 'Website URL added successfully'}), 200
    else:
        return jsonify({'error': 'System message not found'}), 404

@app.route('/get-current-model', methods=['GET'])
@login_required
def get_current_model():
    try:
        # First try to get the default system message
        default_message = SystemMessage.query.filter_by(name="Default System Message").first()
        
        # If not found, try to get any system message
        if not default_message:
            default_message = SystemMessage.query.first()
        
        # If still no system message exists, return default values
        if default_message:
            return jsonify({
                'model_name': default_message.model_name,
                'temperature': default_message.temperature
            })
        else:
            # Return default values if no system message exists
            return jsonify({
                'model_name': 'gpt-3.5-turbo',
                'temperature': 0.7
            })
            
    except Exception as e:
        app.logger.error(f"Error in get_current_model: {str(e)}")
        # Return default values in case of error
        return jsonify({
            'model_name': 'gpt-3.5-turbo',
            'temperature': 0.7
        })

@app.route('/system-messages', methods=['POST'])
@login_required
def create_system_message():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    new_system_message = SystemMessage(
        name=data['name'],
        content=data['content'],
        description=data.get('description', ''),
        model_name=data.get('model_name', ''),
        temperature=data.get('temperature', 0.7),
        created_by=current_user.id,
        enable_web_search=data.get('enable_web_search', False)
    )
    db.session.add(new_system_message)
    db.session.commit()
    return jsonify(new_system_message.to_dict()), 201

@app.route('/api/system_messages')
@login_required
def get_system_messages():
    system_messages = SystemMessage.query.all()
    return jsonify([{
        'id': message.id,  
        'name': message.name,
        'content': message.content,
        'description': message.description,
        'model_name': message.model_name,
        'temperature': message.temperature,
        'enable_web_search': message.enable_web_search
    } for message in system_messages])

@app.route('/system-messages/<int:message_id>', methods=['PUT'])
@login_required
def update_system_message(message_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401

    system_message = SystemMessage.query.get_or_404(message_id)
    data = request.get_json()

    system_message.name = data.get('name', system_message.name)
    system_message.content = data.get('content', system_message.content)
    system_message.description = data.get('description', system_message.description)
    system_message.model_name = data.get('model_name', system_message.model_name)
    system_message.temperature = data.get('temperature', system_message.temperature)
    system_message.enable_web_search = data.get('enable_web_search', system_message.enable_web_search)

    db.session.commit()
    return jsonify(system_message.to_dict())

@app.route('/system-messages/<int:message_id>', methods=['DELETE'])
@login_required
def delete_system_message(message_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401

    system_message = SystemMessage.query.get_or_404(message_id)
    db.session.delete(system_message)
    db.session.commit()
    return jsonify({'message': 'System message deleted successfully'})

@app.route('/trigger-flash')
def trigger_flash():
    flash("You do not have user admin privileges.", "warning")  # Adjust the message and category as needed
    return redirect(url_for('the_current_page'))  # Replace with the appropriate endpoint

@app.route('/chat/<int:conversation_id>')
@login_required
def chat_interface(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    return render_template('chat.html', conversation=conversation)

# Fetch all conversations from the database and convert them to a list of dictionaries
def get_conversations_from_db():
    conversations = Conversation.query.all()
    return [conv.to_dict() for conv in conversations]

@app.route('/database')
def database():
    try:
        conversations = get_conversations_from_db()
        conversations_json = json.dumps(conversations, indent=4) # Convert to JSON and pretty-print
        return render_template('database.html', conversations_json=conversations_json)
    except Exception as e:
        print(e)  # For debugging purposes
        return "Error fetching data from the database", 500

@app.cli.command("clear-db")
def clear_db():
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("Database cleared.")

@app.route('/folders', methods=['GET'])
def get_folders():
    folders = Folder.query.all()
    return jsonify([folder.title for folder in folders])

@app.route('/folders', methods=['POST'])
def create_folder():
    title = request.json.get('title')
    new_folder = Folder(title=title)
    db.session.add(new_folder)
    db.session.commit()
    return jsonify({"message": "Folder created successfully"}), 201

@app.route('/folders/<int:folder_id>/conversations', methods=['GET'])
def get_folder_conversations(folder_id):
    conversations = Conversation.query.filter_by(folder_id=folder_id).all()
    return jsonify([conversation.title for conversation in conversations])

@app.route('/folders/<int:folder_id>/conversations', methods=['POST'])
def create_conversation_in_folder(folder_id):
    title = request.json.get('title')
    new_conversation = Conversation(title=title, folder_id=folder_id)
    db.session.add(new_conversation)
    db.session.commit()
    return jsonify({"message": "Conversation created successfully"}), 201

# Fetch all conversations from the database for listing in the left sidebar
@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    # Fetch all conversations from database for the current user
    conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.updated_at.desc()).all()
 
    # Convert the list of Conversation objects into a list of dictionaries
    conversations_dict = [{"id": c.id, 
                           "title": c.title, 
                           "history": json.loads(c.history), 
                           "model_name": c.model_name, 
                           "token_count": c.token_count,
                           "updated_at": c.updated_at,
                           "temperature": c.temperature} 
                          for c in conversations]  
    return jsonify(conversations_dict)

# Fetch a specific conversation from the database to display in the chat interface
@app.route('/conversations/<int:conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    # Fetch a specific conversation from database
    conversation = Conversation.query.get(conversation_id)
    if conversation is None:
        return jsonify({'error': 'Conversation not found'}), 404

    # Convert the Conversation object into a dictionary with all fields, including the new ones
    conversation_dict = {
        "id": conversation.id,
        "title": conversation.title,
        "history": json.loads(conversation.history),
        "token_count": conversation.token_count,
        "model_name": conversation.model_name,
        "temperature": conversation.temperature,
        "vector_search_results": json.loads(conversation.vector_search_results) if conversation.vector_search_results else None,
        "generated_search_queries": json.loads(conversation.generated_search_queries) if conversation.generated_search_queries else None,
        "web_search_results": json.loads(conversation.web_search_results) if conversation.web_search_results else None,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
        "sentiment": conversation.sentiment,
        "tags": conversation.tags,
        "language": conversation.language,
        "status": conversation.status,
        "rating": conversation.rating,
        "confidence": conversation.confidence,
        "intent": conversation.intent,
        "entities": json.loads(conversation.entities) if conversation.entities else None,
        "prompt_template": conversation.prompt_template
    }
    return jsonify(conversation_dict)

@app.route('/c/<conversation_id>')
def show_conversation(conversation_id):
    print(f"Attempting to load conversation {conversation_id}")  # Log the attempt
    # Your logic to load the specific conversation by conversation_id from the database
    conversation = Conversation.query.get(conversation_id)
    
    if not conversation:
        # If no conversation is found with that ID, you can either:
        # 1. Render a 404 page
        # return render_template('404.html'), 404
        # 2. Redirect to a default page
        print(f"No conversation found for ID {conversation_id}")  # Log the error
        return redirect(url_for('index'))
    
    # If a conversation is found, you'll render the chat interface.
    # You'll also pass the conversation data to the template, 
    # so the frontend can load the conversation when the page loads.
    return render_template('chat.html', conversation_id=conversation.id)

@app.route('/api/conversations/<int:conversation_id>/update_title', methods=['POST'])
def update_conversation_title(conversation_id):
    try:
        # Fetch the conversation by ID
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404
        
        # Get the new title from request data
        data = request.get_json()
        new_title = data.get('title')
        if not new_title:
            return jsonify({"error": "New title is required"}), 400
        
        # Update title
        conversation.title = new_title
        db.session.commit()

        return jsonify({"message": "Title updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    try:
        # Fetch the conversation by ID
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404
        
        # Delete the conversation
        db.session.delete(conversation)
        db.session.commit()

        return jsonify({"message": "Conversation deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    app.logger.info("Home route accessed")
    app.logger.info(f"Request Path: {request.path}")
    app.logger.info(f"Request Headers: {request.headers}")
    app.logger.info(f"Request Data: {request.data}")
    app.logger.info(f"User authenticated: {current_user.is_authenticated}")
    app.logger.info(f"Session contents: {session}")
    # Check if user is authenticated
    if current_user.is_authenticated:
        app.logger.info("User is authenticated")
        # Clear conversation-related session data for a fresh start
        if 'conversation_id' in session:
            del session['conversation_id']
        # If logged in, show the main chat page or dashboard
        return render_template('chat.html', conversation=None)
    else:
        app.logger.info("User is not authenticated, redirecting to login")
        # If not logged in, redirect to the login page
        return redirect(url_for('auth.login'))

@app.route('/clear-session', methods=['POST'])
def clear_session():
    session.clear()
    return jsonify({"message": "Session cleared"}), 200

def estimate_token_count(text):
    # Simplistic estimation. You may need a more accurate method.
    return len(text.split())

def generate_summary(messages):
    # Use only the most recent messages or truncate to reduce token count
    conversation_history = ' '.join([message['content'] for message in messages[-5:]])
    
    if estimate_token_count(conversation_history) > 4000:  # Adjust the limit as needed
        conversation_history = conversation_history[:4000]  # Truncate to fit the token limit
        app.logger.info("Conversation history truncated for summary generation")

    summary_request_payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Please create a very short (2-4 words) summary title for the following text:\n" + conversation_history}
        ],
        "max_tokens": 10,
        "temperature": 0.5  # Adjust the temperature if needed
    }

    app.logger.info(f"Sending summary request to OpenAI for conversation title: {str(summary_request_payload)[:100]}...")

    try:
        response = client.chat.completions.create(**summary_request_payload)
        summary = response.choices[0].message.content.strip()
        app.logger.info(f"Response from OpenAI for summary: {response}")
        app.logger.info(f"Generated conversation summary: {summary}")
    except Exception as e:
        app.logger.error(f"Error in generate_summary: {e}")
        summary = "Conversation Summary"  # Fallback title

    return summary




@app.route('/reset-conversation', methods=['POST'])
@login_required
def reset_conversation():
    if 'conversation_id' in session:
        del session['conversation_id']
    return jsonify({"message": "Conversation reset successful"})

async def get_response_from_model(client, model, messages, temperature):
    """
    Routes the request to the appropriate API based on the model selected.
    Supports both synchronous and asynchronous calls.
    """
    app.logger.info(f"Getting response from model: {model}")
    app.logger.info(f"Temperature: {temperature}")
    app.logger.info(f"Number of messages: {len(messages)}")

    try:
        if model.startswith("gpt-"):
            # OpenAI chat models
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 4096  # Current maximum tokens supported by OpenAI
            }
            # Use synchronous call for OpenAI models
            response = client.chat.completions.create(**payload)
            chat_output = response.choices[0].message.content.strip()
            model_name = response.model

        elif model.startswith("claude-"):
            # Anthropic model
            anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

            anthropic_messages = []
            system_message = None
            for message in messages:
                if message['role'] == 'system':
                    system_message = message['content']
                elif message['role'] in ['user', 'assistant']:
                    anthropic_messages.append({"role": message['role'], "content": message['content']})

            if system_message and anthropic_messages:
                anthropic_messages[0]['content'] = f"{system_message}\n\nUser: {anthropic_messages[0]['content']}"

            if not anthropic_messages or anthropic_messages[0]['role'] != 'user':
                anthropic_messages.insert(0, {"role": "user", "content": ""})

            max_tokens = 8192 if model == "claude-3-5-sonnet-20240620" else 4096

            response = await asyncio.to_thread(
                anthropic_client.messages.create,
                model=model,
                messages=anthropic_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                extra_headers={"anthropic-beta": "max-tokens-3-5-sonnet-2024-07-15"} if model == "claude-3-5-sonnet-20240620" else None
            )
            chat_output = response.content[0].text
            model_name = model

        elif model.startswith("gemini-"):
            # Gemini models
            gemini_model = GenerativeModel(model_name=model)
            contents = [{
                "role": "user",
                "parts": [{"text": "\n".join([m['content'] for m in messages])}]
            }]
            response = await asyncio.to_thread(
                gemini_model.generate_content,
                contents,
                generation_config={"temperature": temperature}
            )
            chat_output = response.text
            model_name = model

        else:
            raise ValueError(f"Unsupported model: {model}")

        app.logger.info(f"Response received from {model_name}")
        app.logger.info(f"Response content (first 100 chars): {chat_output[:100]}...")
        return chat_output, model_name

    except Exception as e:
        app.logger.error(f"Error getting response from model {model}: {str(e)}")
        app.logger.exception("Full traceback:")
        return None, None

# Wrapper function for synchronous calls
def get_response_from_model_sync(client, model, messages, temperature):
    return asyncio.run(get_response_from_model(client, model, messages, temperature))




@app.route('/chat', methods=['POST'])
@login_required
def chat():
    try:
        messages = request.json.get('messages')
        model = request.json.get('model')
        temperature = request.json.get('temperature')
        system_message_id = request.json.get('system_message_id')
        enable_web_search = request.json.get('enable_web_search', False)
        enable_intelligent_search = request.json.get('enable_intelligent_search', False)
        
        if system_message_id is None:
            app.logger.error("No system_message_id provided in the chat request")
            return jsonify({'error': 'No system message ID provided'}), 400
        
        conversation_id = request.json.get('conversation_id') or session.get('conversation_id')

        app.logger.info(f'Received model: {model}, temperature: {temperature}, system_message_id: {system_message_id}, enable_web_search: {enable_web_search}, enable_intelligent_search: {enable_intelligent_search}')

        conversation = None
        if conversation_id:
            conversation = Conversation.query.get(conversation_id)
            if conversation and conversation.user_id == current_user.id:
                app.logger.info(f'Using existing conversation with id {conversation_id}.')
            else:
                app.logger.info(f'No valid conversation found with id {conversation_id}, starting a new one.')
                conversation = None

        app.logger.info(f'Getting storage context for system_message_id: {system_message_id}')
        storage_context = embedding_store.get_storage_context(system_message_id)
        app.logger.info(f'Storage context retrieved: {storage_context}')

        user_query = messages[-1]['content']
        app.logger.info(f'User query: {user_query}')

        relevant_info = None
        try:
            app.logger.info(f'Querying index with user query: {user_query[:50]}...')
            relevant_info = file_processor.query_index(user_query, storage_context)
            app.logger.info(f'Retrieved relevant info: {relevant_info[:100]}...')
            if not relevant_info or relevant_info.strip() == "":
                app.logger.warning('No relevant information found in the index.')
                relevant_info = None
        except Exception as e:
            app.logger.error(f'Error querying index: {str(e)}')
            app.logger.exception("Full traceback:")
            relevant_info = None

        # Update the system message with the vector search results
        system_message = next((msg for msg in messages if msg['role'] == 'system'), None)
        
        if system_message is None:
            system_message = {
                "role": "system",
                "content": ""
            }
            messages.insert(0, system_message)

        # Append vector search results
        if relevant_info:
            system_message['content'] += f"\n\n<Added Context Provided by Vector Search>\n{relevant_info}\n</Added Context Provided by Vector Search>"
        
        # Log the updated system message
        app.logger.info(f"Updated system message: {system_message['content']}")

        summarized_results = None
        generated_search_queries = None
        
        if enable_web_search:
            try:
                app.logger.info('Web search enabled, starting search process...')
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                with ThreadPoolExecutor() as pool:
                    generated_search_queries, summarized_results = loop.run_until_complete(
                        perform_web_search_process(client, model, messages, user_query, current_user.id, system_message_id, enable_intelligent_search)
                    )
                loop.close()
                
                app.logger.info(f'Web search process completed. Generated queries: {generated_search_queries}')
                app.logger.info(f'Summarized results: {summarized_results[:100] if summarized_results else None}')
                
                # Ensure generated_search_queries is always a list
                if not isinstance(generated_search_queries, list):
                    app.logger.warning(f"generated_search_queries is not a list. Type: {type(generated_search_queries)}. Value: {generated_search_queries}")
                    generated_search_queries = [str(generated_search_queries)] if generated_search_queries else []
                
                if summarized_results:
                    system_message['content'] += f"\n\n<Added Context Provided by Web Search>\n{summarized_results}\n</Added Context Provided by Web Search>"
                    
                    system_message['content'] += "\n\nIMPORTANT: In your response, please include relevant footnotes using [1], [2], etc. At the end of your response, list all sources under a 'Sources:' section, providing full URLs for each footnote."
                else:
                    app.logger.warning('No summarized results from web search')
            except Exception as e:
                app.logger.error(f'Error in web search process: {str(e)}')
                app.logger.exception("Full traceback:")
                generated_search_queries = None
                summarized_results = None
        else:
            app.logger.info('Web search is disabled')

        # Log the final system message after all updates
        app.logger.info(f"Final system message: {system_message['content']}")

        # Get a response from the AI model
        app.logger.info(f'Sending messages to model: {json.dumps(messages, indent=2)}')
        chat_output, model_name = get_response_from_model_sync(client, model, messages, temperature)

        if chat_output is None:
            raise Exception("Failed to get response from model")
        
        app.logger.info(f"Final response from model after prompt injections: {chat_output}")

        prompt_tokens = count_tokens(model_name, messages)
        completion_tokens = count_tokens(model_name, [{"content": chat_output}])
        total_tokens = prompt_tokens + completion_tokens

        app.logger.info(f'Tokens - Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}')

        new_message = {"role": "assistant", "content": chat_output}
        messages.append(new_message)

        if not conversation:
            conversation = Conversation(
                history=json.dumps(messages), 
                temperature=temperature,
                user_id=current_user.id,
                token_count=total_tokens
            )
            conversation_title = generate_summary(messages)
            conversation.title = conversation_title
            db.session.add(conversation)
            app.logger.info(f'Created new conversation with title: {conversation_title}')
        else:
            conversation.history = json.dumps(messages)
            conversation.temperature = temperature
            conversation.token_count += total_tokens
            app.logger.info(f'Updated existing conversation with id: {conversation.id}')

        conversation.model_name = model
        conversation.vector_search_results = json.dumps(relevant_info) if relevant_info else None
        conversation.generated_search_queries = json.dumps(generated_search_queries) if generated_search_queries else None
        conversation.web_search_results = json.dumps(summarized_results) if summarized_results else None

        db.session.commit()
        session['conversation_id'] = conversation.id

        app.logger.info(f'Chat response prepared. Conversation ID: {conversation.id}, Title: {conversation.title}')

        return jsonify({
            'chat_output': chat_output,
            'conversation_id': conversation.id,
            'conversation_title': conversation.title,
            'vector_search_results': relevant_info if relevant_info else "No results found",
            'generated_search_queries': generated_search_queries if generated_search_queries else [],
            'web_search_results': summarized_results if summarized_results else "No web search performed",
            'system_message_content': system_message['content'],
            'usage': {
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': total_tokens
            },
            'enable_web_search': enable_web_search,
            'enable_intelligent_search': enable_intelligent_search
        })  

    except Exception as e:
        app.logger.error(f'Unexpected error in chat route: {str(e)}')
        app.logger.exception("Full traceback:")
        return jsonify({'error': 'An unexpected error occurred'}), 500

def count_tokens(model_name, messages):
    if model_name.startswith("gpt-"):
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to cl100k_base encoding if the specific model encoding is not found
            encoding = tiktoken.get_encoding("cl100k_base")
        
        num_tokens = 0
        for message in messages:
            # Count tokens in the content
            num_tokens += len(encoding.encode(message['content']))
            
            # Add tokens for role (and potentially name)
            num_tokens += 4  # Every message follows <im_start>{role/name}\n{content}<im_end>\n
            if 'name' in message:
                num_tokens += len(encoding.encode(message['name']))
        
        # Add tokens for the messages separator
        num_tokens += 2  # Every reply is primed with <im_start>assistant
        
        return num_tokens

    elif model_name.startswith("claude-"):
        encoding = tiktoken.get_encoding("cl100k_base")
        num_tokens = 0
        
        for message in messages:
            if isinstance(message, dict):
                content = message.get('content', '')
                role = message.get('role', '')
            elif isinstance(message, str):
                content = message
                role = ''
            else:
                continue  # Skip if message is neither dict nor str

            num_tokens += len(encoding.encode(content))
            
            if role:
                num_tokens += len(encoding.encode(role))
            
            if role == 'user':
                num_tokens += len(encoding.encode("Human: "))
            elif role == 'assistant':
                num_tokens += len(encoding.encode("Assistant: "))
            
            num_tokens += 2  # Each message ends with '\n\n'
        
        # Add tokens for the system message if present
        if messages and isinstance(messages[0], dict) and messages[0].get('role') == 'system':
            num_tokens += len(encoding.encode("\n\nHuman: "))
        
        return num_tokens

    elif model_name == "gemini-pro":
        try:
            genai.configure(api_key="YOUR_GOOGLE_API_KEY")  # Replace with your actual API key
            model = genai.GenerativeModel('gemini-pro')
            
            num_tokens = 0
            for message in messages:
                if isinstance(message, dict):
                    content = message.get('content', '')
                elif isinstance(message, str):
                    content = message
                else:
                    continue

                # Use the count_tokens method to get an estimate
                token_count = model.count_tokens(content)
                num_tokens += token_count.total_tokens

            return num_tokens
        except Exception as e:
            print(f"Error counting tokens for Gemini: {e}")
            # Fallback to word count if there's an error
            return sum(len(m.get('content', '').split()) if isinstance(m, dict) else len(m.split()) for m in messages)

    else:
        # Fallback to a generic tokenization method
        num_tokens = 0
        for message in messages:
            num_tokens += len(message['content'].split())  # Fallback to word count
        return num_tokens

@app.route('/get_active_conversation', methods=['GET'])
def get_active_conversation():
    conversation_id = session.get('conversation_id')
    return jsonify({'conversationId': conversation_id})

# This has to be at the bottom of the file
if __name__ == '__main__':
    # Set host to '0.0.0.0' to make the server externally visible
    port = int(os.getenv('PORT', 8080))  # Needs to be set to 8080
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
