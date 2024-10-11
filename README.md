# AI ∞ UI -- A Web Interface for LLM APIs

## Overview

AI ∞ UI is a web-based conversational interface that facilitates interactions with various AI models and is intended for crafting and architecting layered (multi-system) AI orchestration using a variety of tools and models.

## Features

**Persisted Conversations**: Conversations are stored in a database, allowing for historical review and continuation of discussions.
**Real-time Chat**: Immediate communication with AI models, simulating a real-time conversation.
**Conversation Management**: Users can create, read, update, and delete conversations.
**Multiple AI Models**: The interface supports switching between different AI models, including OpenAI and Anthropic models, to cater to diverse conversational needs. (More models to come later)
**Interactive UI**: A user-friendly interface with a chat box and messaging system that ensures a seamless conversational flow.
**Admin Dashboard**: An admin interface for user management and system message configuration.
**Flash Messages**: Provides feedback on user actions via transient notifications.
**Direct Database Access**: Includes a button to open a direct view of the database entries in a new tab, facilitating easy access to raw data.
**Rich Text Interaction**: Supports Markdown, code snippets with syntax highlighting, LaTeX content, and lists, enabling rich text interactions within the chat interface.
**System Message Customization**: Offers a comprehensive system message management interface, allowing users to create, update, delete, and select system messages with customizable content, model names, and temperature settings.
**Flexible AI Behavior**: Users can adjust the "temperature" setting to influence the variability of AI responses and select from different AI models to tailor interactions to their needs.
**Dynamic UI and Real-time Feedback**: Features a dynamic user interface that updates in real-time, providing an interactive and responsive user experience.
**Rich Text Editor**: Incorporates a text area that automatically adjusts its height based on content, providing a seamless user experience for message input.
**Embedding Storage**: Utilizes Pinecone for efficient storage and retrieval of embeddings, enabling advanced search and similarity matching capabilities.
**File Upload and Processing**: Supports uploading and associating files with system messages for enhanced context in conversations.
**Website Indexing**: Allows indexing of websites associated with system messages, enabling retrieval of relevant information during conversations. (In development)
**User Usage Tracking**: Monitors and records user API usage, including tokens used and associated costs.
**Flexible System Message Configuration**: Enables creation and management of system messages with customizable content, model selection, temperature settings, and associated resources (websites and files).
**Web Search Integration**: Ability to perform web searches during conversations, providing additional context from the internet.
**Vector Search**: Utilizes vector search to retrieve relevant information from uploaded documents and websites.
**Dynamic System Messages**: System messages are dynamically updated with context from vector search and web search results.
**Token Counting**: Implements token counting for various AI models to track usage and manage conversation length.
**Dynamic System Messages**: System messages are dynamically updated with context from vector search and web search results.
**Structured File Management**: Implements a hierarchical file structure to organize user uploads, processed texts, and LLMWhisperer outputs, facilitating efficient file handling and retrieval.


## Global Variables
`messages`: An array that stores the conversation messages.
`systemMessages`: An array that stores the system messages.
`model`: Stores the selected model name.
`activeConversationId`: Keeps track of the currently selected conversation.
`currentSystemMessage`: Stores the default system message.
`currentSystemMessageDescription`: Stores the description of the current system message.
`initialTemperature`: Stores the initial temperature setting.
`isSaved`: A flag to track whether the system message changes have been saved.
`activeSystemMessageId`: Tracks the currently active system message ID.
`showTemperature`: Tracks the visibility of the temperature settings.
`selectedTemperature`: Stores the default temperature value.
`activeWebsiteId`: Stores the currently active website ID for the Websites Group.

## Key Components

**Backend**: The server is built with Flask and handles API routes, database interactions, communication with LLM APIs (OpenAI, Anthropic, Google), web scraping, vector search, and web search integration. Prod uses Gunicorn.
**Frontend**: The frontend is developed using HTML, CSS, JavaScript, Bootstrap, and additional libraries such as Prism.js, Marked.js, and MathJax for enhanced functionality.
**Database**: PostgreSQL is used for storing user data, conversation history, system messages, websites, and uploaded files. It includes tables for users, conversations, folders, system messages, websites, and uploaded files.
**Vector Storage**: Pinecone is used for efficient storage and retrieval of embeddings, enabling advanced search and similarity matching capabilities.
**File Processing**: Supports uploading and processing of various file types, including PDFs, using LLMWhisperer for advanced text extraction.
**Web Scraping**: Implements a flexible spider using Scrapy for indexing websites associated with system messages.
**File Management**: The application implements a structured file management system using utility functions in file_utils.py to organize user uploads, processed texts, and LLMWhisperer outputs.


