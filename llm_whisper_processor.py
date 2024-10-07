# llm_whisper_processor.py

import os
from unstract.llmwhisperer.client import LLMWhispererClient, LLMWhispererClientException
from file_utils import get_file_path

class LLMWhisperProcessor:
    def __init__(self, app):
        api_key = os.getenv("LLMWHISPERER_API_KEY")
        if not api_key:
            raise ValueError("LLMWHISPERER_API_KEY environment variable not set")
        self.client = LLMWhispererClient(api_key=api_key)
        self.app = app

    def process_file(self, file_path, user_id, system_message_id, file_id):
        try:
            result = self.client.whisper(
                file_path=file_path,
                processing_mode="text",
                output_mode="line-printer",
                force_text_processing=True,
                store_metadata_for_highlighting=True
            )
            
            # Save full LLMWhisperer output
            llmwhisperer_output_path = get_file_path(self.app, user_id, system_message_id, f"{file_id}_llmwhisperer_output.txt", 'llmwhisperer_output')
            with open(llmwhisperer_output_path, 'w', encoding='utf-8') as f:
                f.write(str(result))
            
            return result["extracted_text"], str(result)
        except LLMWhispererClientException as e:
            print(f"Error processing file: {e}")
            return None, None

    def highlight_text(self, whisper_hash, search_text):
        try:
            result = self.client.highlight_data(whisper_hash, search_text)
            return result["highlight_data"]
        except LLMWhispererClientException as e:
            print(f"Error highlighting text: {e}")
            return None