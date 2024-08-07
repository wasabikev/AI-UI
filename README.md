# AI ∞ UI -- A Web Interface for LLM APIs

## Overview

AI ∞ UI is a web-based conversational interface that facilitates interactions with various AI models and is intended for crafting and architecting layered (multi-system) AI orchestration using a variety of tools and models.

## Features

- **Persisted Conversations**: Conversations are stored in a database, allowing for historical review and continuation of discussions.
- **Real-time Chat**: Immediate communication with AI models, simulating a real-time conversation.
- **Conversation Management**: Users can create, read, update, and delete conversations.
- **Multiple AI Models**: The interface supports switching between different AI models, including OpenAI and Anthropic models, to cater to diverse conversational needs. (More models to come later)
- **Interactive UI**: A user-friendly interface with a chat box and messaging system that ensures a seamless conversational flow.
- **Admin Dashboard**: An admin interface for user management and system message configuration.
- **Flash Messages**: Provides feedback on user actions via transient notifications.
- **Direct Database Access**: Includes a button to open a direct view of the database entries in a new tab, facilitating easy access to raw data.
- **Rich Text Interaction**: Supports Markdown, code snippets with syntax highlighting, LaTeX content, and lists, enabling rich text interactions within the chat interface.
- **System Message Customization**: Offers a comprehensive system message management interface, allowing users to create, update, delete, and select system messages with customizable content, model names, and temperature settings.
- **Flexible AI Behavior**: Users can adjust the "temperature" setting to influence the variability of AI responses and select from different AI models to tailor interactions to their needs.
- **Dynamic UI and Real-time Feedback**: Features a dynamic user interface that updates in real-time, providing an interactive and responsive user experience.
- **Rich Text Editor**: Incorporates a text area that automatically adjusts its height based on content, providing a seamless user experience for message input.
- **Embedding Storage**: Utilizes Pinecone for efficient storage and retrieval of embeddings, enabling advanced search and similarity matching capabilities.
- **File Upload and Processing**: Supports processing of various file types and text content, creating searchable indexes for enhanced information retrieval.

## Key Components

- **Backend**: The server is built with Flask and handles API routes, database interactions, and communication with LLM APIs. Prod utilizes Gunicorn.
- **Frontend**: The frontend is developed using HTML, CSS, JavaScript, Bootstrap, and additional libraries such as Prism.js and Marked.js for enhanced functionality.
- **Database**: PostgreSQL is used for storing user data, conversation history, and system messages. Pinecone is used for vector storage.
- **System Message Modal**: The system message modal serves as a central hub for orchestrating various layers of interaction, including system message content, model selection, temperature settings, and the integration of controls for adding websites and files. Intended for expansion of additional orchestration layers.


## Main Files & Their Roles

- **app.py**: Flask server that handles routes, API communication, and session management.
- **auth.py**: Authentication logic for user login, registration, and session handling.
- **models.py**: SQLAlchemy models defining the database schema for users, conversations, and system messages.
- **main.js**: Client-side logic for handling UI events, API calls, and dynamic content updates. Includes detailed modal interactions for system messages, model selection, and temperature adjustments, enhancing user control over AI behavior.
- **chat.html**: The primary user interface for real-time conversation with AI models. It includes functionalities such as initiating new conversations, accessing the admin dashboard, and adjusting AI model settings. It also integrates a rich text editor and supports rendering of Markdown, LaTeX, and syntax-highlighted code snippets.
- **admin.html**: The admin dashboard template for managing users and system messages.
- **login.html/register.html**: Templates for user authentication flows.

## Key Functions

### app.py

