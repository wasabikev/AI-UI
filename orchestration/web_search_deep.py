import asyncio
import json
import logging
from typing import List, Dict, Callable, Any, Optional

from orchestration.web_search_utils import (
    WebSearchError,
    perform_web_search,
    fetch_full_content,
    brave_api_rate_limiter,
)

# --- Module-level constants for configuration ---
MAX_CONTENT_LENGTH = 5000
DEFAULT_SUMMARY_TOKENS = 1000
MODEL_COMBINE = "gpt-4o-mini-2024-07-18"
MODEL_FALLBACK = "gpt-3.5-turbo"

logger = logging.getLogger(__name__)

async def generate_search_queries(
    client: Any,
    model: str,
    interpretation: str,
    get_response_from_model: Callable,
) -> List[str]:
    """
    Generate diverse search queries from an interpreted user query via LLM.

    Args:
        client: LLM client instance.
        model: Model name to use for query generation.
        interpretation: User query as interpreted by the system.
        get_response_from_model: LLM response function.

    Returns:
        List[str]: List of generated search queries.

    Raises:
        WebSearchError: On failure to generate or parse queries.
    """
    system_message = (
        "Generate three diverse search queries based on the given interpretation. "
        'Respond with only valid JSON in the format: {"queries": ["query1", "query2", "query3"]}'
    )
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": interpretation},
    ]
    try:
        response, *_ = await get_response_from_model(client, model, messages, temperature=0.3)
        queries = json.loads(response.strip())["queries"]
        return queries
    except Exception as e:
        logger.error(f"Error in generate_search_queries: {str(e)}", exc_info=True)
        raise WebSearchError(f"Failed to generate search queries: {str(e)}")

async def perform_multiple_web_searches(
    queries: List[str],
    BRAVE_SEARCH_API_KEY: str,
    logger: logging.Logger,
    perform_web_search_func: Callable = perform_web_search,
) -> List[Dict]:
    """
    Perform multiple web searches sequentially with rate limiting, deduplicating URLs.

    Args:
        queries: List of queries to search for.
        BRAVE_SEARCH_API_KEY: API key for Brave.
        logger: Logger instance.
        perform_web_search_func: Function to perform the search.

    Returns:
        List[Dict]: List of unique search results.
    """
    all_results = []
    urls_seen = set()
    successful_searches = 0

    for i, query in enumerate(queries):
        try:
            # Use the rate limiter for each search
            async with brave_api_rate_limiter:
                logger.info(f"Performing search {i+1}/{len(queries)}: '{query[:50]}{'...' if len(query) > 50 else ''}'")
                results = await perform_web_search_func(query, BRAVE_SEARCH_API_KEY, logger=logger)
                
                # Process results and deduplicate
                if results:
                    for result in results:
                        url = result.get("url")
                        if url and url not in urls_seen:
                            urls_seen.add(url)
                            all_results.append(result)
                    successful_searches += 1
                    logger.info(f"Search {i+1} completed successfully, found {len(results)} results")
                else:
                    logger.warning(f"Search {i+1} returned no results")
                    
        except WebSearchError as e:
            logger.error(f"Search {i+1} failed for query '{query[:50]}': {str(e)}")
            # Continue with remaining searches instead of failing completely
            continue
        except Exception as e:
            logger.error(f"Unexpected error in search {i+1} for query '{query[:50]}': {str(e)}")
            continue

    logger.info(f"Completed {successful_searches}/{len(queries)} searches successfully. Total unique results: {len(all_results)}")
    
    if successful_searches == 0:
        raise WebSearchError("All search queries failed due to rate limits or errors")
    
    return all_results


async def summarize_page_content(
    client: Any,
    content: str,
    query: str,
    get_response_from_model: Callable,
) -> str:
    """
    Summarize the content of a web page with relevance to a query.

    Args:
        client: LLM client.
        content: Page content to summarize.
        query: Search query for context.
        get_response_from_model: LLM response function.

    Returns:
        str: Summary string.

    Raises:
        WebSearchError: On summary generation failure.
    """
    system_message = (
        "Summarize the given content, focusing on information relevant to the query. "
        "Be concise but include key points and any relevant code snippets."
    )
    user_message = (
        f'Summarize the following content, focusing on information relevant to the query: "{query}"\n'
        f"Content: {content[:500]}  # Truncated for logging purposes\n"
        "Provide a concise summary that captures the main points relevant to the query."
    )
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]
    try:
        summary, *_ = await get_response_from_model(client, MODEL_COMBINE, messages, temperature=0.3)
        return summary.strip()
    except Exception as e:
        logger.error(f"Error in summarize_page_content: {str(e)}", exc_info=True)
        raise WebSearchError(f"Failed to summarize page content: {str(e)}")

