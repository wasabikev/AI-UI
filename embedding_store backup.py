import os
from pinecone import Pinecone, ServerlessSpec
from llama_index.core import StorageContext
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding

class EmbeddingStore:
    def __init__(self):
        # Initialize Pinecone
        self.pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        self.index_name = "aiui"
        
        # Create Pinecone index if it doesn't exist
        if self.index_name not in self.pc.list_indexes().names():
            self.pc.create_index(
                name=self.index_name,
                dimension=1536,  # OpenAI embedding dimension
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=os.getenv("PINECONE_CLOUD", "aws"),
                    region=os.getenv("PINECONE_REGION", "us-east-1")
                )
            )
        
        # Initialize PineconeVectorStore
        pinecone_index = self.pc.Index(self.index_name)
        self.vector_store = PineconeVectorStore(
            pinecone_index=pinecone_index,
            text_key="content"  # Specify the key for the text content
        )
        
        # Initialize OpenAI embedding
        self.embed_model = OpenAIEmbedding()

    def get_storage_context(self):
        return StorageContext.from_defaults(vector_store=self.vector_store)

    def get_embed_model(self):
        return self.embed_model