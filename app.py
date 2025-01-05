# app.py

# Standard library imports
import asyncio
import json
import logging
import os
import platform
import socket
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from functools import lru_cache, partial
from logging.handlers import RotatingFileHandler
from pathlib import Path
from queue import Queue, Empty, Full
from typing import List, Dict
import time
import math

# Third-party imports - Core Web Framework
from quart import (
    Quart, request, jsonify, render_template, url_for, redirect, 
    session, abort, Response, send_file, make_response, request,
    render_template_string, flash, send_from_directory, websocket
)
from quart_cors import cors
from quart_schema import QuartSchema
from quart_auth import (
    QuartAuth, AuthUser, current_user, login_user, 
    logout_user, Unauthorized
)
import pkg_resources

# Third-party imports - Database and ORM
from sqlalchemy import select, func
from alembic import command
from alembic.config import Config as AlembicConfig
from dotenv import load_dotenv

# Third-party imports - AI/ML Services
import openai
import anthropic
import tiktoken
import google.generativeai as genai
from google.generativeai import GenerativeModel
from openai import OpenAI

# Third-party imports - Vector Storage
from pinecone import Pinecone
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding

# Third-party imports - Async HTTP and Network
import aiohttp
from aiohttp import ClientSession, AsyncResolver, ClientTimeout
from aiolimiter import AsyncLimiter
import aiofiles
import aiofiles.os as aio_os
from async_timeout import timeout
from tenacity import retry, stop_after_attempt, wait_exponential
import dns.resolver

# Third-party imports - Web Scraping and Processing
from bs4 import BeautifulSoup
from werkzeug.utils import secure_filename

# Local imports - Auth and Models
from auth import auth_bp, UserWrapper, login_required
from models import (
    get_session, engine, Base,
    Folder, Conversation, User, SystemMessage, Website, UploadedFile
)

# Local imports - Utils and Processing
from text_processing import format_text
from file_utils import (
    get_user_folder, get_system_message_folder, get_uploads_folder,
    get_processed_texts_folder, get_llmwhisperer_output_folder, 
    ensure_folder_exists, get_file_path, FileUtils
)
from file_processing import FileProcessor
from embedding_store import EmbeddingStore
from init_db import init_db

# Load environment variables
load_dotenv()

# Initialize OpenAI
from openai import OpenAI
client = OpenAI()
openai.api_key = os.getenv("OPENAI_API_KEY")
if openai.api_key is None:
    raise ValueError("OPENAI_API_KEY environment variable not set")

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
db_url = os.getenv('DATABASE_URL')
BRAVE_SEARCH_API_KEY = os.getenv('BRAVE_SEARCH_API_KEY')

# Debug configuration
debug_mode = True

# Initialize application
app = Quart(__name__)
app = cors(app, allow_origin="*")
QuartSchema(app)

# Application configuration
app.config.update(
    ASYNC_MODE=True,
    PROPAGATE_EXCEPTIONS=True,
    SSE_RETRY_TIMEOUT=30000,
    SECRET_KEY=os.getenv('SECRET_KEY'),
    TEMPLATES_AUTO_RELOAD=True,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16 MB max-body-size
    MAX_FORM_MEMORY_SIZE=16 * 1024 * 1024,  # 16 MB max-form-size
)


# Configure auth settings - do this BEFORE initializing QuartAuth
app.config.update(
    QUART_AUTH_COOKIE_SECURE=False if app.debug else True,
    QUART_AUTH_COOKIE_DOMAIN=None,
    QUART_AUTH_COOKIE_NAME="auth_token",
    QUART_AUTH_COOKIE_PATH="/",
    QUART_AUTH_COOKIE_SAMESITE="Lax",
    # Convert duration to seconds instead of using timedelta
    QUART_AUTH_DURATION=60 * 60 * 24 * 30,  # 30 days in seconds
    QUART_AUTH_SALT='cookie-session-aiui'
)

# Initialize QuartAuth
auth_manager = QuartAuth(app)
auth_manager.user_class = UserWrapper


# Register the blueprint
app.register_blueprint(auth_bp)  

@app.errorhandler(Unauthorized)
async def unauthorized_handler(error):
    await flash('Please log in to access this page.', 'warning')
    return redirect(url_for('auth.login'))

@app.errorhandler(Exception)
async def handle_exception(error):
    app.logger.error(f"Unhandled exception: {str(error)}")
    app.logger.exception("Full error traceback:")
    return await render_template('error.html', error=str(error))

@app.errorhandler(404)
async def not_found_error(error):
    app.logger.error(f"404 Error: {error}")
    return await render_template('error.html', error="Page not found"), 404

@app.errorhandler(500)
async def internal_error(error):
    app.logger.error(f"500 Error: {error}")
    return await render_template('error.html', error="Internal server error"), 500


@app.route('/static/<path:filename>')
async def static_files(filename):
    return await send_from_directory('static', filename)

# Define the UnicodeFormatter class for logging
class UnicodeFormatter(logging.Formatter):
    """Custom formatter that properly handles Unicode characters in log messages."""
    def format(self, record):
        if isinstance(record.msg, bytes):
            record.msg = record.msg.decode('utf-8', errors='replace')
        elif not isinstance(record.msg, str):
            record.msg = str(record.msg)
            
        if record.args:
            record.args = tuple(
                arg.decode('utf-8', errors='replace') if isinstance(arg, bytes)
                else str(arg) if not isinstance(arg, str)
                else arg
                for arg in record.args
            )
            
        return super().format(record)

def setup_logging(app, debug_mode):
    # Remove any existing handlers
    logging.getLogger().handlers.clear()
    app.logger.handlers.clear()
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG if debug_mode else logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Custom Unicode formatter
    unicode_formatter = UnicodeFormatter("%(asctime)s - %(levelname)s - %(message)s")

    # Set up file handler with rotation
    file_handler = RotatingFileHandler(
        "app.log",
        maxBytes=100000,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(unicode_formatter)
    file_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    # Set up console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(unicode_formatter)
    console_handler.setLevel(logging.INFO if debug_mode else logging.WARNING)

    # Configure app logger
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.propagate = False
    app.logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    # Completely silence SQLAlchemy logging
    logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
    logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.ERROR)
    logging.getLogger('sqlalchemy.dialects').setLevel(logging.ERROR)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.ERROR)
    logging.getLogger('sqlalchemy.orm').setLevel(logging.ERROR)
    
    # Additional SQLAlchemy logging suppression
    logging.getLogger('sqlalchemy.engine.base').setLevel(logging.ERROR)
    logging.getLogger('sqlalchemy.engine.impl').setLevel(logging.ERROR)
    logging.getLogger('sqlalchemy.engine.logger').setLevel(logging.ERROR)

    # Reduce noise from other loggers
    noisy_loggers = [
        'httpcore',
        'hypercorn.error',
        'hypercorn.access',
        'pinecone',
        'unstract',
        'asyncio',
        'httpx',
        'urllib3',
        'requests',
        'pinecone_plugin_interface.logging'
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Disable SQL statement logging explicitly
    logging.getLogger('sqlalchemy.engine.Engine.logger').disabled = True

    # Log startup message
    app.logger.info("Application logging initialized")

    if debug_mode:
        app.logger.debug("Debug mode enabled")


# Usage in app.py
setup_logging(app, debug_mode)

# File upload configuration
BASE_UPLOAD_FOLDER = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), 'user_files'))).resolve()
app.config['BASE_UPLOAD_FOLDER'] = str(BASE_UPLOAD_FOLDER)
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}

# Create the upload folder if it doesn't exist
try:
    upload_folder = Path(app.config['BASE_UPLOAD_FOLDER'])
    upload_folder.mkdir(parents=True, exist_ok=True)
    os.chmod(str(upload_folder), 0o777)
    app.logger.info(f"Successfully configured BASE_UPLOAD_FOLDER: {upload_folder}")
except Exception as e:
    app.logger.error(f"Error during upload folder configuration: {str(e)}")

# Initialize file processing
embedding_store = None
file_processor = None

@app.before_serving
async def startup():
    global embedding_store, file_processor
    
    try:
        app.logger.info("Initializing application components")
        
        # Initialize database
        await init_db()
        
        # Initialize EmbeddingStore
        embedding_store = EmbeddingStore(db_url, logger=app.logger)
        await embedding_store.initialize()
        
        # Initialize FileProcessor
        file_processor = FileProcessor(embedding_store, app)
        
        # Initialize FileUtils and verify upload folder
        app.file_utils = FileUtils(app)
        base_upload_folder = Path(app.config['BASE_UPLOAD_FOLDER'])
        await app.file_utils.ensure_folder_exists(base_upload_folder)
        
        app.logger.info("Application initialization completed successfully")
            
    except Exception as e:
        app.logger.error("Application startup failed", exc_info=True)
        raise

@app.after_serving
async def shutdown():
    try:
        # Close database connection
        await engine.dispose()
        app.logger.info("Database connection closed")

        # Add explicit cleanup of any active connections
        if hasattr(app, '_connection_pool'):
            await app._connection_pool.close()
            app.logger.info("Connection pool closed")

        # Clear FileUtils cache if it exists
        if hasattr(app, 'file_utils'):
            app.file_utils.get_user_folder.cache_clear()
            app.file_utils.get_system_message_folder.cache_clear()
            app.file_utils.get_uploads_folder.cache_clear()
            app.file_utils.get_processed_texts_folder.cache_clear()
            app.file_utils.get_llmwhisperer_output_folder.cache_clear()
            app.file_utils.get_web_search_results_folder.cache_clear()
            app.logger.info("FileUtils caches cleared")

            delattr(app, 'file_utils')
            app.logger.info("FileUtils cleanup completed")

    except Exception as e:
        app.logger.error(f"Error during shutdown: {str(e)}")
        app.logger.exception("Full shutdown error traceback:")
        raise

# Begin of status update manager

# Begin of status update manager
class StatusUpdateManager:
    PING_INTERVAL = 30  # seconds

    def __init__(self):
        self.connections = {}  # Store WebSocket connections
        self.locks = {}
        self.connection_count = 0
        self._cleanup_lock = asyncio.Lock()
        self.active_sessions = set()  # Track active chat sessions
        self.initial_messages_sent = set()  # Track which sessions have received initial message

    async def register_connection(self, session_id, websocket):
        """Register a new WebSocket connection"""
        async with self._cleanup_lock:
            # If there's an existing connection, close it first
            if session_id in self.connections:
                try:
                    old_connection = self.connections[session_id]
                    await old_connection['websocket'].close(1000, "New connection established")
                except Exception as e:
                    app.logger.debug(f"Error closing old connection: {str(e)}")

            self.connections[session_id] = {
                'websocket': websocket,
                'active': True,
                'last_ping': datetime.now()
            }
            self.locks[session_id] = asyncio.Lock()
            self.connection_count = len(self.connections)
            app.logger.debug(f"WebSocket connection registered for session ID: {session_id}. Active connections: {self.connection_count}")

    async def send_update(self, session_id, message):
        """Send an update to a specific session via WebSocket"""
        if session_id not in self.connections or not self.connections[session_id]['active']:
            app.logger.debug(f"No active connection found for session {session_id}")
            return False

        lock = self.locks.get(session_id) or asyncio.Lock()
        async with lock:
            try:
                status_data = {
                    'type': 'status',
                    'message': message,
                    'timestamp': datetime.now().isoformat(),
                    'id': str(uuid.uuid4())
                }
                
                websocket = self.connections[session_id]['websocket']
                await websocket.send(json.dumps(status_data))
                app.logger.debug(f"Status update sent to {session_id}: {message}")
                return True
            except Exception as e:
                app.logger.error(f"Error sending status update: {str(e)}")
                await self.remove_connection(session_id)
                return False

    async def send_ping(self, session_id):
        """Send a ping message to keep the connection alive"""
        if session_id not in self.connections or not self.connections[session_id]['active']:
            return False

        try:
            ping_data = {
                'type': 'ping',
                'timestamp': datetime.now().isoformat()
            }
            websocket = self.connections[session_id]['websocket']
            await websocket.send(json.dumps(ping_data))
            self.connections[session_id]['last_ping'] = datetime.now()
            return True
        except Exception as e:
            app.logger.debug(f"Error sending ping: {str(e)}")
            await self.remove_connection(session_id)
            return False

    async def send_initial_message(self, session_id):
        """Send initial connection message if not already sent"""
        if session_id not in self.initial_messages_sent:
            try:
                websocket = self.connections[session_id]['websocket']
                initial_message = {
                    'type': 'status',
                    'message': 'Connected to status updates',
                    'timestamp': datetime.now().isoformat(),
                    'id': str(uuid.uuid4())
                }
                await websocket.send(json.dumps(initial_message))
                self.initial_messages_sent.add(session_id)
            except Exception as e:
                app.logger.error(f"Error sending initial message: {str(e)}")

    async def remove_connection(self, session_id):
        """Remove a session's WebSocket connection"""
        async with self._cleanup_lock:
            if session_id in self.connections:
                try:
                    connection = self.connections[session_id]
                    connection['active'] = False
                    await connection['websocket'].close(1000, "Connection closed normally")
                except Exception as e:
                    app.logger.debug(f"Error closing websocket: {str(e)}")
                
                self.connections.pop(session_id, None)
                self.locks.pop(session_id, None)
                self.initial_messages_sent.discard(session_id)
                self.connection_count = len(self.connections)
                app.logger.debug(f"WebSocket connection removed for session ID: {session_id}. Active connections: {self.connection_count}")

    def mark_session_active(self, session_id):
        """Mark a session as active (during chat)"""
        self.active_sessions.add(session_id)

    def mark_session_inactive(self, session_id):
        """Mark a session as inactive (after chat completion)"""
        self.active_sessions.discard(session_id)

# Initialize the status manager
status_manager = StatusUpdateManager()

