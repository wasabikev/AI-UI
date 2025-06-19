"""
Migration: Add enable_deep_search column to system_message table
"""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_migration():
    """Add enable_deep_search column to system_message table if it doesn't exist"""
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    # Create async engine
    engine = create_async_engine(database_url, echo=True)
    
    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            logger.info("Starting migration: Add enable_deep_search column")
            
            # Check if column already exists
            check_column_sql = text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'system_message' 
                    AND column_name = 'enable_deep_search'
                );
            """)
            
            result = await session.execute(check_column_sql)
            column_exists = result.scalar()
            
            if column_exists:
                logger.info("Column enable_deep_search already exists, skipping migration")
                return
            
            # Add the column
            add_column_sql = text("""
                ALTER TABLE system_message 
                ADD COLUMN enable_deep_search BOOLEAN DEFAULT FALSE;
            """)
            
            await session.execute(add_column_sql)
            await session.commit()
            
            logger.info("Successfully added enable_deep_search column to system_message table")
            
            # Verify the column was added
            verify_result = await session.execute(check_column_sql)
            if verify_result.scalar():
                logger.info("Migration verified successfully")
            else:
                logger.error("Migration verification failed")
                
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_migration())
