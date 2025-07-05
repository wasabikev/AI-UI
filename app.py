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

# Default System Message configuration
DEFAULT_SYSTEM_MESSAGE = {
    "name": "Default System Message",
    "content": "You are a knowledgeable assistant that specializes in critical thinking and analysis.",
    "description": "Default entry for database",
    "model_name": "gpt-3.5-turbo",
    "temperature": 0.3
}

# =========================
# 5. App Initialization
# =========================
app = Quart(__name__)
app = cors(app, allow_origin="*")
QuartSchema(app)
app.config.from_object(get_config())

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

        # 16. Register API blueprints
        from api.v1 import register_api_blueprints
        register_api_blueprints(app)

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
# 14. Website Scraper Management Routes
# =========================
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
    result, status = await web_scraper_orchestrator.add_website(url, system_message_id, current_user)
    return jsonify(result), status

@app.route('/remove-website/<int:website_id>', methods=['DELETE'])
@login_required
async def remove_website(website_id):
    result, status = await web_scraper_orchestrator.remove_website(website_id, current_user)
    return jsonify(result), status

# =========================
# 15. Image Generation Management Routes
# =========================
@app.route('/generate-image', methods=['POST'])
@login_required
async def generate_image():
    data = await request.get_json()
    prompt = data.get('prompt', '').strip()
    size = data.get('size', '256x256')

    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400

    result, status = await image_generation_orchestrator.generate_image(prompt, n=1, size=size)
    return jsonify(result), status

# =========================
# 16. System Messages Management Routes
# =========================
@app.route('/api/system-messages/default-model', methods=['GET'])
@login_required
async def get_current_model():
    result, status = await system_message_orchestrator.get_default_model_name(DEFAULT_SYSTEM_MESSAGE["name"])
    return jsonify(result), status

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

@app.route('/api/system-messages/<int:system_message_id>/toggle-search', methods=['POST'])
@login_required
async def toggle_search(system_message_id):
    """
    Toggle web search settings for a system message.
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

        result, status = await system_message_orchestrator.toggle_search(
            system_message_id=system_message_id,
            enable_web_search=enable_web_search,
            enable_deep_search=enable_deep_search,
            current_user=current_user,
        )
        return jsonify(result), status

    except Exception as e:
        app.logger.error(f"Error in toggle_search: {str(e)}")
        return jsonify({
            'error': 'Failed to update search settings',
            'details': str(e)
        }), 500

# =========================
# 17. Database Management Routes
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
# 18. Conversation Management Routes
# =========================
@app.route('/get_active_conversation', methods=['GET'])
def get_active_conversation():
    conversation_id = session.get('conversation_id')
    return jsonify({'conversationId': conversation_id})

@app.route('/chat/<int:conversation_id>')
@login_required
async def chat_interface(conversation_id):
    conversation = await get_conversation_by_id(conversation_id)
    return await render_template('chat.html', conversation=conversation)

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

# =========================
# 19. Home and Session Routes
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
# 20. Main Entrypoint
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
