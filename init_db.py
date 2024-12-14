from flask import Flask
from models import db, User, SystemMessage
from werkzeug.security import generate_password_hash
import os
from dotenv import load_dotenv
from sqlalchemy import inspect

def init_db():
    # Load environment variables from .env file
    load_dotenv()

    # Create a minimal Flask app just for database initialization
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')  
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the database
    db.init_app(app)
    
    with app.app_context():
        # Check if tables exist
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if not tables:
            # Only create tables if database is empty
            db.create_all()
            print("Database tables created successfully")

            # Create admin user only in empty database
            ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME')
            ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
            ADMIN_EMAIL = "admin@backup.com"

            admin_user = User.query.filter_by(username=ADMIN_USERNAME).first()
            if not admin_user and ADMIN_USERNAME and ADMIN_PASSWORD:
                simple_hash = generate_password_hash(ADMIN_PASSWORD, method='pbkdf2:sha256')
                new_admin = User(
                    username=ADMIN_USERNAME,
                    email=ADMIN_EMAIL,
                    password_hash=simple_hash,
                    is_admin=True,
                    status="Active"
                )
                try:
                    db.session.add(new_admin)
                    db.session.commit()
                    print("Admin user created successfully")

                    # Create default system message after admin user is created
                    default_system_message = SystemMessage(
                        name="Default System Message",
                        content="You are a knowledgeable assistant that specializes in critical thinking and analysis.",
                        description="Default system message for the application",
                        model_name="gpt-3.5-turbo",
                        temperature=0.7,
                        created_by=new_admin.id  # Use the newly created admin's ID
                    )
                    try:
                        db.session.add(default_system_message)
                        db.session.commit()
                        print("Default system message created successfully")
                    except Exception as e:
                        print(f"Error creating default system message: {e}")
                        db.session.rollback()

                except Exception as e:
                    print(f"Error creating admin user: {e}")
                    db.session.rollback()
        else:
            print("Database tables already exist, checking for default system message...")
            
            # Check for default system message even if tables exist
            with app.app_context():
                default_message = SystemMessage.query.filter_by(name="Default System Message").first()
                if not default_message:
                    admin_user = User.query.filter_by(is_admin=True).first()
                    if admin_user:
                        default_system_message = SystemMessage(
                            name="Default System Message",
                            content="You are a knowledgeable assistant that specializes in critical thinking and analysis.",
                            description="Default system message for the application",
                            model_name="gpt-3.5-turbo",
                            temperature=0.7,
                            created_by=admin_user.id
                        )
                        try:
                            db.session.add(default_system_message)
                            db.session.commit()
                            print("Default system message created successfully")
                        except Exception as e:
                            print(f"Error creating default system message: {e}")
                            db.session.rollback()
                    else:
                        print("No admin user found, skipping default system message creation")
                else:
                    print("Default system message already exists")

if __name__ == '__main__':
    init_db()