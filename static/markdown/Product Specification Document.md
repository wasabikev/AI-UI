# Product Specification Document

## Product Overview

This application is a chatbot platform built using Python and Flask. It integrates with OpenAI's GPT-4 AI model for generating responses to user inputs. It supports multiple chat sessions, allows users to choose different AI models, and maintains a historical record of chat sessions for continued interactions.

## Application Structure

The application follows a typical Flask application structure with the following primary components:

1. **app.py:** The main Flask application.
2. **routes.py:** Defines the routes or endpoints of the application.
3. **models.py:** Describes the database schema.
4. **main.js:** Handles client-side functionality, event handling and API requests.

## Database

The database is PostgreSQL, with SQLAlchemy as the ORM. The database contains two primary tables: `Folder` and `Conversation`.

**Folder**:
- `id`: Primary key.
- `title`: Title of the folder.
- `conversations`: A list of conversations within this folder.

**Conversation**:
- `id`: Primary key.
- `title`: Title of the conversation.
- `history`: JSON format of the conversation history, including both user inputs and bot outputs.
- `token_count`: The total number of tokens used in a conversation.
- `folder_id`: Foreign key from the Folder table.
- Additional future fields: `user_id`, `created_at`, `updated_at`, `model_name`, `sentiment`, `tags`, `language`, `status`, `rating`, `confidence`, `intent`, `entities`.

## Server-side Code

- All chat sessions are managed by the server. 
- The server sends a list of messages (user input and bot responses) to the OpenAI API and receives the AI-generated response.
- User inputs and AI responses are stored in the `history` field of a conversation, allowing the resumption of past conversations.
- The server also exposes API endpoints to manage folders and conversations.

## Client-side Code

- Handles user interactions like sending a chat message, changing the AI model, and starting a new chat session.
- Calls server-side APIs to manage conversations and get AI responses.

## Key Functions

- **updateConversationList()**: Fetches and displays the list of past conversations.
- **loadConversation()**: Fetches and displays a specific past conversation.
- **sendChat()**: Sends user input to the server, receives AI responses, and updates the chat UI.

## Future Enhancements

- Token count tracking for effective utilization of AI usage.
- User management with the ability to handle multiple users, preserving their individual chat histories.
- Rich chat history data structure to facilitate AI training and analysis.
- Enhanced capabilities like intent recognition, entity extraction, and sentiment analysis.

## Final Note

This application is intended to be a starting point for integrating with the OpenAI GPT-4 model. It provides the foundational structure for a fully functional chatbot platform with a focus on maintaining chat history, allowing for further development and customization based on specific requirements.