async def send_status_update(message: str):
    """Send a status update to the current user."""
    user_id = str(current_user.auth_id)
    app.logger.debug(f"Sending status update (for user {user_id}): {message}")

    success = await status_manager.send_update(user_id, message)
    if success:
        app.logger.debug("Status update sent successfully")
    else:
        app.logger.debug("Status update failed")



@app.websocket('/ws/chat/status')
@login_required
async def ws_chat_status():
    """WebSocket endpoint for status updates"""
    connection_id = str(current_user.auth_id)
    app.logger.info(f"WebSocket connection attempt from {connection_id}")
    
    try:
        app.logger.info("Getting WebSocket object")
        ws = websocket._get_current_object()
        
        app.logger.info(f"Registering connection for {connection_id}")
        await status_manager.register_connection(connection_id, ws)
        
        app.logger.info(f"Connection registered. Active sessions: {status_manager.active_sessions}")
        app.logger.info(f"Is session active? {connection_id in status_manager.active_sessions}")
        
        # Mark the session as active
        status_manager.mark_session_active(connection_id)
        app.logger.info(f"Session marked active. Active sessions now: {status_manager.active_sessions}")
        
        # Send initial message
        app.logger.info("Attempting to send initial message")
        await status_manager.send_initial_message(connection_id)
        app.logger.info("Initial message sent successfully")
        
        while connection_id in status_manager.active_sessions:
            try:
                app.logger.debug("Waiting for message...")
                message = await ws.receive()
                app.logger.debug(f"Received message: {message}")
                
                if message.type == "websocket.disconnect":
                    app.logger.info("Received disconnect message")
                    break
                    
            except Exception as e:
                app.logger.error(f"Error in message loop: {str(e)}")
                app.logger.exception("Full traceback:")
                break
                
    except Exception as e:
        app.logger.error(f"Error in WebSocket connection: {str(e)}")
        app.logger.exception("Full traceback:")
    finally:
        app.logger.info(f"Cleaning up connection for {connection_id}")
        status_manager.mark_session_inactive(connection_id)
        await status_manager.remove_connection(connection_id)
        app.logger.info("Cleanup complete")


async def periodic_ping(connection_id):
    """Periodically send ping messages to keep the connection alive"""
    try:
        while True:
            await asyncio.sleep(status_manager.PING_INTERVAL)
            if not await status_manager.send_ping(connection_id):
                break
    except asyncio.CancelledError:
        pass
    except Exception as e:
        app.logger.error(f"Error in periodic ping: {str(e)}")

@app.route('/chat/status/health')
@login_required
async def chat_status_health():
    """Health check endpoint for WebSocket connections"""
    try:
        quart_version = pkg_resources.get_distribution('quart').version
    except:
        quart_version = "unknown"

    connection_id = str(current_user.auth_id)
    connection_exists = connection_id in status_manager.connections
    
    response_data = {
        'status': 'healthy',
        'active_connections': status_manager.connection_count,
        'connection_exists': connection_exists,
        'server_time': datetime.now().isoformat(),
        'server_info': {
            'worker_pid': os.getpid(),
            'python_version': sys.version,
            'quart_version': quart_version
        }
    }
    
    return jsonify(response_data)

@app.route('/debug/config')
async def debug_config():
    """Debug endpoint to verify configuration"""
    return jsonify({
        'env_vars': {
            'DEBUG_CONFIG': os.getenv('DEBUG_CONFIG'),
            'WEBSOCKET_PATH': os.getenv('WEBSOCKET_PATH'),
            'PORT': os.getenv('PORT'),
        },
        'routes': {
            'websocket': '/ws/chat/status',
            'health': '/chat/status/health'
        },
        'server_info': {
            'worker_class': 'uvicorn.workers.UvicornWorker',
            'gunicorn_config_path': os.path.exists('gunicorn.conf.py'),
            'app_yaml_path': os.path.exists('.do/app.yaml')
        }
    })

@app.route('/debug/config/full')
@login_required
async def debug_config_full():
    """Detailed debug endpoint to verify configuration (login required)"""
    import os
    
    def mask_sensitive_value(key: str, value: str) -> str:
        """Mask sensitive values in environment variables"""
        sensitive_keys = {'API_KEY', 'SECRET', 'PASSWORD', 'TOKEN', 'DATABASE_URL'}
        if any(sensitive_word in key.upper() for sensitive_word in sensitive_keys):
            if len(str(value)) > 8:
                return f"{value[:4]}...{value[-4:]}"
            return "****"
        return value

    try:
        # Get all files in the current directory
        files = os.listdir('.')
        do_files = os.listdir('.do') if os.path.exists('.do') else []
        
        # Read the contents of the config files
        gunicorn_config = ''
        if os.path.exists('gunicorn.conf.py'):
            with open('gunicorn.conf.py', 'r') as f:
                gunicorn_config = f.read()
        
        app_yaml = ''
        if os.path.exists('.do/app.yaml'):
            with open('.do/app.yaml', 'r') as f:
                app_yaml = f.read()
        
        # Mask sensitive environment variables
        masked_env_vars = {
            key: mask_sensitive_value(key, value)
            for key, value in os.environ.items()
        }
            
        response_data = {
            'env_vars': masked_env_vars,
            'files': {
                'root': files,
                'do_directory': do_files
            },
            'configs': {
                'gunicorn': gunicorn_config,
                'app_yaml': app_yaml
            },
            'routes': {
                'websocket': '/ws/chat/status',
                'health': '/chat/status/health'
            },
            'server_info': {
                'worker_class': 'uvicorn.workers.UvicornWorker',
                'gunicorn_config_path': os.path.exists('gunicorn.conf.py'),
                'app_yaml_path': os.path.exists('.do/app.yaml'),
                'current_directory': os.getcwd()
            },
            'user_info': {
                'is_authenticated': current_user.is_authenticated
            }
        }
        
        app.logger.info("Debug configuration accessed by authenticated user")
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error("Error in debug configuration endpoint: %s", str(e))
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/debug/websocket-config')
@login_required
async def debug_websocket_config():
    """Debug endpoint to check WebSocket configuration"""
    return jsonify({
        'websocket_enabled': True,
        'websocket_path': '/ws/chat/status',
        'current_connections': len(status_manager.connections),
        'active_sessions': len(status_manager.active_sessions),
        'server_info': {
            'worker_class': 'uvicorn.workers.UvicornWorker',
            'websocket_timeout': 300
        }
    })

# Ending of status update manager

# Begining of web search 

#### Common helper functions for both standard and intelligent web search

@app.route('/api/system-messages/<int:system_message_id>/toggle-search', methods=['POST'])
@login_required
async def toggle_search(system_message_id):
    """
    Toggle web search settings for a system message.
    
    Args:
        system_message_id (int): The ID of the system message to update
        
    Returns:
        JSON response with updated search settings
    """
    try:
        data = await request.get_json()
        enable_web_search = data.get('enableWebSearch')
        enable_intelligent_search = data.get('enableIntelligentSearch')
        
        # Input validation
        if enable_web_search is None:
            return jsonify({'error': 'enableWebSearch parameter is required'}), 400
        
        if not isinstance(enable_web_search, bool):
            return jsonify({'error': 'enableWebSearch must be a boolean value'}), 400
            
        async with get_session() as session:
            # Get the system message
            result = await session.execute(
                select(SystemMessage).filter_by(id=system_message_id)
            )
            system_message = result.scalar_one_or_none()
            
            if not system_message:
                return jsonify({'error': 'System message not found'}), 404
            
            # Get current user from database
            user_result = await session.execute(
                select(User).filter_by(id=int(current_user.auth_id))
            )
            current_user_obj = user_result.scalar_one_or_none()
            
            if not current_user_obj:
                return jsonify({'error': 'User not found'}), 404
            
            # Check permissions
            if not current_user_obj.is_admin and system_message.created_by != current_user_obj.id:
                return jsonify({'error': 'Unauthorized to modify this system message'}), 403
            
            # Update the search settings
            system_message.enable_web_search = enable_web_search
            
            # Add timestamp for tracking
            system_message.updated_at = datetime.now(timezone.utc)
            
            # Commit the changes
            await session.commit()
            
            app.logger.info(f"Search settings updated for system message {system_message_id} by user {current_user_obj.id}")
            
            return jsonify({
                'message': 'Search settings updated successfully',
                'enableWebSearch': system_message.enable_web_search,
                'enableIntelligentSearch': enable_intelligent_search,
                'updatedAt': system_message.updated_at.isoformat()
            }), 200
            
    except Exception as e:
        app.logger.error(f"Error in toggle_search: {str(e)}")
        return jsonify({
            'error': 'Failed to update search settings',
            'details': str(e)
        }), 500

async def understand_query(client, model: str, messages: List[Dict[str, str]], user_query: str, is_standard_search: bool = True) -> str:
    app.logger.info(f"Starting query understanding for user query: '{user_query[:50]}'")

    system_message = """Analyze the conversation history and the latest user query. 
    Provide a concise interpretation of what information the user is seeking, 
    considering the full context of the conversation."""

    # Only include the conversation history, excluding the latest user query
    conversation_history = "\n".join([f"{msg['role'].capitalize()}: {msg['content'][:50]}..." for msg in messages[:-1]])
    
    # Add the latest user query separately
    conversation_history += f"\nUser: {user_query}"

    app.logger.debug(f"Constructed conversation history for query understanding: {conversation_history}")

    messages_for_model = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": conversation_history}
    ]

    # Use gpt-4o-mini-2024-07-18 for standard search, otherwise use the provided model
    query_model = "gpt-4o-mini-2024-07-18" if is_standard_search else model
    app.logger.info(f"Sending request to model {query_model} for query interpretation")

    try:
        interpretation, _ = await get_response_from_model(client, query_model, messages_for_model, temperature=0.3)
        interpreted_query = interpretation.strip()
        app.logger.info(f"Query interpreted. Interpretation: '{interpreted_query[:100]}'")
        await send_status_update(f"Asking {query_model} for analysis to generate a query")
        return interpreted_query
    except Exception as e:
        app.logger.error(f"Error in understand_query: {str(e)}")
        await send_status_update("Error occurred during query interpretation")
        raise WebSearchError(f"Failed to interpret query: {str(e)}")

class WebSearchError(Exception):
    """Custom exception for web search errors."""
    pass

class CustomResolver:
    """A simple custom DNS resolver that uses socket.getaddrinfo"""
    
    def __init__(self, loop):
        self._loop = loop

    async def resolve(self, hostname, port=0, family=socket.AF_INET):
        try:
            result = await self._loop.run_in_executor(
                None, 
                partial(
                    socket.getaddrinfo, 
                    hostname, 
                    port, 
                    family, 
                    socket.SOCK_STREAM
                )
            )
            return [{'hostname': hostname, 'host': r[4][0], 'port': port} for r in result]
        except socket.gaierror as e:
            raise aiohttp.ClientError(f"DNS lookup failed for {hostname}: {str(e)}")
        
async def perform_web_search(query: str) -> List[Dict[str, str]]:
    app.logger.info(f"Starting web search for query: '{query[:50]}'")
    
    url = 'https://api.search.brave.com/res/v1/web/search'
    headers = {
        'Accept': 'application/json',
        'X-Subscription-Token': BRAVE_SEARCH_API_KEY
    }
    params = {
        'q': query,
        'count': 3
    }

    app.logger.info(f"Sending request to Brave Search API")

    # Configure connector based on platform
    if platform.system() == 'Windows':
        resolver = CustomResolver(asyncio.get_event_loop())
        connector = aiohttp.TCPConnector(
            use_dns_cache=False,
            limit=10,
            resolver=resolver
        )
    else:
        connector = aiohttp.TCPConnector(
            ttl_dns_cache=300,
            use_dns_cache=True,
            limit=10
        )

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(url, headers=headers, params=params) as response:
                app.logger.info(f"Received response from Brave Search API. Status: {response.status}")
                if response.status == 429:
                    raise WebSearchError("Rate limit reached. Please try again later.")
                response.raise_for_status()
                results = await response.json()
        
        if not results.get('web', {}).get('results', []):
            app.logger.warning(f'No results found for query: "{query[:50]}"')
            return []
        
        formatted_results = [
            {
                "title": result['title'],
                "url": result['url'],
                "description": result['description'],
                "citation_number": i
            }
            for i, result in enumerate(results['web']['results'], 1)
        ]
        
        app.logger.info(f'Web search completed. Number of results: {len(formatted_results)}')
        return formatted_results

    except aiohttp.ClientError as e:
        app.logger.error(f'Error performing Brave search: {str(e)}')
        raise WebSearchError(f"Failed to perform web search: {str(e)}")
    except Exception as e:
        app.logger.error(f'Unexpected error in perform_web_search: {str(e)}')
        raise WebSearchError(f"Unexpected error during web search: {str(e)}")
    finally:
        if 'connector' in locals():
            await connector.close()