## Main Files & Their Roles
**app.py**: Flask server that handles routes, API communication, and session management. It includes functions for chat processing, file handling, web scraping, image generation, and integrates with various AI models (OpenAI, Anthropic, Google). It also manages database operations, user authentication, and implements web search functionality.
**auth.py**: Authentication logic for user login, registration, and session handling.**models.py**: SQLAlchemy models defining the database schema for users, conversations, system messages, folders, websites, and uploaded files.
**main.js**: Client-side logic for handling UI events, API calls, and dynamic content updates. Includes detailed modal interactions for system messages, model selection, and temperature adjustments, enhancing user control over AI behavior.
**chat.html**: The primary user interface for real-time conversation with AI models. It includes functionalities such as initiating new conversations, accessing the admin dashboard, and adjusting AI model settings. It also integrates a rich text editor and supports rendering of Markdown, LaTeX, and syntax-highlighted code snippets.
**admin.html**: The admin dashboard template for managing users and system messages.
**login.html/register.html**: Templates for user authentication flows.
**file_utils.py**: Utility functions for managing file and folder structures within the application.
**file_processing.py**: Handles the processing of various file types, including PDFs and other text-based documents.
**embedding_store.py**: Manages the interaction with Pinecone for vector storage and retrieval.
**llm_whisper_processor.py**: Interfaces with the Unstract LLMWhisperer API for advanced document processing and text extraction.


### app.py
`chat()`: Main route for processing chat messages, integrating vector search and web search capabilities.
`get_response_from_model()`: Handles routing requests to different AI models (OpenAI, Anthropic, Google).
`perform_web_search_process()`: Orchestrates the web search process, including query interpretation and result summarization.
`generate_image()`: Endpoint for generating images using OpenAI's DALL-E.
`count_tokens()`: Estimates token count for different AI models.
`upload_file()`, 
`get_files()`, 
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
`renderOpenAIWithFootnotes(content, enableWebSearch)`: Renders AI responses with hyperlinked footnotes for web search results when enabled.
`updateConversationList()`: Refreshes the conversation list in the sidebar, including model and temperature information for each conversation.
`loadConversation(conversationId)`: Loads a specific conversation, updating the UI with message history and conversation metadata.
`showConversationControls(title, tokens)`: Updates the UI to display conversation title and token usage information.
`handleAddFileButtonClick()`: Manages the file upload process within the system message modal.
`handleAddWebsiteButtonClick()`: Handles the addition of websites to system messages for indexing.
`updateWebsiteControls()`: Manages the visibility of website-related controls in the system message modal.
`populateModelDropdownInModal()`: Populates the model selection dropdown in the system message modal.
`updateModelDropdownInModal(modelName)`: Updates the model dropdown in the modal to reflect the selected model.
`fetchAndProcessSystemMessages()`: Fetches system messages from the server and processes them to update the UI.
`displaySystemMessage(systemMessage)`: Updates the chat interface to display a system message, including its description, associated model name, and temperature setting.


## models.py

This file defines the database schema using SQLAlchemy ORM. The following models are defined:

### Folder
Represents a folder for organizing conversations.Fields: id, titleRelationship: One-to-many with Conversation

### Conversation
Represents a conversation between a user and the AI.Fields: id, title, history (JSON), token_count, folder_id, user_id, created_at, updated_at, model_name, sentiment, tags, language, status, rating, confidence, intent, entities (JSON), temperature, prompt_template, vector_search_results (JSON), generated_search_queries (JSON), web_search_results (JSON)Relationships: Many-to-one with User and Folder

### User
Represents a user of the application.Fields: id, username, email, password_hash, is_admin, status, created_at, updated_at, last_loginRelationships: One-to-many with Conversation and UserUsage