async def combine_summaries(
    client: Any,
    summaries: List[Dict],
    query: str,
    get_response_from_model: Callable,
) -> str:
    """
    Combine multiple summary dicts into a single LLM-generated summary with citations.

    Args:
        client: LLM client.
        summaries: List of summaries with 'index', 'url', 'summary'.
        query: The original query.
        get_response_from_model: LLM response function.

    Returns:
        str: Combined summary with citations.

    Raises:
        WebSearchError: On combination failure.
    """
    system_message = (
        "Combine the given summaries into a coherent overall summary. "
        "Include relevant information from all sources and cite them using numbered footnotes [1], [2], etc. "
        "At the end, include a 'Sources:' section with full URLs for each footnote."
    )
    truncated_summaries = [
        {
            "index": s["index"],
            "url": s["url"],
            "summary": s["summary"][:100] + "..." if len(s["summary"]) > 100 else s["summary"]
        }
        for s in summaries
    ]
    user_message = (
        f'Combine the following summaries into a coherent overall summary, focusing on information relevant to the query: "{query}"\n'
        f"Summaries:\n{json.dumps(truncated_summaries, indent=2)}\n"
        "Provide a concise but comprehensive summary that addresses the query, citing sources with footnotes."
    )
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]
    try:
        final_summary, *_ = await get_response_from_model(client, MODEL_COMBINE, messages, temperature=0.3)
        return final_summary.strip()
    except Exception as e:
        logger.error(f"Error in combine_summaries: {str(e)}", exc_info=True)
        raise WebSearchError(f"Failed to combine summaries: {str(e)}")

async def intelligent_summarize(
    client: Any,
    model: str,
    content: str,
    query: str,
    get_response_from_model: Callable,
    max_tokens: int = DEFAULT_SUMMARY_TOKENS,
) -> str:
    """
    Intelligently summarize the content with emphasis on query relevance and code.

    Args:
        client: LLM client.
        model: Model name.
        content: Text to summarize.
        query: Relevant query.
        get_response_from_model: LLM response function.
        max_tokens: Max tokens for output.

    Returns:
        str: Summary.
    """
    if not content:
        return "No content available for summarization."
    system_message = (
        "You are an advanced AI assistant tasked with intelligently summarizing web content. "
        "Your summaries should be informative, relevant to the query, and include key information. "
        "If the content contains code, especially for newer libraries, repos, or APIs, include it verbatim in your summary. "
        "Adjust the level of detail based on the content's relevance and information density. "
        "Your summary should be comprehensive yet concise."
    )
    truncated_content = content[:MAX_CONTENT_LENGTH]
    if len(content) > MAX_CONTENT_LENGTH:
        truncated_content += "... [Content truncated]"
    user_message = (
        f'Summarize the following content, focusing on information relevant to the query: "{query}"\n'
        f"Content: {truncated_content}\n"
        "Remember to include any relevant code snippets verbatim, especially if they relate to new technologies or APIs."
    )
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]
    try:
        summary, *_ = await get_response_from_model(client, model, messages, temperature=0.3)
        return summary.strip()
    except Exception as e:
        logger.error(f"Error in intelligent_summarize: {str(e)}", exc_info=True)
        raise WebSearchError(f"Failed to generate intelligent summary: {str(e)}")

