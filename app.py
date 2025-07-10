# app.py

# =========================
# 1. Standard Library Imports
# =========================
import asyncio
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# =========================
# 2. Third-Party Imports
# =========================
# -- Core Web Framework
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

# -- Database/ORM
from sqlalchemy import select, func
from alembic.config import Config as AlembicConfig
from dotenv import load_dotenv

# -- Async/Network
import aiofiles.os as aio_os

# =========================
# 3. Local Imports
# =========================
# -- Auth/Models
from auth import auth_bp, UserWrapper, login_required
from models import (
    get_session, engine, Base,
    Folder, Conversation, User, SystemMessage, Website, UploadedFile
)

# -- Utilities
from utils.file_utils import (
    get_user_folder, get_system_message_folder, get_uploads_folder,
    get_processed_texts_folder, get_llmwhisperer_output_folder, 
    ensure_folder_exists, get_file_path, FileUtils, allowed_file, ALLOWED_EXTENSIONS
)
from utils.time_utils import clean_and_update_time_context, generate_time_context
from utils.generate_title_utils import generate_summary_title
from utils.logging_utils import setup_logging 
from utils.debug_routes import DebugRoutes

# -- Orchestration Modules
from orchestration.file_processing import FileProcessor
from orchestration.status import StatusUpdateManager, SessionStatus
from orchestration.session_attachment_handler import SessionAttachmentHandler
from orchestration.web_search_orchestrator import perform_web_search_process
from orchestration.vectordb_file_manager import VectorDBFileManager
from orchestration.vector_search_utils import VectorSearchUtils
from orchestration.chat_orchestrator import ChatOrchestrator
from orchestration.web_scraper_orchestrator import WebScraperOrchestrator
from orchestration.image_generation import ImageGenerationOrchestrator
from orchestration.llm_router import LLMRouter, count_tokens
from orchestration.conversation import ConversationOrchestrator
from orchestration.system_message_orchestrator import SystemMessageOrchestrator
from orchestration.websocket_manager import WebSocketManager

# -- Services
from services.embedding_store import EmbeddingStore
from services.client_manager import ClientManager

# -- Config/Init
from config import get_config
from init_db import init_db

# =========================
# 4. Global Constants & Config
# =========================
load_dotenv()
EMBEDDING_MODEL_TOKEN_LIMIT = 8190 # Default token limit for embedding models
db_url = os.getenv('DATABASE_URL')
debug_mode = True


# =========================
# 5. App Initialization
# =========================
app = Quart(__name__)
app = cors(app, allow_origin="*")
QuartSchema(app)
app.config.from_object(get_config())
app.config['PREFERRED_URL_SCHEME'] = 'https'



# Auth
auth_manager = QuartAuth(app)
auth_manager.user_class = UserWrapper
app.register_blueprint(auth_bp)  

# Logging
setup_logging(app, debug_mode)

# Upload folder
try:
    upload_folder = Path(app.config['BASE_UPLOAD_FOLDER'])
    upload_folder.mkdir(parents=True, exist_ok=True)
    os.chmod(str(upload_folder), 0o777)
    app.logger.info(f"Successfully configured BASE_UPLOAD_FOLDER: {upload_folder}")
except Exception as e:
    app.logger.error(f"Error during upload folder configuration: {str(e)}")


# =========================
# 6. Orchestrator/Manager Instantiation
# =========================
vectordb_file_manager = None
vector_search_utils = None
chat_orchestrator = None
image_generation_orchestrator = None
llm_router = None
embedding_store = None
file_processor = None
session_attachment_handler = None
web_scraper_orchestrator = None
conversation_orchestrator = ConversationOrchestrator(app.logger)
system_message_orchestrator = SystemMessageOrchestrator(app.logger)
status_manager = StatusUpdateManager()
websocket_manager = WebSocketManager(status_manager, app.logger)
client_manager = ClientManager()

# =========================
# 7. Helper Functions
# =========================
def safe_json_loads(json_string, default=None):
    """Safely load JSON string, return default on error or if input is None."""
    if json_string is None:
        return default
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError) as e:
        app.logger.warning(f"Failed to load JSON: {e}. Input: '{str(json_string)[:50]}...'. Returning default: {default}")
        return default

async def async_file_exists(file_path: str) -> bool:
    """Async wrapper for checking if a file exists."""
    try:
        await aio_os.stat(file_path)
        return True
    except (OSError, FileNotFoundError):
        return False