async def fetch_full_content(results: List[Dict[str, str]], app, user_id: int, system_message_id: int) -> List[Dict[str, str]]:
    app.logger.info(f"Starting to fetch full content for {len(results)} results")

    async def get_page_content(url: str) -> str:
        if platform.system() == 'Windows':
            resolver = CustomResolver(asyncio.get_event_loop())
            connector = aiohttp.TCPConnector(
                use_dns_cache=False,
                limit=10,
                resolver=resolver
            )
        else:
            connector = aiohttp.TCPConnector(
                ttl_dns_cache=300,
                use_dns_cache=True,
                limit=10
            )

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                app.logger.info(f"Fetching content from URL: {url}")
                async with session.get(url) as response:
                    app.logger.info(f"Received response from {url}. Status: {response.status}")
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    text_content = soup.get_text(strip=True, separator='\n')
                    app.logger.info(f"Extracted {len(text_content)} characters of text from {url}")
                    return text_content
        except Exception as e:
            app.logger.error(f"Error fetching content for {url}: {str(e)}")
            return ""
        finally:
            if 'connector' in locals():
                await connector.close()

    # Create tasks with proper error handling
    async def safe_get_content(result):
        try:
            content = await get_page_content(result['url'])
            return content
        except Exception as e:
            app.logger.error(f"Error processing URL {result['url']}: {str(e)}")
            return ""

    # Create and gather tasks
    tasks = [asyncio.create_task(safe_get_content(result)) for result in results]
    contents = await asyncio.gather(*tasks, return_exceptions=True)

    full_content_results = []
    used_citation_numbers = set()

    for result, content in zip(results, contents):
        if isinstance(content, Exception):
            app.logger.error(f"Error processing content for {result['url']}: {str(content)}")
            content = ""

        original_citation_number = result['citation_number']
        unique_citation_number = original_citation_number
        while unique_citation_number in used_citation_numbers:
            unique_citation_number += 1
        used_citation_numbers.add(unique_citation_number)

        full_result = {**result, "full_content": content, "citation_number": unique_citation_number}
        full_content_results.append(full_result)

        file_name = f"result_{unique_citation_number}.json"
        file_path = get_file_path(app, user_id, system_message_id, file_name, 'web_search_results')
        try:
            file_path = await get_file_path(app, user_id, system_message_id, file_name, 'web_search_results')
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(full_result, ensure_ascii=False, indent=2))
            app.logger.info(f"Saved full content for result {unique_citation_number} to {file_path}")
        except Exception as e:
            app.logger.error(f"Error saving file for result {unique_citation_number}: {str(e)}")


    app.logger.info(f"Completed fetching full content for {len(full_content_results)} results")
    return full_content_results

# Rate limiter: 3 requests per second
rate_limiter = AsyncLimiter(3, 1)

# Utility function that serves both standard and intelligent web search
async def perform_web_search_process(client, model: str, messages: List[Dict[str, str]], user_query: str, user_id: int, system_message_id: int, enable_intelligent_search: bool):
    app.logger.info(f"Starting web search process for query: '{user_query[:50]}'")
    app.logger.info(f"Search type: {'Intelligent' if enable_intelligent_search else 'Standard'}")

    try:
        app.logger.info('Step 1: Understanding user query')
        await send_status_update("Analyzing user query for web search")
        understood_query = await understand_query(client, model, messages, user_query, is_standard_search=not enable_intelligent_search)
        app.logger.info(f'Understood query: {understood_query}')
        await send_status_update("User query analyzed successfully.")

        if enable_intelligent_search:
            app.logger.info('Initiating intelligent web search')
            await send_status_update("Starting intelligent web search")
            results = await intelligent_web_search_process(client, model, messages, understood_query, user_id, system_message_id)
            await send_status_update("Intelligent web search completed.")
            return results
        else:
            app.logger.info('Initiating standard web search')
            await send_status_update("Starting standard web search")
            results = await standard_web_search_process(client, model, understood_query, user_id, system_message_id)
            await send_status_update("Standard web search completed.")
            return results

    except WebSearchError as e:
        app.logger.error(f'Web search process error: {str(e)}')
        await send_status_update("Error occurred during web search process.")
        return [], f"An error occurred during the web search process: {str(e)}"
    except Exception as e:
        app.logger.error(f'Unexpected error in web search process: {str(e)}')
        app.logger.exception("Full traceback:")
        await send_status_update("Unexpected error during web search process.")
        return [], "An unexpected error occurred during the web search process."
    
#### Functions for intelligent web search

async def generate_search_queries(client, model: str, interpretation: str) -> List[str]:
    app.logger.info(f"Starting search query generation based on interpretation: '{interpretation[:50]}'")
    
    system_message = """Generate three diverse search queries based on the given interpretation. 
    Respond with only valid JSON in the format: {"queries": ["query1", "query2", "query3"]}"""

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": interpretation}
    ]

    app.logger.info(f"Sending request to model {model} for search query generation")

    try:
        response, _ = await get_response_from_model(client, model, messages, temperature=0.3)
        app.logger.info(f"Received response from model: '{response[:100]}'")
        
        queries = json.loads(response.strip())["queries"]
        
        app.logger.info("Generated search queries:")
        for i, query in enumerate(queries, 1):
            app.logger.info(f"Query {i}: '{query}'")
        
        return queries
    except json.JSONDecodeError as e:
        app.logger.error(f"Error decoding JSON in generate_search_queries: {str(e)}")
        app.logger.error(f"Raw response: {response}")
        raise WebSearchError(f"Failed to parse generated search queries: {str(e)}")
    except Exception as e:
        app.logger.error(f"Error in generate_search_queries: {str(e)}")
        raise WebSearchError(f"Failed to generate search queries: {str(e)}")

async def intelligent_web_search_process(client, model: str, messages: List[Dict[str, str]], understood_query: str, user_id: int, system_message_id: int):
    app.logger.info(f"Starting intelligent web search for understood query: '{understood_query[:50]}'")

    try:
        # Step 1: Use the understood query to generate search queries
        app.logger.info("Step 1: Generating search queries based on understood query")
        generated_search_queries = await generate_search_queries(client, model, understood_query)
        app.logger.info(f"Generated {len(generated_search_queries)} search queries")

        if not generated_search_queries:
            app.logger.error("Failed to generate search queries")
            raise WebSearchError('Failed to generate search queries')

        # Step 2: Performing multiple web searches
        app.logger.info("Step 2: Performing multiple web searches")
        web_search_results = await perform_multiple_web_searches(generated_search_queries)
        app.logger.info(f"Received {len(web_search_results)} web search results")

        if web_search_results:
            # Step 3: Fetching full content for search results
            app.logger.info("Step 3: Fetching full content for search results")
            full_content_results = await fetch_full_content(web_search_results, app, user_id, system_message_id)
            app.logger.info(f"Fetched full content for {len(full_content_results)} results")

            # Step 4: Summarizing search results
            app.logger.info("Step 4: Summarizing search results")
            summarized_results = await summarize_search_results(client, model, full_content_results, understood_query)
            app.logger.info(f"Generated summary of length: {len(summarized_results)} characters")

            app.logger.info("Intelligent web search completed successfully")
            return generated_search_queries, summarized_results
        else:
            app.logger.warning("No relevant web search results were found")
            return generated_search_queries, "No relevant web search results were found."

    except WebSearchError as e:
        app.logger.error(f"WebSearchError in intelligent web search: {str(e)}")
        raise
    except Exception as e:
        app.logger.error(f"Unexpected error in intelligent web search: {str(e)}")
        app.logger.exception("Full traceback:")
        raise WebSearchError(f"Unexpected error during intelligent web search: {str(e)}")

# Create a rate limiter: 1 request per second
rate_limiter = AsyncLimiter(1, 1)

async def perform_multiple_web_searches(queries: List[str]) -> List[Dict[str, str]]:
    app.logger.info(f"Starting multiple web searches for {len(queries)} queries")
    all_results = []
    urls_seen = set()

    async def process_query(query):
        async with rate_limiter:
            app.logger.info(f"Processing query: '{query[:50]}'")
            try:
                results = await perform_web_search(query)
                app.logger.info(f"Received {len(results)} results for query: '{query[:50]}'")
                new_results_count = 0
                for result in results:
                    url = result.get("url")
                    if url and url not in urls_seen:
                        urls_seen.add(url)
                        all_results.append(result)
                        new_results_count += 1
                app.logger.info(f"Added {new_results_count} new results for query: '{query[:50]}'")
            except WebSearchError as e:
                app.logger.error(f"Error searching for query '{query[:50]}': {str(e)}")

    app.logger.info("Running web searches concurrently")
    # Use asyncio.gather to run searches concurrently while respecting rate limits
    await asyncio.gather(*(process_query(query) for query in queries))

    app.logger.info(f"Multiple web searches completed. Total unique results: {len(all_results)}")
    app.logger.info(f"Unique URLs found: {len(urls_seen)}")

    return all_results


async def summarize_page_content(client, content: str, query: str) -> str:
    app.logger.info("Starting summarize_page_content")
    
    system_message = """Summarize the given content, focusing on information relevant to the query. 
    Be concise but include key points and any relevant code snippets."""

    user_message = f"""Summarize the following content, focusing on information relevant to the query: "{query}"

    Content: {content[:500]}  # Truncated for logging purposes

    Provide a concise summary that captures the main points relevant to the query."""

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]

    try:
        summary, _ = await get_response_from_model(client, "gpt-4o-mini-2024-07-18", messages, temperature=0.3)
        summarized_content = summary.strip()
        app.logger.info(f"Page content summarized. Summary length: {len(summarized_content)} characters")
        return summarized_content
    except Exception as e:
        app.logger.error(f"Error in summarize_page_content: {str(e)}")
        raise WebSearchError(f"Failed to summarize page content: {str(e)}")

async def combine_summaries(client, summaries: List[Dict[str, str]], query: str) -> str:
    app.logger.info(f"Starting combine_summaries for query: '{query}'")
    
    system_message = """Combine the given summaries into a coherent overall summary. 
    Include relevant information from all sources and cite them using numbered footnotes [1], [2], etc. 
    At the end, include a 'Sources:' section with full URLs for each footnote."""

    # Truncate summaries for logging purposes
    truncated_summaries = [
        {
            "index": s["index"],
            "url": s["url"],
            "summary": s["summary"][:100] + "..." if len(s["summary"]) > 100 else s["summary"]
        }
        for s in summaries
    ]

    user_message = f"""Combine the following summaries into a coherent overall summary, focusing on information relevant to the query: "{query}"

    Summaries:
    {json.dumps(truncated_summaries, indent=2)}

    Provide a concise but comprehensive summary that addresses the query, citing sources with footnotes."""

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]

    try:
        app.logger.info(f"Sending request to combine {len(summaries)} summaries")
        final_summary, _ = await get_response_from_model(client, "gpt-4o-mini-2024-07-18", messages, temperature=0.3)
        combined_summary = final_summary.strip()
        app.logger.info(f"Summaries combined. Final summary length: {len(combined_summary)} characters")
        return combined_summary
    except Exception as e:
        app.logger.error(f"Error in combine_summaries: {str(e)}")
        raise WebSearchError(f"Failed to combine summaries: {str(e)}")

async def intelligent_summarize(client, model: str, content: str, query: str, max_tokens: int = 1000) -> str:
    app.logger.info(f"Starting intelligent summarization for query: '{query[:50]}'")
    
    if not content:
        app.logger.warning("No content provided for summarization")
        return "No content available for summarization."
    
    system_message = """You are an advanced AI assistant tasked with intelligently summarizing web content. 
    Your summaries should be informative, relevant to the query, and include key information. 
    If the content contains code, especially for newer libraries, repos, or APIs, include it verbatim in your summary. 
    Adjust the level of detail based on the content's relevance and information density.
    Your summary should be comprehensive yet concise."""

    # Truncate content if it's too long
    max_content_length = 5000  # Adjust this value as needed
    truncated_content = content[:max_content_length]
    if len(content) > max_content_length:
        truncated_content += "... [Content truncated]"

    user_message = f"""Summarize the following content, focusing on information relevant to the query: "{query}"
    
    Content: {truncated_content}
    
    Remember to include any relevant code snippets verbatim, especially if they relate to new technologies or APIs."""

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]

    app.logger.info(f"Sending request to model {model} for intelligent summarization")
    app.logger.debug(f"Content length for summarization: {len(truncated_content)} characters")

    try:
        summary, _ = await get_response_from_model(client, model, messages, temperature=0.3)
        summarized_content = summary.strip()
        app.logger.info(f"Intelligent summarization completed. Summary length: {len(summarized_content)} characters")
        return summarized_content
    except Exception as e:
        app.logger.error(f"Error in intelligent_summarize: {str(e)}")
        raise WebSearchError(f"Failed to generate intelligent summary: {str(e)}")


