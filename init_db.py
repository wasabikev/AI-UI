# init_db.py
from models import get_session, engine, Base, User, SystemMessage
from werkzeug.security import generate_password_hash
import os
from dotenv import load_dotenv
from sqlalchemy import inspect, select
import asyncio
import logging
import sqlalchemy

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

async def init_db():
    load_dotenv()
    logger.info("Initializing database...")

    try:
        async with engine.begin() as conn:
            tables = await get_table_names(conn)
            logger.info("Database connection established")

            if not tables:
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Database tables created")

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
                            await create_default_system_message(session, new_admin.id)
                        except Exception as e:
                            logger.error("Failed to create admin user", exc_info=True)
                            await session.rollback()
            else:
                async with get_session() as session:
                    result = await session.execute(
                        select(SystemMessage).filter_by(name="Default System Message")
                    )
                    if not result.scalar_one_or_none():
                        result = await session.execute(select(User).filter_by(is_admin=True))
                        admin_user = result.scalar_one_or_none()
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