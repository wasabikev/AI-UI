# api/v1/vector_files.py

import json
from quart import Blueprint, request, jsonify, Response
from quart_auth import current_user
from auth import login_required

def create_vector_files_blueprint(
    vectordb_file_manager,
    allowed_file,
    get_session,
    UploadedFile,
    select,
    logger
):
    """
    Factory for vector file management blueprint.
    All dependencies are injected for modularity and testability.
    """
    bp = Blueprint('vector_files', __name__, url_prefix='/api/v1/vector-files')

    @bp.route('/upload', methods=['POST'])
    @login_required
    async def upload_file():
        # pylint: disable=unused-function
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

    @bp.route('/<file_id>/original', methods=['GET'])
    @login_required
    async def view_original_file(file_id):
        html_content, status, message = await vectordb_file_manager.get_original_file_html(file_id, current_user.id)
        if status != 200:
            return Response(json.dumps({'error': message}), status=status, mimetype='application/json')
        return Response(html_content, mimetype='text/html')

    @bp.route('/<file_id>/serve', methods=['GET'])
    @login_required
    async def serve_file(file_id):
        data, status, mimetype, headers = await vectordb_file_manager.get_file_bytes(file_id, current_user.id)
        if status != 200:
            return Response(json.dumps({'error': mimetype}), status=status, mimetype='application/json')
        response = Response(data, mimetype=mimetype)
        for k, v in headers.items():
            response.headers[k] = v
        return response

    @bp.route('/<file_id>/processed', methods=['GET'])
    @login_required
    async def view_processed_text(file_id):
        content, status, mimetype, headers = await vectordb_file_manager.get_processed_text(file_id, current_user.id)
        if status != 200:
            return Response(json.dumps({'error': mimetype}), status=status, mimetype='application/json')
        response = Response(content, mimetype=mimetype)
        for k, v in headers.items():
            response.headers[k] = v
        return response

    @bp.route('/<file_id>', methods=['DELETE'])
    @login_required
    async def remove_file(file_id):
        response_data, status = await vectordb_file_manager.remove_file(file_id, current_user.id)
        return jsonify(response_data), status

    @bp.route('/list/<int:system_message_id>', methods=['GET'])
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
            logger.error(f"Error fetching files: {str(e)}")
            return jsonify({'error': 'Error fetching files'}), 500

    return bp
