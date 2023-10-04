# AI ∞ UI   --   A Web Interface for LLM APIs

## Overview

This project is a conversational web application that allows users to interact with different AI models. It features a persistent chat history, enabling users to revisit previous conversations.

## Features

- **Persisted Conversations**: Chat sessions are saved in the database, allowing users to revisit past interactions.
- **Real-time Chat**: Users can send messages to the AI and receive responses in real-time.
- **Conversation Management**: Provides CRUD operations for managing conversations.
- **Multiple AI Models**: Users can switch between different AI assistants for varied interactions.
- **Message History**: Access to entire chat logs for any conversation.
- **Interactive UI**: Features a chat box, messaging system, and a smooth conversational flow.

## Key Components

- **Backend**: Built using Flask, it manages API routes and communicates with the OpenAI API.
- **Frontend**: Developed using HTML, CSS, and JS, it provides the user interface and client-side logic.
- **Database**: Responsible for storing conversation data, including message history.

## Main Files & Their Roles

- **server.py**: The heart of the Flask server. It manages API routes, communicates with OpenAI, and handles conversation state.
- **static/js/main.js**: Manages client-side interactions, API calls to the backend, and UI updates.
- **templates/chat.html**: Provides the UI for the conversational web app, with dynamic elements managed by `main.js`.
- **static/css/styles.css**: Contains the CSS styling for the application.
- **static/js/prism.js**: Used for syntax highlighting.
- **static/js/marked.min.js**: Handles Markdown rendering for the application.

## Key Functions

### server.py

- `home()`: Renders the main chat interface.
- `chat()`: Manages chat logic and OpenAI interactions.
- `get_conversations()`: Retrieves all conversations from the database.
- `get_conversation()`: Fetches details of a specific conversation.
- `update_conversation_title()`: Allows updating the title of a conversation.
- `delete_conversation()`: Deletes a specific conversation from the database.

### main.js

- `updateConversationList()`: Refreshes and displays the list of conversations.
- `loadConversation()`: Loads messages and details of a specific conversation.
- `showConversationControls()`: Displays controls related to the active conversation.
- `modelNameMapping()`: Converts internal model names to user-friendly display names.
- `sendMessage()`: Handles the sending of user messages to the AI.
- `renderOpenAI()`: Applies specific UI modifications for the OpenAI Playground.

### Additional Functions

- `generate_summary()`: Creates a title or summary for a conversation.

## Getting Started

To get started with this project:

1. Clone the repository.
2. Set up the required environment.
3. Run the Flask server using `python server.py`.
4. Access the web application through your browser.

## Contributing



## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Contact

https://www.linkedin.com/in/atkinsonkevin/

---

Note: Some sections like "Getting Started", "Contributing", "License", and "Contact" are placeholders and can be filled in or modified as per your project's specifics.
