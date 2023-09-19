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

    def __repr__(self):
        return '<Conversation %r>' % self.title

class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)  # Unique ID for the user
    username = db.Column(db.String(80), unique=True, nullable=False)  # Unique username for the user
    email = db.Column(db.String(120), unique=True, nullable=False)  # Unique email address for the user
    password_hash = db.Column(db.String(128))  # Hashed password for the user
    conversations = db.relationship('Conversation', backref='user', lazy=True)  # Relationship to the Conversation model

    def __repr__(self):
        return '<User %r>' % self.username
