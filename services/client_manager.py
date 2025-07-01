# services/client_manager.py

import logging
import os
from typing import Optional, Dict, Any

import openai
import anthropic
import google.generativeai as genai
from google.generativeai import GenerativeModel
from openai import OpenAI
from pinecone import Pinecone
from unstract.llmwhisperer.client import LLMWhispererClient, LLMWhispererClientException
from cerebras.cloud.sdk import Client as CerebrasClient


logger = logging.getLogger(__name__)


class ClientManager:
    """Centralized manager for all external service clients"""
    
    def __init__(self):
        self.clients = {}
        self.api_keys = {}
        self.logger = logger
        
    def initialize_all_clients(self) -> Dict[str, Any]:
        """Initialize all external service clients and return them as a dict"""
        
        clients = {}
        
        # Initialize OpenAI
        clients['openai'] = self._initialize_openai()
        
        # Initialize Anthropic
        clients['anthropic'] = self._initialize_anthropic()
        
        # Initialize Google Generative AI
        clients['google'] = self._initialize_google()
        
        # Initialize Pinecone
        clients['pinecone'] = self._initialize_pinecone()
        
        # Initialize Cerebras
        clients['cerebras'] = self._initialize_cerebras()
        
        # Initialize LLMWhisperer
        clients['llmwhisperer'] = self._initialize_llmwhisperer()
        
        # Initialize API keys for services that don't need client objects
        self._initialize_api_keys()
        
        # Store clients for later access
        self.clients = clients
        
        # Log initialization summary
        self._log_initialization_summary(clients)
        
        return clients
    
    def _initialize_openai(self) -> Optional[OpenAI]:
        """Initialize OpenAI client"""
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            
            # Set global API key for backward compatibility
            openai.api_key = api_key
            
            # Create client instance
            client = OpenAI(api_key=api_key)
            
            self.logger.info("OpenAI client initialized successfully")
            return client
            
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            raise
    
    def _initialize_anthropic(self) -> Optional[str]:
        """Initialize Anthropic client (returns API key for backward compatibility)"""
        try:
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            
            # Set global API key for backward compatibility
            anthropic.api_key = api_key
            
            self.logger.info("Anthropic client initialized successfully")
            return api_key
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Anthropic client: {str(e)}")
            raise
    
    def _initialize_google(self) -> bool:
        """Initialize Google Generative AI"""
        try:
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable not set")
            
            # Configure the API
            genai.configure(api_key=api_key)
            
            self.logger.info("Google Generative AI client initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Google Generative AI client: {str(e)}")
            raise
    
    def _initialize_pinecone(self) -> Optional[Pinecone]:
        """Initialize Pinecone client"""
        try:
            api_key = os.getenv("PINECONE_API_KEY")
            if not api_key:
                raise ValueError("PINECONE_API_KEY environment variable not set")
            
            client = Pinecone(api_key=api_key)
            
            self.logger.info("Pinecone client initialized successfully")
            return client
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Pinecone client: {str(e)}")
            raise
    
    def _initialize_cerebras(self) -> Optional[CerebrasClient]:
        """Initialize Cerebras client"""
        try:
            api_key = os.getenv("CEREBRAS_API_KEY")
            if not api_key:
                self.logger.warning("CEREBRAS_API_KEY environment variable not set")
                return None
            
            client = CerebrasClient(api_key=api_key)
            
            self.logger.info("Cerebras client initialized successfully")
            return client
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Cerebras client: {str(e)}")
            self.logger.exception("Full traceback:")
            return None
    
    def _initialize_llmwhisperer(self) -> Optional[LLMWhispererClient]:
        """Initialize LLMWhisperer client"""
        try:
            api_key = os.getenv("LLMWHISPERER_API_KEY")
            if not api_key:
                self.logger.warning("LLMWHISPERER_API_KEY environment variable not set")
                return None
            
            client = LLMWhispererClient(api_key=api_key)
            
            self.logger.info("LLMWhisperer client initialized successfully")
            return client
            
        except Exception as e:
            self.logger.error(f"Failed to initialize LLMWhisperer client: {str(e)}")
            self.logger.exception("Full traceback:")
            return None
    
    def _initialize_api_keys(self) -> None:
        """Initialize API keys for services that don't need client objects"""
        
        # Brave Search API Key
        brave_api_key = os.getenv('BRAVE_SEARCH_API_KEY')
        if brave_api_key:
            self.api_keys['brave_search'] = brave_api_key
            self.logger.info("Brave Search API key loaded successfully")
        else:
            self.logger.warning("BRAVE_SEARCH_API_KEY environment variable not set")
            self.api_keys['brave_search'] = None
        
        # Add other API keys here as needed
        # Example:
        # other_api_key = os.getenv('OTHER_API_KEY')
        # if other_api_key:
        #     self.api_keys['other_service'] = other_api_key
        #     self.logger.info("Other service API key loaded successfully")
    
    def _log_initialization_summary(self, clients: Dict[str, Any]) -> None:
        """Log a summary of client initialization results"""
        
        initialized = []
        failed = []
        
        for service, client in clients.items():
            if client is not None:
                initialized.append(service)
            else:
                failed.append(service)
        
        # Add API key status
        api_key_status = []
        for service, key in self.api_keys.items():
            if key is not None:
                api_key_status.append(service)
            else:
                failed.append(f"{service}_api_key")
        
        if api_key_status:
            initialized.extend([f"{service}_api_key" for service in api_key_status])
        
        self.logger.info(f"Client initialization complete. Initialized: {initialized}")
        
        if failed:
            self.logger.warning(f"Failed to initialize: {failed}")
    
    def get_client(self, service_name: str) -> Any:
        """Get a specific client by service name"""
        return self.clients.get(service_name)
    
    def get_api_key(self, service_name: str) -> Optional[str]:
        """Get a specific API key by service name"""
        return self.api_keys.get(service_name)
    
    def get_all_clients(self) -> Dict[str, Any]:
        """Get all initialized clients"""
        return self.clients.copy()
    
    def get_all_api_keys(self) -> Dict[str, Optional[str]]:
        """Get all API keys"""
        return self.api_keys.copy()
    
    def is_service_available(self, service_name: str) -> bool:
        """Check if a specific service is available"""
        client = self.clients.get(service_name)
        api_key = self.api_keys.get(service_name)
        return client is not None or api_key is not None
    
    def get_available_services(self) -> list:
        """Get list of available service names"""
        available = []
        
        # Add services with clients
        available.extend([name for name, client in self.clients.items() if client is not None])
        
        # Add services with API keys
        available.extend([name for name, key in self.api_keys.items() if key is not None])
        
        return available
