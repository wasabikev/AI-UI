from .chat import create_chat_blueprint

def register_api_blueprints(app):
    chat_bp = create_chat_blueprint(app.chat_orchestrator, app.status_manager)
    app.register_blueprint(chat_bp)
    # Register other blueprints as needed
