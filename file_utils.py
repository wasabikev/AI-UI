# file_utils.py

import os
import uuid
import asyncio
from typing import Optional, Union, Tuple
import aiofiles.os as aio_os
from pathlib import Path, WindowsPath
from functools import lru_cache
from quart import current_app
import shutil

class FileUtils:
    def __init__(self, app):
        self.app = app
        # Convert to proper Path object and resolve
        self.base_upload_folder = Path(app.config['BASE_UPLOAD_FOLDER']).resolve()
        self._lock = asyncio.Lock()

    @lru_cache(maxsize=128)
    def get_user_folder(self, user_id: int) -> Path:
        """Get the base folder for a user's files."""
        return self.base_upload_folder / str(user_id)

    @lru_cache(maxsize=128)
    def get_system_message_folder(self, user_id: int, system_message_id: int) -> Path:
        """Get the folder for a specific system message."""
        return self.get_user_folder(user_id) / str(system_message_id)

    @lru_cache(maxsize=128)
    def get_uploads_folder(self, user_id: int, system_message_id: int) -> Path:
        """Get the uploads folder for a specific system message."""
        return self.get_system_message_folder(user_id, system_message_id) / 'uploads'

    @lru_cache(maxsize=128)
    def get_processed_texts_folder(self, user_id: int, system_message_id: int) -> Path:
        """Get the processed texts folder for a specific system message."""
        return self.get_system_message_folder(user_id, system_message_id) / 'processed_texts'

    @lru_cache(maxsize=128)
    def get_llmwhisperer_output_folder(self, user_id: int, system_message_id: int) -> Path:
        """Get the LLMWhisperer output folder for a specific system message."""
        return self.get_system_message_folder(user_id, system_message_id) / 'llmwhisperer_output'

    @lru_cache(maxsize=128)
    def get_web_search_results_folder(self, user_id: int, system_message_id: int) -> Path:
        """Get the web search results folder for a specific system message."""
        return self.get_system_message_folder(user_id, system_message_id) / 'web_search_results'

    async def ensure_folder_exists(self, folder_path: Union[Path, str]) -> None:
        """Ensure a folder exists, creating it if necessary."""
        folder_path = Path(folder_path).resolve()
        async with self._lock:
            try:
                # Create all parent directories
                folder_path.parent.mkdir(parents=True, exist_ok=True)
                if not folder_path.exists():
                    folder_path.mkdir(parents=True, exist_ok=True)
                    self.app.logger.info(f"Created folder: {folder_path}")
                # Ensure proper permissions
                os.chmod(str(folder_path), 0o755)
            except Exception as e:
                self.app.logger.error(f"Error creating folder {folder_path}: {str(e)}")
                raise

    async def get_file_path(self, user_id: int, system_message_id: int, filename: str, folder_type: str) -> Path:
        """Get the full path for a file based on its type and associated system message."""
        try:
            folder = self._get_folder_by_type(user_id, system_message_id, folder_type)
            await self.ensure_folder_exists(folder)
            return folder / filename
        except Exception as e:
            self.app.logger.error(f"Error getting file path: {str(e)}")
            raise

    def _get_folder_by_type(
        self, 
        user_id: int, 
        system_message_id: int, 
        folder_type: str
    ) -> Path:
        """Get the appropriate folder based on the folder type."""
        folder_getters = {
            'uploads': self.get_uploads_folder,
            'processed_texts': self.get_processed_texts_folder,
            'llmwhisperer_output': self.get_llmwhisperer_output_folder,
            'web_search_results': self.get_web_search_results_folder
        }

        getter = folder_getters.get(folder_type)
        if not getter:
            raise ValueError(f"Invalid folder type: {folder_type}")
        
        return getter(user_id, system_message_id)

    async def check_file_exists(self, file_path: Union[Path, str]) -> bool:
        """Check if a file exists asynchronously."""
        return await aio_os.path.exists(str(file_path))

    async def get_file_size(self, file_path: Union[Path, str]) -> int:
        """Get the size of a file asynchronously."""
        stat = await aio_os.stat(str(file_path))
        return stat.st_size

    async def remove_file(self, file_path: Union[Path, str]) -> None:
        """Remove a file asynchronously."""
        async with self._lock:  # Use lock for thread-safe file operations
            try:
                file_path = Path(file_path)
                if await self.check_file_exists(file_path):
                    await aio_os.remove(str(file_path))
                    self.app.logger.info(f"Removed file: {file_path}")
            except Exception as e:
                self.app.logger.error(f"Error removing file {file_path}: {str(e)}")
                raise

    async def move_file(self, src: Union[Path, str], dst: Union[Path, str]) -> None:
        """Move a file asynchronously."""
        async with self._lock:
            try:
                await aio_os.rename(str(src), str(dst))
            except OSError:
                # Fallback to copy and delete if rename fails (e.g., across devices)
                shutil.copy2(str(src), str(dst))
                await self.remove_file(src)

# Convenience functions
async def get_user_folder(app, user_id):
    utils = FileUtils(app)
    return utils.get_user_folder(user_id)

async def get_system_message_folder(app, user_id, system_message_id):
    utils = FileUtils(app)
    return utils.get_system_message_folder(user_id, system_message_id)

async def get_uploads_folder(app, user_id, system_message_id):
    utils = FileUtils(app)
    return utils.get_uploads_folder(user_id, system_message_id)

async def get_processed_texts_folder(app, user_id, system_message_id):
    utils = FileUtils(app)
    return utils.get_processed_texts_folder(user_id, system_message_id)

async def get_llmwhisperer_output_folder(app, user_id, system_message_id):
    utils = FileUtils(app)
    return utils.get_llmwhisperer_output_folder(user_id, system_message_id)

async def get_web_search_results_folder(app, user_id, system_message_id):
    utils = FileUtils(app)
    return utils.get_web_search_results_folder(user_id, system_message_id)

async def ensure_folder_exists(folder_path):
    utils = FileUtils(current_app._get_current_object())
    await utils.ensure_folder_exists(folder_path)

async def get_file_path(app, user_id, system_message_id, filename, folder_type):
    utils = FileUtils(app)
    return await utils.get_file_path(user_id, system_message_id, filename, folder_type)