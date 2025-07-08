# api/v1/conversations.py

from quart import Blueprint, request, jsonify, render_template, redirect, url_for, session, abort
from quart_auth import current_user
from auth import login_required

def create_conversations_blueprint(conversation_orchestrator, get_session, select, Conversation, logger):
    bp = Blueprint('conversations', __name__, url_prefix='/api/v1/conversations/')

    @bp.route('/active', methods=['GET'])
    def get_active_conversation():
        conversation_id = session.get('conversation_id')
        return jsonify({'conversationId': conversation_id})

    @bp.route('/chat/<int:conversation_id>')
    @login_required
    async def chat_interface(conversation_id):
        conversation = await get_conversation_by_id(conversation_id)
        return await render_template('chat.html', conversation=conversation)

    async def get_conversation_by_id(conversation_id):
        async with get_session() as session_:
            result = await session_.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = result.scalar_one_or_none()
            if conversation is None:
                abort(404, description="Conversation not found")
            return conversation

    @bp.route('/', methods=['GET'])
    @login_required
    async def get_conversations():
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            user_id = int(current_user.auth_id)
            result = await conversation_orchestrator.get_conversations(user_id, page, per_page)
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error fetching conversations: {str(e)}")
            logger.exception("Full traceback:")
            return jsonify({'error': 'Error fetching conversations'}), 500

    @bp.route('/<int:conversation_id>', methods=['GET'])
    @login_required
    async def get_conversation(conversation_id):
        conversation_dict = await conversation_orchestrator.get_conversation_dict(conversation_id)
        if conversation_dict is None:
            return jsonify({'error': 'Conversation not found'}), 404
        return jsonify(conversation_dict)

    @bp.route('/c/<int:conversation_id>')
    @login_required
    async def show_conversation(conversation_id):
        conversation = await conversation_orchestrator.get_conversation(conversation_id)
        if not conversation:
            logger.info(f"No conversation found for ID {conversation_id}")
            return redirect(url_for('home'))
        return await render_template('chat.html', conversation_id=conversation.id)

    @bp.route('/<int:conversation_id>/update_title', methods=['POST'])
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
            logger.error(f"Error in update_conversation_title: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @bp.route('/<int:conversation_id>', methods=['DELETE'])
    @login_required
    async def delete_conversation(conversation_id):
        try:
            success = await conversation_orchestrator.delete_conversation(conversation_id)
            if not success:
                return jsonify({"error": "Conversation not found"}), 404
            return jsonify({"message": "Conversation deleted successfully"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route('/folders', methods=['GET'])
    @login_required
    async def get_folders():
        folders = await conversation_orchestrator.get_folders()
        return jsonify(folders)

    @bp.route('/folders', methods=['POST'])
    @login_required
    async def create_folder():
        data = await request.get_json()
        title = data.get('title')
        folder = await conversation_orchestrator.create_folder(title)
        return jsonify({"message": "Folder created successfully"}), 201

    @bp.route('/folders/<int:folder_id>/conversations', methods=['GET'])
    @login_required
    async def get_folder_conversations(folder_id):
        conversations = await conversation_orchestrator.get_folder_conversations(folder_id)
        return jsonify(conversations)

    @bp.route('/folders/<int:folder_id>/conversations', methods=['POST'])
    @login_required
    async def create_conversation_in_folder(folder_id):
        data = await request.get_json()
        title = data.get('title')
        conversation = await conversation_orchestrator.create_conversation(title, folder_id, current_user.id)
        if conversation is None:
            return jsonify({"error": "Folder not found"}), 404
        return jsonify({"message": "Conversation created successfully"}), 201

    @bp.route('/reset', methods=['POST'])
    @login_required
    def reset_conversation():
        if 'conversation_id' in session:
            del session['conversation_id']
        return jsonify({"message": "Conversation reset successful"})

    return bp
