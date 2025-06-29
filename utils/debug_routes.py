# utils/debug_routes.py

import json
import logging
import os
import sys
import traceback
from pathlib import Path

import pkg_resources
from quart import jsonify, request
from sqlalchemy import select

from auth import login_required, current_user


logger = logging.getLogger(__name__)


class DebugRoutes:
    """Utility class for debug and diagnostic routes"""
    
    def __init__(self, app, status_manager):
        self.app = app
        self.status_manager = status_manager
        self.logger = app.logger
        
    async def websocket_diagnostic(self):
        """
        Endpoint to check WebSocket configuration and connectivity
        """
        try:
            # Gather environment information
            env_info = {
                'WEBSOCKET_ENABLED': os.getenv('WEBSOCKET_ENABLED'),
                'WEBSOCKET_PATH': os.getenv('WEBSOCKET_PATH'),
                'REQUEST_HEADERS': dict(request.headers),
                'SERVER_SOFTWARE': os.getenv('SERVER_SOFTWARE'),
                'FORWARDED_ALLOW_IPS': os.getenv('FORWARDED_ALLOW_IPS'),
                'PROXY_PROTOCOL': os.getenv('PROXY_PROTOCOL'),
            }
            
            # Check if running behind proxy
            is_proxied = any(h in request.headers for h in [
                'X-Forwarded-For',
                'X-Real-IP',
                'X-Forwarded-Proto'
            ])
            
            diagnostic_info = {
                'environment': env_info,
                'is_proxied': is_proxied,
                'websocket_config': {
                    'ping_interval': self.app.config.get('WEBSOCKET_PING_INTERVAL'),
                    'ping_timeout': self.app.config.get('WEBSOCKET_PING_TIMEOUT'),
                    'max_message_size': self.app.config.get('WEBSOCKET_MAX_MESSAGE_SIZE')
                }
            }
            
            return jsonify(diagnostic_info)
            
        except Exception as e:
            return jsonify({
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 500

    async def debug_config(self):
        """Debug endpoint to verify configuration"""
        return jsonify({
            'env_vars': {
                'DEBUG_CONFIG': os.getenv('DEBUG_CONFIG'),
                'WEBSOCKET_PATH': os.getenv('WEBSOCKET_PATH'),
                'PORT': os.getenv('PORT'),
            },
            'routes': {
                'websocket': '/ws/chat/status',
                'health': '/chat/status/health'
            },
            'server_info': {
                'worker_class': 'uvicorn.workers.UvicornWorker',
                'gunicorn_config_path': os.path.exists('gunicorn.conf.py'),
                'app_yaml_path': os.path.exists('.do/app.yaml')
            }
        })

    async def debug_config_full(self):
        """Detailed debug endpoint to verify configuration (login required)"""
        
        def mask_sensitive_value(key: str, value: str) -> str:
            """Mask sensitive values in environment variables"""
            sensitive_keys = {'API_KEY', 'SECRET', 'PASSWORD', 'TOKEN', 'DATABASE_URL'}
            if any(sensitive_word in key.upper() for sensitive_word in sensitive_keys):
                if len(str(value)) > 8:
                    return f"{value[:4]}...{value[-4:]}"
                return "****"
            return value

        try:
            # Get all files in the current directory
            files = os.listdir('.')
            do_files = os.listdir('.do') if os.path.exists('.do') else []
            
            # Read the contents of the config files
            gunicorn_config = ''
            if os.path.exists('gunicorn.conf.py'):
                with open('gunicorn.conf.py', 'r') as f:
                    gunicorn_config = f.read()
            
            app_yaml = ''
            if os.path.exists('.do/app.yaml'):
                with open('.do/app.yaml', 'r') as f:
                    app_yaml = f.read()
            
            # Mask sensitive environment variables
            masked_env_vars = {
                key: mask_sensitive_value(key, value)
                for key, value in os.environ.items()
            }
                
            response_data = {
                'env_vars': masked_env_vars,
                'files': {
                    'root': files,
                    'do_directory': do_files
                },
                'configs': {
                    'gunicorn': gunicorn_config,
                    'app_yaml': app_yaml
                },
                'routes': {
                    'websocket': '/ws/chat/status',
                    'health': '/chat/status/health'
                },
                'server_info': {
                    'worker_class': 'uvicorn.workers.UvicornWorker',
                    'gunicorn_config_path': os.path.exists('gunicorn.conf.py'),
                    'app_yaml_path': os.path.exists('.do/app.yaml'),
                    'current_directory': os.getcwd()
                },
                'user_info': {
                    'is_authenticated': current_user.is_authenticated
                }
            }
            
            self.logger.info("Debug configuration accessed by authenticated user")
            return jsonify(response_data)
            
        except Exception as e:
            self.logger.error("Error in debug configuration endpoint: %s", str(e))
            return jsonify({'error': 'Internal server error'}), 500

    async def debug_websocket_config(self):
        """Debug endpoint to check WebSocket configuration"""
        return jsonify({
            'websocket_enabled': True,
            'websocket_path': '/ws/chat/status',
            'current_connections': self.status_manager.connection_count,
            'server_info': {
                'worker_class': 'uvicorn.workers.UvicornWorker',
                'websocket_timeout': 300
            }
        })

    async def check_directories(self):
        """Debug endpoint to check directory structure and permissions"""
        base_dir = Path(self.app.config['BASE_UPLOAD_FOLDER'])
        
        def scan_directory(path):
            try:
                return {
                    'path': str(path),
                    'exists': path.exists(),
                    'is_dir': path.is_dir() if path.exists() else False,
                    'contents': [str(p) for p in path.glob('**/*')] if path.exists() and path.is_dir() else [],
                    'permissions': oct(os.stat(path).st_mode)[-3:] if path.exists() else None
                }
            except Exception as e:
                return {'path': str(path), 'error': str(e)}

        directories = {
            'base_upload_folder': scan_directory(base_dir),
            'current_user_folder': scan_directory(base_dir / str(current_user.id)),
        }
        
        return jsonify(directories)

    def view_logs(self):
        """View application logs"""
        logs_content = "<link rel='stylesheet' type='text/css' href='/static/css/styles.css'><div class='logs-container'>"
        try:
            with open('app.log', 'r') as log_file:
                logs_content += f"<div class='log-entry'><div class='log-title'>--- app.log ---</div><pre>"
                logs_content += log_file.read() + "</pre></div>\n"
        except FileNotFoundError:
            logs_content += "<div class='log-entry'><div class='log-title'>No log file found.</div></div>"
        logs_content += "</div>"
        return logs_content

    def register_routes(self, app):
        """Register all debug routes with the app"""
        
        @app.route('/ws/diagnostic')
        async def websocket_diagnostic():
            return await self.websocket_diagnostic()

        @app.route('/debug/config')
        async def debug_config():
            return await self.debug_config()

        @app.route('/debug/config/full')
        @login_required
        async def debug_config_full():
            return await self.debug_config_full()

        @app.route('/debug/websocket-config')
        @login_required
        async def debug_websocket_config():
            return await self.debug_websocket_config()

        @app.route('/debug/check-directories')
        @login_required
        async def check_directories():
            return await self.check_directories()

        @app.route('/view-logs')
        @login_required
        def view_logs():
            return self.view_logs()
