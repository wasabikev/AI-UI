from flask import Flask, request, jsonify, render_template, url_for, redirect, session, abort
from flask_cors import CORS
from text_processing import format_text
from flask_login import LoginManager, current_user, login_required
from logging.handlers import RotatingFileHandler


from dotenv import load_dotenv
load_dotenv()

# Dependencies for database
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

import openai
import os
import logging
import anthropic
import tiktoken 
import google.generativeai as genai
import subprocess # imported to support Scrapy

import requests
import json

from models import db, Folder, Conversation, User, SystemMessage, Website, UploadedFile
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler # for log file rotation
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename # for secure file uploads
from google.generativeai import GenerativeModel

# Imports for file uploads
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from file_processing import FileProcessor
from embedding_store import EmbeddingStore
from pinecone import Pinecone

from openai import OpenAI
client = OpenAI()

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")
if openai.api_key is None:
    raise ValueError("OPENAI_API_KEY environment variable not set")

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
db_url = os.getenv('DATABASE_URL')

BRAVE_SEARCH_API_KEY = os.getenv('BRAVE_SEARCH_API_KEY')

embedding_store = EmbeddingStore(db_url)
file_processor = FileProcessor(embedding_store)

from auth import auth as auth_blueprint  # Import the auth blueprint
  
# Set debug directly here. Switch to False for production.
debug_mode = True

# Configure logging
logging.basicConfig(level=logging.DEBUG if debug_mode else logging.INFO)
handler = RotatingFileHandler("app.log", maxBytes=100000, backupCount=3)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO if debug_mode else logging.WARNING)
console_handler.setFormatter(formatter)

# Application Setup
app = Flask(__name__)
CORS(app)  # Cross-Origin Resource Sharing
app.config['DEBUG'] = debug_mode

# Add handlers to the app's logger
app.logger.addHandler(handler)
app.logger.addHandler(console_handler)

# Ensure that all log messages are propagated to the app's logger
app.logger.propagate = False

app.register_blueprint(auth_blueprint)  # Registers auth with Flask application

# Enable auto-reload of templates
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Set up database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Secret key for session handling
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') 

# Initialize database
db.init_app(app)
migrate = Migrate(app, db)

app.logger.info("Logging is set up.")

# Set up file upload folder
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}

# Ensure upload folder exists
try:
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
except OSError as e:
    print(f"Error creating upload folder: {e}")
    

# Initialize the login manager
login_manager = LoginManager()
login_manager.init_app(app)

def check_if_web_search_needed(ai_response):
    # This is a simple check. You might want to use a more sophisticated method.
    search_indicators = [
        "I would need to search the web",
        "I don't have up-to-date information",
        "I would need to look that up",
        "I don't have current data on that",
        "To answer that, I'd need to check"
    ]
    return any(indicator.lower() in ai_response.lower() for indicator in search_indicators)

