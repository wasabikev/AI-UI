# orchestration/session_attachment_handler.py

import os
import uuid
import aiofiles
import aiofiles.os as aio_os
import mimetypes
import logging
from pathlib import Path
import asyncio

class SessionAttachmentHandler:
    """
    Handles session-scoped attachments (files, screenshots, etc.) for chat context injection.
    These attachments are ephemeral and are not indexed for semantic search.
    """

    def __init__(self, file_utils, file_processor):
        """
        Initialize the handler.

        Args:
            file_utils: FileUtils instance for folder resolution.
            file_processor: Reference to the FileProcessor instance for content extraction.
        """
        self.file_utils = file_utils
        self.file_processor = file_processor
        self.logger = logging.getLogger(__name__)
        self.logger.info("SessionAttachmentHandler initialized with per-user folder structure.")

    async def save_attachment(self, file, user_id):
        """
        Save an uploaded file as a session attachment for a specific user.

        Args:
            file: The file object from the request.
            user_id: The user's ID.

        Returns:
            dict: Metadata about the saved attachment.
        """
        try:
            self.logger.info(f"file object type: {type(file)}")
            self.logger.info(f"file.read: {getattr(file, 'read', None)}")

            attachment_id = str(uuid.uuid4())
            filename = file.filename
            safe_filename = f"{attachment_id}_{filename}"
            folder = self.file_utils.get_session_attachment_folder(user_id)
            file_path = folder / safe_filename

            # Use a thread pool for blocking file read/write
            loop = asyncio.get_event_loop()

            def write_file():
                file.stream.seek(0)
                with open(file_path, 'wb') as out_file:
                    while True:
                        chunk = file.stream.read(4096)
                        if not chunk:
                            break
                        out_file.write(chunk)

            await loop.run_in_executor(None, write_file)

            size = await aio_os.stat(file_path)
            mime_type, _ = mimetypes.guess_type(str(file_path))

            self.logger.info(f"Saved session attachment: {safe_filename} (ID: {attachment_id}) for user {user_id}")

            return {
                'success': True,
                'attachmentId': attachment_id,
                'filename': filename,
                'file_path': str(file_path),
                'size': size.st_size,
                'mime_type': mime_type or 'application/octet-stream'
            }
        except Exception as e:
            self.logger.error(f"Failed to save session attachment: {e}")
            return {'success': False, 'error': str(e)}

    async def remove_attachment(self, attachment_id: str, user_id: int) -> bool:
        """
        Remove a session attachment by its ID for a specific user.

        Args:
            attachment_id (str): The UUID of the attachment.
            user_id (int): The user's ID.

        Returns:
            bool: True if removed, False if not found.
        """
        try:
            folder = self.file_utils.get_session_attachment_folder(user_id)
            for file_path in folder.glob(f"{attachment_id}_*"):
                await aio_os.remove(file_path)
                self.logger.info(f"Removed session attachment: {file_path} for user {user_id}")
                return True
            self.logger.warning(f"Session attachment not found for removal: {attachment_id} (user {user_id})")
            return False
        except Exception as e:
            self.logger.error(f"Error removing session attachment {attachment_id} for user {user_id}: {e}")
            return False

    async def get_attachment_content(self, attachment_id: str, user_id: int, system_message_id: int):
        try:
            folder = self.file_utils.get_session_attachment_folder(user_id)
            for file_path in folder.glob(f"{attachment_id}_*"):
                filename = file_path.name.split("_", 1)[1]
                mime_type, _ = mimetypes.guess_type(str(file_path))

                extracted_text = await self.file_processor.extract_text_from_file(
                    str(file_path),
                    user_id,
                    system_message_id,
                    attachment_id
                )

                if extracted_text:
                    self.logger.info(f"Extracted text for session attachment: {file_path} for user {user_id}")
                    return extracted_text, filename, mime_type
                else:
                    self.logger.error(f"Failed to extract text from {file_path}")
                    return None, filename, mime_type

            self.logger.warning(f"Session attachment not found: {attachment_id} (user {user_id})")
            return None, None, None
        except Exception as e:
            self.logger.error(f"Error retrieving session attachment {attachment_id} for user {user_id}: {e}")
            return None, None, None