### UserUsage
Tracks API usage for each user.Fields: id, user_id, api_used, tokens_used, session_start, session_end, costRelationship: Many-to-one with User

### SystemMessage
Represents system messages used to configure AI behavior.Fields: id, name, content, description, model_name, temperature, created_by, created_at, updated_at, source_config (JSON), enable_web_searchRelationships: Many-to-one with User, One-to-many with Website and UploadedFile

### Website
Represents websites associated with system messages for indexing.Fields: id, url, site_metadata (JSON), system_message_id, indexed_at, indexing_status, last_error, indexing_frequency, created_at, updated_atRelationship: Many-to-one with SystemMessage

### UploadedFile
Represents files uploaded by users and associated with system messages.Fields: id, user_id, original_filename, file_path, processed_text_path, upload_timestamp, file_size, mime_type, system_message_idRelationships: Many-to-one with User and SystemMessage

Key features:
Uses SQLAlchemy ORM for database interactions.Implements relationships between models for efficient data retrieval.Includes timestamps for creation and updates on relevant models.Uses JSON fields for storing complex data structures.Implements password hashing for user security.Provides to_dict() methods for easy serialization of model instances.

This comprehensive database schema allows for efficient organization of conversations, system messages, and associated resources while maintaining user-specific data and usage tracking. It supports the application's core functionalities, including conversation management, user authentication, file uploads, website indexing, and system message configuration.

### embedding_store.py

The `EmbeddingStore` class in this file manages the interaction with Pinecone for vector storage and retrieval. Here are the key components and functions:
`__init__(self, db_url)`: Initializes the EmbeddingStore with Pinecone configuration. It sets up the Pinecone client, creates the index if it doesn't exist, and generates a unique database identifier.`generate_db_identifier(self, db_url)`: Generates a unique identifier for the database based on the database URL.`get_embed_model(self)`: Returns the OpenAI embedding model used for generating embeddings.`get_storage_context(self, system_message_id)`: Creates and returns a storage context for a given system message. This includes setting up the Pinecone vector store with the appropriate namespace.`generate_namespace(self, system_message_id)`: Generates a unique namespace for a system message, combining the system message ID and the database identifier.

Key features:
Uses Pinecone for efficient storage and retrieval of embeddings.Integrates with OpenAI's embedding model for generating embeddings.Generates unique namespaces for each system message to organize embeddings.Supports serverless Pinecone index creation with configurable cloud and region settings.Implements error handling and logging for initialization and operation processes.Uses MD5 hashing for generating unique identifiers and namespaces.

This class is crucial for managing the vector storage aspect of the application, enabling efficient semantic search and retrieval of relevant information during conversations. It ensures that embeddings are properly organized and can be quickly accessed based on the system message context.

The EmbeddingStore is designed to work with the broader application architecture, particularly in conjunction with the file processing and querying functionalities, to provide a robust system for managing and retrieving contextual information in AI-driven conversations.


### llm_whisper_processor.py

This file contains the `LLMWhisperProcessor` class, which interfaces with the Unstract LLMWhisperer API for advanced document processing and text extraction. Key features and functions include:
`__init__(self, app)`: Initializes the LLMWhisperProcessor with the API key and sets up the LLMWhisperer client.`process_file(self, file_path, user_id, system_message_id, file_id)`: Processes a file using the LLMWhisperer API, extracting and storing the text content. It returns the extracted text and the full LLMWhisperer output.`highlight_text(self, whisper_hash, search_text)`: Highlights specific text within a processed document using the LLMWhisperer API.

Key features:
Integrates with Unstract's LLMWhisperer API for advanced document processing.Extracts text from various file formats, including complex PDFs.Stores both the extracted text and the full LLMWhisperer output for future reference and analysis.Provides text highlighting capabilities for search and analysis purposes.Handles API exceptions and provides error logging.Uses environment variables for secure API key management.

This class enhances the application's document processing capabilities, allowing for more accurate and structured extraction of text from complex documents. It's particularly useful for scenarios involving detailed document analysis or when working with PDFs that contain intricate layouts or embedded information.

The LLMWhisperProcessor works in conjunction with the FileProcessor to provide comprehensive document handling capabilities, supporting the application's ability to process and analyze a wide range of document types.

