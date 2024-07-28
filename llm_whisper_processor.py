import os, json
from unstract.llmwhisperer.client import LLMWhispererClient, LLMWhispererClientException

class LLMWhisperProcessor:
    def __init__(self):
        api_key = os.getenv("LLMWHISPERER_API_KEY")
        if not api_key:
            raise ValueError("LLMWHISPERER_API_KEY environment variable not set")
        self.client = LLMWhispererClient(api_key=api_key)
        self.processed_texts_folder = "processed_texts"
        os.makedirs(self.processed_texts_folder, exist_ok=True)

    def process_file(self, file_path):
        try:
            result = self.client.whisper(
                file_path=file_path,
                processing_mode="text",
                output_mode="line-printer",
                force_text_processing=True,
                store_metadata_for_highlighting=True
            )
            
            # Save the extracted text to a file
            file_name = os.path.basename(file_path)
            output_file_path = os.path.join(self.processed_texts_folder, f"{file_name}_processed.txt")
            
            with open(output_file_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
            
            return result["extracted_text"]
        except LLMWhispererClientException as e:
            print(f"Error processing file: {e}")
            return None

    def highlight_text(self, whisper_hash, search_text):
        try:
            result = self.client.highlight_data(whisper_hash, search_text)
            return result["highlight_data"]
        except LLMWhispererClientException as e:
            print(f"Error highlighting text: {e}")
            return None