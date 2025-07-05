from .chat import create_chat_blueprint
from .vector_files import create_vector_files_blueprint


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

    # Register other blueprints as needed