# =========================
# 8. App Startup
# =========================
@app.before_serving
async def startup():
    global embedding_store, file_processor, session_attachment_handler
    global vectordb_file_manager, chat_orchestrator, web_scraper_orchestrator
    global llm_router, vector_search_utils, image_generation_orchestrator

    try:
        app.logger.info("Initializing application components")

        # 1. Initialize all external service clients
        clients = client_manager.initialize_all_clients()
        
        # Extract commonly used clients for backward compatibility
        client = clients['openai']
        pc = clients['pinecone']
        cerebras_client = clients['cerebras']
        llm_whisper_client = clients['llmwhisperer']

        # Get API keys
        BRAVE_SEARCH_API_KEY = client_manager.get_api_key('brave_search')

        # 2. Initialize FileUtils and verify upload folder
        app.file_utils = FileUtils(app)
        base_upload_folder = Path(app.config['BASE_UPLOAD_FOLDER'])
        await app.file_utils.ensure_folder_exists(base_upload_folder)

        # 3. Initialize database
        await init_db()

        # 4. Initialize EmbeddingStore
        embedding_store = EmbeddingStore(db_url, logger=app.logger)
        await embedding_store.initialize()

        # 5. Initialize FileProcessor
        file_processor = FileProcessor(embedding_store, app)

        # 6. Initialize SessionAttachmentHandler (needs file_utils and file_processor)
        session_attachment_handler = SessionAttachmentHandler(
            file_utils=app.file_utils,
            file_processor=file_processor
        )

        # 7. Initialize and register debug routes
        debug_routes = DebugRoutes(app, status_manager)
        debug_routes.register_routes(app)

        # 8. Initialize LLMRouter with clients
        llm_router = LLMRouter(
            cerebras_client=cerebras_client,
            logger=app.logger,
        )

        # 9. Initialize vector_search_utils (depends on llm_router)
        vector_search_utils = VectorSearchUtils(
            get_response_from_model=llm_router.get_response_from_model,
            logger=app.logger,
            embedding_model_token_limit=EMBEDDING_MODEL_TOKEN_LIMIT
        )

        # 10. Instantiate ChatOrchestrator (depends on llm_router and vector_search_utils)
        chat_orchestrator = ChatOrchestrator(
            status_manager=status_manager,
            embedding_store=embedding_store,
            file_processor=file_processor,
            session_attachment_handler=session_attachment_handler,
            get_session=get_session,
            Conversation=Conversation,
            SystemMessage=SystemMessage,
            generate_summary_title=generate_summary_title,
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

        # 11. Instantiate VectorDBFileManager
        vectordb_file_manager = VectorDBFileManager(
            file_processor=file_processor,
            embedding_store=embedding_store,
            file_utils=app.file_utils,
            logger=app.logger
        )

        # 12. Instantiate WebScraperOrchestrator
        web_scraper_orchestrator = WebScraperOrchestrator(
            logger=app.logger,
            get_session=get_session,
            SystemMessage=SystemMessage,
            Website=Website
        )
        
        # 13. Instantiate ImageGenerationOrchestrator
        image_generation_orchestrator = ImageGenerationOrchestrator(
            openai_client=clients['openai'],
            logger=app.logger
        )

        # 14. Attach chat orchestrator and status manager to the app
        app.chat_orchestrator = chat_orchestrator
        app.status_manager = status_manager

        # 15. Attach endpoints for vector file management
        app.vectordb_file_manager = vectordb_file_manager
        app.get_session = get_session
        app.UploadedFile = UploadedFile
        app.select = select
        app.allowed_file = allowed_file

        # 16. Attach endpoints for session attachments
        app.session_attachment_handler = session_attachment_handler
        app.allowed_file = allowed_file
        app.file_processor = file_processor

        # 17. Attach endpoints for website scraping
        app.get_session = get_session
        app.select = select
        app.Website = Website
        app.web_scraper_orchestrator = web_scraper_orchestrator

        # 18. Attach endpoints for image generation
        app.image_generation_orchestrator = image_generation_orchestrator

        #19. Attach endpoints for conversation management
        app.conversation_orchestrator = conversation_orchestrator
        app.get_session = get_session
        app.select = select
        app.Conversation = Conversation

        # 20. Attach endpoints for system message management
        app.system_message_orchestrator = system_message_orchestrator
        app.get_session = get_session
        app.select = select
        app.SystemMessage = SystemMessage

        # 16. Register API blueprints
        from api.v1 import register_api_blueprints
        register_api_blueprints(app)

        # Print registered routes for debugging
        # print("Registered routes:")
        # for rule in app.url_map.iter_rules():
        #    print(rule)


        app.logger.info("Application initialization completed successfully")

    except Exception as e:
        app.logger.error("Application startup failed", exc_info=True)
        raise

# =========================
# 9. Error Handlers
# =========================
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

# =========================
# 10. Static/Utility Routes
# =========================
@app.route('/static/<path:filename>')
async def static_files(filename):
    return await send_from_directory('static', filename)

@app.route('/health')
def health_check():
    return 'OK', 200

@app.route('/trigger-flash')
def trigger_flash():
    flash("You do not have user admin privileges.", "warning")  # Adjust the message and category as needed
    return redirect(url_for('the_current_page'))  # Replace with the appropriate endpoint

# =========================
# 11. WebSocket Routes
# =========================
@app.websocket('/ws/chat/status')
@login_required
async def ws_chat_status():
    return await websocket_manager.handle_ws_chat_status()

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


# =========================
# 12. Database Management Routes
# =========================
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


# =========================
# 13. Home and Session Routes
# =========================
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


# =========================
# 14. Main Entrypoint
# =========================
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
