# file_processing.py

from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, Document
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.core.ingestion import IngestionPipeline

class FileProcessor:
    def __init__(self, embedding_store):
        self.embedding_store = embedding_store

    def process_file(self, file_path, storage_context):
        try:
            # Load document
            documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
            return self._create_index(documents, storage_context)
        except ImportError as e:
            print(f"Error processing file: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error processing file: {e}")
            return None

    def process_text(self, text_content, metadata=None, storage_context=None):
        document = Document(text=text_content, metadata=metadata or {})
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