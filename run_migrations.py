# run_migrations.py
import os
import sys
import asyncio
import logging
from alembic.config import Config
from alembic import command

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