async def summarize_search_results(client, model: str, results: List[Dict[str, str]], query: str) -> str:
    """
    Summarizes search results with improved error handling and fallback mechanisms.
    
    Args:
        client: The API client
        model: The model to use for summarization
        results: List of search results to summarize
        query: The original search query
        
    Returns:
        str: A coherent summary combining all results with citations
        
    Raises:
        WebSearchError: If summarization fails completely
    """
    app.logger.info(f"Starting summarization of search results for query: '{query[:50]}'")
    app.logger.info(f"Number of results to summarize: {len(results)}")

    if not results:
        app.logger.warning("No results to summarize")
        return "No search results were found to summarize."

    summaries = []
    failed_summaries = []

    # Process each result with retries and fallback
    for index, result in enumerate(results, 1):
        app.logger.info(f"Summarizing result {index}/{len(results)} (URL: {result['url']})")
        
        content = result.get('full_content', '')
        if not content:
            app.logger.warning(f"Empty content for result {index}, skipping...")
            continue

        app.logger.debug(f"Content preview for result {index}: {content[:100]}...")
        
        try:
            # First attempt with primary model
            summary = await intelligent_summarize(client, model, content, query)
            
            if not summary:
                # Fallback to GPT-3.5-turbo for summarization if primary fails
                app.logger.warning(f"Primary model failed for result {index}, attempting fallback...")
                summary = await intelligent_summarize(client, "gpt-3.5-turbo", content, query)

            if summary:
                summaries.append({
                    "index": result['citation_number'],
                    "url": result['url'],
                    "summary": summary
                })
                app.logger.info(f"Successfully summarized result {index}")
            else:
                raise ValueError("Both primary and fallback summarization failed")

        except Exception as e:
            app.logger.error(f"Failed to summarize result {index}: {str(e)}")
            failed_summaries.append({
                "index": result['citation_number'],
                "url": result['url'],
                "error": str(e)
            })

    if not summaries:
        error_msg = "Failed to generate any summaries from the search results."
        app.logger.error(error_msg)
        if failed_summaries:
            error_msg += f" Errors: {json.dumps(failed_summaries, indent=2)}"
        raise WebSearchError(error_msg)

    app.logger.info(f"Successfully summarized {len(summaries)} results. Combining summaries")

    # Prepare the combined summary prompt with improved structure
    combined_summary_prompt = f"""Combine these summaries into a coherent response that answers the query: "{query}"

    Requirements:
Include relevant information from all sources
Use numbered footnotes [1], [2], etc. for citations
Preserve any code snippets exactly as they appear
Include all sources in the final 'Sources:' section
Maintain a clear, logical flow of information
Focus on information relevant to the query
    
    Format the response as:
Main summary with inline citationsCode snippets (if any) with proper formattingSources section with full URLs
    
    Summaries to combine:
    {json.dumps(summaries, indent=2)}"""

    messages = [
        {
            "role": "system", 
            "content": """You are an expert at combining multiple sources into clear, comprehensive summaries.
            Focus on accuracy, clarity, and proper citation of sources. Preserve technical details and code snippets exactly as provided."""
        },
        {"role": "user", "content": combined_summary_prompt}
    ]

    app.logger.info("Attempting to generate final combined summary")

    try:
        # First attempt with primary model
        final_summary, used_model = await get_response_from_model(client, model, messages, temperature=0.3)
        
        if not final_summary and model != "gpt-3.5-turbo":
            # Fallback to GPT-3.5-turbo if primary model fails
            app.logger.warning("Primary model failed for final summary, attempting fallback")
            final_summary, used_model = await get_response_from_model(
                client, "gpt-3.5-turbo", messages, temperature=0.3
            )

        if not final_summary:
            # If both attempts fail, create a basic summary from the individual summaries
            app.logger.warning("Both primary and fallback models failed, creating basic summary")
            basic_summary = "Summary of found information:\n\n"
            for summary in summaries:
                basic_summary += f"[{summary['index']}] {summary['summary']}\n\n"
            basic_summary += "\nSources:\n"
            for summary in summaries:
                basic_summary += f"[{summary['index']}] {summary['url']}\n"
            return basic_summary

        summarized_content = final_summary.strip()
        app.logger.info(f"Final summary generated using {used_model}. Length: {len(summarized_content)} characters")
        
        # Verify all sources are included
        if not all(f"[{s['index']}]" in summarized_content for s in summaries):
            app.logger.warning("Some sources missing from final summary, appending missing sources")
            summarized_content += "\n\nAdditional Sources:\n"
            for summary in summaries:
                if f"[{summary['index']}]" not in summarized_content:
                    summarized_content += f"[{summary['index']}] {summary['url']}\n"

        return summarized_content

    except Exception as e:
        app.logger.error(f"Error in final summary generation: {str(e)}")
        app.logger.exception("Full traceback:")
        
        # Create a basic summary as a last resort
        try:
            basic_summary = "Error occurred during final summary generation. Here are the individual summaries:\n\n"
            for summary in summaries:
                basic_summary += f"[{summary['index']}] {summary['summary']}\n\n"
            basic_summary += "\nSources:\n"
            for summary in summaries:
                basic_summary += f"[{summary['index']}] {summary['url']}\n"
            return basic_summary
        except Exception as fallback_error:
            app.logger.error(f"Failed to create basic summary: {str(fallback_error)}")
            raise WebSearchError("Complete failure in summary generation process")
        
async def generate_single_search_query(client, model: str, messages: List[Dict[str, str]], user_query: str) -> str:
    """
    Generate a single, focused search query based on the conversation history and user query.
    
    Args:
        client: The API client
        model: The model to use for query generation
        messages: List of previous conversation messages
        user_query: The current user query
        
    Returns:
        str: A refined search query
        
    Raises:
        WebSearchError: If query generation fails
    """
    app.logger.info("Starting generate_single_search_query")
    
    system_message = """Generate a single, focused search query based on the conversation history and user query.
    The query should:
Capture the main intent of the user's request
Be specific enough to find relevant information
Be general enough to get comprehensive results
Use key terms from the original query
Be formatted for web search (no special characters or formatting)
    
    Respond with ONLY the search query, no additional text or explanation."""

    # Take the last 5 messages for context, if any
    recent_messages = messages[-5:] if messages else []
    conversation_history = "\n".join([
        f"{msg['role'].capitalize()}: {msg['content']}" 
        for msg in recent_messages
    ])
    
    # Add the current query
    if conversation_history:
        conversation_history += f"\nCurrent Query: {user_query}"
    else:
        conversation_history = f"Query: {user_query}"

    messages_for_model = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": conversation_history}
    ]

    try:
        # First attempt with specified model
        app.logger.info(f"Attempting to generate search query using {model}")
        query, _ = await get_response_from_model(client, model, messages_for_model, temperature=0.3)
        
        if not query:
            # Fallback to GPT-3.5-turbo if primary model fails
            app.logger.warning("Primary model failed, falling back to GPT-3.5-turbo")
            query, _ = await get_response_from_model(
                client, 
                "gpt-3.5-turbo", 
                messages_for_model, 
                temperature=0.3
            )
        
        if not query:
            # If both attempts fail, use the original query
            app.logger.warning("Query generation failed, using original query")
            return user_query.strip()
            
        generated_query = query.strip()
        app.logger.info(f"Generated search query: {generated_query}")
        
        # Validate the generated query
        if len(generated_query) < 3:
            app.logger.warning("Generated query too short, using original query")
            return user_query.strip()
            
        return generated_query
        
    except Exception as e:
        app.logger.error(f"Error in generate_single_search_query: {str(e)}")
        app.logger.exception("Full traceback:")
        
        # Fallback to original query if generation fails
        app.logger.warning("Query generation failed, using original query as fallback")
        return user_query.strip()
    
async def standard_web_search_process(client, model: str, understood_query: str, user_id: int, system_message_id: int):
    app.logger.info(f"Starting standard web search process for understood query: '{understood_query[:50]}'")
    try:
        app.logger.info('Step 2: Generating search query')
        search_query = await generate_single_search_query(client, model, [], understood_query)
        app.logger.info(f'Generated search query: {search_query}')

        app.logger.info('Step 3: Performing web search')
        web_search_results = await perform_web_search(search_query)
        app.logger.info(f'Web search completed. Results count: {len(web_search_results)}')

        if web_search_results:
            app.logger.info('Step 4: Fetching partial content for search results')
            partial_content_results = await fetch_partial_content(web_search_results, app, user_id, system_message_id)
            app.logger.info(f'Partial content fetched for {len(partial_content_results)} results')
            
            app.logger.info('Step 5: Summarizing search results')
            summarized_results = await standard_summarize_search_results(client, model, partial_content_results, understood_query)
            app.logger.info(f'Summarization completed. Summary length: {len(summarized_results)} characters')
        else:
            app.logger.warning('No web search results found.')
            summarized_results = "No relevant web search results were found."

        app.logger.info('Standard web search process completed successfully')
        return [search_query], summarized_results

    except WebSearchError as e:
        app.logger.error(f'Standard web search process error: {str(e)}')
        return None, f"An error occurred during the standard web search process: {str(e)}"
    except Exception as e:
        app.logger.error(f'Unexpected error in standard web search process: {str(e)}')
        app.logger.exception("Full traceback:")
        return None, "An unexpected error occurred during the standard web search process."

async def fetch_partial_content(results: List[Dict[str, str]], app, user_id: int, system_message_id: int) -> List[Dict[str, str]]:
    app.logger.info(f"Starting to fetch partial content for {len(results)} results")

    async def get_partial_page_content(url: str) -> str:
        # Configure connector based on platform
        if platform.system() == 'Windows':
            resolver = CustomResolver(asyncio.get_event_loop())
            connector = aiohttp.TCPConnector(
                use_dns_cache=False,
                limit=10,
                resolver=resolver
            )
        else:
            connector = aiohttp.TCPConnector(
                ttl_dns_cache=300,
                use_dns_cache=True,
                limit=10
            )

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                app.logger.info(f"Fetching partial content from URL: {url}")
                async with session.get(url) as response:
                    app.logger.info(f"Received response from {url}. Status: {response.status}")
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    text_content = soup.get_text(strip=True, separator='\n')
                    partial_content = text_content[:1000]
                    app.logger.info(f"Extracted {len(partial_content)} characters of text from {url}")
                    return partial_content
        except Exception as e:
            app.logger.error(f"Error fetching content for {url}: {str(e)}")
            return ""
        finally:
            if 'connector' in locals():
                await connector.close()

    # Create tasks with proper error handling
    async def safe_get_content(result):
        try:
            content = await get_partial_page_content(result['url'])
            return content
        except Exception as e:
            app.logger.error(f"Error processing URL {result['url']}: {str(e)}")
            return ""

    # Create and gather tasks
    tasks = [asyncio.create_task(safe_get_content(result)) for result in results]
    contents = await asyncio.gather(*tasks, return_exceptions=True)

    partial_content_results = []
    for result, content in zip(results, contents):
        # Handle any exceptions that were returned
        if isinstance(content, Exception):
            app.logger.error(f"Error processing content for {result['url']}: {str(content)}")
            content = ""

        partial_result = {**result, "partial_content": content}
        partial_content_results.append(partial_result)

        try:
            file_name = f"partial_result_{result['citation_number']}.json"
            # Get the file path asynchronously
            file_path = await get_file_path(app, user_id, system_message_id, file_name, 'web_search_results')
            
            # Use aiofiles for async file operations
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(partial_result, ensure_ascii=False, indent=2))
            app.logger.info(f"Saved partial content for result {result['citation_number']} to {file_path}")
        except Exception as e:
            app.logger.error(f"Error saving file for result {result['citation_number']}: {str(e)}")

    app.logger.info(f"Completed fetching partial content for {len(partial_content_results)} results")
    return partial_content_results

async def standard_summarize_search_results(client, model: str, results: List[Dict[str, str]], query: str) -> str:
    app.logger.info(f"Starting standard summarization of search results for query: '{query[:50]}'")
    
    combined_content = "\n\n".join([
        f"Title: {result['title']}\nURL: {result['url']}\nPartial Content: {result['partial_content']}"
        for result in results
    ])

    system_message = """Summarize the given search results, focusing on information relevant to the query. 
    Include key points from each result and cite them using numbered footnotes [1], [2], etc. 
    At the end, include a 'Sources:' section with full URLs for each footnote."""

    user_message = f"""Summarize the following search results, focusing on information relevant to the query: "{query}"

    Search Results:
    {combined_content}

    Provide a concise but comprehensive summary that addresses the query, citing sources with footnotes."""

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]

    try:
        summary, _ = await get_response_from_model(client, model, messages, temperature=0.3)
        summarized_content = summary.strip()
        app.logger.info(f"Search results summarized. Summary length: {len(summarized_content)} characters")
        return summarized_content
    except Exception as e:
        app.logger.error(f"Error in standard_summarize_search_results: {str(e)}")
        raise WebSearchError(f"Failed to summarize search results: {str(e)}")


# End of web search


# Routes to handle files and file uploads

@app.route('/query_documents', methods=['POST'])
@login_required
def query_documents():
    query = request.json.get('query')
    file_processor = FileProcessor(embedding_store, app)
    results = file_processor.query_index(query)
    return jsonify({'results': results})

from flask import make_response, send_file, abort

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/view_original_file/<file_id>')
@login_required
async def view_original_file(file_id):
    try:
        async with get_session() as session:
            result = await session.execute(
                select(UploadedFile).filter_by(id=file_id)
            )
            file = result.scalar_one_or_none()
            
            if not file:
                return Response(
                    json.dumps({'error': 'File not found'}),
                    status=404,
                    mimetype='application/json'
                )
            
            if file.user_id != current_user.id:
                return Response(
                    json.dumps({'error': 'Unauthorized'}),
                    status=403,
                    mimetype='application/json'
                )
            
            if not os.path.exists(file.file_path):
                return Response(
                    json.dumps({'error': 'File not found on disk'}),
                    status=404,
                    mimetype='application/json'
                )

            try:
                html_content = f'''
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>{file.original_filename}</title>
                    <style>
                        html, body {{
                            margin: 0;
                            padding: 0;
                            height: 100%;
                            overflow: hidden;
                        }}
                        #file-embed {{
                            width: 100%;
                            height: 100%;
                            border: none;
                        }}
                    </style>
                </head>
                <body>
                    <embed id="file-embed" src="/serve_file/{file_id}" type="{file.mime_type}">
                    <script>
                        function resizeEmbed() {{
                            var embed = document.getElementById('file-embed');
                            embed.style.height = window.innerHeight + 'px';
                        }}
                        window.onload = resizeEmbed;
                        window.onresize = resizeEmbed;
                    </script>
                </body>
                </html>
                '''
                
                return Response(
                    html_content,
                    mimetype='text/html'
                )

            except Exception as render_error:
                app.logger.error(f"Error rendering template: {str(render_error)}")
                app.logger.exception("Full traceback:")
                return Response(
                    json.dumps({'error': 'Error rendering file view'}),
                    status=500,
                    mimetype='application/json'
                )

    except Exception as e:
        app.logger.error(f"Error in view_original_file: {str(e)}")
        app.logger.exception("Full traceback:")
        return Response(
            json.dumps({'error': 'Internal server error'}),
            status=500,
            mimetype='application/json'
        )


