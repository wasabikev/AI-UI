from flask import Flask, request, jsonify, render_template, url_for, redirect, session
from flask_cors import CORS
from text_processing import format_text
from flask_login import LoginManager, current_user, login_required

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
import logging

import requests
import json

from models import db, Folder, Conversation, User, SystemMessage, Website
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler # for log file rotation
from werkzeug.security import generate_password_hash
from google.generativeai import GenerativeModel

from auth import auth as auth_blueprint  # Import the auth blueprint

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

app.logger.setLevel(logging.INFO)  # Set logging level to INFO
handler = RotatingFileHandler("app.log", maxBytes=10000, backupCount=3) # Create log file with max size of 10KB and max number of 3 files
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.register_blueprint(auth_blueprint)  

# Add stream handler for console output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
app.logger.addHandler(console_handler)

app.logger.info("Logging is set up.")

# Initialize the login manager
login_manager = LoginManager()
login_manager.init_app(app)

CORS(app)  # Cross-Origin Resource Sharing

@app.route('/health')
def health_check():
    return 'OK', 200

@app.route('/generate-image', methods=['POST'])
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

if __name__ == '__main__':
       # Set host to '0.0.0.0' to make the server externally visible
       # Get the port from the environment variable or default to 5000
       port = int(os.getenv('PORT', 8080)) # Was 8080, then got updated to 5000. I switched it back. Still didn't work.
       app.run(host='0.0.0.0', port=port, debug=True)  # Set debug to False for production

@app.route('/get-websites/<int:system_message_id>', methods=['GET'])
def get_websites(system_message_id):
    websites = Website.query.filter_by(system_message_id=system_message_id).all()
    return jsonify({'websites': [website.to_dict() for website in websites]}), 200

@app.route('/add-website', methods=['POST'])
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
def remove_website(website_id):
    website = Website.query.get_or_404(website_id)
    db.session.delete(website)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Website removed successfully'}), 200

@app.route('/reindex-website/<int:website_id>', methods=['POST'])
def reindex_website(website_id):
    website = Website.query.get_or_404(website_id)
    # Trigger re-indexing logic here (e.g., update indexed_at, change status)
    website.indexed_at = datetime.now(timezone.utc)
    website.indexing_status = 'In Progress'
    db.session.commit()

    return jsonify({'message': 'Re-indexing initiated', 'website': website.to_dict()}), 200





# User loader function
@login_manager.user_loader
def load_user(user_id):
    from models import User  # Import here to avoid circular dependencies
    return User.query.get(int(user_id))

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
@login_required  # Ensure only authenticated users can perform this action
def create_system_message():
    if not current_user.is_admin:  # Ensure only admins can create system messages
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    new_system_message = SystemMessage(
        name=data['name'],
        content=data['content'],
        description=data.get('description', ''),
        model_name=data.get('model_name', ''),
        temperature=data.get('temperature', 0.7),
        created_by=current_user.id
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
        'temperature': message.temperature
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


openai.api_key = os.getenv("OPENAI_API_KEY")
if openai.api_key is None:
    raise ValueError("OPENAI_API_KEY environment variable not set")

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

@app.errorhandler(404)
def not_found_error(error):
    app.logger.error(f"404 Error: {error}, Path: {request.path}")
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"500 Error: {error}, Path: {request.path}, Details: {error}")
    return render_template('500.html'), 500


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
        "max_tokens": 10
    }

    app.logger.info(f"Sending summary request to OpenAI: {summary_request_payload}")

    try:
        response = openai.ChatCompletion.create(**summary_request_payload)
        summary = response['choices'][0]['message']['content'].strip()
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