async def summarize_search_results(
    client: Any,
    model: str,
    results: List[Dict],
    query: str,
    get_response_from_model: Callable,
) -> str:
    """
    Summarize all search results and combine into a coherent answer.

    Args:
        client: LLM client.
        model: Model name.
        results: Search results with content.
        query: User query.
        get_response_from_model: LLM response function.

    Returns:
        str: Combined summary.

    Raises:
        WebSearchError: If all summarizations fail.
    """
    if not results:
        return "No search results were found to summarize."
    summaries = []
    failed_summaries = []
    for index, result in enumerate(results, 1):
        content = result.get('full_content', '')
        if not content:
            continue
        try:
            summary = await intelligent_summarize(client, model, content, query, get_response_from_model)
            if not summary:
                summary = await intelligent_summarize(client, MODEL_FALLBACK, content, query, get_response_from_model)
            if summary:
                summaries.append({
                    "index": result['citation_number'],
                    "url": result['url'],
                    "summary": summary
                })
            else:
                raise ValueError("Both primary and fallback summarization failed")
        except Exception as e:
            failed_summaries.append({
                "index": result['citation_number'],
                "url": result['url'],
                "error": str(e)
            })
    if not summaries:
        error_msg = "Failed to generate any summaries from the search results."
        if failed_summaries:
            error_msg += f" Errors: {json.dumps(failed_summaries, indent=2)}"
        raise WebSearchError(error_msg)
    # Combine summaries
    combined_summary_prompt = (
        f"""Combine these summaries into a coherent response that answers the query: "{query}"
Requirements:
Include relevant information from all sources
Use numbered footnotes [1], [2], etc. for citations
Preserve any code snippets exactly as they appear
Include all sources in the final 'Sources:' section
Maintain a clear, logical flow of information
Focus on information relevant to the query
Format the response as:
Main summary with inline citations
Code snippets (if any) with proper formatting
Sources section with full URLs
Summaries to combine:
{json.dumps(summaries, indent=2)}"""
    )
    messages = [
        {
            "role": "system", 
            "content": (
                "You are an expert at combining multiple sources into clear, comprehensive summaries. "
                "Focus on accuracy, clarity, and proper citation of sources. Preserve technical details and code snippets exactly as provided."
            )
        },
        {"role": "user", "content": combined_summary_prompt}
    ]
    try:
        final_summary, *_ = await get_response_from_model(client, model, messages, temperature=0.3)
        if not final_summary and model != MODEL_FALLBACK:
            final_summary, *_ = await get_response_from_model(
                client, MODEL_FALLBACK, messages, temperature=0.3
            )
        if not final_summary:
            basic_summary = "Summary of found information:\n\n"
            for summary in summaries:
                basic_summary += f"[{summary['index']}] {summary['summary']}\n\n"
            basic_summary += "\nSources:\n"
            for summary in summaries:
                basic_summary += f"[{summary['index']}] {summary['url']}\n"
            return basic_summary
        summarized_content = final_summary.strip()
        # Verify all sources are included
        if not all(f"[{s['index']}]" in summarized_content for s in summaries):
            summarized_content += "\n\nAdditional Sources:\n"
            for summary in summaries:
                if f"[{summary['index']}]" not in summarized_content:
                    summarized_content += f"[{summary['index']}] {summary['url']}\n"
        return summarized_content
    except Exception as e:
        try:
            basic_summary = "Error occurred during final summary generation. Here are the individual summaries:\n\n"
            for summary in summaries:
                basic_summary += f"[{summary['index']}] {summary['summary']}\n\n"
            basic_summary += "\nSources:\n"
            for summary in summaries:
                basic_summary += f"[{summary['index']}] {summary['url']}\n"
            return basic_summary
        except Exception:
            raise WebSearchError("Complete failure in summary generation process")

async def deep_web_search_process(
    client: Any,
    model: str,
    messages: List[Dict],
    understood_query: str,
    user_id: int,
    system_message_id: int,
    BRAVE_SEARCH_API_KEY: str,
    get_response_from_model: Callable,
    get_file_path: Callable,
    logger: Optional[logging.Logger] = None,
):
    """
    Orchestrate the full deep web search process.

    Args:
        client: LLM client.
        model: Model for queries.
        messages: Conversation history.
        understood_query: Final interpreted user query.
        user_id: User performing the search.
        system_message_id: System message context.
        BRAVE_SEARCH_API_KEY: Brave API key.
        get_response_from_model: LLM response function.
        get_file_path: Path resolution function for file storage.
        logger: Logger (optional).

    Returns:
        Tuple of (generated_search_queries, summarized_results).

    Raises:
        WebSearchError: On any orchestrator failure.
    """
    logger = logger or logging.getLogger(__name__)
    try:
        logger.info(f"[user_id={user_id}][system_msg_id={system_message_id}] Step 1: Generating search queries based on understood query")
        generated_search_queries = await generate_search_queries(
            client, model, understood_query, get_response_from_model
        )
        if not generated_search_queries:
            logger.error("Failed to generate search queries")
            raise WebSearchError('Failed to generate search queries')
        logger.info(f"[user_id={user_id}][system_msg_id={system_message_id}] Step 2: Performing multiple web searches")
        web_search_results = await perform_multiple_web_searches(
            generated_search_queries, BRAVE_SEARCH_API_KEY, logger, perform_web_search
        )
        if web_search_results:
            logger.info(f"[user_id={user_id}][system_msg_id={system_message_id}] Step 3: Fetching full content for search results")
            full_content_results = await fetch_full_content(
                web_search_results, logger, user_id, system_message_id, get_file_path
            )
            logger.info(f"[user_id={user_id}][system_msg_id={system_message_id}] Step 4: Summarizing search results")
            summarized_results = await summarize_search_results(
                client, model, full_content_results, understood_query, get_response_from_model
            )
            return generated_search_queries, summarized_results
        else:
            logger.warning(f"[user_id={user_id}][system_msg_id={system_message_id}] No relevant web search results were found")
            return generated_search_queries, "No relevant web search results were found."
    except WebSearchError as e:
        logger.error(f"WebSearchError in deep web search: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in deep web search: {str(e)}", exc_info=True)
        raise WebSearchError(f"Unexpected error during deep web search: {str(e)}")