- `get_response_from_model(model, messages, temperature)': Routes the request to the appropriate API based on the selected model (OpenAI, Anthropic, and Gemini Pro... more to come.)
- `chat()`: Endpoint for processing and responding to user messages from AI models
- `get_conversations()`: Retrieves a list of conversations for the current user.
- `get_conversation()`: Fetches details of a specific conversation.
- `update_conversation_title()`: Endpoint to update a conversation's title.
- `delete_conversation()`: Endpoint to remove a conversation from the database.
- `get_active_conversation()`: Retrieves the active conversation ID from the session.
- `get_websites(system_message_id)`: Retrieves all websites associated with a specific system message.
- `add_website_to_system_message(system_message_id)`: Adds a website URL to the source configuration of a specific system message.
- `add_website()`: Adds a new website URL to a system message.
- `remove_website(website_id)`: Removes a website from a system message.
- `reindex_website(website_id)`: Initiates the re-indexing process for a website.
- `get_current_model()`: Retrieves the current model associated with the default system message.
- `create_system_message()`: Creates a new system message (admin only).
- `get_system_messages()`: Retrieves all system messages.
- `update_system_message(message_id)`: Updates an existing system message (admin only).
- `delete_system_message(message_id)`: Deletes a system message (admin only).
- `get_folders()`: Retrieves all folders.
- `create_folder()`: Creates a new folder.
- `get_folder_conversations(folder_id)`: Retrieves conversations within a specific folder.
- `create_conversation_in_folder(folder_id)`: Creates a new conversation within a folder.
- `update_conversation_title(conversation_id)`: Updates the title of a conversation.
- `delete_conversation(conversation_id)`: Deletes a conversation.
- `clear_session()`: Clears the session data.
- `generate_summary(messages)`: Generates a summary title for a conversation based on the recent messages.
- `reset_conversation()`: Resets the current conversation.
- `get_response_from_model(model, messages, temperature)`: Routes the request to the appropriate API based on the selected model (OpenAI, Anthropic, and Gemini models).
- `count_tokens(model_name, messages)`: Counts the number of tokens in the messages based on the model.
- `get_files()`: Retrieves a list of files associated with a specific system message.
- `remove_file()`: Removes a file from the filesystem, database, and vector store.

### main.js

- `updateConversationList()`: Refreshes the conversation list in the sidebar.
- `checkActiveConversation()`: Checks if there is an active conversation and loads it if present.
- `showConversationControls(title, tokens)`: Updates the UI to show conversation controls and token usage information.
- $('#chat-form').on('submit', function (e)): Handles the submission of the chat form, preventing default behavior, capturing and displaying user input, sending it to the server, and processing the AI's response to update the chat interface dynamically. This function also manages the display of system messages, updates conversation lists, and handles URL and UI updates based on the conversation context
- `renderOpenAI(content)`: Processes and renders Markdown, code snippets, and LaTeX content within the chat interface.
- `updateSystemMessageDropdown()`, `populateSystemMessageModal()`, `updateModelDropdownInModal(modelName)`: Functions related to system message management, allowing for the customization of automated responses.
- `updateTemperatureDisplay()` : Function for managing the temperature setting and model selection, providing flexibility in AI interactions.
- `createMessageElement(message)`, `updateConversationList()`, `loadConversation(conversationId)`: Functions for dynamically updating the UI and handling real-time user interactions.
- `saveWebsiteURL(websiteURL, systemMessageId)`: Saves a website URL associated with a particular system message to the backend. Handles POST request and error management.
- `updateModelDropdownInModal(modelName)`: Updates the model dropdown in the system message modal to reflect the selected model name, ensuring the UI is synchronized with the backend model settings.
- `populateModelDropdownInModal()`: Populates the model dropdown in the system message modal with available AI models, allowing users to select different models dynamically.
- `fetchAndProcessSystemMessages()`: Fetches system messages from the server and processes them to update the UI.
- `showModalFlashMessage(message, category)`: Displays a modal flash message of a specified category (e.g., success, warning).
- `checkAdminStatus(e)`: Checks if the user is an admin before allowing access to admin-specific features.
- `openStatusModal(userId, currentStatus)`: Opens a modal for updating the status of a user, pre-filling it with current information.
- `updateStatus()`: Submits the form inside the status update modal.
- `renderMathInElement(element)`: Checks and processes any LaTeX content within the specified element using MathJax.
- `createMessageElement(message)`: Creates and returns a message element for the chat interface based on the message role and content.
- `displaySystemMessage(systemMessage)`: Updates the chat interface to display a system message, including its description, associated model name, and temperature setting. It removes any existing system messages, prepends the new system message to the chat, and updates the internal messages array to include this system message. This function ensures that system messages are prominently displayed at the top of the chat interface.
- `openModalAndShowGroup(targetGroup)` and `toggleContentGroup(groupID)`: These functions manage the visibility of content groups within modals. openModalAndShowGroup is used to open a modal and display a specific content group by hiding others and showing the targeted one. toggleContentGroup handles the visibility toggle of content groups within a modal, ensuring only the selected group is visible while others are hidden. Both functions are essential for dynamic UI interactions within modals, allowing for context-specific displays.
- `saveWebsiteURL(websiteURL, systemMessageId)`: Saves a website URL associated with a particular system message to the backend. Handles POST request and error management.

### embedding_store.py
`__init__(self, db_url)`: Initializes the EmbeddingStore with Pinecone configuration.`generate_db_identifier(self, db_url)`: Generates a unique identifier for the database.`get_embed_model(self)`: Returns the OpenAI embedding model.`get_storage_context(self, system_message_id)`: Creates and returns a storage context for a given system message.`generate_namespace(self, system_message_id)`: Generates a unique namespace for a system message.

### file_processing.py
`process_file(self, file_path, storage_context)`: Processes a file and creates an index.`process_text(self, text_content, metadata, storage_context)`: Processes text content and creates an index.`_create_index(self, documents, storage_context)`: Creates an index from documents.`query_index(self, query_text, storage_context)`: Performs a RAG query on the index.

### Global Variables

messages: An array that stores the conversation messages.
systemMessages: An array that stores the system messages.
model: Stores the selected model name.
activeConversationId: Keeps track of the currently selected conversation.
currentSystemMessage: Stores the default system message.
currentSystemMessageDescription: Stores the description of the current system message.
initialTemperature: Stores the initial temperature setting.
isSaved: A flag to track whether the system message changes have been saved.
activeSystemMessageId: Tracks the currently active system message ID.
showTemperature: Tracks the visibility of the temperature settings.
selectedTemperature: Stores the default temperature value.
activeWebsiteId: Stores the currently active website ID for the Websites Group.

### models.py

- `Conversation`: Represents a conversation with fields such as title, history, token count, folder_id, user_id, created_at, updated_at, model_name, sentiment, tags, language, status, rating, confidence, intent, entities, temperature, and prompt_template. This model is crucial for storing comprehensive details about each conversation, including metadata and interaction specifics.
- `User`: Represents a user with fields for username, email, and password.
- `SystemMessage`: Represents a system message that can be used as a template or preset response.
- `Folder`: Manages groups of conversations, allowing users to categorize and organize conversations into folders for better usability and management.
- `UserUsage`: Tracks the usage details of users, including the API used, tokens consumed, session timings, and cost. This model helps in monitoring and managing the resource utilization by individual users.



### Modal-Based User Interface Guidelines

- In our project, we prioritize a modal-based approach for user interfaces when requesting input or displaying information that requires user interaction. This approach ensures a consistent, accessible, and user-friendly experience across the application. 
- Use Modals for User Input: Whenever the application requires input from the user, whether it's form submission, settings configuration, or any other input-driven task, use a modal window. This includes actions like adding or editing data, confirming decisions, or any interaction that benefits from focused attention.
- For future iterations and feature implementations, we strongly encourage maintaining the modal-based approach for user interfaces. This consistency is key to providing an intuitive and pleasant user experience across our application.
- The system message modal allows for comprehensive configuration of system messages, including templates setup, model selection, and temperature settings. It also provides controls for adding websites and files, which can be used in specific scenarios like real-time data analysis or document review.  Intended as a hub for systemic orchestration.

## Error Handling and Feedback
**Client-Side**: Errors are logged in the console and user-friendly messages are displayed using modal alerts.
**Server-Side**: Errors are logged using Flask's app.logger and appropriate HTTP status codes are returned to the frontend.

## External Libraries and Scripts
**Bootstrap**: Used for responsive design and UI components like modals and buttons.
**jQuery**: Facilitates DOM manipulation and event handling.
**Popper.js**: Used for tooltip and popover position.
**Marked.js**: A markdown parser used to render markdown content within chats.
**Prism.js**: A syntax highlighting library used for displaying code snippets.
**MathJax**: Renders mathematical notation written in LaTeX within the chat interface.
**Chart.js**: Enables graphical representation of data, potentially useful for visual AI data analysis.
**DOMPurify**: Sanitizes HTML and prevents XSS attacks.
**tiktoken**: A tokenizer library used for counting tokens in messages based on the selected model.
**google.generativeai**: A library for interacting with Google's Generative AI models (e.g., Gemini).
**Pinecone**: Vector database for efficient storage and retrieval of embeddings.
**LlamaIndex**: Framework for building RAG applications and connecting LLMs with external data.
**Unstract LLMWhisperer**: An API for extracting and structuring text from complex PDF documents, enhancing the accuracy and efficiency of document processing for LLMs.

## Setting up API Keys

## Feature Roadmap
**Support for Additional AI Models**: Integrate more models from different providers to enhance versatility.
**Expansion of System Message Modal**: Enhance the system message modal to serve as a central hub for orchestrating various layers of interaction, including but not limited to system messages, temperature settings, and the integration of controls for adding websites, files, graph databases, and advanced AI parameters like top-k settings.
**Enhanced Security Features**: Implement advanced authentication and authorization features to secure user interactions.
**Folder Management**: Enhance the folder management system to allow users to organize conversations into folders for better organization and retrieval.
**Website Indexing**: Implement a feature to index websites associated with system messages, enabling users to retrieve relevant information from external sources during conversations.
**Token Usage Tracking**: Extend the token usage tracking functionality to provide detailed insights into token consumption across different models and conversations.

## Setting up API Keys
1. Create a new file called `.env` in the project's root directory.
2. Add the following line to the `.env` file, replacing `<your_api_key_here>` with your actual API key:

## Getting Started

1. Clone the repository: `git clone <repository-url>`
2. Install dependencies: `pip install -r requirements.txt`
3. Initialize the database: `flask db upgrade`
4. Start the Flask server: `flask run`
5. Access the application at `http://localhost:5000/`

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For inquiries or assistance, reach out via [LinkedIn](https://www.linkedin.com/in/atkinsonkevin/).

---

**Note**: This README is intended for use as contextual reference within a system prompt.