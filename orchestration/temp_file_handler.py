# orchestration/temp_file_handler.py

import os
import uuid
import time
import asyncio
import aiofiles
import aiofiles.os as aio_os
import logging
from typing import Optional
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

class TemporaryFileHandler:
    def __init__(self, temp_folder, file_processor):
        self.temp_folder = temp_folder
        self.file_processor = file_processor

    async def save_temp_file(self, file):
        try:
            file_id = str(uuid.uuid4())
            filename = secure_filename(file.filename)
            temp_subfolder = os.path.join(self.temp_folder, file_id)
            os.makedirs(temp_subfolder, exist_ok=True)
            file_path = os.path.join(temp_subfolder, filename)
            await file.save(file_path)
            token_count = None
            try:
                import tiktoken
                encoding = tiktoken.get_encoding("cl100k_base")
                async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    sample_text = await f.read(8192)
                    token_count = len(encoding.encode(sample_text))
            except Exception as token_error:
                logger.warning(f"Could not estimate tokens for file: {str(token_error)}")
            return {
                'success': True,
                'fileId': file_id,
                'filename': filename,
                'file_path': file_path,
                'size': os.path.getsize(file_path),
                'mime_type': file.content_type,
                'tokenCount': token_count
            }
        except Exception as e:
            logger.error(f"Error saving temporary file: {str(e)}")
            raise

    async def get_temp_file_content(self, file_id: str, user_id: int, system_message_id: int, status_manager=None, session_id: Optional[str] = None) -> Optional[str]:
        log_prefix = f"[{session_id}] " if session_id else ""
        try:
            temp_subfolder = os.path.join(self.temp_folder, file_id)
            if not os.path.exists(temp_subfolder):
                logger.warning(f"{log_prefix}Temporary folder not found for file ID: {file_id}")
                return None
            file_path_local = None
            found_filename = None
            loop = asyncio.get_event_loop()
            def find_file_sync():
                try:
                    for entry in os.scandir(temp_subfolder):
                        if entry.is_file():
                            return entry.path, entry.name
                    return None, None
                except Exception as sync_find_err:
                    logger.error(f"Sync error scanning {temp_subfolder}: {sync_find_err}")
                    return None, None
            file_path_local, found_filename = await loop.run_in_executor(None, find_file_sync)
            if file_path_local is None:
                logger.error(f"{log_prefix}No file found in temporary folder {temp_subfolder} for file ID: {file_id}")
                if session_id and status_manager:
                    await status_manager.update_status(f"Could not locate file for ID {file_id[:8]}.", session_id, status="error")
                return None
            if not file_path_local:
                logger.warning(f"{log_prefix}No file found in temporary folder {temp_subfolder} for file ID: {file_id}")
                if session_id and status_manager:
                    await status_manager.update_status(f"Could not locate file for ID {file_id[:8]}.", session_id, status="error")
                return None
            try:
                logger.info(f"{log_prefix}Extracting document via FileProcessor: {file_path_local}")
                start_time = time.time()
                extracted_text, _ = await self.file_processor.llm_whisper.process_file(
                    file_path=file_path_local,
                    user_id=user_id,
                    system_message_id=system_message_id,
                    file_id=file_id
                )
                end_time = time.time()
                logger.info(f"{log_prefix}FileProcessor extraction took {end_time - start_time:.2f} seconds.")
                if extracted_text:
                    logger.info(f"{log_prefix}FileProcessor extracted text successfully for file ID: {file_id}")
                    if session_id and status_manager:
                        await status_manager.update_status(f"Text extracted from {found_filename or file_id[:8]}.", session_id)
                    return extracted_text
                else:
                    logger.warning(f"{log_prefix}FileProcessor extraction for {file_id} completed but no text found.")
                    if session_id and status_manager:
                        await status_manager.update_status(f"Extraction complete but no text found for {found_filename or file_id[:8]}.", session_id, status="warning")
                    return None
            except Exception as llm_error:
                logger.error(f"{log_prefix}LLMWhisperer extraction failed for {file_id}: {llm_error}")
                if session_id and status_manager:
                    await status_manager.update_status(f"Error processing file {file_id[:8]}...", session_id, status="error")
                return None
        except Exception as e:
            logger.error(f"{log_prefix}Error retrieving temporary file content for {file_id}: {str(e)}")
            if session_id and status_manager:
                await status_manager.update_status(f"Error processing file ID {file_id[:8]}...", session_id, status="error")
            return None

    async def remove_temp_file(self, file_id):
        try:
            temp_subfolder = os.path.join(self.temp_folder, file_id)
            if await aio_os.path.exists(temp_subfolder):
                files = await aio_os.scandir(temp_subfolder)
                for file in files:
                    await aio_os.remove(file.path)
                await aio_os.rmdir(temp_subfolder)
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing temporary file: {str(e)}")
            raise
