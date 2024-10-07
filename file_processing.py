# file_processing.py

import os
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, Document
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.core.ingestion import IngestionPipeline
from llm_whisper_processor import LLMWhisperProcessor
from file_utils import get_file_path

class FileProcessor:
    def __init__(self, embedding_store, app):
        self.embedding_store = embedding_store
        self.app = app
        self.llm_whisper = LLMWhisperProcessor(app)

class FileProcessor:
    def __init__(self, embedding_store, app):
        self.embedding_store = embedding_store
        self.app = app
        self.llm_whisper = LLMWhisperProcessor(app)

    def process_file(self, file_path, storage_context, file_id, user_id, system_message_id):
        try:
            print(f"Processing file: {file_path}")
            # Check if the file is a PDF
            if file_path.lower().endswith('.pdf'):
                print("Processing PDF file")
                # Use LLMWhisperer for PDF files
                extracted_text, full_response = self.llm_whisper.process_file(file_path, user_id, system_message_id, file_id)
                if extracted_text is None:
                    raise ValueError("Failed to extract text from PDF")
                documents = [Document(text=extracted_text, metadata={'file_id': str(file_id)})]
                
                # LLMWhisperer output is now saved within the process_file method of LLMWhisperProcessor
            else:
                print("Processing non-PDF file")
                # Use original logic for non-PDF files
                documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
                # Add file_id to metadata for each document
                for doc in documents:
                    doc.metadata['file_id'] = str(file_id)
            
            # Create the index
            index = self._create_index(documents, storage_context)
            
            # Generate a path for the processed text
            processed_text_path = get_file_path(self.app, user_id, system_message_id, f"{file_id}_processed.txt", 'processed_texts')
            
            # Save the processed text
            with open(processed_text_path, 'w', encoding='utf-8') as f:
                for doc in documents:
                    f.write(doc.text + "\n\n")
            
            print(f"Processed text saved to: {processed_text_path}")
            return processed_text_path
        except Exception as e:
            print(f"Error processing file: {e}")
            return None

    def process_text(self, text_content, metadata=None, storage_context=None):
        metadata = metadata or {}
        document = Document(text=text_content, metadata=metadata)
        return self._create_index([document], storage_context)

    def _create_index(self, documents, storage_context):
        # Create ingestion pipeline
        pipeline = IngestionPipeline(
            transformations=[
                SimpleNodeParser(),
                self.embedding_store.get_embed_model(),
            ]
        )
        
        # Process documents and get nodes
        nodes = pipeline.run(documents=documents)
        
        # Ensure file_id is in metadata for each node
        for node in nodes:
            if 'file_id' in node.metadata:
                node.metadata['file_id'] = str(node.metadata['file_id'])  # Ensure it's a string
            else:
                # If file_id is not present, this is an error condition
                # You might want to log this or raise an exception
                print(f"Node missing file_id in metadata: {node.metadata}")
        
        # Create index
        index = VectorStoreIndex(
            nodes,
            storage_context=storage_context,
            embed_model=self.embedding_store.get_embed_model()
        )
        
        return index

    def query_index(self, query_text, storage_context):
        try:
            # Create query engine
            query_engine = VectorStoreIndex.from_vector_store(
                storage_context.vector_store
            ).as_query_engine()
            
            # Perform RAG query
            response = query_engine.query(query_text)
            
            return response.response
        except Exception as e:
            print(f"Error querying index: {e}")
            return None

    def highlight_text(self, whisper_hash, search_text):
        return self.llm_whisper.highlight_text(whisper_hash, search_text)