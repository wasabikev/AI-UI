# api/v1/image_generation.py

from quart import Blueprint, request, jsonify
from quart_auth import current_user
from auth import login_required

def create_image_generation_blueprint(image_generation_orchestrator):
    bp = Blueprint('image_generation', __name__, url_prefix='/api/v1/image-generation')

    @bp.route('/generate', methods=['POST'])
    @login_required
    async def generate_image():
        data = await request.get_json()
        prompt = data.get('prompt', '').strip()
        size = data.get('size', '256x256')

        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400

        result, status = await image_generation_orchestrator.generate_image(prompt, n=1, size=size)
        return jsonify(result), status

    return bp
