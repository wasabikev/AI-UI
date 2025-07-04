# api/v1/chat.py

from quart import Blueprint, request, jsonify, session
from auth import login_required, current_user

def create_chat_blueprint(chat_orchestrator, status_manager):
    """
    Factory function to create the chat API blueprint with dependency injection.
    """
    chat_bp = Blueprint('chat_api', __name__, url_prefix='/api/v1')

    @chat_bp.route('/chat', methods=['POST'])
    @login_required
    async def chat():
        """
        Main chat endpoint for LLM conversation orchestration.
        Expects JSON payload with messages, model, temperature, etc.
        """
        request_data = await request.get_json()
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

        # Call the orchestrator to handle the chat logic
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

    return chat_bp
