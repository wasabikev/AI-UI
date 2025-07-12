# run_migrations.py
import os
import sys
import logging
import asyncio
from alembic.config import Config
from alembic import command
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def convert_async_url_to_sync(async_url):
    """Convert async database URL to sync URL for Alembic"""
    if async_url and 'postgresql+asyncpg://' in async_url:
        sync_url = async_url.replace('postgresql+asyncpg://', 'postgresql://')
        logger.info("Converted async URL to sync URL for Alembic")
        return sync_url
    return async_url


def run_alembic_migrations():
    """Run database migrations using Alembic"""
    try:
        logger.info("Running Alembic migrations...")
        
        # Get the path to alembic.ini
        alembic_cfg = Config("alembic.ini")
        
        # Enable more verbose Alembic logging
        alembic_cfg.set_main_option("sqlalchemy.echo", "True")
        
        # Override the SQLAlchemy URL with the environment variable if available
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            # Convert async URL to sync URL for Alembic
            sync_db_url = convert_async_url_to_sync(db_url)
            logger.info(f"Using converted sync database URL for Alembic")
            alembic_cfg.set_main_option("sqlalchemy.url", sync_db_url)
        
        # Detailed logging for the migration process
        logger.info(f"Alembic config file: {alembic_cfg.config_file_name}")
        logger.info(f"Database URL: {alembic_cfg.get_main_option('sqlalchemy.url').split('@')[0]}...") # Log partial URL for security
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Current directory: {os.getcwd()}")
        logger.info(f"Files in migrations directory: {os.listdir('migrations') if os.path.exists('migrations') else 'Directory not found'}")

        logger.info("Starting Alembic upgrade command...")
        
        # Check current revision first
        try:
            logger.info("Checking current Alembic revision...")
            current_rev = command.current(alembic_cfg)
            logger.info(f"Current Alembic revision: {current_rev}")
        except Exception as e:
            logger.warning(f"Could not get current revision: {e}")
        
        # Check what revisions are available
        try:
            logger.info("Checking available revisions...")
            command.heads(alembic_cfg)
            logger.info("Available revisions checked")
        except Exception as e:
            logger.warning(f"Could not check heads: {e}")
        
        # Run the upgrade command
        logger.info("Executing Alembic upgrade to head...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic upgrade command completed successfully")
        
        logger.info("Alembic migrations completed successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to run Alembic migrations: {str(e)}", exc_info=True)
        return False



def run_migrations_sync():
    """Synchronous wrapper for backwards compatibility"""
    return run_alembic_migrations()

if __name__ == "__main__":
    success = run_migrations_sync()
    sys.exit(0 if success else 1)
