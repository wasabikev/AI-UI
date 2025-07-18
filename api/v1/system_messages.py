from quart import Blueprint, request, jsonify
from auth import current_user, login_required  

def create_system_message_blueprint(system_message_orchestrator, DEFAULT_SYSTEM_MESSAGE):
    bp = Blueprint('system_message_api', __name__, url_prefix='/api/v1/system_messages')

    @bp.route('/default-model', methods=['GET'])
    @login_required
    async def get_current_model():
        result, status = await system_message_orchestrator.get_default_model_name(DEFAULT_SYSTEM_MESSAGE["name"])
        return jsonify(result), status

    @bp.route('', methods=['POST'])
    @login_required
    async def create_system_message():
        user = await current_user.get_user()
        if not user or not user.is_admin:
            return jsonify({'error': 'Unauthorized'}), 401
        data = await request.get_json()
        result, status = await system_message_orchestrator.create(data, user)
        return jsonify(result), status

    @bp.route('', methods=['GET'])
    @login_required
    async def get_system_messages():
        result, status = await system_message_orchestrator.get_all()
        return jsonify(result), status

    @bp.route('/<int:message_id>', methods=['PUT'])
    @login_required
    async def update_system_message(message_id):
        user = await current_user.get_user()
        data = await request.get_json()
        result, status = await system_message_orchestrator.update(message_id, data, user)
        return jsonify(result), status

    @bp.route('/<int:message_id>', methods=['DELETE'])
    @login_required
    async def delete_system_message(message_id):
        user = await current_user.get_user()
        result, status = await system_message_orchestrator.delete(message_id, user)
        return jsonify(result), status

    @bp.route('/<int:system_message_id>/toggle-search', methods=['POST'])
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

            user = await current_user.get_user()
            result, status = await system_message_orchestrator.toggle_search(
                system_message_id=system_message_id,
                enable_web_search=enable_web_search,
                enable_deep_search=enable_deep_search,
                current_user=user,
            )
            return jsonify(result), status

        except Exception as e:
            bp.logger.error(f"Error in toggle_search: {str(e)}")
            return jsonify({
                'error': 'Failed to update search settings',
                'details': str(e)
            }), 500

    return bp
