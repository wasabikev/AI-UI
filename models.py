from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_bcrypt import generate_password_hash, check_password_hash
from flask_login import UserMixin

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)    # Time when the conversation was created
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)    # Time when the conversation was last updated
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
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
    session_start = db.Column(db.DateTime)
    session_end = db.Column(db.DateTime)
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
        }

