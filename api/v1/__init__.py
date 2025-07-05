from .chat import create_chat_blueprint
from .vector_files import create_vector_files_blueprint
from .session_attachments import create_session_attachments_blueprint
from .websites import create_websites_blueprint

def register_api_blueprints(app):
    app.register_blueprint(create_chat_blueprint(
        app.chat_orchestrator, app.status_manager
    ))
    app.register_blueprint(create_vector_files_blueprint(
        app.vectordb_file_manager,
        app.allowed_file,
        app.get_session,
        app.UploadedFile,
        app.select,
        app.logger
    ))
    app.register_blueprint(create_session_attachments_blueprint(
    app.session_attachment_handler,
    app.allowed_file,
    app.file_processor,
    app.logger
    ))
    app.register_blueprint(create_websites_blueprint(
        app.get_session,
        app.select,
        app.Website,
        app.web_scraper_orchestrator,
        app.logger
    ))


    # Register other blueprints as needed

