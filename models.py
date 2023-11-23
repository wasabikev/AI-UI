from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

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
    code_abstracts = db.relationship('CodeAbstract', backref='conversation', lazy=True)
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

class CodeAbstract(db.Model):
    __tablename__ = 'codeabstract'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    code_abstract = db.Column(db.Text, nullable=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    file_type = db.Column(db.String(50))

class ChangesLog(db.Model):
    __tablename__ = 'changeslog'

    id = db.Column(db.Integer, primary_key=True)
    abstract_id = db.Column(db.Integer, db.ForeignKey('codeabstract.id'), nullable=False)
    change_description = db.Column(db.Text, nullable=True)
    change_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    change_type = db.Column(db.String(50))
   
class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)  # Unique ID for the user
    username = db.Column(db.String(80), unique=True, nullable=False)  # Unique username for the user
    email = db.Column(db.String(120), unique=True, nullable=False)  # Unique email address for the user
    password_hash = db.Column(db.String(128))  # Hashed password for the user
    conversations = db.relationship('Conversation', backref='user', lazy=True)  # Relationship to the Conversation model

    def __repr__(self):
        return '<User %r>' % self.username
