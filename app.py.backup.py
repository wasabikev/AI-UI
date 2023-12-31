from flask import Flask, request, jsonify, render_template, url_for, redirect, session
from flask_cors import CORS
from text_processing import format_text
from flask_login import LoginManager, current_user, login_required

from dotenv import load_dotenv
load_dotenv()

# Dependencies for database
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Dependencies for authentication
from auth import auth  # Import the auth blueprint

import openai
import os
import logging

import requests
import json

from models import db, Folder, Conversation
from logging.handlers import RotatingFileHandler # for log file rotation

app = Flask(__name__)
app.logger.setLevel(logging.INFO)  # Set logging level to INFO
handler = RotatingFileHandler("app.log", maxBytes=10000, backupCount=3) # Create log file with max size of 10KB and max number of 3 files
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.register_blueprint(auth, url_prefix='/auth')  # Register the auth blueprint

# Initialize the login manager
login_manager = LoginManager()
login_manager.init_app(app)

CORS(app)  # Cross-Origin Resource Sharing

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

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    # Fetch all conversations from database ordered by 'updated_at' descending (latest first)
    conversations = Conversation.query.order_by(Conversation.updated_at.desc()).all()
    # Convert the list of Conversation objects into a list of dictionaries
    # Include id, title, history, model_name, and token_count in each dictionary
    conversations_dict = [{"id": c.id, 
                           "title": c.title, 
                           "history": json.loads(c.history), 
                           "model_name": c.model_name, 
                           "token_count": c.token_count,
                           "updated_at": c.updated_at,
                           "temperature": c.temperature} 

                          for c in conversations]
    return jsonify(conversations_dict)

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
    # Check if user is authenticated
    if current_user.is_authenticated:
        # Clear conversation-related session data for a fresh start
        if 'conversation_id' in session:
            del session['conversation_id']
        # If logged in, show the main chat page or dashboard
        return render_template('chat.html', conversation=None)
    else:
        # If not logged in, redirect to the login page
        return redirect(url_for('auth.login'))


@app.route('/clear-session', methods=['POST'])
def clear_session():
    session.clear()
    
    return jsonify({"message": "Session cleared"}), 200


def generate_summary(messages):
    conversation_history = ' '.join([message['content'] for message in messages])

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", # or any appropriate model you are using
            messages=[
                {"role": "system", "content": "Please create a very short (2-4 words) summary title for the following text. Since it is a title it should have no periods and all the words should be Capatilized Like This:\n" + conversation_history}
            ],
            max_tokens=10
        )
        summary = response['choices'][0]['message']['content'].strip()
    except KeyError:
        app.logger.error(f"Failed to generate conversation summary: {response.json()}")
        summary = messages[0]['content']  # use the first user message as a fallback title
        if len(summary) > 120:
            summary = summary[:117] + '...'

    return summary


@app.route('/reset-conversation', methods=['POST'])
@login_required
def reset_conversation():
    if 'conversation_id' in session:
        del session['conversation_id']
    return jsonify({"message": "Conversation reset successful"})



@app.route('/chat', methods=['POST'])
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
        if conversation:
            app.logger.info(f'Fetched conversation with id {conversation_id} from provided ID/session.')
        else:
            app.logger.info(f'No conversation found with id {conversation_id} from provided ID/session.')

    # Preparing the payload for the OpenAI API
    api_request_payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature  
    }

    # Log the request payload for debugging
    app.logger.info(f"Sending request to OpenAI: {api_request_payload}")


    # Generating a response from the selected model
    response = openai.ChatCompletion.create(**api_request_payload)
    chat_output = response['choices'][0]['message']['content']
    app.logger.info("Response from OpenAI: {}".format(response))

    new_message = {"role": "assistant", "content": chat_output}
    messages.append(new_message)  # Append AI's message to the list

    if not conversation:
        # Create a new Conversation object with the temperature
        conversation = Conversation(history=json.dumps(messages), temperature=temperature)

        # Generate the title for the conversation
        conversation_title = generate_summary(messages)

        # Update the title of the conversation
        conversation.title = conversation_title
        
        db.session.add(conversation)
        db.session.commit()

        # Store conversation ID in session
        session['conversation_id'] = conversation.id
    else:
        # Update existing conversation
        conversation.history = json.dumps(messages)
        conversation.temperature = temperature  # Update the temperature here

        db.session.commit()

    # Extract token data from OpenAI API's response
    token_data = {
        'prompt_tokens': response.get('usage', {}).get('prompt_tokens', 0),
        'completion_tokens': response.get('usage', {}).get('completion_tokens', 0),
        'total_tokens': response.get('usage', {}).get('total_tokens', 0)
    }

    # Update the model name and token count of the conversation
    conversation.model_name = model
    conversation.token_count = token_data['total_tokens']

    # Commit changes made to the conversation object
    db.session.commit()

    # Update the session's conversation_id every time
    session['conversation_id'] = conversation.id

    return jsonify({
        'chat_output': chat_output,
        'conversation_id': conversation.id,
        'conversation_title': conversation.title,
        'usage': token_data
    })



@app.route('/get_active_conversation', methods=['GET'])
def get_active_conversation():
    conversation_id = session.get('conversation_id')
    return jsonify({'conversationId': conversation_id})


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))  # Get port from PORT environment variable or default to 8080
    app.run(debug=True, host='0.0.0.0', port=port)


