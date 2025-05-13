# init_db.py
from models import get_session, engine, Base, User, SystemMessage, Folder
from werkzeug.security import generate_password_hash
import os
from dotenv import load_dotenv
from sqlalchemy import inspect, select, text
from sqlalchemy_utils import Ltree
import asyncio
import logging
import sqlalchemy

import sys

# Run database migrations using Alembic
async def run_migrations():
    """Run database migrations using external script"""
    try:
        logger.info("Running database migrations...")
        
        # Use subprocess to run the migration script
        import subprocess
        result = subprocess.run([sys.executable, "run_migrations.py"], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("Database migrations completed successfully")
        else:
            logger.error(f"Migration failed: {result.stderr}")
            raise Exception(f"Migration failed: {result.stderr}")
    except Exception as e:
        logger.error(f"Failed to run migrations: {str(e)}", exc_info=True)
        raise

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Silence all SQLAlchemy logging
for logger_name in [
    'sqlalchemy',
    'sqlalchemy.engine',
    'sqlalchemy.engine.base.Engine',
    'sqlalchemy.pool',
    'sqlalchemy.dialects',
    'sqlalchemy.orm'
]:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

async def get_table_names(conn):
    """Helper function to get table names using run_sync"""
    def _get_tables(connection):
        inspector = inspect(connection)
        return inspector.get_table_names()
    return await conn.run_sync(_get_tables)

async def create_default_system_message(session, admin_id):
    """Helper function to create default system message"""
    default_system_message = SystemMessage(
        name="Default System Message",
        content="You are a knowledgeable assistant that specializes in critical thinking and analysis.",
        description="Default system message for the application",
        model_name="gpt-3.5-turbo",
        temperature=0.7,
        created_by=admin_id
    )
    try:
        session.add(default_system_message)
        await session.commit()
        logger.info("Default system message created")
    except Exception as e:
        logger.error("Failed to create default system message", exc_info=True)
        await session.rollback()

async def ensure_root_folders(session):
    """Ensure all users have a root folder"""
    try:
        # Get all users
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        for user in users:
            # Check if user already has a root folder
            result = await session.execute(
                select(Folder).where(
                    Folder.user_id == user.id,
                    Folder.path == Ltree('0')
                )
            )
            root_folder = result.scalar_one_or_none()
            
            if not root_folder:
                # Create root folder
                root_folder = Folder(
                    name="Root",
                    path=Ltree('0'),
                    user_id=user.id
                )
                session.add(root_folder)
                logger.info(f"Created root folder for user {user.username}")
        
        await session.commit()
        logger.info("Root folders check completed")
    except Exception as e:
        logger.error(f"Failed to ensure root folders: {str(e)}", exc_info=True)
        await session.rollback()

async def init_db():
    load_dotenv()
    logger.info("Initializing database...")

    try:
        async with engine.begin() as conn:
            # Ensure ltree extension is installed
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS ltree"))
            logger.info("Ltree extension check completed")
            
            tables = await get_table_names(conn)
            logger.info("Database connection established")

            if not tables:
                # If no tables exist, create them and run migrations
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Database tables created")
                await run_migrations()

                ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME')
                ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
                
                if ADMIN_USERNAME and ADMIN_PASSWORD:
                    async with get_session() as session:
                        new_admin = User(
                            username=ADMIN_USERNAME,
                            email="admin@backup.com",
                            password_hash=generate_password_hash(ADMIN_PASSWORD, method='pbkdf2:sha256'),
                            is_admin=True,
                            status="Active"
                        )
                        try:
                            session.add(new_admin)
                            await session.commit()
                            logger.info("Admin user created")
                            
                            # Create root folder for admin
                            root_folder = Folder(
                                name="Root",
                                path=Ltree('0'),
                                user_id=new_admin.id
                            )
                            session.add(root_folder)
                            await session.commit()
                            logger.info("Admin root folder created")
                            
                            await create_default_system_message(session, new_admin.id)
                        except Exception as e:
                            logger.error("Failed to create admin user", exc_info=True)
                            await session.rollback()
            else:
                # If tables exist, just run migrations to catch up
                await run_migrations()

                async with get_session() as session:
                    # Ensure all users have root folders
                    await ensure_root_folders(session)
                    
                    result = await session.execute(
                        select(SystemMessage).filter_by(name="Default System Message")
                    )
                    if not result.scalar_one_or_none():
                        result = await session.execute(select(User).filter_by(is_admin=True))
                        admin_user = result.scalars().first()
                        if admin_user:
                            await create_default_system_message(session, admin_user.id)
                        else:
                            logger.warning("No admin user found")


        logger.info("Database initialization completed")

    except Exception as e:
        logger.error("Database initialization failed", exc_info=True)
        raise

if __name__ == '__main__':
    asyncio.run(init_db())