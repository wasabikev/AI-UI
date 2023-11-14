from flask import Flask, request, jsonify, render_template, url_for, redirect, session
from flask_cors import CORS
from text_processing import format_text

# Dependencies for database
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

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

CORS(app)  # Cross-Origin Resource Sharing

# Set up database
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Bamboo garden.@localhost/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Secret key for session handling
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'my_precious_secret_key') 

# Initialize database
db.init_app(app)
migrate = Migrate(app, db)

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
                           "updated_at": c.updated_at} 
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
        'model_name': conversation.model_name
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
    return render_template('chat.html', converstation=None)

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

@app.route('/chat', methods=['POST'])
def chat():
    messages = request.json.get('messages')
    model = request.json.get('model')  # Fetch the model

    # Log the selected model
    app.logger.info(f'Received model: {model}')

    # If a conversation ID is provided, fetch that specific conversation
    conversation = None
    conversation_id = request.json.get('conversation_id') or session.get('conversation_id')

    app.logger.info(f'=== New Request to /chat ===')
    app.logger.info(f'Received model: {model}')
    app.logger.info(f'Received conversation_id: {conversation_id}')
    app.logger.info(f'Received messages: {messages}')

    if conversation_id:
        conversation = Conversation.query.get(conversation_id)
        if conversation:
            app.logger.info(f'Fetched conversation with id {conversation_id} from provided ID/session.')
        else:
            app.logger.info(f'No conversation found with id {conversation_id} from provided ID/session.')

    # Generating a response from the selected model
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages
    )
    chat_output = response['choices'][0]['message']['content']
    print("Response from OpenAI:", response)

    # Format the output with format_text function
    formatted_chat_output = format_text(chat_output)
    print("Formatted chat output:", formatted_chat_output)

    new_message = {"role": "assistant", "content": formatted_chat_output}
    print("new message being added:", new_message)
    messages.append(new_message)  # Append AI's message to the list
    
    if not conversation:
        # Create a new Conversation object without setting its title yet
        conversation = Conversation(history=json.dumps(messages))
        
        # Generate the title for the conversation (including user input and AI response)
        conversation_title = generate_summary(messages)
        
        # Update the title of the conversation
        conversation.title = conversation_title
        
        db.session.add(conversation)
        db.session.commit()

        # Store conversation ID in session
        session['conversation_id'] = conversation.id
    else:
        app.logger.info(f'Updating conversation with id {conversation.id}. Previous history: {conversation.history}')
        # If the conversation already exists, save the updated messages list as its history
        conversation.history = json.dumps(messages)
        app.logger.info(f'Updated history for conversation with id {conversation.id}: {conversation.history}')

        # Check for the 'generate_title_next' flag
        if 'generate_title_next' in session and session['generate_title_next']:
            # Use the user input and AI response to generate a title
            conversation_title = generate_summary(messages)

            # Update the title of the existing conversation
            conversation.title = conversation_title
            session.pop('generate_title_next', None)  # Remove the flag from the session

            # Save the updated conversation to the database
            db.session.commit()

    # Extract token data from OpenAI API's response
    token_data = {
    'prompt_tokens': response.get('usage', {}).get('prompt_tokens', 0),
    'completion_tokens': response.get('usage', {}).get('completion_tokens', 0),
    'total_tokens': response.get('usage', {}).get('total_tokens', 0)
}
    # Add the model name to the conversation
    conversation.model_name = model

    # Calculate the token count for the conversation and update it
    # Assuming the API response provides a 'usage' field with 'total_tokens' (adjust if it's different)
    conversation.token_count = token_data['total_tokens']

    # Commit changes made to the conversation object
    db.session.commit()

    # Update the session's conversation_id every time
    session['conversation_id'] = conversation.id
    
    app.logger.info(f'Responding with formatted chat output: {formatted_chat_output}')
    app.logger.info(f'Updated conversation_id being returned: {conversation.id}')

    return jsonify({
        'chat_output': formatted_chat_output, 
        'conversation_id': conversation.id, 
        'conversation_title': conversation.title, 
        'usage': token_data
    })

@app.route('/get_active_conversation', methods=['GET'])
def get_active_conversation():
    conversation_id = session.get('conversation_id')
    return jsonify({'conversationId': conversation_id})


if __name__ == '__main__':
    app.run(debug=True)

