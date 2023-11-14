class Conversation(db.Model): 
    ...
    code_abstracts = db.relationship('CodeAbstract', backref='conversation', lazy=True)
    ...

class CodeAbstract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    code_abstract = db.Column(db.Text, nullable=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    file_type = db.Column(db.String(50))

class ChangesLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    abstract_id = db.Column(db.Integer, db.ForeignKey('codeabstract.id'), nullable=False)
    change_description = db.Column(db.Text, nullable=True)
    change_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    change_type = db.Column(db.String(50))

Users Table (If you don't have one):

user_id (Primary Key): Unique identifier for each user.
username: Unique username of the user.
password_hash: Hashed password for user authentication.
email: Email of the user (optional).
Other fields like registration_date, last_login, etc.