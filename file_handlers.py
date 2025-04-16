
import os
import uuid
import aiofiles
import aiofiles.os as aio_os
from typing import Tuple

class TemporaryFileHandler:
    """Handles temporary file uploads for chat context"""
    
    def __init__(self, app, llm_whisper):
        self.app = app
        self.llm_whisper = llm_whisper
        self.temp_folder = app.config['TEMP_UPLOAD_FOLDER']
        
    async def save_temp_file(self, file_data: bytes, filename: str) -> Tuple[str, str]:
        """
        Saves a temporary file and returns its path and ID
        Returns: (file_path, file_id)
        """
        file_id = str(uuid.uuid4())
        temp_path = os.path.join(self.temp_folder, file_id)
        
        try:
            async with aiofiles.open(temp_path, 'wb') as f:
                await f.write(file_data)
            return temp_path, file_id
        except Exception as e:
            self.app.logger.error(f"Error saving temporary file: {str(e)}")
            raise

    async def extract_text_content(self, file_path: str, mime_type: str) -> str:
        """Extract text from file using LLMWhisperer without vectorization"""
        try:
            result = await self.llm_whisper.whisper(
                file_path=file_path,
                processing_mode="text",
                output_mode="text"
            )
            return result.get('extracted_text', '')
        except Exception as e:
            self.app.logger.error(f"Error extracting text from file: {str(e)}")
            raise

    async def cleanup_temp_file(self, file_path: str):
        """Remove a temporary file"""
        try:
            if os.path.exists(file_path):
                await aio_os.remove(file_path)
        except Exception as e:
            self.app.logger.error(f"Error removing temporary file: {str(e)}")

