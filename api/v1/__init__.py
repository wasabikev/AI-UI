# api\v1\__init__.py

"""
API v1 Blueprint Registration

This module imports all API v1 blueprint factories and provides a single
function to register them on the Quart app instance, using dependency injection.
"""

# --- Import blueprint factories ---
from .chat import create_chat_blueprint
from .vector_files import create_vector_files_blueprint
from .session_attachments import create_session_attachments_blueprint
from .websites import create_websites_blueprint
from .image_generation import create_image_generation_blueprint
from .conversations import create_conversations_blueprint
from .system_messages import create_system_message_blueprint

def register_api_blueprints(app):
    """
    Register all API v1 blueprints on the given Quart app instance.
    All dependencies are injected from the app object.
    """
    # Chat endpoints
    app.register_blueprint(create_chat_blueprint(
        app.chat_orchestrator,
        app.status_manager
    ))

    # Vector file management endpoints
    app.register_blueprint(create_vector_files_blueprint(
        app.vectordb_file_manager,
        app.allowed_file,
        app.get_session,
        app.UploadedFile,
        app.select,
        app.logger
    ))

    # Session attachment endpoints
    app.register_blueprint(create_session_attachments_blueprint(
        app.session_attachment_handler,
        app.allowed_file,
        app.file_processor,
        app.logger
    ))

    # Website scraper endpoints
    app.register_blueprint(create_websites_blueprint(
        app.get_session,
        app.select,
        app.Website,
        app.web_scraper_orchestrator,
        app.logger
    ))

    # Image generation endpoints
    app.register_blueprint(create_image_generation_blueprint(
        app.image_generation_orchestrator
    ))

    # Conversation management endpoints
    app.register_blueprint(create_conversations_blueprint(
        app.conversation_orchestrator,
        app.get_session,
        app.select,
        app.Conversation,
        app.logger
    ))

    # System message endpoints
    # DEFAULT_SYSTEM_MESSAGE is available from config.py
    app.register_blueprint(create_system_message_blueprint(
    app.system_message_orchestrator,
    app.config['DEFAULT_SYSTEM_MESSAGE']
    ))


    # Register other blueprints as needed
