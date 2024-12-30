# migrations.py
from alembic import command
from alembic.config import Config as AlembicConfig
import os
from dotenv import load_dotenv

def run_migrations():
    """Run database migrations using Alembic."""
    load_dotenv()
    
    # Create Alembic config
    alembic_cfg = AlembicConfig("alembic.ini")
    
    # Set the SQLAlchemy URL in the Alembic config
    alembic_cfg.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))
    
    try:
        command.upgrade(alembic_cfg, "head")
        print("Database migrations completed successfully")
    except Exception as e:
        print(f"Error running database migrations: {str(e)}")
        raise

if __name__ == "__main__":
    run_migrations()