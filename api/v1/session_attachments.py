# api/v1/session_attachments.py

import time
import json
from quart import Blueprint, request, jsonify, Response
from quart_auth import current_user
from auth import login_required

def create_session_attachments_blueprint(
    session_attachment_handler,
    allowed_file,
    file_processor,
    logger
):
    bp = Blueprint('session_attachments', __name__, url_prefix='/api/v1/session-attachments')

    @bp.route('/upload', methods=['POST'])
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
                logger.warning(f"Could not estimate tokens for extracted text: {str(token_error)}")

            logger.info(f"FileProcessor extraction took {processing_time:.2f} seconds for {filename}")

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
            logger.error(f"Error processing session attachment: {str(e)}")
            return jsonify({'success': False, 'error': f'Error processing attachment: {str(e)}'}), 500

    @bp.route('/<attachment_id>/remove', methods=['DELETE'])
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
            logger.error(f"Error removing session attachment: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    return bp
