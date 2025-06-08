# llm_whisper_processor.py

import os
import asyncio
from typing import Optional, Tuple, Dict, Any
from unstract.llmwhisperer.client import LLMWhispererClient, LLMWhispererClientException
from utils.file_utils import get_file_path
import aiofiles

class LLMWhisperProcessor:
    def __init__(self, app):
        """Initialize the LLMWhisperProcessor with the application instance."""
        api_key = os.getenv("LLMWHISPERER_API_KEY")
        if not api_key:
            raise ValueError("LLMWHISPERER_API_KEY environment variable not set")
        
        self.client = LLMWhispererClient(api_key=api_key)
        self.app = app
        self.logger = app.logger

    async def process_file(
        self, 
        file_path: str, 
        user_id: int, 
        system_message_id: int, 
        file_id: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Process a file using LLMWhisperer asynchronously.
        
        Args:
            file_path: Path to the file to process
            user_id: ID of the user
            system_message_id: ID of the system message
            file_id: ID of the file
            
        Returns:
            Tuple of (extracted_text, full_result_string) or (None, None) if processing fails
        """
        try:
            self.logger.info(f"Processing file: {file_path}")
            
            # Run the whisper operation in a thread pool since it's blocking
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.whisper(
                    file_path=file_path,
                    processing_mode="text",
                    output_mode="line-printer",
                    force_text_processing=True,
                    store_metadata_for_highlighting=True
                )
            )
            
            # Get the output path
            llmwhisperer_output_path = await get_file_path(
                self.app, 
                user_id, 
                system_message_id, 
                f"{file_id}_llmwhisperer_output.txt", 
                'llmwhisperer_output'
            )
            
            # Save full LLMWhisperer output asynchronously
            async with aiofiles.open(llmwhisperer_output_path, 'w', encoding='utf-8') as f:
                await f.write(str(result))
            
            self.logger.info(f"File processed successfully: {file_path}")
            return result["extracted_text"], str(result)
            
        except LLMWhispererClientException as e:
            self.logger.error(f"Error processing file {file_path}: {str(e)}")
            return None, None
        except Exception as e:
            self.logger.error(f"Unexpected error processing file {file_path}: {str(e)}")
            return None, None

    async def highlight_text(
        self, 
        whisper_hash: str, 
        search_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Highlight text in a processed document asynchronously.
        
        Args:
            whisper_hash: Hash of the processed document
            search_text: Text to highlight
            
        Returns:
            Dictionary containing highlight data or None if highlighting fails
        """
        try:
            self.logger.info(f"Highlighting text in document {whisper_hash[:8]}...")
            
            # Run the highlight operation in a thread pool since it's blocking
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.highlight_data(whisper_hash, search_text)
            )
            
            self.logger.info(f"Text highlighted successfully in document {whisper_hash[:8]}")
            return result["highlight_data"]
            
        except LLMWhispererClientException as e:
            self.logger.error(f"Error highlighting text in document {whisper_hash[:8]}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error highlighting text in document {whisper_hash[:8]}: {str(e)}")
            return None

    async def get_document_metadata(
        self, 
        whisper_hash: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a processed document asynchronously.
        
        Args:
            whisper_hash: Hash of the processed document
            
        Returns:
            Dictionary containing document metadata or None if retrieval fails
        """
        try:
            self.logger.info(f"Retrieving metadata for document {whisper_hash[:8]}...")
            
            # Run the metadata retrieval in a thread pool since it's blocking
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.get_metadata(whisper_hash)
            )
            
            self.logger.info(f"Metadata retrieved successfully for document {whisper_hash[:8]}")
            return result
            
        except LLMWhispererClientException as e:
            self.logger.error(f"Error retrieving metadata for document {whisper_hash[:8]}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error retrieving metadata for document {whisper_hash[:8]}: {str(e)}")
            return None