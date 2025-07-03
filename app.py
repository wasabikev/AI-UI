# app.py

# Standard library imports
import asyncio
import json
import os
import platform
import sys
import time

import openai

from datetime import datetime, timezone, timedelta
from pathlib import Path


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


# Third-party imports - Database and ORM
from sqlalchemy import select, func
from alembic.config import Config as AlembicConfig
from dotenv import load_dotenv



# Third-party imports - Async HTTP and Network
import aiofiles.os as aio_os



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

from orchestration.session_attachment_handler import SessionAttachmentHandler

# Local imports - Web Search
from orchestration.web_search_orchestrator import perform_web_search_process

# Local imports - Vector DB Management
from orchestration.vectordb_file_manager import VectorDBFileManager
vectordb_file_manager = None
from orchestration.vector_search_utils import VectorSearchUtils
vector_search_utils = None
# Define the approximate token limit for your embedding model
# text-embedding-ada-002 and text-embedding-3-small have 8191/8192 limits
EMBEDDING_MODEL_TOKEN_LIMIT = 8190 # Use a slightly lower buffer



# Local imports - Chat Orchestration
from orchestration.chat_orchestrator import ChatOrchestrator
chat_orchestrator = None

from orchestration.web_scraper_orchestrator import WebScraperOrchestrator

from utils.generate_title_utils import generate_summary_title


from orchestration.llm_router import LLMRouter, count_tokens
llm_router= None

from services.embedding_store import EmbeddingStore

from init_db import init_db

from utils.logging_utils import setup_logging 
from utils.debug_routes import DebugRoutes

from services.client_manager import ClientManager

from config import get_config


# Load environment variables
load_dotenv()

# Initialize application
app = Quart(__name__)
app = cors(app, allow_origin="*")
QuartSchema(app)

app.config.from_object(get_config())

# Local imports - Conversation Orchestration
from orchestration.conversation import ConversationOrchestrator
conversation_orchestrator = ConversationOrchestrator(app.logger)

from orchestration.system_message_orchestrator import SystemMessageOrchestrator
system_message_orchestrator = SystemMessageOrchestrator(app.logger)

from orchestration.websocket_manager import WebSocketManager
# Initialize the status update manager
status_manager = StatusUpdateManager()


websocket_manager = WebSocketManager(status_manager, app.logger)

# Initialize client manager and all external service clients
client_manager = ClientManager()


db_url = os.getenv('DATABASE_URL')


# Debug configuration
debug_mode = True



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




# Usage in app.py
setup_logging(app, debug_mode)




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
    global embedding_store, file_processor, session_attachment_handler
    global vectordb_file_manager, chat_orchestrator, web_scraper_orchestrator
    global llm_router, vector_search_utils

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

        app.logger.info("Application initialization completed successfully")

    except Exception as e:
        app.logger.error("Application startup failed", exc_info=True)
        raise


# Define the WebSocket route for chat status updates
@app.websocket('/ws/chat/status')
@login_required
async def ws_chat_status():
    return await websocket_manager.handle_ws_chat_status()



# Health check endpoint for WebSocket connections
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




# Toggle web search settings for system messages

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



#------------------------- Session Attachment Management

# Initialize session attachment handler
session_attachment_handler = None  

@app.route('/api/session-attachments/upload', methods=['POST'])
@login_required
async def upload_session_attachment():
    """
    Handle session attachment uploads for chat context.
    Process the attachment immediately and return extracted text and metadata.
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

        # Save the session attachment using the handler
        save_result = await session_attachment_handler.save_attachment(file, current_user.id)
        if not save_result.get('success'):
            return jsonify({'success': False, 'error': 'Failed to save attachment'}), 500

        attachment_id = save_result['attachmentId']
        filename = save_result['filename']
        file_path = save_result['file_path']
        file_size = save_result['size']
        mime_type = save_result['mime_type']

        # Process the attachment immediately using FileProcessor
        start_time = time.time()
        # Use the current user and a dummy system_message_id (0) for session attachments
        extracted_text, _ = await file_processor.llm_whisper.process_file(
            file_path=file_path,
            user_id=current_user.id,
            system_message_id=0,
            file_id=attachment_id
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
            'attachmentId': attachment_id,
            'filename': filename,
            'size': file_size,
            'mime_type': mime_type,
            'tokenCount': token_count,
            'extractedText': extracted_text,
            'processingTime': processing_time
        })

    except Exception as e:
        app.logger.error(f"Error processing session attachment: {str(e)}")
        return jsonify({'success': False, 'error': f'Error processing attachment: {str(e)}'}), 500

@app.route('/api/session-attachments/<attachment_id>/remove', methods=['DELETE'])
@login_required
async def remove_session_attachment(attachment_id):
    """Remove a session attachment by its ID."""
    try:
        success = await session_attachment_handler.remove_attachment(attachment_id, current_user.id)
        return jsonify({
            'success': success,
            'message': 'Attachment removed' if success else 'Attachment not found'
        })
    except Exception as e:
        app.logger.error(f"Error removing session attachment: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

#------------------------- End Session Attachment Management



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
    result, status = await web_scraper_orchestrator.add_website(url, system_message_id, current_user)
    return jsonify(result), status

@app.route('/remove-website/<int:website_id>', methods=['DELETE'])
@login_required
async def remove_website(website_id):
    result, status = await web_scraper_orchestrator.remove_website(website_id, current_user)
    return jsonify(result), status


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
        
@app.route('/trigger-flash')
def trigger_flash():
    flash("You do not have user admin privileges.", "warning")  # Adjust the message and category as needed
    return redirect(url_for('the_current_page'))  # Replace with the appropriate endpoint

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

#----------------- End Database management


#----------------- Begining of conversation management

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


#-------------------------- Home route

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


#-------------------------- End of chat-related routes


# This has to be at the bottom of the file!
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