def get_response_from_model(model, messages, temperature):
    """
    Routes the request to the appropriate API based on the model selected.
    """
    if model in ["gpt-3.5-turbo", "gpt-4-0613", "gpt-4-1106-preview", "gpt-4-turbo-2024-04-09","gpt-4o-2024-05-13"]:
        # OpenAI models
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        response = openai.ChatCompletion.create(**payload)
        chat_output = response['choices'][0]['message']['content']
        model_name = response['model']  # Extract the model name from the API response
    elif model == "claude-3-opus-20240229":
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

        # Send the conversation to the Anthropic Messages API
        response = client.messages.create(
            model=model,
            messages=anthropic_messages,
            max_tokens=2000,  # Specify the maximum number of tokens to generate
            temperature=temperature
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
    messages = request.json.get('messages')
    model = request.json.get('model')  # Fetch the model
    temperature = request.json.get('temperature')  # Fetch the temperature

    # Log the selected model and temperature
    app.logger.info(f'Received model: {model}')
    app.logger.info(f'Received temperature: {temperature}')

    conversation_id = request.json.get('conversation_id') or session.get('conversation_id')
    conversation = None

    if conversation_id:
        conversation = Conversation.query.get(conversation_id)
        # Check if the conversation belongs to the current user
        if conversation and conversation.user_id == current_user.id:
            app.logger.info(f'Using existing conversation with id {conversation_id}.')
        else:
            app.logger.info(f'No valid conversation found with id {conversation_id}, starting a new one.')
            conversation = None

    # Use the abstracted function to get a response from the appropriate model
    chat_output, model_name = get_response_from_model(model, messages, temperature)
    app.logger.info("Response from model: {}".format(chat_output))

    # Count tokens in the entire conversation history
    prompt_tokens = count_tokens(model_name, messages)

    # Count tokens in the assistant's output
    completion_tokens = count_tokens(model_name, [{"content": chat_output}])

    # Calculate total tokens
    total_tokens = prompt_tokens + completion_tokens

    # Log the token counts
    app.logger.info(f'Prompt tokens: {prompt_tokens}')
    app.logger.info(f'Completion tokens: {completion_tokens}')
    app.logger.info(f'Total tokens: {total_tokens}')

    new_message = {"role": "assistant", "content": chat_output}
    messages.append(new_message)  # Append AI's message to the list

    if not conversation:
        # Create a new Conversation object with the temperature and token counts
        conversation = Conversation(history=json.dumps(messages), 
                                    temperature=temperature,
                                    user_id=current_user.id,
                                    token_count=total_tokens)

        # Generate the title for the conversation
        conversation_title = generate_summary(messages)  # Uses GPT-3.5-turbo by default

        # Update the title of the conversation
        conversation.title = conversation_title
        
        db.session.add(conversation)
    else:
        # Update existing conversation
        conversation.history = json.dumps(messages)
        conversation.temperature = temperature
        conversation.token_count = conversation.token_count + total_tokens  # Update the token count

    # Update the model name of the conversation
    conversation.model_name = model

    db.session.commit()

    # Log the messages to ensure they are received correctly
    app.logger.info(f'Received messages: {messages}')
                                          
    # Store/update the conversation ID in session
    session['conversation_id'] = conversation.id

    return jsonify({
        'chat_output': chat_output,
        'conversation_id': conversation.id,
        'conversation_title': conversation.title,
        'usage': {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': total_tokens
        }
    })

def count_tokens(model_name, messages):
    if model_name.startswith("gpt-"):
        if model_name == "gpt-4o-2024-05-13":
            # Temporarily return "0" for token count for the gpt-4o-2024-05-13 model
            return 0
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            raise ValueError(f"Tokenizer not found for model: {model_name}")
        
        num_tokens = 0
        for message in messages:
            num_tokens += len(encoding.encode(message['content']))
        return num_tokens

    elif model_name.startswith("claude-"):
        encoding = tiktoken.get_encoding("cl100k_base")
        num_tokens = 0
        for message in messages:
            num_tokens += len(encoding.encode(message['content']))
        return num_tokens

    elif model_name == "gemini-pro":
        # Return "0" for token count for the gemini-pro model
        return 0

    else:
        raise ValueError(f"Unsupported model: {model_name}")


@app.route('/get_active_conversation', methods=['GET'])
def get_active_conversation():
    conversation_id = session.get('conversation_id')
    return jsonify({'conversationId': conversation_id})




