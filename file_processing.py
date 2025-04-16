# file_processing.py

import os
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, Document
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.core.ingestion import IngestionPipeline
from llm_whisper_processor import LLMWhisperProcessor
from file_utils import get_file_path
import asyncio
from typing import List, Optional, Tuple, Any
from aiofiles import open as aio_open
from functools import partial
from concurrent.futures import ThreadPoolExecutor

# Utility functions
async def run_in_executor(executor: ThreadPoolExecutor, func: Any, *args, **kwargs) -> Any:
    """Helper function to run CPU-bound operations in thread pool"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        executor, 
        partial(func, *args, **kwargs)
    )

async def ensure_directory_exists(executor: ThreadPoolExecutor, path: str) -> None:
    """Ensure a directory exists"""
    await run_in_executor(executor, os.makedirs, os.path.dirname(path), exist_ok=True)

async def save_processed_text(file_path: str, documents: List[Document]) -> None:
    """Save processed text to file"""
    async with aio_open(file_path, 'w', encoding='utf-8') as f:
        for doc in documents:
            await f.write(doc.text + "\n\n")

# Document processing functions
async def process_pdf(
    llm_whisper: LLMWhisperProcessor,
    file_path: str,
    user_id: int,
    system_message_id: int,
    file_id: str
) -> Optional[List[Document]]:
    """Process PDF file using LLMWhisperer"""
    extracted_text, full_response = await llm_whisper.process_file(
        file_path, user_id, system_message_id, file_id
    )
    if extracted_text is None:
        raise ValueError("Failed to extract text from PDF")
    return [Document(text=extracted_text, metadata={'file_id': str(file_id)})]

async def process_text_file(
    executor: ThreadPoolExecutor,
    file_path: str,
    file_id: str
) -> List[Document]:
    """Process non-PDF text file"""
    reader = SimpleDirectoryReader(input_files=[file_path])
    documents = await run_in_executor(executor, reader.load_data)
    for doc in documents:
        doc.metadata['file_id'] = str(file_id)
    return documents

# Index creation and querying functions
async def create_index(
    executor: ThreadPoolExecutor,
    app,
    documents: List[Document],
    storage_context,
    embed_model
) -> VectorStoreIndex:
    """Create document index"""
    # Configure the node parser with specific chunk settings
    node_parser = SimpleNodeParser.from_defaults(
        chunk_size=512,
        chunk_overlap=50,
        include_metadata=True
    )
    
    # Create and run ingestion pipeline
    pipeline = IngestionPipeline(
        transformations=[
            node_parser,
            embed_model,
        ]
    )
    
    # Process documents
    nodes = await run_in_executor(executor, pipeline.run, documents=documents)
    
    # Log chunking information
    app.logger.info(f"Created {len(nodes)} chunks from {len(documents)} documents")
    
    # Ensure file_id is in metadata for each node
    for node in nodes:
        if 'file_id' in node.metadata:
            node.metadata['file_id'] = str(node.metadata['file_id'])
        else:
            app.logger.warning(f"Node missing file_id in metadata: {node.metadata}")
    
    # Create index
    index = await run_in_executor(
        executor,
        lambda: VectorStoreIndex(
            nodes,
            storage_context=storage_context,
            embed_model=embed_model
        )
    )
    
    return index

async def perform_semantic_search(
    executor: ThreadPoolExecutor,
    app,
    query_text: str,
    storage_context
) -> Optional[str]:
    """Perform semantic search on indexed documents"""
    try:
        def retrieval_operation():
            # Create index from vector store
            index = VectorStoreIndex.from_vector_store(storage_context.vector_store)
            
            # Configure retriever with specific parameters
            retriever = index.as_retriever(
                similarity_top_k=5,
                similarity_cutoff=0.7
            )
            
            # Get relevant nodes
            nodes = retriever.retrieve(query_text)
            
            # Filter and format the retrieved content
            if nodes:
                retrieved_texts = []
                for node_with_score in nodes:
                    app.logger.debug(f"Node similarity score: {node_with_score.score}")
                    
                    if node_with_score.score >= 0.7:
                        source_info = (
                            f"[Source: Document {node_with_score.node.metadata.get('file_id', 'unknown')}, "
                            f"Relevance: {node_with_score.score:.2f}]"
                        )
                        text_chunk = node_with_score.node.text.strip()
                        if text_chunk:
                            retrieved_texts.append(f"{source_info}\n{text_chunk}")
                
                if retrieved_texts:
                    return "\n\n---\n\n".join(retrieved_texts)
                
                app.logger.info("No text chunks met the similarity threshold")
                return None
            return None

        response = await run_in_executor(executor, retrieval_operation)
        
        if response:
            app.logger.info(f"Retrieved relevant content (first 100 chars): {response[:100]}...")
        else:
            app.logger.info("No relevant content found")
            
        return response
        
    except Exception as e:
        app.logger.error(f"Error in semantic search: {str(e)}")
        app.logger.exception("Full traceback:")
        return None

class FileProcessor:
    def __init__(self, embedding_store, app):
        self.embedding_store = embedding_store
        self.app = app
        self.llm_whisper = LLMWhisperProcessor(app)
        self._executor = None
        self._loop = asyncio.get_event_loop()

    @property
    def executor(self) -> ThreadPoolExecutor:
        """Lazy initialization of thread pool executor"""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=4)
        return self._executor

    async def process_file(
        self, 
        file_path: str, 
        storage_context, 
        file_id: str, 
        user_id: int, 
        system_message_id: int
    ) -> Optional[str]:
        try:
            self.app.logger.info(f"Processing file: {file_path}")
            
            # Process file based on type
            if file_path.lower().endswith('.pdf'):
                self.app.logger.info("Processing PDF file")
                documents = await process_pdf(
                    self.llm_whisper, file_path, user_id, system_message_id, file_id
                )
            else:
                self.app.logger.info("Processing non-PDF file")
                documents = await process_text_file(self.executor, file_path, file_id)
            
            # Create the index
            index = await create_index(
                self.executor,
                self.app,
                documents,
                storage_context,
                self.embedding_store.get_embed_model()
            )
            
            # Generate and create processed text path
            processed_text_path = await get_file_path(
                self.app, user_id, system_message_id,
                f"{file_id}_processed.txt", 'processed_texts'
            )
            
            await ensure_directory_exists(self.executor, processed_text_path)
            await save_processed_text(processed_text_path, documents)
            
            self.app.logger.info(f"Processed text saved to: {processed_text_path}")
            return processed_text_path
            
        except Exception as e:
            self.app.logger.error(f"Error processing file: {str(e)}")
            self.app.logger.exception("Full traceback:")
            return None

    async def process_text(
        self, 
        text_content: str, 
        metadata: dict = None, 
        storage_context = None
    ) -> VectorStoreIndex:
        try:
            metadata = metadata or {}
            document = Document(text=text_content, metadata=metadata)
            return await create_index(
                self.executor,
                self.app,
                [document],
                storage_context,
                self.embedding_store.get_embed_model()
            )
        except Exception as e:
            self.app.logger.error(f"Error processing text: {str(e)}")
            self.app.logger.exception("Full traceback:")
            raise

    async def query_index(
        self, 
        query_text: str, 
        storage_context
    ) -> Optional[str]:
        try:
            if not storage_context or not storage_context.vector_store:
                self.app.logger.warning("No valid storage context or vector store available for query")
                return None

            return await perform_semantic_search(
                self.executor,
                self.app,
                query_text,
                storage_context
            )
            
        except Exception as e:
            self.app.logger.error(f"Error querying index: {str(e)}")
            self.app.logger.exception("Full traceback:")
            return None

    async def highlight_text(
        self, 
        whisper_hash: str, 
        search_text: str
    ) -> Optional[str]:
        try:
            return await self.llm_whisper.highlight_text(whisper_hash, search_text)
        except Exception as e:
            self.app.logger.error(f"Error highlighting text: {str(e)}")
            self.app.logger.exception("Full traceback:")
            return None

    async def cleanup(self):
        """Cleanup method to be called when shutting down"""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