@app.route('/serve_file/<file_id>')
@login_required
async def serve_file(file_id):
    try:
        async with get_session() as session:
            result = await session.execute(
                select(UploadedFile).filter_by(id=file_id)
            )
            file = result.scalar_one_or_none()
            
            if not file:
                return Response(
                    json.dumps({'error': 'File not found'}),
                    status=404,
                    mimetype='application/json'
                )
            
            if file.user_id != current_user.id:
                return Response(
                    json.dumps({'error': 'Unauthorized'}),
                    status=403,
                    mimetype='application/json'
                )
            
            if not os.path.exists(file.file_path):
                return Response(
                    json.dumps({'error': 'File not found on disk'}),
                    status=404,
                    mimetype='application/json'
                )

            try:
                # Create response using Quart's Response class
                with open(file.file_path, 'rb') as f:
                    data = f.read()
                
                response = Response(
                    data,
                    mimetype=file.mime_type
                )
                
                # Add headers
                response.headers['Content-Disposition'] = f'inline; filename="{file.original_filename}"'
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                
                return response

            except Exception as file_error:
                app.logger.error(f"Error serving file: {str(file_error)}")
                app.logger.exception("Full traceback:")
                return Response(
                    json.dumps({'error': 'Error serving file'}),
                    status=500,
                    mimetype='application/json'
                )

    except Exception as e:
        app.logger.error(f"Error in serve_file: {str(e)}")
        app.logger.exception("Full traceback:")
        return Response(
            json.dumps({'error': 'Internal server error'}),
            status=500,
            mimetype='application/json'
        )


@app.route('/view_processed_text/<file_id>')
@login_required
async def view_processed_text(file_id):
    try:
        async with get_session() as session:
            # Get the file record
            result = await session.execute(
                select(UploadedFile).filter_by(id=file_id)
            )
            file = result.scalar_one_or_none()
            
            if not file:
                return Response(
                    json.dumps({'error': 'File not found'}),
                    status=404,
                    mimetype='application/json'
                )
            
            # Check authorization
            if file.user_id != current_user.id:
                return Response(
                    json.dumps({'error': 'Unauthorized'}),
                    status=403,
                    mimetype='application/json'
                )
            
            if not file.processed_text_path or not os.path.exists(file.processed_text_path):
                app.logger.error(f"Processed text not found for file ID: {file_id}")
                return Response(
                    json.dumps({'error': 'Processed text not available'}),
                    status=404,
                    mimetype='application/json'
                )

            try:
                # Read the processed text file
                async with aiofiles.open(file.processed_text_path, 'r', encoding='utf-8') as f:
                    content = await f.read()

                # Create a response with the text content
                response = Response(
                    content,
                    mimetype='text/plain'
                )
                
                # Add headers
                processed_filename = f"{file.original_filename}_processed.txt"
                response.headers['Content-Disposition'] = f'inline; filename="{processed_filename}"'
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                
                return response

            except Exception as e:
                app.logger.error(f"Error reading processed text file: {str(e)}")
                app.logger.exception("Full traceback:")
                return Response(
                    json.dumps({'error': 'Error reading processed text file'}),
                    status=500,
                    mimetype='application/json'
                )

    except Exception as e:
        app.logger.error(f"Error in view_processed_text: {str(e)}")
        app.logger.exception("Full traceback:")
        return Response(
            json.dumps({'error': 'Internal server error'}),
            status=500,
            mimetype='application/json'
        )

# File handling routes

@app.route('/debug/check-directories')
@login_required
async def check_directories():
    base_dir = Path(app.config['BASE_UPLOAD_FOLDER'])
    
    def scan_directory(path):
        try:
            return {
                'path': str(path),
                'exists': path.exists(),
                'is_dir': path.is_dir() if path.exists() else False,
                'contents': [str(p) for p in path.glob('**/*')] if path.exists() and path.is_dir() else [],
                'permissions': oct(os.stat(path).st_mode)[-3:] if path.exists() else None
            }
        except Exception as e:
            return {'path': str(path), 'error': str(e)}

    directories = {
        'base_upload_folder': scan_directory(base_dir),
        'current_user_folder': scan_directory(base_dir / str(current_user.id)),
    }
    
    return jsonify(directories)

@app.route('/upload_file', methods=['POST'])
@login_required
async def upload_file():
    files = await request.files
    if 'file' not in files:
        return jsonify({'success': False, 'error': 'No file part'})
    
    file = files['file']
    form = await request.form
    
    try:
        system_message_id = int(form.get('system_message_id'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Invalid system message ID'}), 400
    
    app.logger.info(f"Received file upload request: {file.filename}, system_message_id: {system_message_id}")
    
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'})
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        try:
            # Get file path using FileUtils
            file_path = await app.file_utils.get_file_path(
                current_user.id,
                system_message_id,
                filename,
                'uploads'
            )
            
            # Ensure the directory exists
            await app.file_utils.ensure_folder_exists(file_path.parent)
            
            # Save the file
            app.logger.info(f"Attempting to save file to: {file_path}")
            await file.save(str(file_path))
            app.logger.info(f"File saved successfully to: {file_path}")
            
            async with get_session() as session:
                # Get file size asynchronously
                file_size = await async_get_file_size(str(file_path))
                
                # Create timezone-naive datetime for database
                current_time = datetime.now(timezone.utc).replace(tzinfo=None)
                
                # Create a new UploadedFile record
                new_file = UploadedFile(
                    id=str(uuid.uuid4()),
                    user_id=current_user.id,
                    original_filename=filename,
                    file_path=str(file_path),
                    system_message_id=system_message_id,
                    file_size=file_size,
                    mime_type=file.content_type,
                    upload_timestamp=current_time
                )
                
                session.add(new_file)
                await session.commit()
                await session.refresh(new_file)
                
                app.logger.info(f"New file record created with ID: {new_file.id}")
                
                # Get the storage context for this system message
                storage_context = await embedding_store.get_storage_context(system_message_id)
                
                # Process and index the file
                processed_text_path = await file_processor.process_file(
                    str(file_path),
                    storage_context,
                    new_file.id,
                    current_user.id,
                    system_message_id
                )
                
                app.logger.info(f"Processed text path returned: {processed_text_path}")
                
                # Update the processed_text_path
                if processed_text_path:
                    new_file.processed_text_path = str(processed_text_path)
                    await session.commit()
                    app.logger.info(f"File {filename} processed successfully. Processed text path: {processed_text_path}")
                else:
                    app.logger.warning(f"File {filename} processed, but no processed text path was returned.")
                
                return jsonify({
                    'success': True,
                    'message': 'File uploaded and indexed successfully',
                    'file_id': new_file.id
                })
                
        except Exception as e:
            app.logger.error(f"Error processing file: {str(e)}")
            # Try to clean up the file if something went wrong
            try:
                if await async_file_exists(str(file_path)):
                    await aio_os.remove(str(file_path))
                    app.logger.info(f"Cleaned up file after error: {file_path}")
            except Exception as cleanup_error:
                app.logger.error(f"Error during cleanup: {str(cleanup_error)}")
            
            return jsonify({
                'success': False,
                'error': f'Error processing file: {str(e)}'
            }), 500
    
    app.logger.error(f"File type not allowed: {file.filename}")
    return jsonify({'success': False, 'error': 'File type not allowed'}), 400

# Helper functions for async file operations
async def async_file_exists(file_path: str) -> bool:
    """Async wrapper for checking if a file exists."""
    try:
        await aio_os.stat(file_path)
        return True
    except (OSError, FileNotFoundError):
        return False

async def async_get_file_size(file_path: str) -> int:
    """Async wrapper for getting file size."""
    stat = await aio_os.stat(file_path)
    return stat.st_size

@app.route('/get_files/<int:system_message_id>')
@login_required
async def get_files(system_message_id):
    try:
        async with get_session() as session:
            result = await session.execute(
                select(UploadedFile).filter_by(system_message_id=system_message_id)
            )
            files = result.scalars().all()
            
            file_list = [{
                'id': file.id,
                'name': file.original_filename,
                'path': file.file_path,
                'size': file.file_size,
                'type': file.mime_type,
                'upload_date': file.upload_timestamp.isoformat() if file.upload_timestamp else None
            } for file in files]
            
            return jsonify(file_list)
    except Exception as e:
        app.logger.error(f"Error fetching files: {str(e)}")
        return jsonify({'error': 'Error fetching files'}), 500
    
@app.route('/remove_file/<file_id>', methods=['DELETE'])
@login_required
async def remove_file(file_id):
    """
    Delete a file and all its associated resources (vectors, processed text, etc.).
    
    Args:
        file_id (str): The ID of the file to delete
        
    Returns:
        JSON response indicating success or failure
    """
    app.logger.info(f"Starting file removal process for file ID: {file_id}")
    
    async with get_session() as session:
        try:
            # Fetch the file record
            result = await session.execute(
                select(UploadedFile).filter_by(id=file_id)
            )
            file = result.scalar_one_or_none()
            
            if not file:
                app.logger.warning(f"File not found: {file_id}")
                return jsonify({'success': False, 'error': 'File not found'}), 404
            
            # Check authorization
            if file.user_id != current_user.id:
                app.logger.warning(f"Unauthorized access attempt for file {file_id} by user {current_user.id}")
                return jsonify({'success': False, 'error': 'Unauthorized'}), 403

            deletion_results = {
                'vectors_deleted': False,
                'original_file_deleted': False,
                'processed_file_deleted': False,
                'database_entry_deleted': False
            }

            try:
                # Delete vectors from Pinecone
                system_message_id = file.system_message_id
                storage_context = await embedding_store.get_storage_context(system_message_id)
                namespace = embedding_store.generate_namespace(system_message_id)
                
                if storage_context and storage_context.vector_store:
                    try:
                        deleted = await delete_vectors_for_file(
                            storage_context.vector_store, 
                            file_id, 
                            namespace
                        )
                        deletion_results['vectors_deleted'] = deleted
                        app.logger.info(f"Vector deletion {'successful' if deleted else 'not needed'} for file {file_id}")
                    except Exception as vector_error:
                        app.logger.error(f"Error deleting vectors: {str(vector_error)}")
                        # Continue with file deletion even if vector deletion fails
                
                # Remove original file
                if await async_file_exists(file.file_path):
                    try:
                        await aio_os.remove(file.file_path)
                        deletion_results['original_file_deleted'] = True
                        app.logger.info(f"Original file removed: {file.file_path}")
                    except Exception as file_error:
                        app.logger.error(f"Error deleting original file: {str(file_error)}")
                else:
                    app.logger.warning(f"Original file not found: {file.file_path}")
                
                # Remove processed text file if it exists
                if file.processed_text_path and await async_file_exists(file.processed_text_path):
                    try:
                        await aio_os.remove(file.processed_text_path)
                        deletion_results['processed_file_deleted'] = True
                        app.logger.info(f"Processed text file removed: {file.processed_text_path}")
                    except Exception as processed_error:
                        app.logger.error(f"Error deleting processed file: {str(processed_error)}")
                
                # Remove database entry
                try:
                    await session.delete(file)
                    await session.commit()
                    deletion_results['database_entry_deleted'] = True
                    app.logger.info(f"Database entry deleted for file {file_id}")
                except Exception as db_error:
                    app.logger.error(f"Error deleting database entry: {str(db_error)}")
                    await session.rollback()
                    raise
                
                # Prepare detailed response
                success_message = "File and associated resources removed successfully"
                if not all(deletion_results.values()):
                    success_message = "File partially removed with some errors"
                
                response_data = {
                    'success': True,
                    'message': success_message,
                    'details': deletion_results
                }
                
                app.logger.info(f"File removal completed for {file_id}: {deletion_results}")
                return jsonify(response_data)
                
            except Exception as e:
                app.logger.error(f"Error during file removal process for {file_id}: {str(e)}")
                app.logger.exception("Full traceback:")
                
                # Try to clean up any remaining files if database deletion failed
                if not deletion_results['database_entry_deleted']:
                    try:
                        await session.rollback()
                    except Exception as rollback_error:
                        app.logger.error(f"Error during session rollback: {str(rollback_error)}")
                
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'partial_deletion_results': deletion_results
                }), 500
                
        except Exception as outer_error:
            app.logger.error(f"Unexpected error in remove_file: {str(outer_error)}")
            app.logger.exception("Full traceback:")
            return jsonify({
                'success': False,
                'error': 'An unexpected error occurred during file removal'
            }), 500
    
async def delete_vectors_for_file(vector_store, file_id: str, namespace: str) -> bool:
    """
    Delete vectors associated with a specific file from the vector store.
    
    Args:
        vector_store: The vector store instance
        file_id (str): The ID of the file whose vectors should be deleted
        namespace (str): The namespace in which to search for vectors
        
    Returns:
        bool: True if vectors were deleted successfully, False otherwise
        
    Raises:
        ValueError: If vector_store or file_id is invalid
    """
    if not vector_store or not hasattr(vector_store, '_pinecone_index'):
        raise ValueError("Invalid vector store provided")
    
    if not file_id:
        raise ValueError("file_id cannot be empty")

    try:
        # Get the Pinecone index from the vector store
        pinecone_index = vector_store._pinecone_index
        app.logger.debug(f"Attempting to delete vectors for file ID {file_id} in namespace {namespace}")

        # Query for vectors related to this file
        try:
            query_response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: pinecone_index.query(
                    namespace=namespace,
                    vector=[0] * 1536,  # Dummy vector of zeros
                    top_k=10000,
                    include_metadata=True
                )
            )
        except Exception as query_error:
            app.logger.error(f"Error querying vectors: {str(query_error)}")
            raise

        # Filter the results to only include vectors with matching file_id
        vector_ids = [
            match.id for match in query_response.matches 
            if match.metadata.get('file_id') == str(file_id)
        ]

        if vector_ids:
            try:
                # Delete the vectors
                delete_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: pinecone_index.delete(
                        ids=vector_ids,
                        namespace=namespace
                    )
                )
                app.logger.info(
                    f"Successfully deleted {len(vector_ids)} vectors for file ID: {file_id}. "
                    f"Delete response: {delete_response}"
                )
                return True
            except Exception as delete_error:
                app.logger.error(f"Error deleting vectors: {str(delete_error)}")
                raise
        else:
            app.logger.warning(f"No vectors found for file ID: {file_id} in namespace: {namespace}")
            return False

    except Exception as e:
        app.logger.error(
            f"Error in delete_vectors_for_file for file ID {file_id}: {str(e)}\n"
            f"Namespace: {namespace}"
        )
        raise

