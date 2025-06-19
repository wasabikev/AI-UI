# orchestration/web_search_standard.py

import logging
from orchestration.web_search_utils import (
    perform_web_search,
    fetch_partial_content,
    WebSearchError,
    brave_api_rate_limiter,
)
# Import any other needed utilities (e.g., token counters, model callers)

logger = logging.getLogger(__name__)

async def generate_single_search_query(client, model: str, messages, user_query: str, get_response_from_model=None):
    """
    Generate a single, focused search query based on the conversation history and user query.
    """
    system_message = """Generate a single, focused search query based on the conversation history and user query.
The query should:
- Capture the main intent of the user's request
- Be specific enough to find relevant information
- Be general enough to get comprehensive results
- Use key terms from the original query
- Be formatted for web search (no special characters or formatting)
Respond with ONLY the search query, no additional text or explanation."""
    # Take the last 5 messages for context, if any
    recent_messages = messages[-5:] if messages else []
    conversation_history = "\n".join([
        f"{msg['role'].capitalize()}: {msg['content']}" 
        for msg in recent_messages
    ])
    if conversation_history:
        conversation_history += f"\nCurrent Query: {user_query}"
    else:
        conversation_history = f"Query: {user_query}"
    messages_for_model = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": conversation_history}
    ]
    try:
        logger.info(f"Attempting to generate search query using {model}")
        if get_response_from_model is None:
            raise RuntimeError("get_response_from_model function must be provided")
        query, *_  = await get_response_from_model(client, model, messages_for_model, temperature=0.3)
        if not query:
            logger.warning("Query generation failed, using original query")
            return user_query.strip()
        generated_query = query.strip()
        if len(generated_query) < 3:
            logger.warning("Generated query too short, using original query")
            return user_query.strip()
        return generated_query
    except Exception as e:
        logger.error(f"Error in generate_single_search_query: {str(e)}")
        return user_query.strip()

async def standard_web_search_process(
    client, model: str, understood_query: str, user_id: int, system_message_id: int,
    BRAVE_SEARCH_API_KEY: str, get_response_from_model, get_file_path, logger=None
):
    logger = logger or logging.getLogger(__name__)
    try:
        logger.info('Step 2: Generating search query')
        search_query = await generate_single_search_query(
            client, model, [], understood_query, get_response_from_model=get_response_from_model
        )
        logger.info(f'Generated search query: {search_query}')
        logger.info('Step 3: Performing web search')
        web_search_results = await perform_web_search(search_query, BRAVE_SEARCH_API_KEY, logger=logger)
        logger.info(f'Web search completed. Results count: {len(web_search_results)}')
        if web_search_results:
            logger.info('Step 4: Fetching partial content for search results')
            partial_content_results = await fetch_partial_content(
                web_search_results, logger, user_id, system_message_id, get_file_path
            )
            logger.info(f'Partial content fetched for {len(partial_content_results)} results')
            logger.info('Step 5: Summarizing search results')
            summarized_results = await standard_summarize_search_results(
                client, model, partial_content_results, understood_query, get_response_from_model
            )
            logger.info(f'Summarization completed. Summary length: {len(summarized_results)} characters')
        else:
            logger.warning('No web search results found.')
            summarized_results = "No relevant web search results were found."
        logger.info('Standard web search process completed successfully')
        return [search_query], summarized_results
    except WebSearchError as e:
        logger.error(f'Standard web search process error: {str(e)}')
        return None, f"An error occurred during the standard web search process: {str(e)}"
    except Exception as e:
        logger.error(f'Unexpected error in standard web search process: {str(e)}')
        return None, "An unexpected error occurred during the standard web search process."

async def standard_summarize_search_results(
    client, model: str, results, query: str, get_response_from_model
):
    logger.info(f"Starting standard summarization of search results for query: '{query[:50]}'")
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
        summary, *_ = await get_response_from_model(client, model, messages, temperature=0.3)
        summarized_content = summary.strip()
        logger.info(f"Search results summarized. Summary length: {len(summarized_content)} characters")
        return summarized_content
    except Exception as e:
        logger.error(f"Error in standard_summarize_search_results: {str(e)}")
        raise WebSearchError(f"Failed to summarize search results: {str(e)}")