Note: Ensure that the LLMWHISPERER_API_KEY environment variable is set before using this class.

### file_processing.py

The `FileProcessor` class in this file handles the processing of various file types, including PDFs and other text-based documents. It integrates with LLMWhisperer for advanced PDF processing and uses LlamaIndex for indexing and querying. Key functions include:
`__init__(self, embedding_store, app)`: Initializes the FileProcessor with an embedding store and LLMWhisperProcessor.`process_file(self, file_path, storage_context, file_id, user_id, system_message_id)`: Processes a file, using LLMWhisperer for PDFs and SimpleDirectoryReader for other file types. It creates an index, saves the processed text, and returns the path to the processed text file.`process_text(self, text_content, metadata, storage_context)`: Processes raw text content, creating a Document object and an index.`_create_index(self, documents, storage_context)`: Creates a vector index from processed documents using an ingestion pipeline and LlamaIndex's VectorStoreIndex.`query_index(self, query_text, storage_context)`: Performs a RAG (Retrieval-Augmented Generation) query on the created index.`highlight_text(self, whisper_hash, search_text)`: Utilizes LLMWhisperer to highlight specific text in processed documents.

Key features:
Differentiates between PDF and non-PDF file processing.Integrates LLMWhisperer for advanced PDF text extraction.Uses LlamaIndex for efficient document indexing and querying.Maintains file metadata throughout the processing pipeline, including file_id for each document and node.Implements an ingestion pipeline for document processing, including node parsing and embedding.Provides RAG capabilities for intelligent information retrieval.Handles exceptions and provides error logging.Saves processed text files for future reference.

This class is crucial for the application's document processing and information retrieval capabilities, enabling efficient handling of various file types and intelligent querying of processed content. It works in conjunction with the EmbeddingStore to manage vector representations of documents and the LLMWhisperProcessor for specialized PDF handling.

The FileProcessor is designed to integrate seamlessly with the broader application architecture, particularly in supporting the chat functionality by providing relevant context from processed documents during conversations.


### file_utils.py

This file contains utility functions for managing file and folder structures within the application. It provides a consistent and organized approach to handling user uploads, processed texts, and LLMWhisperer outputs.

Key functions include:

`get_user_folder(app, user_id)`: Retrieves the base folder for a specific user.
`get_system_message_folder(app, user_id, system_message_id)`: Gets the folder for a specific system message within a user's folder.
`get_uploads_folder(app, user_id, system_message_id)`: Returns the uploads folder for a specific system message.
`get_processed_texts_folder(app, user_id, system_message_id)`: Returns the folder for processed texts of a specific system message.
`get_llmwhisperer_output_folder(app, user_id, system_message_id)`: Returns the folder for LLMWhisperer outputs of a specific system message.
`ensure_folder_exists(folder_path)`: Creates a folder if it doesn't exist.
`get_file_path(app, user_id, system_message_id, filename, folder_type)`: Retrieves the full path for a file based on its type and associated system message.

These utilities ensure a structured and consistent file management system across the application, separating user data, system messages, and different types of processed files. This organization facilitates easier file retrieval, processing, and management throughout the application's lifecycle.

## File Structure

The application uses a hierarchical file structure for organizing user uploads and processed files:
BASE_UPLOAD_FOLDER/ ├── user_id/ │ └── system_message_id/ │ ├── uploads/ │ ├── processed_texts/ │ └── llmwhisperer_output/

This structure allows for efficient organization and retrieval of files based on user, system message, and file type.


## Modal-Based User Interface Guidelines
In our project, we prioritize a modal-based approach for user interfaces when requesting input or displaying information that requires user interaction. This approach ensures a consistent, accessible, and user-friendly experience across the application. Use Modals for User Input: Whenever the application requires input from the user, whether it's form submission, settings configuration, or any other input-driven task, use a modal window. This includes actions like adding or editing data, confirming decisions, or any interaction that benefits from focused attention.For future iterations and feature implementations, we strongly encourage maintaining the modal-based approach for user interfaces. This consistency is key to providing an intuitive and pleasant user experience across our application.
The system message modal allows for comprehensive configuration of system messages, including templates setup, model selection, and temperature settings. It also provides controls for adding websites and files, which can be used in specific scenarios like real-time data analysis or document review. Intended as a hub for systemic orchestration.

