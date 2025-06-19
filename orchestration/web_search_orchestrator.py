from typing import List, Dict
import logging

from orchestration.web_search_standard import standard_web_search_process
from orchestration.web_search_deep import deep_web_search_process
from orchestration.web_search_utils import WebSearchError

async def perform_web_search_process(
    client, 
    model: str, 
    messages: List[Dict[str, str]], 
    user_query: str, 
    user_id: int, 
    system_message_id: int, 
    enable_deep_search: bool,
    session_id: str,  # Session ID for websockets
    status_manager,
    logger,
    get_response_from_model,
    BRAVE_SEARCH_API_KEY,     
    get_file_path,           
):
    logger.info(f"Starting web search process for query: '{user_query[:50]}'")
    logger.info(f"Search type: {'Deep' if enable_deep_search else 'Standard'}")

    try:
        logger.info('Step 1: Understanding user query')
        await status_manager.update_status("Analyzing user query for web search", session_id)
        understood_query = await understand_query(
            client, model, messages, user_query, 
            is_standard_search=not enable_deep_search,
            session_id=session_id,
            status_manager=status_manager,
            logger=logger,
            get_response_from_model=get_response_from_model
        )
        logger.info(f'Understood query: {understood_query}')
        await status_manager.update_status("User query analyzed successfully.", session_id)

        if enable_deep_search:
            logger.info('Initiating deep web search')
            await status_manager.update_status("Starting deep web search", session_id)
            results = await deep_web_search_process(
                client, model, messages, understood_query, user_id, system_message_id,
                BRAVE_SEARCH_API_KEY, get_response_from_model, get_file_path, logger
            )
            await status_manager.update_status("Deep web search completed.", session_id)
            return results
        else:
            logger.info('Initiating standard web search')
            await status_manager.update_status("Starting standard web search", session_id)
            results = await standard_web_search_process(
                client, model, understood_query, user_id, system_message_id,
                BRAVE_SEARCH_API_KEY, get_response_from_model, get_file_path, logger
            )
            await status_manager.update_status("Standard web search completed.", session_id)
            return results

    except WebSearchError as e:
        logger.error(f'Web search process error: {str(e)}')
        await status_manager.update_status("Error occurred during web search process.", session_id)
        return [], f"An error occurred during the web search process: {str(e)}"
    except Exception as e:
        logger.error(f'Unexpected error in web search process: {str(e)}')
        logger.exception("Full traceback:")
        await status_manager.update_status("Unexpected error during web search process.", session_id)
        return [], "An unexpected error occurred during the web search process."
    

async def understand_query(
    client, model: str, messages: List[Dict[str, str]], user_query: str,
    is_standard_search: bool = True, session_id: str = None,
    status_manager=None, logger=None, get_response_from_model=None
) -> str:
    logger = logger or logging.getLogger(__name__)

    logger.info(f"Starting query understanding for user query: '{user_query[:50]}'")

    system_message = """Analyze the conversation history and the latest user query. 
Provide a concise interpretation of what information the user is seeking, 
considering the full context of the conversation."""

    conversation_history = "\n".join([f"{msg['role'].capitalize()}: {msg['content'][:50]}..." for msg in messages[:-1]])
    conversation_history += f"\nUser: {user_query}"

    logger.debug(f"Constructed conversation history for query understanding: {conversation_history}")

    messages_for_model = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": conversation_history}
    ]

    query_model = "gpt-4o-mini-2024-07-18" if is_standard_search else model
    logger.info(f"Sending request to model {query_model} for query interpretation")

    try:
        if session_id and status_manager:
            await status_manager.update_status(f"Asking {query_model} for analysis to generate a query", session_id)
        if get_response_from_model is None:
            raise RuntimeError("get_response_from_model function must be provided")
        interpretation, _, _ = await get_response_from_model(client, query_model, messages_for_model, temperature=0.3)
        interpreted_query = interpretation.strip()
        logger.info(f"Query interpreted. Interpretation: '{interpreted_query[:100]}'")
        if session_id and status_manager:
            await status_manager.update_status("Query analysis completed", session_id)
        return interpreted_query
    except Exception as e:
        logger.error(f"Error in understand_query: {str(e)}")
        if session_id and status_manager:
            await status_manager.update_status("Error occurred during query interpretation", session_id)
        raise WebSearchError(f"Failed to interpret query: {str(e)}")
