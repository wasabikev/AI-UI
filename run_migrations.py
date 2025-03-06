# run_migrations.py
import os
import sys
import logging
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

def run_migrations():
    """Run database migrations using Alembic"""
    try:
        logger.info("Running database migrations...")
        
        # Get the path to alembic.ini
        alembic_cfg = Config("alembic.ini")
        
        # Override the SQLAlchemy URL with the environment variable if available
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            logger.info(f"Using database URL from environment variable")
            alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        
        #Detailed logging for the migration process
        logger.info(f"Alembic config file: {alembic_cfg.config_file_name}")
        logger.info(f"Database URL: {alembic_cfg.get_main_option('sqlalchemy.url').split('@')[0]}...") # Log partial URL for security
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Current directory: {os.getcwd()}")
        logger.info(f"Files in migrations directory: {os.listdir('migrations') if os.path.exists('migrations') else 'Directory not found'}")

        # Run the upgrade command
        command.upgrade(alembic_cfg, "head")
        
        logger.info("Database migrations completed successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to run migrations: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)