def perform_web_search(query):
    url = 'https://api.search.brave.com/res/v1/web/search'
    headers = {
        'Accept': 'application/json',
        'X-Subscription-Token': BRAVE_SEARCH_API_KEY
    }
    params = {
        'q': query,
        'count': 5  # Limit to 5 results
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        results = response.json()
        
        # Process and format the results
        formatted_results = []
        for result in results.get('web', {}).get('results', []):
            formatted_results.append(f"Title: {result['title']}\nURL: {result['url']}\nDescription: {result['description']}\n")
        
        return "\n".join(formatted_results)
    except requests.RequestException as e:
        app.logger.error(f'Error performing Brave search: {str(e)}')
        return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/system-messages/<int:system_message_id>/toggle-web-search', methods=['POST'])
@login_required
def toggle_web_search(system_message_id):
    data = request.json
    enable_web_search = data.get('enableWebSearch')
    
    system_message = SystemMessage.query.get_or_404(system_message_id)
    system_message.enable_web_search = enable_web_search
    db.session.commit()
    
    return jsonify({'message': 'Web search setting updated successfully'}), 200

@app.route('/query_documents', methods=['POST'])
@login_required
def query_documents():
    query = request.json.get('query')
    file_processor = FileProcessor(embedding_store)
    results = file_processor.query_index(query)
    return jsonify({'results': results})

@app.route('/upload_file', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'})
    
    file = request.files['file']
    system_message_id = request.form.get('system_message_id')
    
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'})
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Create a new UploadedFile record
        new_file = UploadedFile(
            filename=filename,
            file_path=file_path,
            system_message_id=system_message_id
        )
        
        # Add and commit the new file to the database to get the id
        db.session.add(new_file)
        db.session.commit()
        
        try:
            # Get the storage context for this system message
            storage_context = embedding_store.get_storage_context(system_message_id)
            
            # Process and index the file
            index = file_processor.process_file(file_path, storage_context, new_file.id)
            app.logger.info("File processed successfully")
        except Exception as e:
            app.logger.error(f"Error processing file: {str(e)}")
            return jsonify({'success': False, 'error': f'Error processing file: {str(e)}'})
        
        return jsonify({'success': True, 'message': 'File uploaded and indexed successfully'})
    
    return jsonify({'success': False, 'error': 'File type not allowed'})

@app.route('/get_files/<int:system_message_id>')
@login_required
def get_files(system_message_id):
    try:
        files = UploadedFile.query.filter_by(system_message_id=system_message_id).all()
        file_list = [{'id': file.id, 'filename': file.filename} for file in files]
        return jsonify({'success': True, 'files': file_list})
    except Exception as e:
        app.logger.error(f"Error fetching files: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
@app.route('/remove_file/<int:file_id>', methods=['DELETE'])
@login_required
def remove_file(file_id):
    file = UploadedFile.query.get_or_404(file_id)
    
    try:
        # Get the system message ID associated with this file
        system_message_id = file.system_message_id

        # Get the storage context for this system message
        storage_context = embedding_store.get_storage_context(system_message_id)

        # Remove the file's content from the vector store
        vector_store = storage_context.vector_store
        
        # Get the namespace for this system message
        namespace = embedding_store.generate_namespace(system_message_id)
        
        # Delete vectors for the file
        delete_vectors_for_file(vector_store, file.id, namespace)

        # Remove the file from the filesystem
        if os.path.exists(file.file_path):
            os.remove(file.file_path)
        
        # Remove the file record from the database
        db.session.delete(file)
        db.session.commit()
        
        app.logger.info(f"File {file_id} removed successfully from filesystem, database, and vector store.")
        return jsonify({'success': True, 'message': 'File removed successfully'})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error removing file {file_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
def delete_vectors_for_file(vector_store, file_id, namespace):
    try:
        # Get the Pinecone index from the vector store
        pinecone_index = vector_store._pinecone_index

        # Query for vectors related to this file
        query_response = pinecone_index.query(
            namespace=namespace,
            vector=[0] * 1536,  # Dummy vector of zeros
            # This query is a workaround for Serverless and Starter Pinecone indexes, which don't support
            # metadata filtering during deletion. We're fetching a large number of vectors and filtering
            # them client-side to find those associated with the file we want to delete. (higher values may slow down the query).
            top_k=10000,  # Adjust this value based on your needs
            include_metadata=True
        )

        # Filter the results to only include vectors with matching file_id
        vector_ids = [
            match.id for match in query_response.matches 
            if match.metadata.get('file_id') == str(file_id)
        ]

        if vector_ids:
            # Delete the vectors
            delete_response = pinecone_index.delete(ids=vector_ids, namespace=namespace)
            app.logger.info(f"Deleted {len(vector_ids)} vectors for file ID: {file_id}. Delete response: {delete_response}")
        else:
            app.logger.warning(f"No vectors found for file ID: {file_id}")
    except Exception as e:
        app.logger.error(f"Error deleting vectors for file ID {file_id}: {str(e)}")
        raise

@app.route('/health')
def health_check():
    return 'OK', 200

@app.route('/get-website/<int:website_id>', methods=['GET'])
@login_required
def get_website(website_id):
    app.logger.debug(f"Attempting to fetch website with ID: {website_id}")
    try:
        query = Website.query.get(website_id)
        app.logger.debug(f"Query executed: {query}")  # Log the actual query object
        website = query
        if not website:
            app.logger.warning(f"No website found with ID: {website_id}")
            return jsonify({'error': 'Website not found'}), 404
        app.logger.debug(f"Website data: {website.to_dict()}")
        return jsonify({'website': website.to_dict()}), 200
    except Exception as e:
        app.logger.error(f"Exception occurred: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/test-website', methods=['GET'])
@login_required
def test_website():
    return jsonify({'message': 'Route is working'}), 200

@app.route('/index-website', methods=['POST'])
@login_required
def index_website():
    data = request.get_json()
    app.logger.debug(f"Received indexing request with data: {data}")
    url = data.get('url')
    if not url:
        app.logger.error("URL is missing from request data")
        return jsonify({'success': False, 'message': 'URL is required'}), 400

    allowed_domain = data.get('allowed_domain', '')
    custom_settings = data.get('custom_settings', {})

    # Run Scrapy spider
    process = subprocess.Popen(
        ['scrapy', 'runspider', 'webscraper/spiders/flexible_spider.py',
         '-a', f'url={url}', '-a', f'allowed_domain={allowed_domain}',
         '-a', f'custom_settings={json.dumps(custom_settings)}'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()

    stdout_decoded = stdout.decode('utf-8', errors='replace')
    stderr_decoded = stderr.decode('utf-8', errors='replace')
    app.logger.debug("STDOUT: %s", stdout_decoded)
    app.logger.debug("STDERR: %s", stderr_decoded)

    if process.returncode != 0:
        app.logger.error("Scraping failed with error: %s", stderr_decoded)
        return jsonify({'success': False, 'message': 'Error during scraping', 'error': stderr_decoded}), 500

    if stdout_decoded:
        try:
            scraped_content = json.loads(stdout_decoded)
            if 'content' in scraped_content:
                return jsonify({'success': True, 'message': 'Website indexed successfully', 'content': scraped_content['content']}), 200
            else:
                app.logger.error("Expected key 'content' not found in JSON output")
                return jsonify({'success': False, 'message': 'Expected data not found in the scraped output'}), 500
        except json.JSONDecodeError as e:
            app.logger.error("Error decoding JSON from scraping output: %s", str(e))
            return jsonify({'success': False, 'message': 'Invalid JSON data received', 'details': stdout_decoded}), 500
    else:
        app.logger.error("No data received from spider")
        return jsonify({'success': False, 'message': 'No data received from spider'}), 500

@app.route('/scrape', methods=['POST'])
@login_required
def scrape():
    data = request.get_json()
    url = data.get('url')
    allowed_domain = data.get('allowed_domain', '')

    command = [
        'scrapy', 'runspider', 'webscraper/spiders/flexible_spider.py',
        '-a', f'url={url}', '-a', f'allowed_domain={allowed_domain}'
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        app.logger.error(f"Spider error: {stderr.decode()}")
        return jsonify({'error': 'Failed to scrape the website'}), 500

    try:
        result = json.loads(stdout.decode())
        return jsonify({'data': result['content']}), 200
    except json.JSONDecodeError:
        app.logger.error("Failed to decode JSON from spider output")
        return jsonify({'error': 'Failed to decode JSON from spider output'}), 500

@app.route('/get-websites/<int:system_message_id>', methods=['GET'])
@login_required
def get_websites(system_message_id):
    websites = Website.query.filter_by(system_message_id=system_message_id).all()
    return jsonify({'websites': [website.to_dict() for website in websites]}), 200

@app.route('/add-website', methods=['POST'])
@login_required
def add_website():
    data = request.get_json()
    url = data.get('url')
    system_message_id = data.get('system_message_id')

    if not url:
        return jsonify({'success': False, 'message': 'URL is required'}), 400

    if not system_message_id:
        return jsonify({'success': False, 'message': 'System message ID is required'}), 400

    # Validate URL format here (optional, can be done in the frontend too)
    if not url.startswith('http://') and not url.startswith('https://'):
        return jsonify({'success': False, 'message': 'Invalid URL format'}), 400

    new_website = Website(url=url, system_message_id=system_message_id)
    db.session.add(new_website)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Website added successfully', 'website': new_website.to_dict()}), 201

@app.route('/remove-website/<int:website_id>', methods=['DELETE'])
@login_required
def remove_website(website_id):
    website = Website.query.get_or_404(website_id)
    db.session.delete(website)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Website removed successfully'}), 200

@app.route('/reindex-website/<int:website_id>', methods=['POST'])
@login_required
def reindex_website(website_id):
    website = Website.query.get_or_404(website_id)
    # Trigger re-indexing logic here (e.g., update indexed_at, change status)
    website.indexed_at = datetime.now(timezone.utc)
    website.indexing_status = 'In Progress'
    db.session.commit()

    return jsonify({'message': 'Re-indexing initiated', 'website': website.to_dict()}), 200

@app.route('/generate-image', methods=['POST'])
@login_required
def generate_image():
    data = request.json
    prompt = data.get('prompt', '')

    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400

    try:
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="256x256"
        )
        image_url = response['data'][0]['url']
        return jsonify({"image_url": image_url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/view-logs')
@login_required
def view_logs():
    logs_content = "<link rel='stylesheet' type='text/css' href='/static/css/styles.css'><div class='logs-container'>"
    try:
        with open('app.log', 'r') as log_file:
            logs_content += f"<div class='log-entry'><div class='log-title'>--- app.log ---</div><pre>"
            logs_content += log_file.read() + "</pre></div>\n"
    except FileNotFoundError:
        logs_content += "<div class='log-entry'><div class='log-title'>No log file found.</div></div>"
    logs_content += "</div>"
    return logs_content

# User loader function
@login_manager.user_loader
def load_user(user_id):
    from models import User  # Import here to avoid circular dependencies
    return User.query.get(int(user_id))

# Configure authentication using your API key
genai.configure(api_key=os.environ['GOOGLE_API_KEY'])

anthropic.api_key = os.environ.get('ANTHROPIC_API_KEY')
if anthropic.api_key is None:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set")

# Backup Admin user creation logic
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') # set this in your .env file
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
ADMIN_EMAIL = "admin@backup.com" # Change this to your own email address

with app.app_context():
    # Check if the admin user exists
    admin_user = User.query.filter_by(username=ADMIN_USERNAME).first()

    if not admin_user and ADMIN_USERNAME and ADMIN_PASSWORD:
        # Create a new admin user
        hashed_password = generate_password_hash(ADMIN_PASSWORD)
        new_admin = User(username=ADMIN_USERNAME, email=ADMIN_EMAIL,
                         password_hash=hashed_password, is_admin=True, status="Active")

        try:
            db.session.add(new_admin)
            db.session.commit()
            print("Admin user created")
        except Exception as e:
            print(f"Error creating admin user: {e}")

# Default System Message creation logic
DEFAULT_SYSTEM_MESSAGE = {
    "name": "Default System Message",
    "content": "You are a knowledgeable assistant that specializes in critical thinking and analysis.",
    "description": "Default entry for database",
    "model_name": "gpt-3.5-turbo",
    "temperature": 0.3
}

@app.cli.command("init_app")
def init_app():
    """Initialize the application."""
    with app.app_context():
        # Retrieve the admin user
        admin_user = User.query.filter_by(username=ADMIN_USERNAME).first()

        # Check if the default system message exists
        default_message = SystemMessage.query.filter_by(name=DEFAULT_SYSTEM_MESSAGE["name"]).first()

        if not default_message and admin_user:
            # Create a new default system message associated with the admin user
            new_default_message = SystemMessage(
                name=DEFAULT_SYSTEM_MESSAGE["name"],
                content=DEFAULT_SYSTEM_MESSAGE["content"],
                description=DEFAULT_SYSTEM_MESSAGE["description"],
                model_name=DEFAULT_SYSTEM_MESSAGE["model_name"],
                temperature=DEFAULT_SYSTEM_MESSAGE["temperature"],
                created_by=admin_user.id  # Associate with the admin user's ID
            )

            try:
                db.session.add(new_default_message)
                db.session.commit()
                print("Default system message created")
            except Exception as e:
                print(f"Error creating default system message: {e}")

@app.route('/api/system-messages/<int:system_message_id>/add-website', methods=['POST'])
@login_required
def add_website_to_system_message(system_message_id):
    data = request.json
    website_url = data.get('websiteURL')
    
    system_message = SystemMessage.query.get(system_message_id)
    if system_message:
        if not system_message.source_config:
            system_message.source_config = {'websites': []}
        system_message.source_config['websites'].append(website_url)
        db.session.commit()
        return jsonify({'message': 'Website URL added successfully'}), 200
    else:
        return jsonify({'error': 'System message not found'}), 404

@app.route('/get-current-model', methods=['GET'])
@login_required
def get_current_model():
    # Assuming the current model is associated with the default system message
    default_message = SystemMessage.query.filter_by(name=DEFAULT_SYSTEM_MESSAGE["name"]).first()

    if default_message:
        return jsonify({'model_name': default_message.model_name})
    else:
        return jsonify({'error': 'Default system message not found'}), 404

@app.route('/system-messages', methods=['POST'])
@login_required
def create_system_message():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    new_system_message = SystemMessage(
        name=data['name'],
        content=data['content'],
        description=data.get('description', ''),
        model_name=data.get('model_name', ''),
        temperature=data.get('temperature', 0.7),
        created_by=current_user.id,
        enable_web_search=data.get('enable_web_search', False)
    )
    db.session.add(new_system_message)
    db.session.commit()
    return jsonify(new_system_message.to_dict()), 201

@app.route('/api/system_messages')
@login_required
def get_system_messages():
    system_messages = SystemMessage.query.all()
    return jsonify([{
        'id': message.id,  
        'name': message.name,
        'content': message.content,
        'description': message.description,
        'model_name': message.model_name,
        'temperature': message.temperature,
        'enable_web_search': message.enable_web_search
    } for message in system_messages])

@app.route('/system-messages/<int:message_id>', methods=['PUT'])
@login_required
def update_system_message(message_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401

    system_message = SystemMessage.query.get_or_404(message_id)
    data = request.get_json()

    system_message.name = data.get('name', system_message.name)
    system_message.content = data.get('content', system_message.content)
    system_message.description = data.get('description', system_message.description)
    system_message.model_name = data.get('model_name', system_message.model_name)
    system_message.temperature = data.get('temperature', system_message.temperature)
    system_message.enable_web_search = data.get('enable_web_search', system_message.enable_web_search)

    db.session.commit()
    return jsonify(system_message.to_dict())

@app.route('/system-messages/<int:message_id>', methods=['DELETE'])
@login_required
def delete_system_message(message_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401

    system_message = SystemMessage.query.get_or_404(message_id)
    db.session.delete(system_message)
    db.session.commit()
    return jsonify({'message': 'System message deleted successfully'})

@app.route('/trigger-flash')
def trigger_flash():
    flash("You do not have user admin privileges.", "warning")  # Adjust the message and category as needed
    return redirect(url_for('the_current_page'))  # Replace with the appropriate endpoint

@app.route('/chat/<int:conversation_id>')
@login_required
def chat_interface(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    return render_template('chat.html', conversation=conversation)

# Fetch all conversations from the database and convert them to a list of dictionaries
def get_conversations_from_db():
    conversations = Conversation.query.all()
    return [conv.to_dict() for conv in conversations]

@app.route('/database')
def database():
    try:
        conversations = get_conversations_from_db()
        conversations_json = json.dumps(conversations, indent=4) # Convert to JSON and pretty-print
        return render_template('database.html', conversations_json=conversations_json)
    except Exception as e:
        print(e)  # For debugging purposes
        return "Error fetching data from the database", 500

@app.cli.command("clear-db")
def clear_db():
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("Database cleared.")

@app.route('/folders', methods=['GET'])
def get_folders():
    folders = Folder.query.all()
    return jsonify([folder.title for folder in folders])

@app.route('/folders', methods=['POST'])
def create_folder():
    title = request.json.get('title')
    new_folder = Folder(title=title)
    db.session.add(new_folder)
    db.session.commit()
    return jsonify({"message": "Folder created successfully"}), 201

@app.route('/folders/<int:folder_id>/conversations', methods=['GET'])
def get_folder_conversations(folder_id):
    conversations = Conversation.query.filter_by(folder_id=folder_id).all()
    return jsonify([conversation.title for conversation in conversations])

@app.route('/folders/<int:folder_id>/conversations', methods=['POST'])
def create_conversation_in_folder(folder_id):
    title = request.json.get('title')
    new_conversation = Conversation(title=title, folder_id=folder_id)
    db.session.add(new_conversation)
    db.session.commit()
    return jsonify({"message": "Conversation created successfully"}), 201

# Fetch all conversations from the database for listing in the left sidebar
@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    # Fetch all conversations from database for the current user
    conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.updated_at.desc()).all()
 
    # Convert the list of Conversation objects into a list of dictionaries
    conversations_dict = [{"id": c.id, 
                           "title": c.title, 
                           "history": json.loads(c.history), 
                           "model_name": c.model_name, 
                           "token_count": c.token_count,
                           "updated_at": c.updated_at,
                           "temperature": c.temperature} 
                          for c in conversations]  
    return jsonify(conversations_dict)

# Fetch a specific conversation from the database to display in the chat interface
@app.route('/conversations/<int:conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    # Fetch a specific conversation from database
    conversation = Conversation.query.get(conversation_id)
    if conversation is None:
        return jsonify({'error': 'Conversation not found'}), 404

    # Convert the Conversation object into a dictionary with current fields.
    conversation_dict = {
        "title": conversation.title,
        "history": json.loads(conversation.history),
        "token_count": conversation.token_count,
        'model_name': conversation.model_name,
        "temperature": conversation.temperature
    }
    return jsonify(conversation_dict)

@app.route('/c/<conversation_id>')
def show_conversation(conversation_id):
    print(f"Attempting to load conversation {conversation_id}")  # Log the attempt
    # Your logic to load the specific conversation by conversation_id from the database
    conversation = Conversation.query.get(conversation_id)
    
    if not conversation:
        # If no conversation is found with that ID, you can either:
        # 1. Render a 404 page
        # return render_template('404.html'), 404
        # 2. Redirect to a default page
        print(f"No conversation found for ID {conversation_id}")  # Log the error
        return redirect(url_for('index'))
    
    # If a conversation is found, you'll render the chat interface.
    # You'll also pass the conversation data to the template, 
    # so the frontend can load the conversation when the page loads.
    return render_template('chat.html', conversation_id=conversation.id)

@app.route('/api/conversations/<int:conversation_id>/update_title', methods=['POST'])
def update_conversation_title(conversation_id):
    try:
        # Fetch the conversation by ID
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404
        
        # Get the new title from request data
        data = request.get_json()
        new_title = data.get('title')
        if not new_title:
            return jsonify({"error": "New title is required"}), 400
        
        # Update title
        conversation.title = new_title
        db.session.commit()

        return jsonify({"message": "Title updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    try:
        # Fetch the conversation by ID
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404
        
        # Delete the conversation
        db.session.delete(conversation)
        db.session.commit()

        return jsonify({"message": "Conversation deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    app.logger.info("Home route accessed")
    app.logger.info(f"Request Path: {request.path}")
    app.logger.info(f"Request Headers: {request.headers}")
    app.logger.info(f"Request Data: {request.data}")
    app.logger.info(f"User authenticated: {current_user.is_authenticated}")
    app.logger.info(f"Session contents: {session}")
    # Check if user is authenticated
    if current_user.is_authenticated:
        app.logger.info("User is authenticated")
        # Clear conversation-related session data for a fresh start
        if 'conversation_id' in session:
            del session['conversation_id']
        # If logged in, show the main chat page or dashboard
        return render_template('chat.html', conversation=None)
    else:
        app.logger.info("User is not authenticated, redirecting to login")
        # If not logged in, redirect to the login page
        return redirect(url_for('auth.login'))

@app.route('/clear-session', methods=['POST'])
def clear_session():
    session.clear()
    return jsonify({"message": "Session cleared"}), 200

def estimate_token_count(text):
    # Simplistic estimation. You may need a more accurate method.
    return len(text.split())

def generate_summary(messages):
    # Use only the most recent messages or truncate to reduce token count
    conversation_history = ' '.join([message['content'] for message in messages[-5:]])
    
    if estimate_token_count(conversation_history) > 4000:  # Adjust the limit as needed
        conversation_history = conversation_history[:4000]  # Truncate to fit the token limit
        app.logger.info("Conversation history truncated for summary generation")

    summary_request_payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "Please create a very short (2-4 words) summary title for the following text:\n" + conversation_history}
        ],
        "max_tokens": 10,
        "temperature": 0.5  # Adjust the temperature if needed
    }

    app.logger.info(f"Sending summary request to OpenAI: {summary_request_payload}")

    try:
        response = client.chat.completions.create(**summary_request_payload)
        summary = response.choices[0].message.content.strip()
        app.logger.info(f"Response from OpenAI for summary: {response}")
        app.logger.info(f"Generated conversation summary: {summary}")
    except Exception as e:
        app.logger.error(f"Error in generate_summary: {e}")
        summary = "Conversation Summary"  # Fallback title

    return summary




@app.route('/reset-conversation', methods=['POST'])
@login_required
def reset_conversation():
    if 'conversation_id' in session:
        del session['conversation_id']
    return jsonify({"message": "Conversation reset successful"})

def get_response_from_model(client, model, messages, temperature):
    """
    Routes the request to the appropriate API based on the model selected.
    """
    if model in ["gpt-3.5-turbo", "gpt-4-0613", "gpt-4-1106-preview", "gpt-4-turbo-2024-04-09", "gpt-4o-2024-05-13"]:
        # OpenAI chat models
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1500  # You can adjust max_tokens as needed
        }
        response = client.chat.completions.create(**payload)
        chat_output = response.choices[0].message.content.strip()
        model_name = response.model
    elif model in ["claude-3-opus-20240229", "claude-3-5-sonnet-20240620"]:
        # Anthropic model
        client = anthropic.Client(api_key=os.environ["ANTHROPIC_API_KEY"])

        # Construct the conversation history for Messages API
        anthropic_messages = []
        system_message = None
        for message in messages:
            if message['role'] == 'system':
                system_message = message['content']
            elif message['role'] == 'user':
                anthropic_messages.append({"role": "user", "content": message['content']})
            elif message['role'] == 'assistant':
                anthropic_messages.append({"role": "assistant", "content": message['content']})

        # Prepend the system message to the user's first message
        if system_message and anthropic_messages:
            anthropic_messages[0]['content'] = f"{system_message}\n\nUser: {anthropic_messages[0]['content']}"

        # Ensure the first message has the "user" role
        if not anthropic_messages or anthropic_messages[0]['role'] != 'user':
            anthropic_messages.insert(0, {"role": "user", "content": ""})

        # Set max_tokens based on the model
        max_tokens = 8192 if model == "claude-3-5-sonnet-20240620" else 4096

        # Send the conversation to the Anthropic Messages API
        response = client.messages.create(
            model=model,
            messages=anthropic_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            extra_headers={"anthropic-beta": "max-tokens-3-5-sonnet-2024-07-15"} if model == "claude-3-5-sonnet-20240620" else None
        )
        chat_output = response.content[0].text  # Extract the text content from the first ContentBlock
        model_name = model  # Use the provided model name for Anthropic
    elif model.startswith("gemini-"):
        # Gemini models
        gemini_model = GenerativeModel(model_name=model)
        contents = [{
            "role": "user",
            "parts": [{"text": "\n".join([m['content'] for m in messages])}]
        }]
        response = gemini_model.generate_content(contents, generation_config={"temperature": temperature})
        chat_output = response.text
        model_name = model
    else:
        chat_output = "Sorry, the selected model is not supported yet."
        model_name = None  # Set model_name to None for unsupported models
        
    return chat_output, model_name



@app.route('/chat', methods=['POST'])
@login_required
def chat():
    try:
        messages = request.json.get('messages')
        model = request.json.get('model')
        temperature = request.json.get('temperature')
        system_message_id = request.json.get('system_message_id')
        
        if system_message_id is None:
            app.logger.error("No system_message_id provided in the chat request")
            return jsonify({'error': 'No system message ID provided'}), 400
        
        conversation_id = request.json.get('conversation_id') or session.get('conversation_id')

        app.logger.info(f'Received model: {model}, temperature: {temperature}, system_message_id: {system_message_id}')

        conversation = None
        if conversation_id:
            conversation = Conversation.query.get(conversation_id)
            if conversation and conversation.user_id == current_user.id:
                app.logger.info(f'Using existing conversation with id {conversation_id}.')
            else:
                app.logger.info(f'No valid conversation found with id {conversation_id}, starting a new one.')
                conversation = None

        app.logger.info(f'Getting storage context for system_message_id: {system_message_id}')
        storage_context = embedding_store.get_storage_context(system_message_id)
        app.logger.info(f'Storage context retrieved: {storage_context}')

        user_query = messages[-1]['content']
        app.logger.info(f'User query: {user_query}')

        relevant_info = None
        try:
            app.logger.info(f'Querying index with user query: {user_query[:50]}...')
            relevant_info = file_processor.query_index(user_query, storage_context)
            app.logger.info(f'Retrieved relevant info: {relevant_info[:100]}...')
            if not relevant_info or relevant_info.strip() == "":
                app.logger.warning('No relevant information found in the index.')
                relevant_info = None
        except Exception as e:
            app.logger.error(f'Error querying index: {str(e)}')
            relevant_info = None

        # Update the system message with the vector search results
        system_message = next((msg for msg in messages if msg['role'] == 'system'), None)
        
        if system_message is None:
            system_message = {
                "role": "system",
                "content": ""
            }
            messages.insert(0, system_message)

        # Append vector search results
        if relevant_info:
            system_message['content'] += f"\n\n<Added Context Provided by Vector Search>\n{relevant_info}\n</Added Context Provided by Vector Search>"
        
        # Log the updated system message
        app.logger.info(f"Updated system message: {system_message['content']}")

        # First, get a response from the AI model
        app.logger.info(f'Sending initial messages to model: {json.dumps(messages, indent=2)}')
        initial_response, model_name = get_response_from_model(client, model, messages, temperature)
        app.logger.info(f"Initial response from model: {initial_response[:100]}...")

        # Check if the AI suggests a web search
        should_web_search = check_if_web_search_needed(initial_response)

        web_search_results = None
        if should_web_search:
            try:
                app.logger.info(f'Performing web search for query: {user_query[:50]}...')
                web_search_results = perform_web_search(user_query)
                app.logger.info(f'Web search results: {web_search_results[:100]}...')

                # Append web search results to messages
                messages.append({"role": "system", "content": f"<Added Context Provided by Web Search>\n{web_search_results}\n</Added Context Provided by Web Search>"})

                # Get a new response from the AI model with the web search results
                app.logger.info(f'Sending messages with web search results to model: {json.dumps(messages, indent=2)}')
                chat_output, _ = get_response_from_model(client, model, messages, temperature)
                app.logger.info(f"Final response from model: {chat_output[:100]}...")
            except Exception as e:
                app.logger.error(f'Error performing web search: {str(e)}')
                chat_output = initial_response
        else:
            chat_output = initial_response

        prompt_tokens = count_tokens(model_name, messages)
        completion_tokens = count_tokens(model_name, [{"content": chat_output}])
        total_tokens = prompt_tokens + completion_tokens

        app.logger.info(f'Tokens - Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}')

        new_message = {"role": "assistant", "content": chat_output}
        messages.append(new_message)

        if not conversation:
            conversation = Conversation(
                history=json.dumps(messages), 
                temperature=temperature,
                user_id=current_user.id,
                token_count=total_tokens
            )
            conversation_title = generate_summary(messages)
            conversation.title = conversation_title
            db.session.add(conversation)
            app.logger.info(f'Created new conversation with title: {conversation_title}')
        else:
            conversation.history = json.dumps(messages)
            conversation.temperature = temperature
            conversation.token_count += total_tokens
            app.logger.info(f'Updated existing conversation with id: {conversation.id}')

        conversation.model_name = model

        db.session.commit()
        session['conversation_id'] = conversation.id

        app.logger.info(f'Chat response prepared. Conversation ID: {conversation.id}, Title: {conversation.title}')

        return jsonify({
            'chat_output': chat_output,
            'conversation_id': conversation.id,
            'conversation_title': conversation.title,
            'vector_search_results': relevant_info if relevant_info else "No results found",
            'web_search_results': web_search_results if web_search_results else "No web search performed",
            'system_message_content': system_message['content'],
            'usage': {
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': total_tokens
            }
        })  

    except Exception as e:
        app.logger.error(f'Unexpected error in chat route: {str(e)}')
        return jsonify({'error': 'An unexpected error occurred'}), 500

def count_tokens(model_name, messages):
    if model_name.startswith("gpt-"):
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to cl100k_base encoding if the specific model encoding is not found
            encoding = tiktoken.get_encoding("cl100k_base")
        
        num_tokens = 0
        for message in messages:
            # Count tokens in the content
            num_tokens += len(encoding.encode(message['content']))
            
            # Add tokens for role (and potentially name)
            num_tokens += 4  # Every message follows <im_start>{role/name}\n{content}<im_end>\n
            if 'name' in message:
                num_tokens += len(encoding.encode(message['name']))
        
        # Add tokens for the messages separator
        num_tokens += 2  # Every reply is primed with <im_start>assistant
        
        return num_tokens

    elif model_name.startswith("claude-"):
        encoding = tiktoken.get_encoding("cl100k_base")
        num_tokens = 0
        
        for message in messages:
            if isinstance(message, dict):
                content = message.get('content', '')
                role = message.get('role', '')
            elif isinstance(message, str):
                content = message
                role = ''
            else:
                continue  # Skip if message is neither dict nor str

            num_tokens += len(encoding.encode(content))
            
            if role:
                num_tokens += len(encoding.encode(role))
            
            if role == 'user':
                num_tokens += len(encoding.encode("Human: "))
            elif role == 'assistant':
                num_tokens += len(encoding.encode("Assistant: "))
            
            num_tokens += 2  # Each message ends with '\n\n'
        
        # Add tokens for the system message if present
        if messages and isinstance(messages[0], dict) and messages[0].get('role') == 'system':
            num_tokens += len(encoding.encode("\n\nHuman: "))
        
        return num_tokens

    elif model_name == "gemini-pro":
        try:
            genai.configure(api_key="YOUR_GOOGLE_API_KEY")  # Replace with your actual API key
            model = genai.GenerativeModel('gemini-pro')
            
            num_tokens = 0
            for message in messages:
                if isinstance(message, dict):
                    content = message.get('content', '')
                elif isinstance(message, str):
                    content = message
                else:
                    continue

                # Use the count_tokens method to get an estimate
                token_count = model.count_tokens(content)
                num_tokens += token_count.total_tokens

            return num_tokens
        except Exception as e:
            print(f"Error counting tokens for Gemini: {e}")
            # Fallback to word count if there's an error
            return sum(len(m.get('content', '').split()) if isinstance(m, dict) else len(m.split()) for m in messages)

    else:
        # Fallback to a generic tokenization method
        num_tokens = 0
        for message in messages:
            num_tokens += len(message['content'].split())  # Fallback to word count
        return num_tokens

@app.route('/get_active_conversation', methods=['GET'])
def get_active_conversation():
    conversation_id = session.get('conversation_id')
    return jsonify({'conversationId': conversation_id})

# This has to be at the bottom of the file
if __name__ == '__main__':
    # Set host to '0.0.0.0' to make the server externally visible
    port = int(os.getenv('PORT', 8080))  # Needs to be set to 8080
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
