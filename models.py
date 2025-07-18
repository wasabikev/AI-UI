# Modles.py

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text, Index, text, event # Ensure Boolean is imported
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy_utils import LtreeType
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

# Create async engine with logging disabled
engine = create_async_engine(
    db_url,
    echo=False,
    echo_pool=False,
    pool_pre_ping=True,
    pool_size=2,  # Reduced from 5
    max_overflow=3,  # Reduced from 10
    pool_timeout=30,
    pool_recycle=1800,  # Add connection recycling every 30 minutes
    logging_name=None,
    hide_parameters=True,
    pool_logging_name=None,
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
            # First, ensure ltree extension is installed
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS ltree"))

            # Test connection
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
    name = Column(String(120), nullable=False)
    path = Column(LtreeType, nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), 
                       default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="folders")
    conversations = relationship("Conversation", back_populates="folder", lazy="selectin")

    __table_args__ = (
        # GiST index for efficient hierarchical queries
        Index('ix_folder_path_gist', path, postgresql_using='gist'),
        # Index for user's folders
        Index('ix_folder_user_id', user_id),
    )

    def __repr__(self):
        return f"<Folder(id={self.id}, name='{self.name}', path='{self.path}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'path': str(self.path),
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Conversation(Base):
    __tablename__ = 'conversation'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    history = Column(JSON)
    token_count = Column(Integer, default=0)
    folder_id = Column(Integer, ForeignKey('folder.id'), nullable=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True),
                       default=lambda: datetime.now(timezone.utc),
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

    # Relationship to UploadedFile
    uploaded_files = relationship('UploadedFile', back_populates='conversation', cascade='all, delete-orphan', lazy='dynamic')

    # Update relationship to use back_populates instead of backref
    user = relationship("User", back_populates="conversations")
    folder = relationship("Folder", back_populates="conversations")

    def __repr__(self):
        return f'<Conversation {self.title}>'

    def to_dict(self):
        # Base dictionary
        data = {
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
        # Note: uploaded_files is not included by default due to lazy='dynamic'
        # It needs to be queried separately if needed in the dict representation.
        return data


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128))
    is_admin = Column(Boolean, default=False)
    status = Column(String(20), default="Pending")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), 
                       default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime(timezone=True))

    # Update relationships to use back_populates
    conversations = relationship('Conversation', back_populates='user', lazy='selectin')
    folders = relationship('Folder', back_populates='user', cascade='all, delete-orphan')
    usage = relationship('UserUsage', back_populates='user')
    created_system_messages = relationship('SystemMessage', back_populates='creator')
    uploaded_files = relationship('UploadedFile', back_populates='user') # Relationship to UploadedFile

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
    session_start = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    session_end = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    cost = Column(Float)

    # Update to use back_populates
    user = relationship('User', back_populates='usage')

class SystemMessage(Base):
    __tablename__ = 'system_message'

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    content = Column(Text, nullable=False)
    description = Column(Text)
    model_name = Column(String(120))
    temperature = Column(Float)
    created_by = Column(Integer, ForeignKey('user.id'))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True),
                       default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))
    source_config = Column(JSON)
    enable_web_search = Column(Boolean, default=False)
    enable_deep_search = Column(Boolean, default=False)
    enable_time_sense = Column(Boolean, default=False)

    # Update relationships to use back_populates
    uploaded_files = relationship('UploadedFile', back_populates='system_message', # Relationship to UploadedFile
                                cascade='all, delete-orphan')
    creator = relationship('User', back_populates='created_system_messages')
    websites = relationship('Website', back_populates='system_message', cascade='all, delete-orphan')

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
            'enable_deep_search': self.enable_deep_search,
            'enable_time_sense': self.enable_time_sense,
        }

class Website(Base):
    __tablename__ = 'website'

    id = Column(Integer, primary_key=True)
    url = Column(String(2048), nullable=False)
    site_metadata = Column(JSON)
    system_message_id = Column(Integer, ForeignKey('system_message.id', ondelete='CASCADE'),
                             nullable=False)
    indexed_at = Column(DateTime(timezone=True))
    indexing_status = Column(String(50), default='Pending')
    last_error = Column(Text)
    indexing_frequency = Column(Integer, nullable=True, default=None)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True),
                       default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))

    # Update to use back_populates
    system_message = relationship('SystemMessage', back_populates='websites')

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

    # --- Core Fields ---
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False) # Path to the original uploaded file
    processed_text_path = Column(String(255), nullable=True) # Path to the processed text (e.g., from LLMWhisperer)
    upload_timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    file_size = Column(Integer)
    mime_type = Column(String(100))

    # --- Linkage Fields ---
    # Link to SystemMessage (for RAG context) - Optional
    system_message_id = Column(Integer, ForeignKey('system_message.id'), nullable=True)
    # Link to Conversation (for message attachments) - Optional
    conversation_id = Column(Integer, ForeignKey('conversation.id'), nullable=True)

    # --- Status & Metadata Fields ---
    # Tracks the status of file processing (e.g., 'pending', 'processing', 'completed', 'failed')
    processing_status = Column(String(50), default='pending', nullable=False)
    # Stores the estimated token count after processing. Nullable initially.
    token_count = Column(Integer, nullable=True)
    # Flags if the file is a temporary upload (True) or permanently associated (False).
    is_temporary = Column(Boolean, default=True, nullable=False)

    # --- Relationships ---
    # Relationship back to the User who uploaded the file
    user = relationship('User', back_populates='uploaded_files')
    # Relationship back to the SystemMessage (if linked)
    system_message = relationship('SystemMessage', back_populates='uploaded_files')
    # Relationship back to the Conversation (if linked)
    conversation = relationship('Conversation', back_populates='uploaded_files')

    def __repr__(self):
        # Updated repr to show temporary status and linkage
        status = "Temp" if self.is_temporary else "Perm"
        linked_to = f"Conv:{self.conversation_id}" if self.conversation_id else f"SysMsg:{self.system_message_id}" if self.system_message_id else "None"
        return f'<UploadedFile {self.original_filename} ({status}, {linked_to})>'

    # Update to_dict method to include new fields
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'system_message_id': self.system_message_id,
            'conversation_id': self.conversation_id,
            'original_filename': self.original_filename,
            'file_path': self.file_path,
            'processed_text_path': self.processed_text_path,
            'upload_timestamp': self.upload_timestamp.isoformat() if self.upload_timestamp else None,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'processing_status': self.processing_status,
            'token_count': self.token_count,
            'is_temporary': self.is_temporary
        }
