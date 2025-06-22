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
import time
import math
import re
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from functools import lru_cache, partial
from logging.handlers import RotatingFileHandler
from pathlib import Path
from queue import Queue, Empty, Full
from typing import List, Dict, Optional
from dataclasses import dataclass

def safe_json_loads(json_string, default=None):
    """Safely load JSON string, return default on error or if input is None."""
    if json_string is None:
        return default
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError) as e:
        app.logger.warning(f"Failed to load JSON: {e}. Input: '{str(json_string)[:50]}...'. Returning default: {default}")
        return default


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
import traceback

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

# Import LLMWhisperer client and exception if needed for type hinting or specific checks
from unstract.llmwhisperer.client import LLMWhispererClient, LLMWhispererClientException
import sqlalchemy as sa

# Local imports - Auth and Models
from auth import auth_bp, UserWrapper, login_required
from models import (
    get_session, engine, Base,
    Folder, Conversation, User, SystemMessage, Website, UploadedFile
)

# Local imports - Utils and Processing

from utils.file_utils import (
    get_user_folder, get_system_message_folder, get_uploads_folder,
    get_processed_texts_folder, get_llmwhisperer_output_folder, 
    ensure_folder_exists, get_file_path, FileUtils, allowed_file, ALLOWED_EXTENSIONS
)
from utils.time_utils import clean_and_update_time_context, generate_time_context

from orchestration.file_processing import FileProcessor
from orchestration.status import StatusUpdateManager, SessionStatus
from orchestration.temp_file_handler import TemporaryFileHandler

# Local imports - Web Search
from orchestration.web_search_orchestrator import perform_web_search_process

# Local imports - Vector DB Management
from orchestration.vectordb_file_manager import VectorDBFileManager
vectordb_file_manager = None
from orchestration.vector_search_utils import VectorSearchUtils

# Local imports - Chat Orchestration
from orchestration.chat_orchestrator import ChatOrchestrator
chat_orchestrator = None


from orchestration.llm_router import LLMRouter, count_tokens

from services.embedding_store import EmbeddingStore

from init_db import init_db


# Load environment variables
load_dotenv()

# Initialize application
app = Quart(__name__)
app = cors(app, allow_origin="*")
QuartSchema(app)

# Local imports - Conversation Orchestration
from orchestration.conversation import ConversationOrchestrator
conversation_orchestrator = ConversationOrchestrator(app.logger)

from orchestration.system_message_orchestrator import SystemMessageOrchestrator
system_message_orchestrator = SystemMessageOrchestrator(app.logger)

# Initialize LLMWhisperer client
from unstract.llmwhisperer.client import LLMWhispererClient

llm_whisper_client = None
llmwhisperer_api_key = os.getenv("LLMWHISPERER_API_KEY")
if llmwhisperer_api_key:
    try:
        llm_whisper_client = LLMWhispererClient(api_key=llmwhisperer_api_key)
        app.logger.info("LLMWhisperer client initialized successfully")
    except Exception as e:
        app.logger.error(f"Failed to initialize LLMWhisperer client: {str(e)}")
        app.logger.exception("Full traceback:")
else:
    app.logger.warning("LLMWHISPERER_API_KEY environment variable not set")

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

# Initiatlize LLMWhisperer client
llmwhisperer_client: LLMWhispererClient | None = None

# Debug configuration
debug_mode = True



