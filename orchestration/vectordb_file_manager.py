# orchestration/vectordb_file_manager.py

import os
import aiofiles
import aiofiles.os as aio_os
import logging
import asyncio
import json
from sqlalchemy import select
from models import UploadedFile, get_session
import uuid
from datetime import datetime, timezone
from werkzeug.utils import secure_filename

class VectorDBFileManager:
    def __init__(self, file_processor, embedding_store, file_utils, logger=None):
        self.file_processor = file_processor
        self.embedding_store = embedding_store
        self.file_utils = file_utils
        self.logger = logger or logging.getLogger(__name__)

    async def get_file_record(self, file_id):
        async with get_session() as session:
            result = await session.execute(
                select(UploadedFile).filter_by(id=file_id)
            )
            return result.scalar_one_or_none()

    async def get_original_file_html(self, file_id, current_user_id):
        file = await self.get_file_record(file_id)
        if not file:
            return None, 404, 'File not found'
        if file.user_id != current_user_id:
            return None, 403, 'Unauthorized'
        if not os.path.exists(file.file_path):
            return None, 404, 'File not found on disk'

        html_content = f'''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{file.original_filename}</title>
            <style>
                html, body {{
                    margin: 0;
                    padding: 0;
                    height: 100%;
                    overflow: hidden;
                }}
                #file-embed {{
                    width: 100%;
                    height: 100%;
                    border: none;
                }}
            </style>
        </head>
        <body>
            <embed id="file-embed" src="/serve_file/{file_id}" type="{file.mime_type}">
            <script>
                function resizeEmbed() {{
                    var embed = document.getElementById('file-embed');
                    embed.style.height = window.innerHeight + 'px';
                }}
                window.onload = resizeEmbed;
                window.onresize = resizeEmbed;
            </script>
        </body>
        </html>
        '''
        return html_content, 200, 'OK'

    async def get_file_bytes(self, file_id, current_user_id):
        file = await self.get_file_record(file_id)
        if not file:
            return None, 404, 'File not found', None
        if file.user_id != current_user_id:
            return None, 403, 'Unauthorized', None
        if not os.path.exists(file.file_path):
            return None, 404, 'File not found on disk', None

        with open(file.file_path, 'rb') as f:
            data = f.read()
        headers = {
            'Content-Disposition': f'inline; filename="{file.original_filename}"',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
        return data, 200, file.mime_type, headers
    
    async def async_get_file_size(self, file_path: str) -> int:
        stat = await aio_os.stat(file_path)
        return stat.st_size    

    async def get_processed_text(self, file_id, current_user_id):
        file = await self.get_file_record(file_id)
        if not file:
            return None, 404, 'File not found', None
        if file.user_id != current_user_id:
            return None, 403, 'Unauthorized', None
        if not file.processed_text_path or not os.path.exists(file.processed_text_path):
            return None, 404, 'Processed text not available', None

        async with aiofiles.open(file.processed_text_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        headers = {
            'Content-Disposition': f'inline; filename="{file.original_filename}_processed.txt"',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
        return content, 200, 'text/plain', headers
    
    async def remove_file(self, file_id, user_id):
        deletion_results = {
            'vectors_deleted': False,
            'original_file_deleted': False,
            'processed_file_deleted': False,
            'database_entry_deleted': False
        }
        async with get_session() as session:
            try:
                # Fetch the file record
                result = await session.execute(
                    select(UploadedFile).filter_by(id=file_id)
                )
                file = result.scalar_one_or_none()
                if not file:
                    self.logger.warning(f"File not found: {file_id}")
                    return {'success': False, 'error': 'File not found'}, 404
                if file.user_id != user_id:
                    self.logger.warning(f"Unauthorized access attempt for file {file_id} by user {user_id}")
                    return {'success': False, 'error': 'Unauthorized'}, 403

                # Delete vectors from Pinecone
                system_message_id = file.system_message_id
                storage_context = await self.embedding_store.get_storage_context(system_message_id)
                namespace = self.embedding_store.generate_namespace(system_message_id)
                if storage_context and storage_context.vector_store:
                    try:
                        deleted = await self.delete_vectors_for_file(
                            storage_context.vector_store, 
                            file_id, 
                            namespace
                        )
                        deletion_results['vectors_deleted'] = deleted
                        self.logger.info(f"Vector deletion {'successful' if deleted else 'not needed'} for file {file_id}")
                    except Exception as vector_error:
                        self.logger.error(f"Error deleting vectors: {str(vector_error)}")

                # Remove original file
                if await self.async_file_exists(file.file_path):
                    try:
                        await aio_os.remove(file.file_path)
                        deletion_results['original_file_deleted'] = True
                        self.logger.info(f"Original file removed: {file.file_path}")
                    except Exception as file_error:
                        self.logger.error(f"Error deleting original file: {str(file_error)}")
                else:
                    self.logger.warning(f"Original file not found: {file.file_path}")

                # Remove processed text file if it exists
                if file.processed_text_path and await self.async_file_exists(file.processed_text_path):
                    try:
                        await aio_os.remove(file.processed_text_path)
                        deletion_results['processed_file_deleted'] = True
                        self.logger.info(f"Processed text file removed: {file.processed_text_path}")
                    except Exception as processed_error:
                        self.logger.error(f"Error deleting processed file: {str(processed_error)}")

                # Remove database entry
                try:
                    await session.delete(file)
                    await session.commit()
                    deletion_results['database_entry_deleted'] = True
                    self.logger.info(f"Database entry deleted for file {file_id}")
                except Exception as db_error:
                    self.logger.error(f"Error deleting database entry: {str(db_error)}")
                    await session.rollback()
                    raise

                # Prepare detailed response
                success_message = "File and associated resources removed successfully"
                if not all(deletion_results.values()):
                    success_message = "File partially removed with some errors"

                response_data = {
                    'success': True,
                    'message': success_message,
                    'details': deletion_results
                }
                self.logger.info(f"File removal completed for {file_id}: {deletion_results}")
                return response_data, 200

            except Exception as e:
                self.logger.error(f"Error during file removal process for {file_id}: {str(e)}")
                self.logger.exception("Full traceback:")
                if not deletion_results['database_entry_deleted']:
                    try:
                        await session.rollback()
                    except Exception as rollback_error:
                        self.logger.error(f"Error during session rollback: {str(rollback_error)}")
                return {
                    'success': False,
                    'error': str(e),
                    'partial_deletion_results': deletion_results
                }, 500

    async def delete_vectors_for_file(self, vector_store, file_id: str, namespace: str) -> bool:
        if not vector_store or not hasattr(vector_store, '_pinecone_index'):
            raise ValueError("Invalid vector store provided")
        if not file_id:
            raise ValueError("file_id cannot be empty")
        try:
            pinecone_index = vector_store._pinecone_index
            self.logger.debug(f"Attempting to delete vectors for file ID {file_id} in namespace {namespace}")
            # Query for vectors related to this file
            query_response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: pinecone_index.query(
                    namespace=namespace,
                    vector=[0] * 1536,  # Dummy vector of zeros
                    top_k=10000,
                    include_metadata=True
                )
            )
            vector_ids = [
                match.id for match in query_response.matches 
                if match.metadata.get('file_id') == str(file_id)
            ]
            if vector_ids:
                delete_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: pinecone_index.delete(
                        ids=vector_ids,
                        namespace=namespace
                    )
                )
                self.logger.info(
                    f"Successfully deleted {len(vector_ids)} vectors for file ID: {file_id}. "
                    f"Delete response: {delete_response}"
                )
                return True
            else:
                self.logger.warning(f"No vectors found for file ID: {file_id} in namespace: {namespace}")
                return False
        except Exception as e:
            self.logger.error(
                f"Error in delete_vectors_for_file for file ID {file_id}: {str(e)}\n"
                f"Namespace: {namespace}"
            )
            raise

    async def async_file_exists(self, file_path: str) -> bool:
        try:
            await aio_os.stat(file_path)
            return True
        except (OSError, FileNotFoundError):
            return False

    async def upload_file(self, file, user_id, system_message_id):
        if file.filename == '':
            return {'success': False, 'error': 'No selected file'}, 400

        filename = secure_filename(file.filename)
        file_path = await self.file_utils.get_file_path(
            user_id,
            system_message_id,
            filename,
            'uploads'
        )
        await self.file_utils.ensure_folder_exists(file_path.parent)
        await file.save(str(file_path))

        try:
            file_size = await self.async_get_file_size(str(file_path))
            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
            async with get_session() as session:
                new_file = UploadedFile(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    original_filename=filename,
                    file_path=str(file_path),
                    system_message_id=system_message_id,
                    file_size=file_size,
                    mime_type=file.content_type,
                    upload_timestamp=current_time
                )
                session.add(new_file)
                await session.commit()
                await session.refresh(new_file)

                # Index/process
                storage_context = await self.embedding_store.get_storage_context(system_message_id)
                processed_text_path = await self.file_processor.process_file(
                    str(file_path),
                    storage_context,
                    new_file.id,
                    user_id,
                    system_message_id
                )
                if processed_text_path:
                    new_file.processed_text_path = str(processed_text_path)
                    await session.commit()
                else:
                    if self.logger:
                        self.logger.warning(f"File {filename} processed, but no processed text path was returned.")

                return {
                    'success': True,
                    'message': 'File uploaded and indexed successfully',
                    'file_id': new_file.id
                }, 200

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error processing file: {str(e)}")
            # Try to clean up the file if something went wrong
            try:
                if await self.async_file_exists(str(file_path)):
                    await aio_os.remove(str(file_path))
                    if self.logger:
                        self.logger.info(f"Cleaned up file after error: {file_path}")
            except Exception as cleanup_error:
                if self.logger:
                    self.logger.error(f"Error during cleanup: {str(cleanup_error)}")
            return {'success': False, 'error': f'Error processing file: {str(e)}'}, 500
