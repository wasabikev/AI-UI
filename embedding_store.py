import os
import hashlib
from pinecone import Pinecone
from llama_index.core import StorageContext
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from sqlalchemy.engine.url import make_url

class EmbeddingStore:
    def __init__(self, db_url):
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        if not pinecone_api_key:
            raise ValueError("PINECONE_API_KEY environment variable not set")

        self.pc = Pinecone(api_key=pinecone_api_key)
        self.index_name = "aiui"
        self.database_identifier = self.generate_db_identifier(db_url)
        self.embed_model = OpenAIEmbedding()

        try:
            if self.index_name not in self.pc.list_indexes().names():
                self.pc.create_index(
                    name=self.index_name,
                    dimension=1536,
                    metric="cosine",
                    spec=Pinecone.ServerlessSpec(
                        cloud=os.getenv("PINECONE_CLOUD", "aws"),
                        region=os.getenv("PINECONE_REGION", "us-east-1")
                    )
                )
            print(f"Initialized EmbeddingStore using index: {self.index_name} and database identifier: {self.database_identifier}")
        except Exception as e:
            print(f"Error initializing Pinecone index: {str(e)}")
            raise

    def generate_db_identifier(self, db_url):
        try:
            url = make_url(db_url)
            db_info = f"{url.host}_{url.database}"
            return hashlib.md5(db_info.encode()).hexdigest()[:12]
        except Exception as e:
            print(f"Error generating database identifier: {str(e)}")
            raise

    def get_embed_model(self):
        return self.embed_model

    def get_storage_context(self, system_message_id):
        if system_message_id is None:
            raise ValueError("system_message_id cannot be None")
        try:
            namespace = self.generate_namespace(system_message_id)
            pinecone_index = self.pc.Index(self.index_name)
            vector_store = PineconeVectorStore(
                pinecone_index=pinecone_index,
                text_key="content",
                namespace=namespace
            )
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            print(f"Created storage context for system message ID: {system_message_id}, namespace: {namespace}")
            return storage_context
        except Exception as e:
            print(f"Error getting storage context: {str(e)}")
            raise

    def generate_namespace(self, system_message_id):
        try:
            combined_identifier = f"{system_message_id}_{self.database_identifier}"
            namespace_hash = hashlib.md5(combined_identifier.encode()).hexdigest()
            namespace = f"sm_{namespace_hash[:12]}"
            print(f"Generated namespace: {namespace} for system message ID: {system_message_id}")
            return namespace
        except Exception as e:
            print(f"Error generating namespace: {str(e)}")
            raise