# Application configuration
app.config.update(
    ASYNC_MODE=True,
    PROPAGATE_EXCEPTIONS=True,
    SSE_RETRY_TIMEOUT=30000,
    SECRET_KEY=os.getenv('SECRET_KEY'),
    TEMPLATES_AUTO_RELOAD=True,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16 MB max-body-size
    MAX_FORM_MEMORY_SIZE=16 * 1024 * 1024,  # 16 MB max-form-size
    RESPONSE_TIMEOUT=300,  # 5 minutes in seconds
    KEEP_ALIVE_TIMEOUT=300,  # 5 minutes in seconds
    WEBSOCKET_PING_INTERVAL=20,  # Seconds between pings
    WEBSOCKET_PING_TIMEOUT=120,  # Seconds to wait for pong response
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
    app.logger.error(f"404 Not Found: Path={request.path} | Args={dict(request.args)} | Method={request.method}")
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
        format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',  #milliseconds included
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Custom Unicode formatter
    unicode_formatter = UnicodeFormatter("%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s")

    # Set up file handler with rotation
    file_handler = RotatingFileHandler(
        "app.log",
        maxBytes=100000,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(unicode_formatter)
    file_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    # Set up console handler with color formatting
    class ColorFormatter(logging.Formatter):
        """Add colors to log levels"""
        grey = "\x1b[38;21m"
        blue = "\x1b[34;21m"
        yellow = "\x1b[33;21m"
        red = "\x1b[31;21m"
        bold_red = "\x1b[31;1m"
        reset = "\x1b[0m"
        
        FORMATS = {
            logging.DEBUG: blue + "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s" + reset,
            logging.INFO: grey + "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s" + reset,
            logging.WARNING: yellow + "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s" + reset,
            logging.ERROR: red + "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s" + reset,
            logging.CRITICAL: bold_red + "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s" + reset,
        }
        
        def format(self, record):
            log_fmt = self.FORMATS.get(record.levelno)
            formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
            return formatter.format(record)

    # Console handler with color formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColorFormatter())
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)  # Show all levels in console

    # Configure app logger
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.propagate = False
    app.logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    # Add console handler to root logger as well
    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

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

    # Reduce noise from other loggers but show their warnings and errors
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
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
        logger.addHandler(console_handler)
        logger.propagate = False

    # Disable SQL statement logging explicitly
    logging.getLogger('sqlalchemy.engine.Engine.logger').disabled = True

    # Log startup message
    app.logger.info("Application logging initialized")

    if debug_mode:
        app.logger.debug("Debug mode enabled")
        app.logger.debug("Console logging enabled with colors")

# Initialize Cerebras
from cerebras.cloud.sdk import Client as CerebrasClient
cerebras_client = None
cerebras_api_key = os.getenv("CEREBRAS_API_KEY")
if cerebras_api_key:
    try:
        cerebras_client = CerebrasClient(api_key=cerebras_api_key)
        app.logger.info("Cerebras client initialized successfully")
    except Exception as e:
        app.logger.error(f"Failed to initialize Cerebras client: {str(e)}")
        app.logger.exception("Full traceback:")
else:
    app.logger.warning("CEREBRAS_API_KEY environment variable not set")

llm_router = LLMRouter(
    cerebras_client=cerebras_client,
    logger=app.logger,
)

# Usage in app.py
setup_logging(app, debug_mode)

# File upload configuration
BASE_UPLOAD_FOLDER = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), 'user_files'))).resolve()
app.config['BASE_UPLOAD_FOLDER'] = str(BASE_UPLOAD_FOLDER)


# Create the upload folder if it doesn't exist
try:
    upload_folder = Path(app.config['BASE_UPLOAD_FOLDER'])
    upload_folder.mkdir(parents=True, exist_ok=True)
    os.chmod(str(upload_folder), 0o777)
    app.logger.info(f"Successfully configured BASE_UPLOAD_FOLDER: {upload_folder}")
except Exception as e:
    app.logger.error(f"Error during upload folder configuration: {str(e)}")

# Needed for file uploads associated with conversations to review total token counts (not semantic search)
TEMP_UPLOAD_FOLDER = os.path.join(app.root_path, 'temp_uploads')
app.config['TEMP_UPLOAD_FOLDER'] = TEMP_UPLOAD_FOLDER
# Ensure the temporary folder exists
os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)



# Initialize temporary file handler
temp_file_handler = None  # Initialize later in startup

# Initialize file processing
embedding_store = None
file_processor = None