## Error Handling and Logging

The application implements comprehensive error handling and logging mechanisms, including:
Rotating file handlers for log managementConsole logging for development debuggingDetailed error tracking and reporting throughout the application

### Ongoing Logging Enhancements

We are currently in the process of improving our logging system to better handle Unicode characters and special symbols. This involves:
Implementation of a custom UnicodeFormatter for improved character encoding in logs.
Gradual migration of logging calls from f-string formatting to %s placeholder style.

These enhancements aim to:
Prevent UnicodeEncodeErrors in logsImprove log readability and consistencyEnhance the overall robustness of our logging system

Status: Partially implemented, with ongoing updates.

Note for contributors: When working on the codebase, please be aware of this ongoing update. If you encounter any logging statements using f-strings (e.g., `app.logger.info(f"Message: {variable}")`), please update them to the new style: `app.logger.info("Message: %s", variable)`.


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
**LlamaIndex**: A framework for building RAG applications and connecting LLMs with external data.
**Unstract LLMWhisperer**: An API for extracting and structuring text from complex PDF documents, enhancing the accuracy and efficiency of document processing for LLMs.

## Database Schema

The application uses a relational database with the following key relationships:
Users can have multiple Conversations and SystemMessages.Conversations belong to a User and can be organized in Folders.SystemMessages can have multiple associated Websites and UploadedFiles.UserUsage tracks API usage for each User.

This schema allows for efficient organization of conversations, system messages, and associated resources while maintaining user-specific data and usage tracking.

## External Services and APIs
**OpenAI**: Used for GPT models and image generation.
**Anthropic**: Provides access to Claude models.
**Google AI**: Integrates Gemini models.
**Pinecone**: Vector database for efficient storage and retrieval of embeddings.
**Brave Search**: Used for web search functionality.
**Unstract LLMWhisperer**: An API for extracting and structuring text from complex PDF documents.

## API Keys and Environment Variables

The application requires several API keys and environment variables to be set:
`OPENAI_API_KEY`: For OpenAI services
`ANTHROPIC_API_KEY`: For Anthropic's Claude models
`GOOGLE_API_KEY`: For Google's Gemini models
`PINECONE_API_KEY`: For Pinecone vector database
`BRAVE_SEARCH_API_KEY`: For Brave Search API
`DATABASE_URL`: PostgreSQL database connection string
`SECRET_KEY`: Flask secret key for session management
`LLMWHISPERER_API_KEY`: For Unstract's LLMWhisperer API
`ADMIN_USERNAME`: For creating an admin user
`ADMIN_PASSWORD`: For setting the admin user's password

## Data Processing and Search
**File Processing**: The application can process and index various file types for later retrieval during conversations.
**Website Indexing**: Supports indexing of websites to include their content in the vector search.
**Vector Search**: Utilizes Pinecone for efficient storage and retrieval of document embeddings.
**Web Search**: Integrates Brave Search for real-time web information retrieval during conversations.

## Setting up API Keys
Create a new file called `.env` in the project's root directory.
Ensure that the `.env` file is added to your `.gitignore` to keep your API keys secure.

## Feature Roadmap
**Support for Additional AI Models**: Integrate more models from different providers to enhance versatility.
**Expansion of System Message Modal**: Enhance the system message modal to serve as a central hub for orchestrating various layers of interaction, including but not limited to system messages, temperature settings, and the integration of controls for adding websites, files, graph databases, and advanced AI parameters like top-k settings.
**Enhanced Security Features**: Implement advanced authentication and authorization features to secure user interactions.
**Folder Management**: Enhance the folder management system to allow users to organize conversations into folders for better organization and retrieval.
**Website Indexing**: Implement a feature to index websites associated with system messages, enabling users to retrieve relevant information from external sources during conversations.
**Token Usage Tracking**: Extend the token usage tracking functionality to provide detailed insights into token consumption across different models and conversations.
**API Orchestration Layer**: Develop a robust API orchestration layer that allows for seamless integration and coordination of multiple AI services, data sources, and external tools. This layer will enable complex workflows, chained API calls, and dynamic selection of AI models based on task requirements, enhancing the system's ability to handle diverse and complex user queries efficiently.

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