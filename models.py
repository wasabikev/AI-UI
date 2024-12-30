# models.py 
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text, Index, text, event
from sqlalchemy.dialects.postgresql import JSON
from quart_auth import AuthUser
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse
import uuid
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import logging

# Configure SQLAlchemy logging before anything else
def configure_sqlalchemy_logging():
    """Configure SQLAlchemy to minimize logging output"""
    for logger_name in [
        'sqlalchemy',
        'sqlalchemy.engine',
        'sqlalchemy.engine.base.Engine',
        'sqlalchemy.dialects',
        'sqlalchemy.pool',
        'sqlalchemy.orm',
        'sqlalchemy.engine.base',
        'sqlalchemy.engine.impl',
        'sqlalchemy.engine.logger',
    ]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.ERROR)
        logger.propagate = False
        # Remove any existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

# Call the configuration function before creating the engine
configure_sqlalchemy_logging()

# Load environment variables
load_dotenv(override=True)

db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise ValueError("DATABASE_URL environment variable is not set")

print("DEBUG in models.py: final db_url =", db_url)


# Create async engine with logging disabled
engine = create_async_engine(
    db_url,
    echo=False,  # Disable SQL logging
    echo_pool=False,  # Disable connection pool logging
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    logging_name=None,  # Disable logging name
    hide_parameters=True,  # Hide SQL parameters in logs
    pool_logging_name=None,  # Disable pool logging name
    future=True
)

# Create async session factory
async_session = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Create declarative base
Base = declarative_base()

# Session context manager
@asynccontextmanager
async def get_session():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise
        finally:
            await session.close()


# Test the database connection
async def test_db_connection():
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"Database connection successful! PostgreSQL version: {version}")
            await conn.commit()
            return True
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        return False
    finally:
        await engine.dispose()

class Folder(Base):
    __tablename__ = 'folder'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(120), nullable=False)
    conversations = relationship('Conversation', backref='folder', lazy='selectin')

class Conversation(Base):
    __tablename__ = 'conversation'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    history = Column(JSON)
    token_count = Column(Integer, default=0)
    folder_id = Column(Integer, ForeignKey('folder.id'), nullable=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), 
                       onupdate=lambda: datetime.now(timezone.utc))
    model_name = Column(String(120))
    sentiment = Column(String(120))
    tags = Column(String(120))
    language = Column(String(120))
    status = Column(String(120))
    rating = Column(Integer)
    confidence = Column(Float)
    intent = Column(String(120))
    entities = Column(JSON)
    temperature = Column(Float)
    prompt_template = Column(String(500))
    vector_search_results = Column(JSON)
    generated_search_queries = Column(JSON)
    web_search_results = Column(JSON)

    def __repr__(self):
        return f'<Conversation {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'history': self.history,
            'token_count': self.token_count,
            'folder_id': self.folder_id,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'model_name': self.model_name,
            'sentiment': self.sentiment,
            'tags': self.tags,
            'language': self.language,
            'status': self.status,
            'rating': self.rating,
            'confidence': self.confidence,
            'intent': self.intent,
            'entities': self.entities,
            'temperature': self.temperature,
            'prompt_template': self.prompt_template,
            'vector_search_results': self.vector_search_results,
            'generated_search_queries': self.generated_search_queries,
            'web_search_results': self.web_search_results,
        }


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128))
    is_admin = Column(Boolean, default=False)
    status = Column(String(20), default="Pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime)
    conversations = relationship('Conversation', backref='user', lazy='selectin')

    def __repr__(self):
        return f'<User {self.username}>'
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class UserUsage(Base):
    __tablename__ = 'user_usage'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    api_used = Column(String(50))
    tokens_used = Column(Integer)
    session_start = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    session_end = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    cost = Column(Float)

    user = relationship('User', backref='usage')

class SystemMessage(Base):
    __tablename__ = 'system_message'

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    content = Column(Text, nullable=False)
    description = Column(Text)
    model_name = Column(String(120))
    temperature = Column(Float)
    created_by = Column(Integer, ForeignKey('user.id'))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))
    source_config = Column(JSON)
    enable_web_search = Column(Boolean, default=False)
    uploaded_files = relationship('UploadedFile', back_populates='system_message',
                                cascade='all, delete-orphan')
    creator = relationship('User', backref='created_system_messages')

    def __repr__(self):
        return f'<SystemMessage {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'content': self.content,
            'description': self.description,
            'model_name': self.model_name,
            'temperature': self.temperature,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'source_config': self.source_config,
            'enable_web_search': self.enable_web_search,
        }

class Website(Base):
    __tablename__ = 'website'

    id = Column(Integer, primary_key=True)
    url = Column(String(2048), nullable=False)
    site_metadata = Column(JSON)
    system_message_id = Column(Integer, ForeignKey('system_message.id', ondelete='CASCADE'),
                             nullable=False)
    indexed_at = Column(DateTime)
    indexing_status = Column(String(50), default='Pending')
    last_error = Column(Text)
    indexing_frequency = Column(Integer, nullable=True, default=None)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))

    system_message = relationship('SystemMessage', backref='websites')
    
    # Add index for URL field
    __table_args__ = (Index('idx_website_url', url),)

    def __repr__(self):
        return f'<Website {self.url}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'url': self.url,
            'site_metadata': self.site_metadata,
            'indexing_status': self.indexing_status,
            'indexed_at': self.indexed_at.isoformat() if self.indexed_at else None,
            'last_error': self.last_error,
            'indexing_frequency': self.indexing_frequency,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class UploadedFile(Base):
    __tablename__ = 'uploaded_file'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    processed_text_path = Column(String(255))
    upload_timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    file_size = Column(Integer)
    mime_type = Column(String(100))
    system_message_id = Column(Integer, ForeignKey('system_message.id'), nullable=False)

    user = relationship('User', backref='uploaded_files')
    system_message = relationship('SystemMessage', back_populates='uploaded_files')

    def __repr__(self):
        return f'<UploadedFile {self.original_filename}>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'original_filename': self.original_filename,
            'file_path': self.file_path,
            'processed_text_path': self.processed_text_path,
            'upload_timestamp': self.upload_timestamp.isoformat() if self.upload_timestamp else None,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'system_message_id': self.system_message_id
        }