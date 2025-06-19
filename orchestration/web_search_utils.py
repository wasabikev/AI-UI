# orchestration/web_search_utils.py

import asyncio
import platform
import aiohttp
import aiofiles
import json
from bs4 import BeautifulSoup
from aiolimiter import AsyncLimiter
import logging

logger = logging.getLogger(__name__)

# FIXED: Brave Search API rate limiter: 1 request per second (not 3!)
brave_api_rate_limiter = AsyncLimiter(1, 1)

class WebSearchError(Exception):
    """Custom exception for web search errors."""
    pass

class CustomResolver:
    """A simple custom DNS resolver that uses socket.getaddrinfo"""
    def __init__(self, loop):
        self._loop = loop

    async def resolve(self, hostname, port=0, family=0):
        import socket
        from functools import partial
        result = await self._loop.run_in_executor(
            None,
            partial(socket.getaddrinfo, hostname, port, family, socket.SOCK_STREAM)
        )
        return [{'hostname': hostname, 'host': r[4][0], 'port': port} for r in result]


async def perform_web_search(query: str, BRAVE_SEARCH_API_KEY: str, logger=None):
    logger = logger or logging.getLogger(__name__)
    url = 'https://api.search.brave.com/res/v1/web/search'
    headers = {
        'Accept': 'application/json',
        'X-Subscription-Token': BRAVE_SEARCH_API_KEY
    }
    params = {'q': query, 'count': 3}

    if platform.system() == 'Windows':
        resolver = CustomResolver(asyncio.get_event_loop())
        connector = aiohttp.TCPConnector(use_dns_cache=False, limit=10, resolver=resolver)
    else:
        connector = aiohttp.TCPConnector(ttl_dns_cache=300, use_dns_cache=True, limit=10)

    try:
        # Use the rate limiter here too for safety
        async with brave_api_rate_limiter:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 429:
                        raise WebSearchError("Rate limit reached. Please try again later.")
                    response.raise_for_status()
                    results = await response.json()
                    
        if not results.get('web', {}).get('results', []):
            logger.warning(f'No results found for query: "{query[:50]}"')
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
        return formatted_results
        
    except aiohttp.ClientError as e:
        logger.error(f'Error performing Brave search: {str(e)}')
        raise WebSearchError(f"Failed to perform web search: {str(e)}")
    except Exception as e:
        logger.error(f'Unexpected error in perform_web_search: {str(e)}')
        raise WebSearchError(f"Unexpected error during web search: {str(e)}")
    finally:
        if 'connector' in locals():
            await connector.close()

async def fetch_partial_content(results, logger, user_id=None, system_message_id=None, get_file_path=None):
    """Fetch partial content (first 1000 chars) from a list of URLs."""
    async def get_partial_page_content(url: str) -> str:
        if platform.system() == 'Windows':
            resolver = CustomResolver(asyncio.get_event_loop())
            connector = aiohttp.TCPConnector(use_dns_cache=False, limit=10, resolver=resolver)
        else:
            connector = aiohttp.TCPConnector(ttl_dns_cache=300, use_dns_cache=True, limit=10)
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(url) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    text_content = soup.get_text(strip=True, separator='\n')
                    partial_content = text_content[:1000]
                    return partial_content
        except Exception as e:
            logger.error(f"Error fetching content for {url}: {str(e)}")
            return ""
        finally:
            if 'connector' in locals():
                await connector.close()

    async def safe_get_content(result):
        try:
            content = await get_partial_page_content(result['url'])
            return content
        except Exception as e:
            logger.error(f"Error processing URL {result['url']}: {str(e)}")
            return ""

    tasks = [asyncio.create_task(safe_get_content(result)) for result in results]
    contents = await asyncio.gather(*tasks, return_exceptions=True)

    partial_content_results = []
    for result, content in zip(results, contents):
        if isinstance(content, Exception):
            logger.error(f"Error processing content for {result['url']}: {str(content)}")
            content = ""
        partial_result = {**result, "partial_content": content}
        partial_content_results.append(partial_result)
        # Optionally save to disk if get_file_path is provided
        if get_file_path and user_id is not None and system_message_id is not None:
            try:
                file_name = f"partial_result_{result['citation_number']}.json"
                file_path = await get_file_path(user_id, system_message_id, file_name, 'web_search_results')
                import aiofiles
                async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                    import json
                    await f.write(json.dumps(partial_result, ensure_ascii=False, indent=2))
            except Exception as e:
                logger.error(f"Error saving file for result {result['citation_number']}: {str(e)}")
    return partial_content_results

async def fetch_full_content(
    results,
    logger,
    user_id,
    system_message_id,
    get_file_path
):
    logger.info(f"Starting to fetch full content for {len(results)} results")

    async def get_page_content(url: str) -> str:
        if platform.system() == 'Windows':
            from orchestration.web_search_utils import CustomResolver  # or adjust import as needed
            resolver = CustomResolver(asyncio.get_event_loop())
            connector = aiohttp.TCPConnector(use_dns_cache=False, limit=10, resolver=resolver)
        else:
            connector = aiohttp.TCPConnector(ttl_dns_cache=300, use_dns_cache=True, limit=10)
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                logger.info(f"Fetching content from URL: {url}")
                async with session.get(url) as response:
                    logger.info(f"Received response from {url}. Status: {response.status}")
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    text_content = soup.get_text(strip=True, separator='\n')
                    logger.info(f"Extracted {len(text_content)} characters of text from {url}")
                    return text_content
        except Exception as e:
            logger.error(f"Error fetching content for {url}: {str(e)}")
            return ""
        finally:
            if 'connector' in locals():
                await connector.close()

    async def safe_get_content(result):
        try:
            content = await get_page_content(result['url'])
            return content
        except Exception as e:
            logger.error(f"Error processing URL {result['url']}: {str(e)}")
            return ""

    tasks = [asyncio.create_task(safe_get_content(result)) for result in results]
    contents = await asyncio.gather(*tasks, return_exceptions=True)

    full_content_results = []
    used_citation_numbers = set()

    for result, content in zip(results, contents):
        if isinstance(content, Exception):
            logger.error(f"Error processing content for {result['url']}: {str(content)}")
            content = ""

        original_citation_number = result['citation_number']
        unique_citation_number = original_citation_number
        while unique_citation_number in used_citation_numbers:
            unique_citation_number += 1
        used_citation_numbers.add(unique_citation_number)

        full_result = {**result, "full_content": content, "citation_number": unique_citation_number}
        full_content_results.append(full_result)

        file_name = f"result_{unique_citation_number}.json"
        file_path = await get_file_path(user_id, system_message_id, file_name, 'web_search_results')
        try:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(full_result, ensure_ascii=False, indent=2))
            logger.info(f"Saved full content for result {unique_citation_number} to {file_path}")
        except Exception as e:
            logger.error(f"Error saving file for result {unique_citation_number}: {str(e)}")

    logger.info(f"Completed fetching full content for {len(full_content_results)} results")
    return full_content_results