@app.before_serving
async def startup():
    global embedding_store, file_processor, temp_file_handler, vectordb_file_manager
    
    try:
        app.logger.info("Initializing application components")
        
        # Initialize database
        await init_db()
        
        # Initialize EmbeddingStore
        embedding_store = EmbeddingStore(db_url, logger=app.logger)
        await embedding_store.initialize()
        
        # Initialize FileProcessor
        file_processor = FileProcessor(embedding_store, app)
        # Initialize TemporaryFileHandler *after* file_processor is ready
        temp_file_handler = TemporaryFileHandler(
            temp_folder=app.config['TEMP_UPLOAD_FOLDER'],
            file_processor=file_processor
        )
        
        # Initialize FileUtils and verify upload folder
        app.file_utils = FileUtils(app)
        base_upload_folder = Path(app.config['BASE_UPLOAD_FOLDER'])
        await app.file_utils.ensure_folder_exists(base_upload_folder)

        # ---- Instantiate ChatOrchestrator ----
        global chat_orchestrator
        chat_orchestrator = ChatOrchestrator(
            status_manager=status_manager,
            embedding_store=embedding_store,
            file_processor=file_processor,
            temp_file_handler=temp_file_handler,
            get_session=get_session,
            Conversation=Conversation,
            SystemMessage=SystemMessage,
            generate_summary=generate_summary,
            count_tokens=count_tokens,
            get_response_from_model=llm_router.get_response_from_model,
            perform_web_search_process=perform_web_search_process,
            EMBEDDING_MODEL_TOKEN_LIMIT=EMBEDDING_MODEL_TOKEN_LIMIT,
            generate_concise_query_for_embedding=vector_search_utils.generate_concise_query_for_embedding,
            client=client,
            BRAVE_SEARCH_API_KEY=BRAVE_SEARCH_API_KEY,
            file_utils=app.file_utils,
            logger=app.logger,
        )
        # ---- Instantiate VectorDBFileManager ----
        vectordb_file_manager = VectorDBFileManager(
            file_processor=file_processor,
            embedding_store=embedding_store,
            file_utils=app.file_utils,
            logger=app.logger
        )       
        
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


# Initialize the status update manager
status_manager = StatusUpdateManager()




@app.route('/ws/diagnostic')
async def websocket_diagnostic():
    """
    Endpoint to check WebSocket configuration and connectivity
    """
    try:
        # Gather environment information
        env_info = {
            'WEBSOCKET_ENABLED': os.getenv('WEBSOCKET_ENABLED'),
            'WEBSOCKET_PATH': os.getenv('WEBSOCKET_PATH'),
            'REQUEST_HEADERS': dict(request.headers),
            'SERVER_SOFTWARE': os.getenv('SERVER_SOFTWARE'),
            'FORWARDED_ALLOW_IPS': os.getenv('FORWARDED_ALLOW_IPS'),
            'PROXY_PROTOCOL': os.getenv('PROXY_PROTOCOL'),
        }
        
        # Check if running behind proxy
        is_proxied = any(h in request.headers for h in [
            'X-Forwarded-For',
            'X-Real-IP',
            'X-Forwarded-Proto'
        ])
        
        diagnostic_info = {
            'environment': env_info,
            'is_proxied': is_proxied,
            'websocket_config': {
                'ping_interval': app.config.get('WEBSOCKET_PING_INTERVAL'),
                'ping_timeout': app.config.get('WEBSOCKET_PING_TIMEOUT'),
                'max_message_size': app.config.get('WEBSOCKET_MAX_MESSAGE_SIZE')
            }
        }
        
        return jsonify(diagnostic_info)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.websocket('/ws/chat/status')
