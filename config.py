# orchestration/config.py

import os
from pathlib import Path

class BaseConfig:
    # General
    ASYNC_MODE = True
    PROPAGATE_EXCEPTIONS = True
    SSE_RETRY_TIMEOUT = 30000
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret')
    TEMPLATES_AUTO_RELOAD = True
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    MAX_FORM_MEMORY_SIZE = 16 * 1024 * 1024  # 16 MB
    RESPONSE_TIMEOUT = 300
    KEEP_ALIVE_TIMEOUT = 300
    WEBSOCKET_PING_INTERVAL = 20
    WEBSOCKET_PING_TIMEOUT = 120

    # Auth
    QUART_AUTH_COOKIE_SECURE = not os.getenv('DEBUG', 'False').lower() in ('true', '1')
    QUART_AUTH_COOKIE_DOMAIN = None
    QUART_AUTH_COOKIE_NAME = "auth_token"
    QUART_AUTH_COOKIE_PATH = "/"
    QUART_AUTH_COOKIE_SAMESITE = "Lax"
    QUART_AUTH_DURATION = 60 * 60 * 24 * 30  # 30 days in seconds
    QUART_AUTH_SALT = 'cookie-session-aiui'

    # Uploads
    BASE_UPLOAD_FOLDER = str(Path(os.path.abspath(os.path.join(os.path.dirname(__file__), 'user_files'))).resolve())

    # Database
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is required but not set.")


    # Add other global config here as needed

    # For future: e.g. LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

class DigitalOceanConfig(BaseConfig):
    # DigitalOcean-specific overrides (if any)
    DEBUG = False
    ENV = 'production'
    # Add DigitalOcean-specific config here

class AzureConfig(BaseConfig):
    # Azure-specific overrides (if any)
    DEBUG = False
    ENV = 'production'
    # Add Azure-specific config here

class DevelopmentConfig(BaseConfig):
    DEBUG = True
    ENV = 'development'
    QUART_AUTH_COOKIE_SECURE = False

def get_config():
    env = os.getenv('APP_ENV', os.getenv('ENV', 'development')).lower()
    if env == 'digitalocean':
        return DigitalOceanConfig
    elif env == 'azure':
        return AzureConfig
    elif env == 'production':
        return DigitalOceanConfig  # Default to DigitalOcean for now
    else:
        return DevelopmentConfig
