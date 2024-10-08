from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from flask_bcrypt import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import JSON  # Import JSON support
from sqlalchemy import Boolean

import uuid

db = SQLAlchemy()

class Folder(db.Model): # Folder is a table in the database
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    conversations = db.relationship('Conversation', backref='folder', lazy=True)

class Conversation(db.Model): 
    __tablename__ = 'conversation'

    id = db.Column(db.Integer, primary_key=True)    # Primary key for the conversation
    title = db.Column(db.String)    # Title of the conversation
    history = db.Column(db.JSON)    # History of the conversation in JSON format
    token_count = db.Column(db.Integer, default=0)    # Token count of the conversation
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)    # ID of the folder that the conversation belongs to
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)    # ID of the user who initiated the conversation
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))    # Time when the conversation was created
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))    # Time when the conversation was last updated
    model_name = db.Column(db.String(120))    # Name of the AI model used for the conversation
    sentiment = db.Column(db.String(120))    # Overall sentiment of the conversation (positive, neutral, negative)
    tags = db.Column(db.String(120))    # Any tags associated with the conversation
    language = db.Column(db.String(120))    # Language of the conversation
    status = db.Column(db.String(120))    # Status of the conversation (active, archived, deleted, etc.)
    rating = db.Column(db.Integer)    # User's rating of the conversation (if any)
    confidence = db.Column(db.Float)    # AI model's confidence score for the conversation
    intent = db.Column(db.String(120))    # Intent recognized in the conversation (if any)
    entities = db.Column(db.JSON)    # Entities recognized in the conversation (if any)
    temperature = db.Column(db.Float)    # Temperature setting for the conversation
    prompt_template = db.Column(db.String(500))    # Template of the prompt used in the conversation
    vector_search_results = db.Column(db.JSON)  # Store vector search results for each message
    generated_search_queries = db.Column(db.JSON)  # Store generated search queries for each message
    web_search_results = db.Column(db.JSON)  # Store web search results for each message

    def __repr__(self):
        return '<Conversation %r>' % self.title
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'history': self.history,
            'token_count': self.token_count,
            'folder_id': self.folder_id,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
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
            # Add other fields as necessary
        }

class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default="Pending")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)
    conversations = db.relationship('Conversation', backref='user', lazy=True)

    # Additional methods...


    def __repr__(self):
        return '<User %r>' % self.username
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class UserUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    api_used = db.Column(db.String(50))
    tokens_used = db.Column(db.Integer)
    session_start = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    session_end = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    cost = db.Column(db.Float)

    user = db.relationship('User', backref='usage')
 
class SystemMessage(db.Model):
    __tablename__ = 'system_message'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)  # Description of the system message
    model_name = db.Column(db.String(120))  # Model associated with the system message
    temperature = db.Column(db.Float)  # Temperature setting for the system message
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # Foreign key to the user table
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    source_config = db.Column(JSON)  # Field for storing RAG source configurations
    enable_web_search = db.Column(db.Boolean, default=False)  # Field for enabling web search
    uploaded_files = db.relationship('UploadedFile', back_populates='system_message', cascade='all, delete-orphan')

    creator = db.relationship('User', backref='created_system_messages')  # Relationship to the user table

    def __repr__(self):
        return '<SystemMessage %r>' % self.name

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'content': self.content,
            'description': self.description,
            'model_name': self.model_name,
            'temperature': self.temperature,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'source_config': self.source_config,
            'enable_web_search': self.enable_web_search,  
        }

class Website(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(2048), nullable=False, index=True)  # Added index for better performance on queries
    site_metadata = db.Column(db.JSON)  # Renamed to avoid conflict with SQLAlchemy reserved keyword
    system_message_id = db.Column(db.Integer, db.ForeignKey('system_message.id', ondelete='CASCADE'), nullable=False)
    indexed_at = db.Column(db.DateTime)
    indexing_status = db.Column(db.String(50), default='Pending')
    last_error = db.Column(db.Text)
    indexing_frequency = db.Column(db.Integer, nullable=True, default=None)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    system_message = db.relationship('SystemMessage', backref=db.backref('websites', lazy=True, cascade="all, delete-orphan"))

    def __repr__(self):
        return '<Website %r>' % self.url
    
    def to_dict(self):
        return {
            'id': self.id,
            'url': self.url,
            'site_metadata': self.site_metadata,  # Updated field name here as well
            'indexing_status': self.indexing_status,
            'indexed_at': self.indexed_at.isoformat() if self.indexed_at else None,
            'last_error': self.last_error,
            'indexing_frequency': self.indexing_frequency,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class UploadedFile(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    processed_text_path = db.Column(db.String(255))
    upload_timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    system_message_id = db.Column(db.Integer, db.ForeignKey('system_message.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('uploaded_files', lazy=True))
    system_message = db.relationship('SystemMessage', back_populates='uploaded_files')

    def __repr__(self):
        return f'<UploadedFile {self.original_filename}>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'original_filename': self.original_filename,
            'file_path': self.file_path,
            'processed_text_path': self.processed_text_path,
            'upload_timestamp': self.upload_timestamp.isoformat(),
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'system_message_id': self.system_message_id
        }