@login_required
async def ws_chat_status():
    """WebSocket endpoint for status updates"""
    user_id = int(current_user.auth_id)
    session_id = status_manager.create_session(user_id)
    app.logger.info(f"WebSocket connection initiated for session {session_id}")
    
    try:
        # Verify authentication
        if not current_user.is_authenticated:
            app.logger.warning(f"Unauthorized WebSocket connection attempt for session {session_id}")
            return
            
        # Get user and verify status
        user = await current_user.get_user()
        if not user or user.status != 'Active':
            app.logger.warning(f"Inactive or invalid user attempted WebSocket connection: {session_id}")
            return

        # Register the websocket connection
        app.logger.info(f"Registering WebSocket connection for session {session_id}")
        success = await status_manager.register_connection(session_id, websocket._get_current_object())
        
        if not success:
            app.logger.error(f"Failed to register WebSocket connection for session {session_id}")
            return

        # Send initial connection message
        app.logger.info(f"Sending initial connection message for session {session_id}")
        await status_manager.send_status_update(
            session_id=session_id,
            message="WebSocket connection established"
        )

        # Main message loop
        while True:
            try:
                message = await websocket.receive()
                app.logger.debug(f"Received WebSocket message for session {session_id}: {message}")
                
                if not message:
                    continue
                    
                try:
                    data = json.loads(message)
                    if data.get('type') == 'ping':
                        await websocket.send(json.dumps({
                            'type': 'pong',
                            'timestamp': datetime.now().isoformat(),
                            'session_id': session_id
                        }))
                except json.JSONDecodeError:
                    continue
                    
            except asyncio.CancelledError:
                app.logger.info(f"WebSocket connection cancelled for session {session_id}")
                break
                
    except Exception as e:
        app.logger.error(f"Error in WebSocket connection: {str(e)}")
        app.logger.exception("Full traceback:")
    finally:
        try:
            app.logger.info(f"Cleaning up WebSocket connection for session {session_id}")
            # Update the connection state in status_manager without trying to close the WebSocket
            if session_id in status_manager._sessions:
                session = status_manager._sessions[session_id]
                
                # Only decrement if session was active
                if session.active:
                    status_manager.connection_count = max(0, status_manager.connection_count - 1)
                
                # Update session to inactive state without closing the WebSocket
                status_manager._sessions[session_id] = SessionStatus(
                    user_id=session.user_id,
                    session_id=session_id,
                    message=session.message,
                    last_updated=time.time(),
                    expires_at=session.expires_at,
                    websocket=None,
                    active=False
                )

                status_manager.locks.pop(session_id, None)
                status_manager.initial_messages_sent.discard(session_id)
                
            app.logger.info(f"WebSocket cleanup complete for session {session_id}")
        except Exception as cleanup_error:
            app.logger.error(f"Error during WebSocket cleanup: {str(cleanup_error)}")


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

    response_data = {
        'status': 'healthy',
        'active_connections': status_manager.connection_count,
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
        'current_connections': status_manager.connection_count,
        'server_info': {
            'worker_class': 'uvicorn.workers.UvicornWorker',
            'websocket_timeout': 300
        }
    })


# Toggle web search settings for system messages

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
        enable_deep_search = data.get('enableDeepSearch')
        
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
            system_message.enable_deep_search = enable_deep_search
            
            # Add timestamp for tracking
            system_message.updated_at = datetime.now(timezone.utc)
            
            # Commit the changes
            await session.commit()
            
            app.logger.info(f"Search settings updated for system message {system_message_id} by user {current_user_obj.id}")
            
            return jsonify({
                'message': 'Search settings updated successfully',
                'enableWebSearch': system_message.enable_web_search,
                'enableDeepSearch': system_message.enable_deep_search,
                'updatedAt': system_message.updated_at.isoformat()
            }), 200
            
    except Exception as e:
        app.logger.error(f"Error in toggle_search: {str(e)}")
        return jsonify({
            'error': 'Failed to update search settings',
            'details': str(e)
        }), 500

# End web search

@app.route('/query_documents', methods=['POST'])
@login_required
def query_documents():
    query = request.json.get('query')
    file_processor = FileProcessor(embedding_store, app)
    results = file_processor.query_index(query)
    return jsonify({'results': results})

from flask import make_response, send_file, abort