@app.route('/health')
def health_check():
    return 'OK', 200

@app.route('/get-website/<int:website_id>', methods=['GET'])
@login_required
async def get_website(website_id):
    app.logger.debug(f"Attempting to fetch website with ID: {website_id}")
    
    try:
        async with get_session() as session:
            result = await session.execute(
                select(Website).filter_by(id=website_id)
            )
            website = result.scalar_one_or_none()
            
            if not website:
                app.logger.warning(f"No website found with ID: {website_id}")
                return jsonify({'error': 'Website not found'}), 404
                
            app.logger.debug(f"Website data: {website.to_dict()}")
            return jsonify({'website': website.to_dict()}), 200
    except Exception as e:
        app.logger.error(f"Exception occurred: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/test-website', methods=['GET'])
@login_required
def test_website():
    return jsonify({'message': 'Route is working'}), 200

@app.route('/index-website', methods=['POST'])
@login_required
def index_website():
    data = request.get_json()
    app.logger.debug(f"Received indexing request with data: {data}")
    url = data.get('url')
    if not url:
        app.logger.error("URL is missing from request data")
        return jsonify({'success': False, 'message': 'URL is required'}), 400

    allowed_domain = data.get('allowed_domain', '')
    custom_settings = data.get('custom_settings', {})

    # Run Scrapy spider
    process = subprocess.Popen(
        ['scrapy', 'runspider', 'webscraper/spiders/flexible_spider.py',
         '-a', f'url={url}', '-a', f'allowed_domain={allowed_domain}',
         '-a', f'custom_settings={json.dumps(custom_settings)}'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()

    stdout_decoded = stdout.decode('utf-8', errors='replace')
    stderr_decoded = stderr.decode('utf-8', errors='replace')
    app.logger.debug("STDOUT: %s", stdout_decoded)
    app.logger.debug("STDERR: %s", stderr_decoded)

    if process.returncode != 0:
        app.logger.error("Scraping failed with error: %s", stderr_decoded)
        return jsonify({'success': False, 'message': 'Error during scraping', 'error': stderr_decoded}), 500

    if stdout_decoded:
        try:
            scraped_content = json.loads(stdout_decoded)
            if 'content' in scraped_content:
                return jsonify({'success': True, 'message': 'Website indexed successfully', 'content': scraped_content['content']}), 200
            else:
                app.logger.error("Expected key 'content' not found in JSON output")
                return jsonify({'success': False, 'message': 'Expected data not found in the scraped output'}), 500
        except json.JSONDecodeError as e:
            app.logger.error("Error decoding JSON from scraping output: %s", str(e))
            return jsonify({'success': False, 'message': 'Invalid JSON data received', 'details': stdout_decoded}), 500
    else:
        app.logger.error("No data received from spider")
        return jsonify({'success': False, 'message': 'No data received from spider'}), 500

@app.route('/scrape', methods=['POST'])
@login_required
def scrape():
    data = request.get_json()
    url = data.get('url')
    allowed_domain = data.get('allowed_domain', '')

    command = [
        'scrapy', 'runspider', 'webscraper/spiders/flexible_spider.py',
        '-a', f'url={url}', '-a', f'allowed_domain={allowed_domain}'
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        app.logger.error(f"Spider error: {stderr.decode()}")
        return jsonify({'error': 'Failed to scrape the website'}), 500

    try:
        result = json.loads(stdout.decode())
        return jsonify({'data': result['content']}), 200
    except json.JSONDecodeError:
        app.logger.error("Failed to decode JSON from spider output")
        return jsonify({'error': 'Failed to decode JSON from spider output'}), 500

@app.route('/get-websites/<int:system_message_id>', methods=['GET'])
@login_required
async def get_websites(system_message_id):
    async with get_session() as session:
        result = await session.execute(
            select(Website).filter_by(system_message_id=system_message_id)
        )
        websites = result.scalars().all()
        return jsonify({'websites': [website.to_dict() for website in websites]}), 200

@app.route('/add-website', methods=['POST'])
@login_required
async def add_website():
    data = await request.get_json()
    url = data.get('url')
    system_message_id = data.get('system_message_id')

    if not url:
        return jsonify({'success': False, 'message': 'URL is required'}), 400

    if not system_message_id:
        return jsonify({'success': False, 'message': 'System message ID is required'}), 400

    if not url.startswith('http://') and not url.startswith('https://'):
        return jsonify({'success': False, 'message': 'Invalid URL format'}), 400

    async with get_session() as session:
        # Verify system message exists
        system_message_result = await session.execute(
            select(SystemMessage).filter_by(id=system_message_id)
        )
        if not system_message_result.scalar_one_or_none():
            return jsonify({'success': False, 'message': 'System message not found'}), 404

        new_website = Website(
            url=url,
            system_message_id=system_message_id,
            indexing_status='pending'
        )
        session.add(new_website)
        await session.commit()
        await session.refresh(new_website)

        return jsonify({
            'success': True,
            'message': 'Website added successfully',
            'website': new_website.to_dict()
        }), 201


@app.route('/remove-website/<int:website_id>', methods=['DELETE'])
@login_required
async def remove_website(website_id):
    async with get_session() as session:
        result = await session.execute(
            select(Website).filter_by(id=website_id)
        )
        website = result.scalar_one_or_none()
        
        if not website:
            return jsonify({'success': False, 'message': 'Website not found'}), 404
            
        await session.delete(website)
        await session.commit()
        return jsonify({'success': True, 'message': 'Website removed successfully'}), 200

@app.route('/reindex-website/<int:website_id>', methods=['POST'])
@login_required
async def reindex_website(website_id):
    async with get_session() as session:
        result = await session.execute(
            select(Website).filter_by(id=website_id)
        )
        website = result.scalar_one_or_none()
        
        if not website:
            return jsonify({'error': 'Website not found'}), 404
            
        website.indexed_at = datetime.now(timezone.utc)
        website.indexing_status = 'In Progress'
        await session.commit()
        await session.refresh(website)

        return jsonify({
            'message': 'Re-indexing initiated',
            'website': website.to_dict()
        }), 200

@app.route('/generate-image', methods=['POST'])
@login_required
def generate_image():
    data = request.json
    prompt = data.get('prompt', '')

    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400

    try:
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="256x256"
        )
        image_url = response['data'][0]['url']
        return jsonify({"image_url": image_url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/view-logs')
@login_required
def view_logs():
    logs_content = "<link rel='stylesheet' type='text/css' href='/static/css/styles.css'><div class='logs-container'>"
    try:
        with open('app.log', 'r') as log_file:
            logs_content += f"<div class='log-entry'><div class='log-title'>--- app.log ---</div><pre>"
            logs_content += log_file.read() + "</pre></div>\n"
    except FileNotFoundError:
        logs_content += "<div class='log-entry'><div class='log-title'>No log file found.</div></div>"
    logs_content += "</div>"
    return logs_content


# Configure basic auth settings
app.config["QUART_AUTH_COOKIE_SECURE"] = False if app.debug else True
app.config["QUART_AUTH_COOKIE_DOMAIN"] = None  # Set to your domain in production
app.config["QUART_AUTH_COOKIE_NAME"] = "auth_token"
app.config["QUART_AUTH_COOKIE_PATH"] = "/"
app.config["QUART_AUTH_COOKIE_SAMESITE"] = "Lax"
app.config["QUART_AUTH_DURATION"] = timedelta(days=30)  # Set session duration

# Configure authentication using your API key
genai.configure(api_key=os.environ['GOOGLE_API_KEY'])

anthropic.api_key = os.environ.get('ANTHROPIC_API_KEY')
if anthropic.api_key is None:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set")


@app.route('/api/system-messages/<int:system_message_id>/add-website', methods=['POST'])
@login_required
async def add_website_to_system_message(system_message_id):
    data = await request.get_json()
    website_url = data.get('websiteURL')
    
    async with get_session() as session:
        result = await session.execute(
            select(SystemMessage).filter_by(id=system_message_id)
        )
        system_message = result.scalar_one_or_none()
        
        if not system_message:
            return jsonify({'error': 'System message not found'}), 404
            
        if not system_message.source_config:
            system_message.source_config = {'websites': []}
        
        system_message.source_config['websites'].append(website_url)
        await session.commit()
        
        return jsonify({
            'message': 'Website URL added successfully',
            'source_config': system_message.source_config
        }), 200

# Default System Message configuration
DEFAULT_SYSTEM_MESSAGE = {
    "name": "Default System Message",
    "content": "You are a knowledgeable assistant that specializes in critical thinking and analysis.",
    "description": "Default entry for database",
    "model_name": "gpt-3.5-turbo",
    "temperature": 0.3
}

@app.route('/get-current-model', methods=['GET'])
@login_required
async def get_current_model():
    async with get_session() as session:
        result = await session.execute(
            select(SystemMessage).filter_by(name=DEFAULT_SYSTEM_MESSAGE["name"])
        )
        default_message = result.scalar_one_or_none()
        
        if default_message:
            return jsonify({'model_name': default_message.model_name})
        else:
            return jsonify({'error': 'Default system message not found'}), 404

@app.route('/system-messages', methods=['POST'])
@login_required
async def create_system_message():
    try:
        if not await current_user.check_admin():
            return jsonify({'error': 'Unauthorized'}), 401

        data = await request.get_json()
        
        async with get_session() as session:
            # Create naive datetime from UTC time
            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
            
            new_system_message = SystemMessage(
                name=data['name'],
                content=data['content'],
                description=data.get('description', ''),
                model_name=data.get('model_name', ''),
                temperature=data.get('temperature', 0.7),
                created_by=current_user.id,
                created_at=current_time,  # Use naive datetime
                updated_at=current_time,  # Use naive datetime
                enable_web_search=data.get('enable_web_search', False)
            )
            
            session.add(new_system_message)
            try:
                await session.commit()
                await session.refresh(new_system_message)
                return jsonify(new_system_message.to_dict()), 201
            except Exception as db_error:
                await session.rollback()
                app.logger.error(f"Database error creating system message: {str(db_error)}")
                raise

    except Exception as e:
        app.logger.error(f"Error in create_system_message: {str(e)}")
        app.logger.exception("Full traceback:")
        return jsonify({'error': str(e)}), 500

@app.route('/api/system_messages', methods=['GET'])
@login_required
async def get_system_messages():
    try:
        app.logger.info("Fetching system messages")
        async with get_session() as session:
            result = await session.execute(select(SystemMessage))
            system_messages = result.scalars().all()
            
            # Add debug logging
            app.logger.debug(f"Found {len(list(system_messages))} system messages")
            
            messages_list = [{
                'id': message.id,
                'name': message.name,
                'content': message.content,
                'description': message.description,
                'model_name': message.model_name,
                'temperature': message.temperature,
                'enable_web_search': message.enable_web_search
            } for message in system_messages]
            
            app.logger.info(f"Returning {len(messages_list)} system messages")
            return jsonify(messages_list)
    except Exception as e:
        app.logger.error(f"Error in get_system_messages: {str(e)}")
        app.logger.exception("Full traceback:")
        return jsonify({'error': str(e)}), 500



@app.route('/system-messages/<int:message_id>', methods=['PUT'])
@login_required
async def update_system_message(message_id):
    try:
        # Check admin status asynchronously
        is_admin = await current_user.check_admin()
        if not is_admin:
            return jsonify({'error': 'Unauthorized'}), 401

        async with get_session() as session:
            result = await session.execute(
                select(SystemMessage).filter_by(id=message_id)
            )
            system_message = result.scalar_one_or_none()
            
            if not system_message:
                return jsonify({'error': 'System message not found'}), 404

            data = await request.get_json()
            
            # Update fields
            system_message.name = data.get('name', system_message.name)
            system_message.content = data.get('content', system_message.content)
            system_message.description = data.get('description', system_message.description)
            system_message.model_name = data.get('model_name', system_message.model_name)
            system_message.temperature = data.get('temperature', system_message.temperature)
            system_message.enable_web_search = data.get('enable_web_search', system_message.enable_web_search)
            system_message.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

            try:
                await session.commit()
                app.logger.info(f"System message {message_id} updated successfully")
                return jsonify(system_message.to_dict())
            except Exception as db_error:
                await session.rollback()
                app.logger.error(f"Database error while updating system message: {str(db_error)}")
                raise

    except Exception as e:
        app.logger.error(f"Error updating system message: {str(e)}")
        app.logger.exception("Full traceback:")
        return jsonify({'error': str(e)}), 500

@app.route('/system-messages/<int:message_id>', methods=['DELETE'])
@login_required
async def delete_system_message(message_id):
    if not await current_user.check_admin():
        return jsonify({'error': 'Unauthorized'}), 401

    async with get_session() as session:
        result = await session.execute(
            select(SystemMessage).filter_by(id=message_id)
        )
        system_message = result.scalar_one_or_none()
        
        if not system_message:
            return jsonify({'error': 'System message not found'}), 404

        await session.delete(system_message)
        await session.commit()
        return jsonify({'message': 'System message deleted successfully'})


@app.route('/trigger-flash')
def trigger_flash():
    flash("You do not have user admin privileges.", "warning")  # Adjust the message and category as needed
    return redirect(url_for('the_current_page'))  # Replace with the appropriate endpoint

async def get_conversation_by_id(conversation_id):
    async with get_session() as session:
        result = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            # mimic "get_or_404"
            abort(404, description="Conversation not found")
        return conversation
    
@app.route('/chat/<int:conversation_id>')
@login_required
async def chat_interface(conversation_id):
    conversation = await get_conversation_by_id(conversation_id)
    return await render_template('chat.html', conversation=conversation)


# Fetch all conversations from the database and convert them to a list of dictionaries
async def get_conversations_from_db():
    async with get_session() as session:
        result = await session.execute(select(Conversation))
        conversations = result.scalars().all()
        return [c.to_dict() for c in conversations]

@app.route('/database')
def database():
    try:
        conversations = get_conversations_from_db()
        conversations_json = json.dumps(conversations, indent=4) # Convert to JSON and pretty-print
        return render_template('database.html', conversations_json=conversations_json)
    except Exception as e:
        print(e)  # For debugging purposes
        return "Error fetching data from the database", 500

@app.cli.command("clear-db")
def clear_db():
    """
    Flask CLI command to clear and reinitialize the database.
    Usage: flask clear-db
    
    WARNING: This will delete all data in the database!
    Only available in development and testing environments.
    """
    import asyncio
    
    # Safety check for production environment
    if app.config.get('ENV') == 'production':
        print("ERROR: This command cannot be run in production!")
        return
    
    async def _clear_db():
        try:
            print(f"Using database URL: {engine.url}")
            
            # Drop all tables
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                print("All tables dropped successfully")
                
                # Recreate all tables
                await conn.run_sync(Base.metadata.create_all)
                print("All tables recreated successfully")
            
            # Reinitialize the database with default data
            await init_db()
            print("Database reinitialized with default data")
            
        except Exception as e:
            print(f"Error clearing database: {str(e)}")
            raise

    print("WARNING: This will delete all data in the database!")
    print(f"Environment: {app.config.get('ENV', 'development')}")
    print(f"Debug mode: {app.debug}")
    
    confirmation = input("Are you sure you want to continue? (y/N): ")
    
    if confirmation.lower() == 'y':
        second_confirmation = input("Type 'CONFIRM' to proceed with database reset: ")
        if second_confirmation == 'CONFIRM':
            with app.app_context():
                asyncio.run(_clear_db())
                print("Database cleared and reinitialized successfully.")
        else:
            print("Database clear operation cancelled.")
    else:
        print("Database clear operation cancelled.")

@app.route('/folders', methods=['GET'])
@login_required
async def get_folders():
    async with get_session() as session:
        result = await session.execute(select(Folder))
        folders = result.scalars().all()
        return jsonify([folder.title for folder in folders])

@app.route('/folders', methods=['POST'])
@login_required
async def create_folder():
    data = await request.get_json()
    title = data.get('title')
    
    async with get_session() as session:
        new_folder = Folder(title=title)
        session.add(new_folder)
        await session.commit()
        return jsonify({"message": "Folder created successfully"}), 201

@app.route('/folders/<int:folder_id>/conversations', methods=['GET'])
@login_required
async def get_folder_conversations(folder_id):
    async with get_session() as session:
        result = await session.execute(
            select(Conversation).filter_by(folder_id=folder_id)
        )
        conversations = result.scalars().all()
        return jsonify([conversation.title for conversation in conversations])

@app.route('/folders/<int:folder_id>/conversations', methods=['POST'])
@login_required
async def create_conversation_in_folder(folder_id):
    data = await request.get_json()
    title = data.get('title')
    
    async with get_session() as session:
        # First check if folder exists
        folder_result = await session.execute(
            select(Folder).filter_by(id=folder_id)
        )
        folder = folder_result.scalar_one_or_none()
        
        if not folder:
            return jsonify({"error": "Folder not found"}), 404
            
        new_conversation = Conversation(
            title=title,
            folder_id=folder_id,
            user_id=current_user.id
        )
        session.add(new_conversation)
        await session.commit()
        return jsonify({"message": "Conversation created successfully"}), 201

# Fetch all conversations from the database for listing in the left sidebar
@app.route('/api/conversations', methods=['GET'])
@login_required
async def get_conversations():
    try:
        # Get pagination parameters from request
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        async with get_session() as session:
            # Get total count using a subquery
            count_query = select(func.count()).select_from(
                select(Conversation).filter_by(user_id=current_user.id).subquery()
            )
            count_result = await session.execute(count_query)
            total_count = count_result.scalar()
            
            # Build paginated query
            query = (
                select(Conversation)
                .filter_by(user_id=current_user.id)
                .order_by(Conversation.updated_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
            
            # Execute the query
            result = await session.execute(query)
            conversations = result.scalars().all()
            
            # Convert to list of dictionaries
            conversations_dict = [{
                "id": c.id, 
                "title": c.title,
                "model_name": c.model_name,
                "token_count": c.token_count,
                "updated_at": c.updated_at,
                "temperature": c.temperature
            } for c in conversations]
            
            return jsonify({
                "conversations": conversations_dict,
                "total": total_count,
                "page": page,
                "per_page": per_page,
                "total_pages": math.ceil(total_count / per_page)
            })
            
    except Exception as e:
        app.logger.error(f"Error fetching conversations: {str(e)}")
        app.logger.exception("Full traceback:")
        return jsonify({'error': 'Error fetching conversations'}), 500

# Fetch a specific conversation from the database to display in the chat interface
@app.route('/conversations/<int:conversation_id>', methods=['GET'])
@login_required
async def get_conversation(conversation_id):
    async with get_session() as session:
        # Build and execute query
        result = await session.execute(
            select(Conversation).filter_by(id=conversation_id)
        )
        conversation = result.scalar_one_or_none()
        
        if conversation is None:
            return jsonify({'error': 'Conversation not found'}), 404

        # Convert the Conversation object into a dictionary
        conversation_dict = {
            "id": conversation.id,
            "title": conversation.title,
            "history": json.loads(conversation.history),
            "token_count": conversation.token_count,
            "model_name": conversation.model_name,
            "temperature": conversation.temperature,
            "vector_search_results": json.loads(conversation.vector_search_results) if conversation.vector_search_results else None,
            "generated_search_queries": json.loads(conversation.generated_search_queries) if conversation.generated_search_queries else None,
            "web_search_results": json.loads(conversation.web_search_results) if conversation.web_search_results else None,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
            "sentiment": conversation.sentiment,
            "tags": conversation.tags,
            "language": conversation.language,
            "status": conversation.status,
            "rating": conversation.rating,
            "confidence": conversation.confidence,
            "intent": conversation.intent,
            "entities": json.loads(conversation.entities) if conversation.entities else None,
            "prompt_template": conversation.prompt_template
        }
        return jsonify(conversation_dict)

@app.route('/c/<conversation_id>')
@login_required
async def show_conversation(conversation_id):
    print(f"Attempting to load conversation {conversation_id}")  # Log the attempt
    
    async with get_session() as session:
        # Use an async query (select) instead of .query
        result = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            print(f"No conversation found for ID {conversation_id}")
            # You can render 404 or redirect:
            # return await render_template('404.html'), 404
            return redirect(url_for('home'))
        
        # Render the chat interface passing conversation ID
        return await render_template('chat.html', conversation_id=conversation.id)


@app.route('/api/conversations/<int:conversation_id>/update_title', methods=['POST'])
@login_required
async def update_conversation_title(conversation_id):
    try:
        async with get_session() as db_session:
            # Fetch the conversation by ID
            result = await db_session.execute(
                select(Conversation).filter_by(id=conversation_id)
            )
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                return jsonify({"error": "Conversation not found"}), 404
            
            # Get the new title from request data
            request_data = await request.get_json()
            new_title = request_data.get('title')
            if not new_title:
                return jsonify({"error": "New title is required"}), 400
            
            # Update title and updated_at with timezone-naive datetime
            conversation.title = new_title
            conversation.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            
            try:
                await db_session.commit()
                return jsonify({
                    "message": "Title updated successfully",
                    "title": new_title
                }), 200
            except Exception as db_error:
                await db_session.rollback()
                app.logger.error(f"Database error updating title: {str(db_error)}")
                return jsonify({"error": "Failed to update title"}), 500

    except Exception as e:
        app.logger.error(f"Error in update_conversation_title: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
@login_required
async def delete_conversation(conversation_id):
    try:
        async with get_session() as session:
            # Fetch the conversation by ID
            result = await session.execute(
                select(Conversation).filter_by(id=conversation_id)
            )
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                return jsonify({"error": "Conversation not found"}), 404
            
            # Delete the conversation
            await session.delete(conversation)
            await session.commit()

            return jsonify({"message": "Conversation deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/')
@login_required
async def home():
    try:
        app.logger.info("Home route accessed")
        
        user = await current_user.get_user()
        if user is None:
            app.logger.error("No user found in database")
            return redirect(url_for('auth.login'))

        # Clear any existing conversation from session
        if 'conversation_id' in session:
            session.pop('conversation_id', None)

        app.logger.info(f"Rendering chat template for user: {user.username}")
        return await render_template('chat.html', conversation=None, user=user)

    except Exception as e:
        app.logger.error(f"Error in home route: {str(e)}")
        app.logger.exception("Full traceback:")
        return await render_template('error.html', error=str(e))

@app.route('/clear-session', methods=['POST'])
def clear_session():
    session.clear()
    return jsonify({"message": "Session cleared"}), 200

def estimate_token_count(text):
    # Simplistic estimation. You may need a more accurate method.
    return len(text.split())

def generate_summary(messages):
    # Use only the most recent messages or truncate to reduce token count
    conversation_history = ' '.join([message['content'] for message in messages[-5:]])
    
    if estimate_token_count(conversation_history) > 4000:  # Adjust the limit as needed
        conversation_history = conversation_history[:4000]  # Truncate to fit the token limit
        app.logger.info("Conversation history truncated for summary generation")

    summary_request_payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Please create a very short (2-4 words) summary title for the following text:\n" + conversation_history}
        ],
        "max_tokens": 10,
        "temperature": 0.5  # Adjust the temperature if needed
    }

    app.logger.info(f"Sending summary request to OpenAI for conversation title: {str(summary_request_payload)[:100]}")

    try:
        response = client.chat.completions.create(**summary_request_payload)
        summary = response.choices[0].message.content.strip()
        app.logger.info(f"Response from OpenAI for summary: {response}")
        app.logger.info(f"Generated conversation summary: {summary}")
    except Exception as e:
        app.logger.error(f"Error in generate_summary: {e}")
        summary = "Conversation Summary"  # Fallback title

    return summary




@app.route('/reset-conversation', methods=['POST'])
@login_required
def reset_conversation():
    if 'conversation_id' in session:
        del session['conversation_id']
    return jsonify({"message": "Conversation reset successful"})

async def get_response_from_model(client, model, messages, temperature):
    """
    Routes the request to the appropriate API based on the model selected.
    Supports both synchronous and asynchronous calls with retry logic and fallbacks.
    """
    app.logger.info(f"Getting response from model: {model}")
    app.logger.info(f"Temperature: {temperature}")
    app.logger.info(f"Number of messages: {len(messages)}")

    max_retries = 3
    retry_delay = 1  # Initial delay in seconds

    async def handle_openai_request(payload):
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(**payload)
                return response.choices[0].message.content.strip(), response.model
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                    continue
                raise

    async def handle_anthropic_request(anthropic_client, model, anthropic_messages, max_tokens, temperature, extra_headers=None):
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    anthropic_client.messages.create,
                    model=model,
                    messages=anthropic_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    extra_headers=extra_headers
                )
                return response.content[0].text, model
            except anthropic.InternalServerError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                    continue
                # On final attempt, try falling back to OpenAI if available
                if attempt == max_retries - 1 and 'OPENAI_API_KEY' in os.environ:
                    app.logger.warning(f"Anthropic API failed after {max_retries} attempts. Falling back to GPT-4")
                    return await get_response_from_model(client, "gpt-4", messages, temperature)
                raise

    async def handle_gemini_request(model_name, contents, temperature):
        for attempt in range(max_retries):
            try:
                gemini_model = GenerativeModel(model_name=model_name)
                response = await asyncio.to_thread(
                    gemini_model.generate_content,
                    contents,
                    generation_config={"temperature": temperature}
                )
                return response.text, model_name
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                    continue
                raise

    try:
        if model.startswith("gpt-"):
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 4096
            }
            return await handle_openai_request(payload)

        elif model.startswith("claude-"):
            try:
                anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
                
                # Process messages for Anthropic format
                anthropic_messages = []
                system_message = None
                for message in messages:
                    if message['role'] == 'system':
                        system_message = message['content']
                    elif message['role'] in ['user', 'assistant']:
                        anthropic_messages.append({"role": message['role'], "content": message['content']})

                if system_message and anthropic_messages:
                    anthropic_messages[0]['content'] = f"{system_message}\n\nUser: {anthropic_messages[0]['content']}"

                if not anthropic_messages or anthropic_messages[0]['role'] != 'user':
                    anthropic_messages.insert(0, {"role": "user", "content": ""})

                max_tokens = 8192 if model == "claude-3-5-sonnet-20240620" else 4096
                extra_headers = {"anthropic-beta": "max-tokens-3-5-sonnet-2024-07-15"} if model == "claude-3-5-sonnet-20240620" else None

                return await handle_anthropic_request(
                    anthropic_client,
                    model,
                    anthropic_messages,
                    max_tokens,
                    temperature,
                    extra_headers
                )

            except KeyError as e:
                app.logger.error("Anthropic API key not found in environment variables")
                if 'OPENAI_API_KEY' in os.environ:
                    app.logger.info("Falling back to GPT-4")
                    return await get_response_from_model(client, "gpt-4", messages, temperature)
                raise

        elif model.startswith("gemini-"):
            contents = [{
                "role": "user",
                "parts": [{"text": "\n".join([m['content'] for m in messages])}]
            }]
            return await handle_gemini_request(model, contents, temperature)

        else:
            raise ValueError(f"Unsupported model: {model}")

    except Exception as e:
        app.logger.error(f"Error getting response from model {model}: {str(e)}")
        app.logger.exception("Full traceback:")
        
        # Attempt to fall back to a different model if possible
        try:
            if model.startswith("claude-") and 'OPENAI_API_KEY' in os.environ:
                app.logger.info("Attempting to fall back to GPT-4 after error")
                return await get_response_from_model(client, "gpt-4", messages, temperature)
            elif model.startswith("gpt-") and 'ANTHROPIC_API_KEY' in os.environ:
                app.logger.info("Attempting to fall back to Claude after error")
                return await get_response_from_model(client, "claude-3-5-sonnet-20240620", messages, temperature)
        except Exception as fallback_error:
            app.logger.error(f"Fallback attempt failed: {str(fallback_error)}")
        
        return None, None

# Wrapper function for synchronous calls
async def get_response_from_model_sync(client, model, messages, temperature):
    return await get_response_from_model(client, model, messages, temperature)


@app.route('/chat', methods=['POST'])
@login_required
async def chat():
    try:
        # Mark the session as active at the start
        status_manager.mark_session_active(str(current_user.auth_id))
        
        # Send initial connection message
        await status_manager.send_initial_message(str(current_user.auth_id))

        # Get JSON data with await
        request_data = await request.get_json()
        
        # Extract data from the request_data
        messages = request_data.get('messages')
        model = request_data.get('model')
        temperature = request_data.get('temperature')
        system_message_id = request_data.get('system_message_id')
        enable_web_search = request_data.get('enable_web_search', False)
        enable_intelligent_search = request_data.get('enable_intelligent_search', False)
        conversation_id = request_data.get('conversation_id') or session.get('conversation_id')
        
        if system_message_id is None:
            app.logger.error("No system_message_id provided in the chat request")
            return jsonify({'error': 'No system message ID provided'}), 400

        app.logger.info(f'Received model: {model}, temperature: {temperature}, system_message_id: {system_message_id}, enable_web_search: {enable_web_search}, enable_intelligent_search: {enable_intelligent_search}')

        await send_status_update("Initializing conversation")

        conversation = None
        if conversation_id:
            async with get_session() as db_session:  # Renamed to db_session
                result = await db_session.execute(
                    select(Conversation).filter_by(id=conversation_id)
                )
                conversation = result.scalar_one_or_none()
                
                if conversation and conversation.user_id == current_user.id:
                    app.logger.info(f'Using existing conversation with id {conversation_id}.')
                else:
                    app.logger.info(f'No valid conversation found with id {conversation_id}, starting a new one.')
                    conversation = None

        app.logger.info(f'Getting storage context for system_message_id: {system_message_id}')
        await send_status_update("Checking document database")

         # Get storage context coroutine
        storage_context_coroutine = embedding_store.get_storage_context(system_message_id)

        user_query = messages[-1]['content']
        app.logger.info(f'User query: {user_query}')

        relevant_info = None
        try:
            app.logger.info(f'Querying index with user query: {user_query[:50]}')
            await send_status_update("Searching through documents")


            # Pass the storage context coroutine to query_index
            relevant_info = await file_processor.query_index(user_query, storage_context_coroutine)
            
            if relevant_info:
                app.logger.info(f'Retrieved relevant info: {str(relevant_info)[:100]}')
                await send_status_update("Found relevant information in documents")
            else:
                app.logger.warning('No relevant information found in the index.')
                await send_status_update("No relevant documents found")
                relevant_info = None

        except Exception as e:
            app.logger.error(f'Error querying index: {str(e)}')
            app.logger.exception("Full traceback:")
            await send_status_update("Error searching document database")
            relevant_info = None

        system_message = next((msg for msg in messages if msg['role'] == 'system'), None)
        
        if system_message is None:
            system_message = {
                "role": "system",
                "content": ""
            }
            messages.insert(0, system_message)

        if relevant_info:
            system_message['content'] += f"\n\n<Added Context Provided by Vector Search>\n{relevant_info}\n</Added Context Provided by Vector Search>"
        
        app.logger.info(f"Updated system message: {system_message['content']}")

        summarized_results = None
        generated_search_queries = None
        
        # Web search process
        if enable_web_search:
            try:
                app.logger.info('Web search enabled, starting search process')
                await send_status_update("Starting web search process")
                
                generated_search_queries, summarized_results = await perform_web_search_process(
                    client, 
                    model, 
                    messages, 
                    user_query, 
                    current_user.id, 
                    system_message_id, 
                    enable_intelligent_search
                )
                
                await send_status_update("Web search completed, processing results")

                app.logger.info(f'Web search process completed. Generated queries: {generated_search_queries}')
                app.logger.info(f'Summarized results: {summarized_results[:100] if summarized_results else None}')
                
                if not isinstance(generated_search_queries, list):
                    app.logger.warning(f"generated_search_queries is not a list. Type: {type(generated_search_queries)}. Value: {generated_search_queries}")
                    generated_search_queries = [str(generated_search_queries)] if generated_search_queries else []
                
                if summarized_results:
                    system_message['content'] += f"\n\n<Added Context Provided by Web Search>\n{summarized_results}\n</Added Context Provided by Web Search>"
                    system_message['content'] += "\n\nIMPORTANT: In your response, please include relevant footnotes using [1], [2], etc. At the end of your response, list all sources under a 'Sources:' section, providing full URLs for each footnote."
                else:
                    app.logger.warning('No summarized results from web search')
            except Exception as e:
                app.logger.error(f'Error in web search process: {str(e)}')
                app.logger.exception("Full traceback:")
                await send_status_update("Error during web search process")
                generated_search_queries = None
                summarized_results = None
        else:
            app.logger.info('Web search is disabled')

        app.logger.info(f"Final system message: {system_message['content']}")

        await send_status_update(f"Generating final analysis and response using model: {model}")
        app.logger.info(f'Sending messages to model: {json.dumps(messages, indent=2)}')

        # Get model response
        chat_output, model_name = await get_response_from_model(client, model, messages, temperature)

        if chat_output is None:
            await send_status_update("Error getting response from AI model")
            raise Exception("Failed to get response from model")
        
        app.logger.info(f"Final response from model after prompt injections: {chat_output}")

        prompt_tokens = count_tokens(model_name, messages)
        completion_tokens = count_tokens(model_name, [{"content": chat_output}])
        total_tokens = prompt_tokens + completion_tokens

        app.logger.info(f'Tokens - Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}')

        new_message = {"role": "assistant", "content": chat_output}
        messages.append(new_message)

        # Update or create conversation
        async with get_session() as db_session:
            try:
                # Create timezone-naive datetime by converting UTC to naive
                current_time = datetime.now(timezone.utc).replace(tzinfo=None)
                
                if not conversation:
                    # Creating new conversation
                    conversation = Conversation(
                        history=json.dumps(messages),
                        temperature=temperature,
                        user_id=current_user.id,
                        token_count=total_tokens,
                        created_at=current_time,
                        updated_at=current_time,
                        model_name=model
                    )
                    conversation_title = generate_summary(messages)
                    conversation.title = conversation_title
                    db_session.add(conversation)
                    app.logger.info(f'Created new conversation with title: {conversation_title}')
                else:
                    # Fetch fresh instance of existing conversation within this session
                    result = await db_session.execute(
                        select(Conversation).filter_by(id=conversation.id)
                    )
                    conversation = result.scalar_one_or_none()
                    
                    if not conversation:
                        raise ValueError(f"Conversation {conversation.id} not found in database")
                    
                    # Update conversation
                    conversation.history = json.dumps(messages)
                    conversation.temperature = temperature
                    conversation.token_count += total_tokens
                    conversation.updated_at = current_time
                    conversation.model_name = model
                    app.logger.info(f'Updated existing conversation with id: {conversation.id}')

                # Set the additional fields
                conversation.vector_search_results = json.dumps(relevant_info) if relevant_info else None
                conversation.generated_search_queries = json.dumps(generated_search_queries) if generated_search_queries else None
                conversation.web_search_results = json.dumps(summarized_results) if summarized_results else None

                await send_status_update("Saving conversation")
                
                # Commit changes
                await db_session.commit()
                
                # Get fresh instance after commit
                result = await db_session.execute(
                    select(Conversation).filter_by(id=conversation.id)
                )
                conversation = result.scalar_one_or_none()
                
                if not conversation:
                    raise ValueError("Failed to retrieve conversation after commit")

                # Update the request session with the conversation ID
                session['conversation_id'] = conversation.id

                app.logger.info(f'Chat response prepared. Conversation ID: {conversation.id}, Title: {conversation.title}')

                return jsonify({
                    'chat_output': chat_output,
                    'conversation_id': conversation.id,
                    'conversation_title': conversation.title,
                    'vector_search_results': relevant_info if relevant_info else "No results found",
                    'generated_search_queries': generated_search_queries if generated_search_queries else [],
                    'web_search_results': summarized_results if summarized_results else "No web search performed",
                    'system_message_content': system_message['content'],
                    'usage': {
                        'prompt_tokens': prompt_tokens,
                        'completion_tokens': completion_tokens,
                        'total_tokens': total_tokens
                    },
                    'enable_web_search': enable_web_search,
                    'enable_intelligent_search': enable_intelligent_search
                })

            except Exception as db_error:
                app.logger.error(f'Database error: {str(db_error)}')
                await db_session.rollback()
                status_manager.mark_session_inactive(str(current_user.auth_id))
                raise

    except Exception as e:
        app.logger.error(f'Unexpected error in chat route: {str(e)}')
        app.logger.exception("Full traceback:")
        await send_status_update("An error occurred during processing")
        status_manager.mark_session_inactive(str(current_user.auth_id))
        return jsonify({'error': 'An unexpected error occurred'}), 500
        
    finally:
        # Ensure the session is marked as inactive when the chat is complete
        status_manager.mark_session_inactive(str(current_user.auth_id))
        # Small delay to allow final status messages to be sent
        await asyncio.sleep(0.5)

def count_tokens(model_name, messages):
    if model_name.startswith("gpt-"):
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to cl100k_base encoding if the specific model encoding is not found
            encoding = tiktoken.get_encoding("cl100k_base")
        
        num_tokens = 0
        for message in messages:
            # Count tokens in the content
            num_tokens += len(encoding.encode(message['content']))
            
            # Add tokens for role (and potentially name)
            num_tokens += 4  # Every message follows <im_start>{role/name}\n{content}<im_end>\n
            if 'name' in message:
                num_tokens += len(encoding.encode(message['name']))
        
        # Add tokens for the messages separator
        num_tokens += 2  # Every reply is primed with <im_start>assistant
        
        return num_tokens

    elif model_name.startswith("claude-"):
        encoding = tiktoken.get_encoding("cl100k_base")
        num_tokens = 0
        
        for message in messages:
            if isinstance(message, dict):
                content = message.get('content', '')
                role = message.get('role', '')
            elif isinstance(message, str):
                content = message
                role = ''
            else:
                continue  # Skip if message is neither dict nor str

            num_tokens += len(encoding.encode(content))
            
            if role:
                num_tokens += len(encoding.encode(role))
            
            if role == 'user':
                num_tokens += len(encoding.encode("Human: "))
            elif role == 'assistant':
                num_tokens += len(encoding.encode("Assistant: "))
            
            num_tokens += 2  # Each message ends with '\n\n'
        
        # Add tokens for the system message if present
        if messages and isinstance(messages[0], dict) and messages[0].get('role') == 'system':
            num_tokens += len(encoding.encode("\n\nHuman: "))
        
        return num_tokens

    elif model_name == "gemini-pro":
        try:
            # Get API key from environment
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable is not set")

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-pro')
            
            num_tokens = 0
            for message in messages:
                if isinstance(message, dict):
                    content = message.get('content', '')
                elif isinstance(message, str):
                    content = message
                else:
                    continue

                # Use the count_tokens method to get an estimate
                token_count = model.count_tokens(content)
                num_tokens += token_count.total_tokens

            return num_tokens
        except Exception as e:
            app.logger.error(f"Error counting tokens for Gemini: {e}")
            # Fallback to a more sophisticated approximation
            return approximate_gemini_tokens(messages)

    else:
        # Fallback to a generic tokenization method
        num_tokens = 0
        for message in messages:
            num_tokens += len(message['content'].split())  # Fallback to word count
        return num_tokens

def approximate_gemini_tokens(messages):
    """
    Approximate token count for Gemini when API call fails.
    Uses a more sophisticated approximation than simple word count.
    """
    num_tokens = 0
    for message in messages:
        if isinstance(message, dict):
            content = message.get('content', '')
        elif isinstance(message, str):
            content = message
        else:
            continue

        # Approximate tokens based on characters and words
        # Gemini typically uses byte-pair encoding, so this is a rough approximation
        char_count = len(content)
        word_count = len(content.split())
        
        # Approximate formula: 
        # - Average of character count / 4 (typical for BPE)
        # - and word count * 1.3 (accounting for common subword tokens)
        token_estimate = (char_count / 4 + word_count * 1.3) / 2
        num_tokens += int(token_estimate)

    return num_tokens


@app.route('/get_active_conversation', methods=['GET'])
def get_active_conversation():
    conversation_id = session.get('conversation_id')
    return jsonify({'conversationId': conversation_id})



# This has to be at the bottom of the file
if __name__ == '__main__':
    import asyncio
    import platform
    from hypercorn.config import Config
    from hypercorn.asyncio import serve

    # Configure event loop for Windows
    if platform.system() == 'Windows':
        # Force use of selector event loop
        loop = asyncio.SelectorEventLoop()
        asyncio.set_event_loop(loop)
        print("Using SelectorEventLoop for Windows compatibility")
    else:
        loop = asyncio.get_event_loop()

    config = Config()
    config.bind = [f"0.0.0.0:{int(os.getenv('PORT', 8080))}"]
    config.use_reloader = app.debug
    config.workers = 4 if not app.debug else 1
    
    # Initialize the database before starting the server
    async def startup():
        await init_db()
        await serve(app, config)

    loop.run_until_complete(startup())