#----------------- Vector database file management

@app.route('/upload_file', methods=['POST'])
@login_required
async def upload_file():
    files = await request.files
    if 'file' not in files:
        return jsonify({'success': False, 'error': 'No file part'}), 400

    file = files['file']
    form = await request.form
    try:
        system_message_id = int(form.get('system_message_id'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Invalid system message ID'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'File type not allowed'}), 400

    result, status = await vectordb_file_manager.upload_file(
        file=file,
        user_id=current_user.id,
        system_message_id=system_message_id
    )
    return jsonify(result), status

@app.route('/view_original_file/<file_id>')
@login_required
async def view_original_file(file_id):
    html_content, status, message = await vectordb_file_manager.get_original_file_html(file_id, current_user.id)
    if status != 200:
        return Response(json.dumps({'error': message}), status=status, mimetype='application/json')
    return Response(html_content, mimetype='text/html')

@app.route('/serve_file/<file_id>')
@login_required
async def serve_file(file_id):
    data, status, mimetype, headers = await vectordb_file_manager.get_file_bytes(file_id, current_user.id)
    if status != 200:
        return Response(json.dumps({'error': mimetype}), status=status, mimetype='application/json')
    response = Response(data, mimetype=mimetype)
    for k, v in headers.items():
        response.headers[k] = v
    return response

@app.route('/view_processed_text/<file_id>')
@login_required
async def view_processed_text(file_id):
    content, status, mimetype, headers = await vectordb_file_manager.get_processed_text(file_id, current_user.id)
    if status != 200:
        return Response(json.dumps({'error': mimetype}), status=status, mimetype='application/json')
    response = Response(content, mimetype=mimetype)
    for k, v in headers.items():
        response.headers[k] = v
    return response

@app.route('/remove_file/<file_id>', methods=['DELETE'])
@login_required
async def remove_file(file_id):
    response_data, status = await vectordb_file_manager.remove_file(file_id, current_user.id)
    return jsonify(response_data), status

#------------------------ End vector database file management

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

@app.route('/upload-temp-file', methods=['POST'])
@login_required
async def upload_temp_file():
    """
    Handle temporary file uploads for chat context.
    Process the file immediately and return extracted text and metadata.
    """
    try:
        files = await request.files
        if 'file' not in files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = files['file']
        if not file.filename:
            return jsonify({'success': False, 'error': 'No filename provided'}), 400

        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'File type not allowed'}), 400

        # Save the file temporarily using the existing handler
        save_result = await temp_file_handler.save_temp_file(file)
        if not save_result.get('success'):
            return jsonify({'success': False, 'error': 'Failed to save file'}), 500

        file_id = save_result['fileId']
        filename = save_result['filename']
        file_path = save_result['file_path']
        file_size = save_result['size']
        mime_type = save_result['mime_type']

        # Process the file immediately using FileProcessor
        start_time = time.time()
        # Use the current user and a dummy system_message_id (0) for context files
        extracted_text, _ = await file_processor.llm_whisper.process_file(
            file_path=file_path,
            user_id=current_user.id,
            system_message_id=0,
            file_id=file_id
        )
        processing_time = time.time() - start_time

        # Calculate token count if possible
        token_count = None
        try:
            import tiktoken
            encoding = tiktoken.get_encoding("cl100k_base")
            token_count = len(encoding.encode(extracted_text or ""))
        except Exception as token_error:
            app.logger.warning(f"Could not estimate tokens for extracted text: {str(token_error)}")

        app.logger.info(f"FileProcessor extraction took {processing_time:.2f} seconds for {filename}")

        return jsonify({
            'success': True,
            'fileId': file_id,
            'filename': filename,
            'size': file_size,
            'mime_type': mime_type,
            'tokenCount': token_count,
            'extractedText': extracted_text,
            'processingTime': processing_time
        })

    except Exception as e:
        app.logger.error(f"Error processing file: {str(e)}")
        return jsonify({'success': False, 'error': f'Error processing file: {str(e)}'}), 500

@app.route('/remove-temp-file/<file_id>', methods=['DELETE'])
@login_required
async def remove_temp_file(file_id):
    """Remove a temporary file"""
    try:
        success = await temp_file_handler.remove_temp_file(file_id)
        return jsonify({
            'success': success,
            'message': 'File removed' if success else 'File not found'
        })
    except Exception as e:
        app.logger.error(f"Error removing temporary file: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



# Helper functions for async file operations
async def async_file_exists(file_path: str) -> bool:
    """Async wrapper for checking if a file exists."""
    try:
        await aio_os.stat(file_path)
        return True
    except (OSError, FileNotFoundError):
        return False


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



@app.route('/health')
def health_check():
    return 'OK', 200

#----------------- Website Scaper Management

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


@app.route('/scrape', methods=['POST'])
@login_required
async def scrape():
    # Placeholder for future integration with Firecrawl or similar AI-powered extractor
    return jsonify({"success": False, "message": "Web scraping is not currently implemented. Future versions will support AI-powered content extraction."}), 501


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


#----------------- End Website Scaper Management

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

#------------------ System Messages Management

# Default System Message configuration
DEFAULT_SYSTEM_MESSAGE = {
    "name": "Default System Message",
    "content": "You are a knowledgeable assistant that specializes in critical thinking and analysis.",
    "description": "Default entry for database",
    "model_name": "gpt-3.5-turbo",
    "temperature": 0.3
}

@app.route('/system-messages', methods=['POST'])
@login_required
async def create_system_message():
    if not await current_user.check_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    data = await request.get_json()
    result, status = await system_message_orchestrator.create(data, current_user)
    return jsonify(result), status

@app.route('/api/system_messages', methods=['GET'])
@login_required
async def get_system_messages():
    result, status = await system_message_orchestrator.get_all()
    return jsonify(result), status

@app.route('/system-messages/<int:message_id>', methods=['PUT'])
@login_required
async def update_system_message(message_id):
    data = await request.get_json()
    result, status = await system_message_orchestrator.update(message_id, data, current_user)
    return jsonify(result), status

@app.route('/system-messages/<int:message_id>', methods=['DELETE'])
@login_required
async def delete_system_message(message_id):
    result, status = await system_message_orchestrator.delete(message_id, current_user)
    return jsonify(result), status


#----------------- End System Messages Management

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

#---------------------- Database management 

@app.route('/database')
async def database():
    try:
        conversations = await conversation_orchestrator.get_all_conversations_as_dicts()
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


#----------------- Begining of conversation management


# Fetch all conversations from the database for listing in the left sidebar
@app.route('/api/conversations', methods=['GET'])
@login_required
async def get_conversations():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        user_id = int(current_user.auth_id)
        result = await conversation_orchestrator.get_conversations(user_id, page, per_page)
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Error fetching conversations: {str(e)}")
        app.logger.exception("Full traceback:")
        return jsonify({'error': 'Error fetching conversations'}), 500


# Fetch a specific conversation from the database to display in the chat interface
@app.route('/conversations/<int:conversation_id>', methods=['GET'])
@login_required
async def get_conversation(conversation_id):
    conversation_dict = await conversation_orchestrator.get_conversation_dict(conversation_id)
    if conversation_dict is None:
        return jsonify({'error': 'Conversation not found'}), 404
    return jsonify(conversation_dict)


@app.route('/c/<int:conversation_id>')
@login_required
async def show_conversation(conversation_id):
    conversation = await conversation_orchestrator.get_conversation(conversation_id)
    if not conversation:
        print(f"No conversation found for ID {conversation_id}")
        return redirect(url_for('home'))
    return await render_template('chat.html', conversation_id=conversation.id)


@app.route('/api/conversations/<int:conversation_id>/update_title', methods=['POST'])
@login_required
async def update_conversation_title(conversation_id):
    try:
        request_data = await request.get_json()
        new_title = request_data.get('title')
        if not new_title:
            return jsonify({"error": "New title is required"}), 400
        conversation = await conversation_orchestrator.update_title(conversation_id, new_title)
        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404
        return jsonify({
            "success": True,
            "message": "Title updated successfully",
            "title": new_title
        }), 200
    except Exception as e:
        app.logger.error(f"Error in update_conversation_title: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
@login_required
async def delete_conversation(conversation_id):
    try:
        success = await conversation_orchestrator.delete_conversation(conversation_id)
        if not success:
            return jsonify({"error": "Conversation not found"}), 404
        return jsonify({"message": "Conversation deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route('/folders', methods=['GET'])
@login_required
async def get_folders():
    folders = await conversation_orchestrator.get_folders()
    return jsonify(folders)

@app.route('/folders', methods=['POST'])
@login_required
async def create_folder():
    data = await request.get_json()
    title = data.get('title')
    folder = await conversation_orchestrator.create_folder(title)
    return jsonify({"message": "Folder created successfully"}), 201

@app.route('/folders/<int:folder_id>/conversations', methods=['GET'])
@login_required
async def get_folder_conversations(folder_id):
    conversations = await conversation_orchestrator.get_folder_conversations(folder_id)
    return jsonify(conversations)

@app.route('/folders/<int:folder_id>/conversations', methods=['POST'])
@login_required
async def create_conversation_in_folder(folder_id):
    data = await request.get_json()
    title = data.get('title')
    conversation = await conversation_orchestrator.create_conversation(title, folder_id, current_user.id)
    if conversation is None:
        return jsonify({"error": "Folder not found"}), 404
    return jsonify({"message": "Conversation created successfully"}), 201

@app.route('/reset-conversation', methods=['POST'])
@login_required
def reset_conversation():
    if 'conversation_id' in session:
        del session['conversation_id']
    return jsonify({"message": "Conversation reset successful"})

#-------------------------- End of conversation-related routes

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


#-------------------------- Start of vector search-related routes

from orchestration.vector_search_utils import VectorSearchUtils

# Define the approximate token limit for your embedding model
# text-embedding-ada-002 and text-embedding-3-small have 8191/8192 limits
EMBEDDING_MODEL_TOKEN_LIMIT = 8190 # Use a slightly lower buffer

vector_search_utils = VectorSearchUtils(
    get_response_from_model=llm_router.get_response_from_model,  
    logger=app.logger,
    embedding_model_token_limit=EMBEDDING_MODEL_TOKEN_LIMIT
)


#-------------------------- End of vector search-related routes

#-------------------------- Start of chat-related routes


@app.route('/chat', methods=['POST'])
@login_required
async def chat():
    request_data = await request.get_json()
    # Extract all the fields as before...
    messages = request_data.get('messages')
    model = request_data.get('model')
    temperature = request_data.get('temperature')
    system_message_id = request_data.get('system_message_id')
    enable_web_search = request_data.get('enable_web_search', False)
    enable_deep_search = request_data.get('enable_deep_search', False)
    conversation_id = request_data.get('conversation_id')
    user_timezone = request_data.get('timezone', 'UTC')
    extended_thinking = request_data.get('extended_thinking', False)
    thinking_budget = request_data.get('thinking_budget', 12000)
    file_ids = request_data.get('file_ids', [])
    session_id = request.headers.get('X-Session-ID') or status_manager.create_session(int(current_user.auth_id))

    result = await chat_orchestrator.run_chat(
        messages=messages,
        model=model,
        temperature=temperature,
        system_message_id=system_message_id,
        enable_web_search=enable_web_search,
        enable_deep_search=enable_deep_search,
        conversation_id=conversation_id,
        user_timezone=user_timezone,
        extended_thinking=extended_thinking,
        thinking_budget=thinking_budget,
        file_ids=file_ids,
        current_user=current_user,
        session_id=session_id,
        request_data=request_data,
        session=session,  # Quart's session object
    )
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result)






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
