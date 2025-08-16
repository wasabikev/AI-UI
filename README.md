# AI ∞ UI Technical Documentation

AI ∞ UI is no longer under active feature development in this public repository.

**Why forked?**

Ongoing development - including new features, security enhancements, and industry-specific integrations continues in private forks maintained by AsgardSystems.AI.
This transition supports our commercial roadmap, compliance requirements, and protection of proprietary workflows for public accounting and professional services.
This repository remains available as a reference implementation. The last major public effort was a full backend refactor to a modular, API-first architecture.
Note: The frontend is functional but somewhat outdated and in need of modernization.

## Overview

**AI ∞ UI** is a modular, API-first platform for orchestrating advanced AI workflows.  
It enables seamless interaction with multiple AI models and tools through a unified, responsive web interface.

- **Backend:**  
  Built on Quart (async Flask) with a fully asynchronous architecture.  
  All business logic is exposed via versioned API endpoints and organized using blueprint factories and orchestrator modules for clear separation of concerns.

- **Frontend:**  
  Features a modern, modal-based UI for managing conversations, system messages, file uploads, and more.  
  Real-time status updates are delivered via WebSockets for a fluid user experience.

- **Extensibility:**  
  The system is designed for easy integration of new AI models, data sources, and orchestration logic, supporting both rapid prototyping and production deployment.

---

## Features
- **Asynchronous Processing**: Fully async backend using Quart for responsive, non-blocking orchestration of all AI and file operations.
- **Multi-Model Support**: Seamless integration with OpenAI (GPT-3.5, GPT-4, GPT-4o, etc.), Anthropic (Claude 3.5, 3.7, 4), Google Gemini, and Cerebras models.
- **Conversation Management**: Create, view, update, and delete conversations with full message history, model, and metadata.
- **System Message Templates**: Customizable system message templates for different AI interaction scenarios, including model, temperature, and web search settings.
- **Vector Search (Semantic Search)**: Upload and process files for semantic search and retrieval-augmented generation (RAG) using Pinecone vector storage.
- **Web Search (Standard & Deep)**: Real-time web information retrieval using Brave Search API, with both standard and deep search orchestration, including summarization and citation.
- **Website Indexing**: Add, remove, and manage websites for context-aware responses (future support for AI-powered content extraction).
- **File Processing & Vectorization**: Upload and process files (PDF, DOCX, TXT, etc.) for permanent vector storage and semantic search.
- **Session Context File Upload**: Attach files directly to chat sessions; their content is extracted and injected into the current conversation context (ephemeral, not indexed).
- **Temperature Control**: Adjust AI response variability with temperature settings, including use-case explanations.
- **WebSocket Status Updates**: Real-time status updates and progress indicators during long-running operations via WebSocket.
- **Modal-Based Interface**: Modular, modal-based UI for system message editing, website management, file uploads, and admin actions.
- **Authentication System**: User registration, login, logout, and admin management with custom async authentication and status checks.
- **Admin Dashboard**: Manage users, update status, toggle admin privileges, reset passwords, and delete users via a dedicated admin interface.
- **Rich Text Rendering**: Markdown support, code syntax highlighting (Prism.js), and LaTeX rendering (MathJax).
- **Responsive Design**: Mobile-friendly, accessible interface using Bootstrap 4.5.2 and custom CSS.
- **Time Sense**: Context-aware responses with current date, time, and timezone information injected into system messages.
- **Infinite Scrolling**: Efficient conversation list loading with infinite scroll and pagination.
- **Flash Messages & Error Handling**: User feedback via flash messages, error templates, and real-time status updates.
- **Role-Based Access Control**: Admin-only routes and actions, with clear permission boundaries.
- **Extensible Orchestration Layer**: Modular orchestrators for chat, file processing, web search, system messages, and more.
- **Comprehensive Logging**: Structured, colorized, and Unicode-safe logging with log rotation and debug endpoints.

## Global Variables

### Frontend (main.js)

- `messages`: Array storing conversation messages
- `systemMessages`: Array storing system message templates (also available as `window.systemMessages`)
- `model`: Current selected model name
- `activeConversationId`: ID of currently selected conversation
- `currentSystemMessage`: Currently selected system message object
- `currentSystemMessageDescription`: Description of current system message
- `initialTemperature`: Initial temperature setting
- `isSaved`: Flag tracking if system message changes are saved
- `activeSystemMessageId`: Currently active system message ID
- `showTemperature`: Visibility state of temperature settings
- `selectedTemperature`: Current temperature value
- `activeWebsiteId`: Currently active website ID (for modal website management)
- `tempWebSearchState`: Temporary web search toggle state (for modal)
- `tempDeepSearchState`: Temporary deep search toggle state (for modal)
- `maintainWebSocketConnection`: Flag for WebSocket connection management
- `statusWebSocket`: WebSocket connection for status updates
- `currentSessionId`: Current WebSocket session ID
- `isLoadingConversations`: Flag indicating if conversations are being loaded (for infinite scroll)
- `currentPage`: Current page number for conversation pagination
- `hasMoreConversations`: Flag indicating if more conversations are available
- `attachedContextFiles`: Map of temporary file attachments for chat context (`Map<fileId, {name, size, type, tokenCount, content}>`)
- `isAdmin`: Boolean indicating if the current user is an admin (from `APP_DATA`)
- `APP_DATA`: Object containing initial session, conversation, and admin state from the backend

### Backend Functions (app.py)

- `startup()`: Initializes all orchestrators, services, and registers API blueprints.
- `setup_logging()`: Configures application logging.
- `unauthorized_handler()`: Handles unauthorized access (401).
- `handle_exception()`: Global exception handler.
- `not_found_error()`: Handles 404 errors.
- `internal_error()`: Handles 500 errors.
- `static_files()`: Serves static files.
- `health_check()`: Simple health check endpoint.
- `trigger_flash()`: Triggers a flash message for permission errors.
- `ws_chat_status()`: WebSocket endpoint for real-time status updates (delegates to `websocket_manager`).
- `chat_status_health()`: Health check for WebSocket connections.
- `home()`: Main chat interface route (requires login).
- `clear_session()`: Clears the user session.
- `database()`: (Admin/debug) View all conversations as JSON.
- `clear_db()`: (Admin/debug) CLI command to clear and reinitialize the database.

> **Note:** All business logic endpoints (chat, file upload, system message management, web search, etc.) are now handled via API blueprints and orchestrators, not as direct app.py route functions.

## Key Components

### Backend Components

1. **Configuration (`config.py`)**
   - Centralized environment and application settings
   - Environment variable loading
   - Upload folder and database URL configuration
   - Default system message definition
   - Environment-specific config classes (development, production, DigitalOcean, Azure)

2. **Quart Application (`app.py`)**
   - Asynchronous request handling
   - Route definitions
   - Middleware configuration
   - Error handling
   - WebSocket management

3. **Authentication System (`auth.py`)**
   - User authentication
   - Session management
   - Admin authorization
   - Login/logout handling
   - User registration

4. **Database Models (`models.py`)**
   - SQLAlchemy ORM definitions
   - Database schema
   - Relationship mappings
   - Data validation
   - Session management

5. **File Processing (`orchestration/file_processing.py`)**
   - Asynchronous file operations
   - Document parsing
   - Vector indexing
   - Semantic search
   - PDF processing

6. **Embedding Store (`services/embedding_store.py`)**
   - Pinecone integration
   - Vector storage management
   - Namespace organization
   - Query processing
   - Embedding generation

7. **File Utilities (`utils/file_utils.py`)**
   - File path management
   - Directory structure
   - Asynchronous file operations
   - Path resolution
   - File existence checking

8. **LLM Whisper Processor (`services/llm_whisper_processor.py`)**
   - PDF text extraction
   - Document processing
   - Text highlighting
   - Metadata extraction
   - API integration

9. **Status Update Manager (`orchestration/status.py`)**
   - WebSocket connection management
   - Real-time status updates
   - Session tracking
   - Connection health monitoring
   - Reconnection handling

10. **Web Search Process (`orchestration/web_search_orchestrator.py`)**
    - Query understanding
    - Search execution
    - Result summarization
    - Source citation
    - Intelligent search

11. **Web Scraper (`orchestration/web_scraper_orchestrator.py`)**
    - Website crawling
    - Content extraction
    - Metadata collection
    - HTML cleaning
    - Data formatting

### Frontend Components

1. **Main JavaScript (`static/js/main.js`)**
   - UI event handling
   - AJAX requests
   - WebSocket communication for status updates
   - DOM manipulation
   - Conversation management
   - Modal logic and infinite scrolling

2. **File Attachment Handler (`static/js/file_handlers.js`)**
   - Handles file selection, upload, removal, and preview for chat context attachments

3. **Markdown & Code Rendering**
   - **Marked.js (`static/js/marked.min.js`)**: Markdown parsing and rendering
   - **Prism.js (`static/js/prism.js`, `static/css/prism.css`)**: Code syntax highlighting

4. **Modal System**
   - System message configuration
   - Website management
   - File upload interface
   - Model selection
   - Temperature adjustment
   - All modals implemented with Bootstrap 4.5.2

5. **Chat Interface**
   - Message rendering (user, assistant, system)
   - Markdown and code block support
   - LaTeX rendering (MathJax)
   - Infinite scrolling for conversation list
   - Status updates via WebSocket
   - Context file attachment preview

6. **Authentication Interface**
   - Login and registration forms
   - Admin dashboard
   - User management
   - Password handling
   - Flash messages and error handling

7. **CSS Styling (`static/css/styles.css`)**
   - Responsive layout
   - Theme definition
   - Component styling (chat, admin, modals, file upload, etc.)
   - Animation effects
   - Modal customization
   - File upload progress and preview
   - Infinite scroll and sidebar styles

8. **Templates (`templates/`)**
   - `chat.html`: Main chat interface
   - `admin.html`: Admin dashboard
   - `login.html`: Login form
   - `error.html`: Error display

9. **Image Assets (`static/images/`)**
   - `BraveIcon.png`, `PineconeIcon.png`, `SearchIcon.png`, `favicon.ico`: Used for context blocks, branding, and browser tab icon

### Files & Their Roles

#### Core Application Files

- **app.py**: Main Quart application entry point. Handles app initialization, orchestrator/service instantiation, blueprint registration, error handling, static/utility routes, WebSocket endpoints, and admin/debug routes.
- **run.py**: Application runner for development/production (Hypercorn entrypoint).
- **models.py**: SQLAlchemy ORM models and async session management for all database tables (User, Conversation, Folder, SystemMessage, Website, UploadedFile, UserUsage).
- **auth.py**: Custom authentication system (login, registration, admin, decorators) built on top of quart_auth.
- **config.py**: Centralized configuration for environment-specific settings, secrets, upload folder, and default system message. Provides `get_config()` for environment selection.

#### Orchestration Layer

- **orchestration/chat_orchestrator.py**: Main business logic for chat processing, context management, model routing, semantic search, web search, and conversation persistence.
- **orchestration/conversation.py**: CRUD operations and orchestration for conversations and folders.
- **orchestration/file_processing.py**: File upload, processing, text extraction, vectorization, and semantic search orchestration.
- **orchestration/image_generation.py**: AI image generation orchestration.
- **orchestration/llm_router.py**: Routes requests to the correct LLM API (OpenAI, Anthropic, Gemini, Cerebras) and handles token counting.
- **orchestration/session_attachment_handler.py**: Handles temporary file attachments for chat context injection.
- **orchestration/status.py**: Manages WebSocket status sessions and real-time updates.
- **orchestration/system_message_orchestrator.py**: CRUD and business logic for system messages.
- **orchestration/vector_search_utils.py**: Utilities for vector search and concise query generation.
- **orchestration/vectordb_file_manager.py**: Manages file upload, download, deletion, and vector DB cleanup.
- **orchestration/web_scraper_orchestrator.py**: Coordinates website scraping and content extraction.
- **orchestration/web_search_orchestrator.py**: Orchestrates web search (standard and deep) and integrates results.

#### Service Layer

- **services/client_manager.py**: Centralized initialization and management of all external API clients (OpenAI, Anthropic, Pinecone, Google, Cerebras, LLMWhisperer, Brave Search).
- **services/embedding_store.py**: Handles vector embedding storage and retrieval (Pinecone, LlamaIndex).

#### Utilities

- **utils/file_utils.py**: File path management, directory structure, async file operations, and allowed file type checking.
- **utils/time_utils.py**: Time context generation and system message time context management.
- **utils/generate_title_utils.py**: Conversation title generation and summarization utilities.
- **utils/logging_utils.py**: Logging configuration, Unicode/color formatting, and log handler setup.
- **utils/debug_routes.py**: Debug and diagnostic endpoints for configuration, WebSocket, and directory checks.

#### API Layer

- **api/v1/chat.py**: Factory function for the `/api/v1/chat` endpoint blueprint, using dependency injection for orchestrators and status manager.
- **api/v1/__init__.py**: Blueprint registration for API v1 endpoints.

#### File Management Components

- **orchestration/session_attachment_handler.py**: Manages temporary file uploads for chat context (ephemeral, not indexed).
- **orchestration/file_processing.py**: Handles permanent file processing, text extraction, and vector indexing.
- **utils/file_utils.py**: Manages file paths and directory structures.
- **models.py (UploadedFile model)**: Tracks both temporary and permanent file uploads and their metadata.

#### Frontend Files

- **static/js/main.js**: Primary JavaScript for UI interactions, AJAX calls, and WebSocket handling.
- **static/js/marked.min.js**: Markdown parsing and rendering library.
- **static/js/prism.js**: Code syntax highlighting library.
- **static/css/styles.css**: CSS styling for the entire application.

#### Template Files

- **templates/chat.html**: Main chat interface template.
- **templates/admin.html**: Admin dashboard template.
- **templates/login.html**: User login template.
- **templates/error.html**: Error display template.

#### Web Scraping

- **orchestration/web_scraper_orchestrator.py**: Orchestrates website crawling and content extraction.
- **webscraper/spiders/flexible_spider.py**: (Legacy) Scrapy spider for website crawling (if still used).
- **webscraper/items.py**: Scrapy item definitions.
- **webscraper/pipelines.py**: Processing pipeline for scraped website data.

## Function Names & What They Do

#### Authentication Functions (`auth.py`)
- `init_auth(app)`: Initializes the authentication system and sets up the custom user class.
- `login_required(func)`: Decorator to protect routes requiring authentication and "Active" status.
- `async_login_required()`: Async decorator for authentication-required routes.
- `UserWrapper`: Custom user class for async user lookup and admin/status checks.
- `update_password(user_id)`: Updates a user's password (admin only).
- `update_admin(user_id)`: Toggles a user's admin status (admin only).
- `update_status(user_id)`: Updates a user's account status (admin only).
- `admin_dashboard()`: Renders the admin dashboard (admin only).
- `delete_user(user_id)`: Deletes a user account (admin only).
- `login()`: Handles user login requests.
- `logout()`: Handles user logout requests.
- `register()`: Handles user registration.

#### Embedding Store Functions (`services/embedding_store.py`)
- `initialize()`: Initializes the Pinecone connection and embedding model.
- `generate_db_identifier(db_url)`: Creates a unique identifier for the database.
- `get_embed_model()`: Returns the embedding model instance.
- `get_storage_context(system_message_id)`: Creates a storage context for vector operations for a given system message.
- `generate_namespace(system_message_id)`: Generates a unique namespace for a system message.

#### File Utility Functions (`utils/file_utils.py`)
- `FileUtils`: Class for all file/folder path management and async file operations.
- `get_user_folder(user_id)`: Gets the base folder for a user.
- `get_system_message_folder(user_id, system_message_id)`: Gets the folder for a system message.
- `get_uploads_folder(user_id, system_message_id)`: Gets the uploads folder.
- `get_processed_texts_folder(user_id, system_message_id)`: Gets the processed texts folder.
- `get_llmwhisperer_output_folder(user_id, system_message_id)`: Gets the LLMWhisperer output folder.
- `get_web_search_results_folder(user_id, system_message_id)`: Gets the web search results folder.
- `ensure_folder_exists(folder_path)`: Creates folders if they don't exist.
- `get_file_path(user_id, system_message_id, filename, folder_type)`: Gets the full path for a file.
- `check_file_exists(file_path)`: Checks if a file exists.
- `get_file_size(file_path)`: Gets the size of a file.
- `remove_file(file_path)`: Removes a file.
- `move_file(src, dst)`: Moves a file from one location to another.
- `allowed_file(filename)`: Checks if a file extension is allowed.

#### Conversation Orchestrator Functions (`orchestration/conversation.py`)
- `get_all_conversations_as_dicts()`: Fetches all conversations as dicts (admin/debug).
- `get_conversations(user_id, page, per_page)`: Returns paginated conversations for a user.
- `get_conversation_dict(conversation_id)`: Returns a conversation as a dict.
- `get_conversation(conversation_id)`: Fetches a conversation by ID.
- `update_title(conversation_id, new_title)`: Updates the title of a conversation.
- `delete_conversation(conversation_id)`: Deletes a conversation.
- `create_conversation(title, folder_id, user_id)`: Creates a new conversation in a folder.
- `get_folders()`: Returns all folder titles.
- `create_folder(title)`: Creates a new folder.
- `get_folder_conversations(folder_id)`: Gets all conversation titles in a folder.

#### System Message Orchestrator Functions (`orchestration/system_message_orchestrator.py`)
- `create(data, current_user)`: Creates a new system message.
- `get_all()`: Retrieves all system messages.
- `update(message_id, data, current_user)`: Updates a system message.
- `delete(message_id, current_user)`: Deletes a system message.
- `get_by_id(message_id)`: Retrieves a system message by ID.
- `toggle_search(system_message_id, enable_web_search, enable_deep_search, current_user)`: Toggles web search settings for a system message.
- `get_default_model_name(default_message_name)`: Gets the model name from the default system message.

#### Chat Orchestrator Functions (`orchestration/chat_orchestrator.py`)
- `run_chat(...)`: Main entry point for processing chat requests, including context management, semantic search, web search, and response generation.

#### File Processing Functions (`orchestration/file_processing.py`)
- `FileProcessor`: Main class for file processing and vectorization.
- `process_file(file_path, storage_context, file_id, user_id, system_message_id)`: Processes a file and creates a vector index.
- `process_text(text_content, metadata, storage_context)`: Processes raw text and creates a vector index.
- `extract_text_from_file(file_path, user_id, system_message_id, file_id)`: Extracts text from a file (PDF or text).
- `query_index(query_text, storage_context)`: Performs semantic search on indexed documents.
- `highlight_text(whisper_hash, search_text)`: Highlights text in a processed document.
- `cleanup()`: Cleans up resources (thread pool).

#### Session Attachment Handler Functions (`orchestration/session_attachment_handler.py`)
- `save_attachment(file, user_id)`: Saves a session-scoped file attachment.
- `remove_attachment(attachment_id, user_id)`: Removes a session attachment.
- `get_attachment_content(attachment_id, user_id, system_message_id)`: Extracts and returns content from a session attachment.

#### Vector DB File Manager Functions (`orchestration/vectordb_file_manager.py`)
- `upload_file(file, user_id, system_message_id)`: Handles file upload, processing, and indexing.
- `remove_file(file_id, user_id)`: Removes a file and associated vectors.
- `get_file_record(file_id)`: Retrieves a file record from the database.
- `get_original_file_html(file_id, current_user_id)`: Returns HTML for viewing the original file.
- `get_file_bytes(file_id, current_user_id)`: Returns the file as bytes for download/viewing.
- `get_processed_text(file_id, current_user_id)`: Returns the processed text of a file.

#### Status Update Manager Functions (`orchestration/status.py`)
- `create_session(user_id)`: Creates a new WebSocket status session.
- `register_connection(session_id, websocket)`: Registers a WebSocket connection.
- `send_status_update(session_id, message, status)`: Sends a status update to a session.
- `send_ping(session_id)`: Sends a ping to keep the connection alive.
- `remove_connection(session_id)`: Removes a WebSocket connection.
- `update_status(message, session_id, status)`: Helper to send a status update.
- `_cleanup_expired_sessions()`: Cleans up expired sessions.

#### LLM Router Functions (`orchestration/llm_router.py`)
- `get_response_from_model(client, model, messages, temperature, ...)`: Routes requests to the correct LLM API and returns the response.
- `count_tokens(model_name, messages, logger=None)`: Counts tokens for a given model and message list.

#### Vector Search Utils Functions (`orchestration/vector_search_utils.py`)
- `generate_concise_query_for_embedding(client, long_query_text, target_model)`: Summarizes a long query for embedding.

#### Web Search Orchestrator Functions (`orchestration/web_search_orchestrator.py`)
- `perform_web_search_process(...)`: Orchestrates standard or deep web search and integrates results.
- `understand_query(...)`: Analyzes the conversation and user query to generate a search query.

#### Web Scraper Orchestrator Functions (`orchestration/web_scraper_orchestrator.py`)
- `add_website(url, system_message_id, current_user)`: Adds a website for indexing.
- `remove_website(website_id, current_user)`: Removes a website.
- `extract_content(url, ...)`: (Placeholder) For future AI-powered web content extraction.

#### Logging Utils Functions (`utils/logging_utils.py`)
- `setup_logging(app, debug_mode)`: Configures logging for the application.
- `UnicodeFormatter`: Formatter for Unicode-safe log output.
- `ColorFormatter`: Formatter for colorized log output.

#### Debug Routes Functions (`utils/debug_routes.py`)
- `websocket_diagnostic()`: Endpoint to check WebSocket configuration.
- `debug_config()`: Endpoint to verify configuration.
- `debug_config_full()`: Detailed configuration endpoint (login required).
- `debug_websocket_config()`: Checks WebSocket configuration.
- `check_directories()`: Checks directory structure and permissions.
- `view_logs()`: Returns application logs as HTML.
- `register_routes(app)`: Registers all debug routes with the app.

#### Time Utility Functions (`utils/time_utils.py`)
- `generate_time_context(user=None)`: Generates a string with current date, time, and timezone.
- `clean_and_update_time_context(messages, user, enable_time_sense, logger=None)`: Cleans and updates time context in system messages.

#### Conversation Title Utility Functions (`utils/generate_title_utils.py`)
- `generate_summary_title(messages, openai_client, ...)`: Generates a short summary/title for a conversation.
- `summarize_text(text, openai_client, ...)`: Summarizes text using OpenAI.
- `extract_user_assistant_content(messages, max_turns)`: Extracts recent user/assistant messages.
- `extract_system_message(messages)`: Extracts the first system message.
- `estimate_token_count(text, model)`: Estimates token count using tiktoken.

#### Client Manager Functions (`services/client_manager.py`)
- `initialize_all_clients()`: Initializes all external service clients.
- `get_client(service_name)`: Returns a specific client by name.
- `get_api_key(service_name)`: Returns a specific API key by name.
- `get_all_clients()`: Returns all initialized clients.
- `get_all_api_keys()`: Returns all API keys.
- `is_service_available(service_name)`: Checks if a service is available.
- `get_available_services()`: Returns a list of available services.

#### API Blueprint Factory (`api/v1/chat.py`)
- `create_chat_blueprint(chat_orchestrator, status_manager)`: Factory function to create the chat API blueprint with dependency injection.

#### Main Application Functions (`app.py`)
- `startup()`: Initializes orchestrators, services, blueprints, and app context.
- `setup_logging()`: Configures application logging.
- `unauthorized_handler(error)`: Handles unauthorized access (401).
- `handle_exception(error)`: Global exception handler.
- `not_found_error(error)`: Handles 404 errors.
- `internal_error(error)`: Handles 500 errors.
- `static_files(filename)`: Serves static files.
- `health_check()`: Simple health check endpoint.
- `trigger_flash()`: Triggers a flash message for permission errors.
- `ws_chat_status()`: WebSocket endpoint for real-time status updates.
- `chat_status_health()`: Health check for WebSocket connections.
- `database()`: (Admin/debug) View all conversations as JSON.
- `clear_db()`: (Admin/debug) CLI command to clear and reinitialize the database.
- `home()`: Main chat interface route (requires login).
- `clear_session()`: Clears the user session.

├── .env.example
├── README.md
├── app.py
├── auth.py
├── config.py
├── models.py
├── run.py
├── api/
│   └── v1/
│       ├── __init__.py
│       ├── chat.py
│       ├── conversations.py
│       ├── image_generation.py
│       ├── session_attachments.py
│       ├── system_messages.py
│       ├── vector_files.py
│       └── websites.py
├── orchestration/
│   ├── chat_orchestrator.py
│   ├── conversation.py
│   ├── file_processing.py
│   ├── image_generation.py
│   ├── llm_router.py
│   ├── session_attachment_handler.py
│   ├── status.py
│   ├── system_message_orchestrator.py
│   ├── vector_search_utils.py
│   ├── vectordb_file_manager.py
│   ├── web_scraper_orchestrator.py
│   ├── web_search_orchestrator.py
│   ├── web_search_standard.py
│   ├── web_search_deep.py
│   ├── web_search_utils.py
│   └── websocket_manager.py
├── services/
│   ├── client_manager.py
│   ├── embedding_store.py
│   └── llm_whisper_processor.py
├── static/
│   ├── css/
│   │   └── styles.css
│   ├── images/
│   │   ├── BraveIcon.png
│   │   ├── PineconeIcon.png
│   │   ├── SearchIcon.png
│   │   └── favicon.ico
│   ├── js/
│   │   ├── main.js
│   │   ├── marked.min.js
│   │   ├── prism.js
│   │   └── file_handlers.js
├── templates/
│   ├── admin.html
│   ├── chat.html
│   ├── error.html
│   └── login.html
├── utils/
│   ├── debug_routes.py
│   ├── file_utils.py
│   ├── generate_title_utils.py
│   ├── logging_utils.py
│   └── time_utils.py

## Modal-Based User Interface Guidelines

The application uses a modal-based approach for user interfaces when requesting input or displaying information that requires user interaction. This ensures a consistent, accessible, and user-friendly experience across the application.

### System Message Modal
The system message modal serves as a central hub for orchestrating various layers of interaction:

1. **Content Group**
   - System message template editing
   - Description and content configuration
   - Model selection
   - Temperature adjustment

2. **Websites Group**
   - Website URL management
   - Indexing status monitoring
   - Re-indexing triggers
   - Website metadata viewing

3. **Files Group**
   - File upload interface
   - File list management
   - File viewing options
   - File removal functionality

4. **Temperature Group**
   - Temperature selection with descriptions
   - Use case explanations
   - Visual feedback

### Admin Dashboard Modal
The admin dashboard provides interfaces for:
1. **User Management**
   - View all users
   - Update user status
   - Toggle admin privileges
   - Reset passwords
   - Delete users

2. **Status Update Modal**
   - Change user account status
   - Set to Active, Pending, or N/A

3. **Admin Update Modal**
   - Toggle admin privileges
   - Confirm privilege changes

4. **Password Update Modal**
   - Reset user passwords
   - Secure password handling

## Implementation Guidelines

 ### 1. Backend Development

 - **API-First Design:**
   - All business logic is exposed via versioned API endpoints (`/api/v1/...`).
   - No business logic should be implemented directly in `app.py` routes.
 - **Blueprint Factory Pattern:**
   - Define all API endpoints in blueprint factory modules (e.g., `api/v1/chat.py`, `api/v1/conversations.py`, etc.).
   - Use factory functions that accept orchestrators/services as arguments (dependency injection).
   - Register blueprints in `app.py` during startup, passing the required orchestrators/services.
 - **Orchestrators:**
   - Encapsulate business logic for each domain (chat, file processing, web search, system messages, etc.) in orchestrator classes in the `orchestration/` directory.
   - Orchestrators are instantiated in `app.py` and injected into blueprints.
 - **Services:**
   - Handle external integrations (OpenAI, Pinecone, etc.) in the `services/` directory.
   - Services are instantiated in `app.py` and injected as needed.
 - **Async/Await:**
   - Use async/await for all I/O operations (database, file, network).
   - Avoid blocking operations in request handlers.
 - **Error Handling:**
   - Implement comprehensive error handling in orchestrators and blueprints.
   - Use structured logging for all errors and warnings.
   - Return meaningful error responses from API endpoints.
 - **WebSocket Endpoints:**
   - WebSocket endpoints remain in `app.py` for direct access to app context and session management.
   - Use the `WebSocketManager` and `StatusUpdateManager` for real-time status updates.

 ### 2. Frontend Development

 - **API-Driven UI:**
   - All data interactions should use the API endpoints (no direct server-side rendering of business logic).
   - Use AJAX/fetch for all CRUD operations.
 - **Modal-Based Interfaces:**
   - Use Bootstrap 4.5.2 modals for all user interactions (system messages, file uploads, admin actions, etc.).
   - Implement modal state and validation in JavaScript.
 - **Event Delegation:**
   - Use event delegation for dynamic elements (e.g., conversation list, file badges).
 - **Accessibility:**
   - Follow ARIA guidelines for modals, forms, and navigation.
 - **Progressive Enhancement:**
   - Ensure core functionality works without JavaScript where possible.
 - **Responsive Design:**
   - Use Bootstrap grid and custom CSS for mobile-friendly layouts.

 ### 3. Database Interactions

 - **SQLAlchemy ORM:**
   - Use async SQLAlchemy for all database operations.
   - Maintain referential integrity and use proper indexing.
 - **Migrations:**
   - Use Alembic for schema changes.
   - All schema changes must be accompanied by a migration script.
 - **Session Management:**
   - Use the async session context manager (`get_session`) for all DB access.
 - **Alembic env.py customization:**
   - The migration environment is configured to use environment variables for secrets, supporting both async and sync driver URLs for application and migration needs.

 ### 4. Security Considerations

 - **Input Validation:**
   - Validate and sanitize all user input at the API layer.
 - **Parameterized Queries:**
   - Use SQLAlchemy's parameterized queries to prevent SQL injection.
 - **CORS:**
   - Configure CORS policies in `app.py` using `quart_cors`.
 - **Session Management:**
   - Use secure cookies and session timeouts.
 - **Secrets Management:**
   - Load all secrets and API keys via environment variables and `config.py`.

 ### 5. Dependency Injection Pattern

 - **No Global Imports:**
   - Do not import orchestrators/services directly in blueprints.
   - Always use blueprint factory functions for dependency injection.
 - **Testability:**
   - This pattern enables easy mocking and unit testing of API endpoints and orchestrators.

### Minimize Unnecessary Changes in Mature Code
- Respect Stable Code: AI-assisted changes should be limited to the specific feature or bug in question. Avoid refactoring, updating, or “modernizing” mature, stable code unless it directly relates to the task at hand or addresses a known issue.
- Preserve Working Patterns:
When working in established code, maintain the existing framework versions, coding styles, and APIs. Do not upgrade libraries, change APIs, or introduce new patterns unless explicitly required by the feature or bug.
- Justify Broad Changes:
Any change that affects code outside the immediate scope of the task (such as updating library versions, refactoring unrelated modules, or altering UI frameworks) must be clearly justified, documented, and approved by the project owner.
- Change with Context:
Before suggesting or applying “best practices,” always verify the current stack and project conventions. If in doubt, ask for confirmation before proceeding with changes that could impact unrelated functionality.
Minimize Risk:
- Avoid “over-eager” improvements or optimizations in legacy or mature areas of the codebase. Prioritize stability and predictability over theoretical improvements.

### Modal Interaction Patterns
- Open modals with clear triggers (buttons, links)
- Close modals with both "X" button and cancel/close buttons
- Save changes with primary action buttons
- Provide visual feedback for successful operations
- Return focus to triggering element when modal closes
- Support Escape key for closing modals
- Prevent background scrolling when modal is open
- Use flash messages for important notifications

### Authentcation Layer: Useage Guidelines:
Important:
This project uses a custom authentication wrapper (auth.py) on top of quart_auth.
Always import login_required and current_user from auth.py
Why?
Our login_required decorator and current_user wrapper enforce additional checks (such as "Active" status, async user lookup, etc.) beyond what quart_auth provides.


## External Libraries and Scripts

### Frontend Libraries

- **jQuery 3.5.1**: DOM manipulation and AJAX requests
- **Bootstrap 4.5.2**: UI components and responsive design (requires jQuery and Popper.js)
- **Popper.js 1.14.3**: Required for Bootstrap 4.x tooltips and popovers
- **Marked.js 9.0.2**: Markdown parsing and rendering (`static/js/marked.min.js`)
- **Prism.js 1.29.0**: Code syntax highlighting (`static/js/prism.js`, `static/css/prism.css`)
- **MathJax 3.2.2**: LaTeX rendering for mathematical notation
- **Autosize 4.0.2**: Textarea auto-resizing
- **Font Awesome 6.0.0-beta3**: Icon library
- **DOMPurify 2.3.3**: HTML sanitization
- **Chart.js**: (If used, as included in `chat.html`)

### Backend Libraries

- **Quart**: Asynchronous web framework (async Flask)
- **Quart-Auth**: Authentication for Quart
- **Quart-CORS**: Cross-Origin Resource Sharing for Quart
- **Quart-Schema**: Schema validation for Quart
- **SQLAlchemy**: ORM for database operations
- **sqlalchemy-utils**: LtreeType and other extensions for SQLAlchemy
- **Alembic**: Database migration tool
- **Pinecone**: Vector database client
- **OpenAI**: API client for OpenAI models
- **Anthropic**: API client for Claude models
- **Google Generative AI**: API client for Gemini models
- **LlamaIndex**: Framework for RAG applications and vector storage
- **BeautifulSoup**: HTML parsing for web search result extraction
- **aiohttp**: Asynchronous HTTP client/server for web search
- **aiofiles**: Asynchronous file operations
- **tiktoken**: Tokenizer for counting tokens
- **Hypercorn**: ASGI server for Quart
- **python-dotenv**: Environment variable management
- **Werkzeug**: WSGI utilities and password hashing
- **pytz**: Timezone handling
- **tenacity**: Retry library for API calls (if used)

## External Services and APIs

### AI Model Providers
- **OpenAI API**: GPT-3.5, GPT-4, GPT-4 Turbo, GPT-4o, GPT-4.1, GPT-4.1 Mini, GPT-4.1 Nano, o3-mini (Fast/Balanced/Deep)
- **Anthropic API**: Claude 3 Opus, Claude 3.5 Sonnet, Claude 3.7 Sonnet (with Extended Thinking)
- **Google Generative AI API**: Gemini 2.5 Pro, Gemini 2.0 Flash
- **Cerebras API**: Llama 3.1 (8B), Llama 3.3 (70B), DeepSeek R1 (70B)

### Vector Storage
- **Pinecone**: Vector database for efficient storage and retrieval of embeddings

### Web Search
- **Brave Search API**: Web search functionality

### Document Processing
- **Unstract LLMWhisperer API**: Advanced PDF text extraction

## Database Schema

### User
- `id`: Integer, primary key
- `username`: String(80), unique, non-nullable
- `email`: String(120), unique, non-nullable
- `password_hash`: String(128)
- `is_admin`: Boolean, default False
- `status`: String(20), default "Pending"
- `created_at`: DateTime
- `updated_at`: DateTime
- `last_login`: DateTime
- Relationships:
    - One-to-many with Conversation (`conversations`)
    - One-to-many with Folder (`folders`)
    - One-to-many with UserUsage (`usage`)
    - One-to-many with SystemMessage (`created_system_messages`)
    - One-to-many with UploadedFile (`uploaded_files`)

### Conversation
- `id`: Integer, primary key
- `title`: String
- `history`: JSON
- `token_count`: Integer, default 0
- `folder_id`: Integer, foreign key to Folder
- `user_id`: Integer, foreign key to User
- `created_at`: DateTime
- `updated_at`: DateTime
- `model_name`: String(120)
- `sentiment`: String(120)
- `tags`: String(120)
- `language`: String(120)
- `status`: String(120)
- `rating`: Integer
- `confidence`: Float
- `intent`: String(120)
- `entities`: JSON
- `temperature`: Float
- `prompt_template`: String(500)
- `vector_search_results`: JSON
- `generated_search_queries`: JSON
- `web_search_results`: JSON
- Relationships:
    - Many-to-one with User (`user`)
    - Many-to-one with Folder (`folder`)
    - One-to-many with UploadedFile (`uploaded_files`)

### Folder
- `id`: Integer, primary key
- `name`: String(120), non-nullable
- `path`: LtreeType, non-nullable (hierarchical path)
- `user_id`: Integer, foreign key to User, non-nullable
- `created_at`: DateTime
- `updated_at`: DateTime
- Relationships:
    - Many-to-one with User (`user`)
    - One-to-many with Conversation (`conversations`)

### SystemMessage
- `id`: Integer, primary key
- `name`: String(120), non-nullable
- `content`: Text, non-nullable
- `description`: Text
- `model_name`: String(120)
- `temperature`: Float
- `created_by`: Integer, foreign key to User
- `created_at`: DateTime
- `updated_at`: DateTime
- `source_config`: JSON
- `enable_web_search`: Boolean, default False
- `enable_deep_search`: Boolean, default False
- `enable_time_sense`: Boolean, default False
- Relationships:
    - Many-to-one with User (`creator`)
    - One-to-many with Website (`websites`)
    - One-to-many with UploadedFile (`uploaded_files`)

### Website
- `id`: Integer, primary key
- `url`: String(2048), non-nullable
- `site_metadata`: JSON
- `system_message_id`: Integer, foreign key to SystemMessage, non-nullable
- `indexed_at`: DateTime
- `indexing_status`: String(50), default 'Pending'
- `last_error`: Text
- `indexing_frequency`: Integer
- `created_at`: DateTime
- `updated_at`: DateTime
- Relationships:
    - Many-to-one with SystemMessage (`system_message`)

### UploadedFile
- `id`: String(36), primary key, UUID
- `user_id`: Integer, foreign key to User, non-nullable
- `original_filename`: String(255), non-nullable
- `file_path`: String(255), non-nullable
- `processed_text_path`: String(255)
- `upload_timestamp`: DateTime
- `file_size`: Integer
- `mime_type`: String(100)
- `system_message_id`: Integer, foreign key to SystemMessage, nullable
- `conversation_id`: Integer, foreign key to Conversation, nullable
- `processing_status`: String(50), default 'pending', non-nullable
- `token_count`: Integer, nullable
- `is_temporary`: Boolean, default True, non-nullable
- Relationships:
    - Many-to-one with User (`user`)
    - Many-to-one with SystemMessage (`system_message`)
    - Many-to-one with Conversation (`conversation`)

### UserUsage
- `id`: Integer, primary key
- `user_id`: Integer, foreign key to User
- `api_used`: String(50)
- `tokens_used`: Integer
- `session_start`: DateTime
- `session_end`: DateTime
- `cost`: Float
- Relationships:
    - Many-to-one with User (`user`)

## API Keys and Environmental Variables

### Required Environment Variables

All environment variables are loaded and managed via `config.py`.  
See `.env.example` for a template.

- `DATABASE_URL`: PostgreSQL connection string (**required**)
- `SECRET_KEY`: Application secret key for session management (**required**)
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `GOOGLE_API_KEY`: Google AI API key
- `CEREBRAS_API_KEY`: Cerebras API key
- `PINECONE_API_KEY`: Pinecone API key
- `PINECONE_CLOUD`: Pinecone cloud provider (aws, gcp, azure)
- `PINECONE_REGION`: Pinecone region (us-east-1, etc.)
- `LLMWHISPERER_API_KEY`: Unstract LLMWhisperer API key
- `BRAVE_SEARCH_API_KEY`: Brave Search API key
- `ADMIN_USERNAME`: Default admin username
- `ADMIN_PASSWORD`: Default admin password
- `PORT`: Application port (default: 8080)
- `WEBSOCKET_PATH`: WebSocket endpoint path
- `APP_ENV`: Application environment (development, production, digitalocean, azure, etc.)

> **Note:**  
> - All configuration is centralized in `config.py`, which selects the appropriate config class based on `APP_ENV`.
> - The upload folder is set via `BASE_UPLOAD_FOLDER` in `config.py` (defaults to `user_files/` in the project root).
> - If you add new environment variables for features, document them here and in `.env.example`.

### Configuration Best Practices
- Use `.env` files for local development
- Use environment variables for production deployment
- Never commit API keys to version control
- Implement proper secret rotation
- Use separate keys for development and production environments
- Set appropriate rate limits and usage alerts
- Monitor API usage and costs
- Use a secrets manager for production environments

## Development Environment Requirements
- Python 3.11+
- PostgreSQL 13+
- Node.js 14+ (for frontend build tools)
- Git
- Virtual environment (venv or conda)
- VS Code with Python and JavaScript extensions
- Docker (optional, for containerized development)
- Windows 11 with VS Code (primary development environment)

## Deployment Considerations

### 1. ASGI Server & App Startup

- **Use Hypercorn** as the ASGI server for async support.
  - Local development: run with `python run.py` (binds to `127.0.0.1:5000`).
  - Production (DigitalOcean): Hypercorn is started as per `.do/app.yaml` (binds to `0.0.0.0:8080`).
- **Do not use Gunicorn** (not async-compatible for Quart).

### 2. Environment Configuration

- All configuration is managed via `config.py` and environment variables.
- Use `.env` for local development; set environment variables in DigitalOcean App Platform or your cloud provider.
- The `APP_ENV` or `ENV` variable selects the config class (`DevelopmentConfig`, `DigitalOceanConfig`, etc.).
- **Never commit secrets or API keys to version control.**

### 3. DigitalOcean App Platform

- Deployment is configured via `.do/app.yaml`:
  - **Routes**: HTTP and WebSocket (`/ws/chat/status`) are both routed.
  - **Environment variables**: Set all required keys (see `.env.example` and README).
  - **Health check**: Uses `/health` endpoint.
  - **WebSocket**: Explicitly enabled and routed.
  - **Instance size**: Set via `instance_size_slug`.
  - **Concurrency**: Set via `WEB_CONCURRENCY` (number of Hypercorn workers).
- **Static files**: Served from `/static/` by Quart.
- **Uploads**: Ensure `user_files/` is writable by the app.

### 4. Database

- Use **PostgreSQL 13+**.
- Connection string is set via `DATABASE_URL`.
- Connection pooling is configured in `models.py` (see `pool_size`, `max_overflow`, etc.).

#### Automated Migration Workflow

- Schema management is handled exclusively via Alembic migrations.
- All schema changes must be made via Alembic migration scripts (see Alembic documentation).
- The app does **not** create or modify tables/schema directly at startup.

#### How Migrations Are Run

**Production:**
- The app is deployed with a `run_command` in `.do/app.yaml`:
  ```yaml
  run_command: |
    python run_migrations.py && python run.py
  ```
- This ensures all Alembic migrations are applied before the app starts.
- If there are no new migrations, the command is a no-op and the app starts normally.
- If a migration fails, the app will not start and errors will be visible in the DigitalOcean logs.

**Development:**
- Developers are responsible for running Alembic migrations after making changes to `models.py`:
- migrations/env.py	Loads .env, injects ALEMBIC_DATABASE_URL, or converts DATABASE_URL for Alembic
- Use run_migrations.py for both development and production

#### First-Time Deployments

- On first deploy to a new environment (empty database), Alembic will create all tables, indexes, and extensions as defined in migration scripts.
- The app will then run `init_db.py` at startup, which populates default data (admin user, root folders, default system messages) if the tables are empty.
- Extensions (such as ltree) are created on startup as a fallback, unless already handled in migrations.

#### Key Files for Database Management

- **run_migrations.py**:  
  The only migration runner script. Runs Alembic migrations in both development and production.  
- **init_db.py**:  
  Handles default data population (admin user, root folders, default system message) only.  
  Does not create or modify tables/schema.
- **.do/app.yaml**:  
  Configured to always run migrations before starting the app via `run_command`.

#### Best Practices

- Do **not** use `Base.metadata.create_all()` for schema changes. All schema updates must go through Alembic.
- Never run migrations inside your app logic. Always use `run_migrations.py` before app startup.
- Always commit Alembic migration scripts (`migrations/versions/`) to version control when changing models.
- Review migration scripts before applying, especially for destructive changes.

#### Example Developer Workflow

```sh
# Make changes to models.py...

# Generate migration script
alembic revision --autogenerate -m "Add new field to Conversation"

# Apply migration
python run_migrations.py

# Start the app
python run.py
```

> **Note:** If you are deploying to a brand new environment, the process above will initialize the schema and populate all required default data on first run.

### 5. Vector Store

- **Pinecone** is used for vector storage.
- API key, cloud, and region are set via environment variables.
- Ensure Pinecone region and cloud match your deployment.

### 6. WebSocket Support

- **WebSocket endpoint**: `/ws/chat/status`
- Ensure your deployment platform and any reverse proxies (e.g., DigitalOcean, Nginx) support and route WebSocket traffic.
- WebSocket timeout and ping intervals are set in `config.py` and `.do/app.yaml`.

### 7. CORS and Security

- CORS is configured via `quart_cors` in `app.py`.
- All secrets and API keys are loaded via environment variables and `config.py`.
- Use HTTPS in production (DigitalOcean provides SSL by default).

### 8. Monitoring and Logging

- Logging is configured via `utils/logging_utils.py` (rotating file and colorized console).
- Log file: `app.log` (rotated).
- Health endpoints: `/health`, `/chat/status/health`
- Monitor error rates and system health.

### 9. CI/CD

- Use a CI/CD pipeline to automate testing, linting, and deployment.
- All commit messages should follow the [Conventional Commits](https://www.conventionalcommits.org/) standard.

### 10. Backups and Data Safety

- Set up regular **database backups**.
- Monitor Pinecone usage and costs.

### 11. Scaling

- Scale horizontally by increasing `WEB_CONCURRENCY` (Hypercorn workers).
- Use connection pooling for both database and Pinecone.

### 12. SSL/TLS

- SSL is terminated by DigitalOcean App Platform (or your reverse proxy).
- All traffic to the app should be encrypted in production.

### 13. Error Handling

- Custom error templates and flash messages are used for user feedback.
- All exceptions are logged with context.

---

## Error Handling and Logging
- Structured logging with UnicodeFormatter
- Proper exception handling with context
- Graceful degradation for service failures
- Meaningful user feedback
- Error rate monitoring
- Log rotation and management
- Separate logs for different severity levels
- Custom error templates
- Flash messages for user notifications
- WebSocket status updates

## Performance Optimization
- Optimize database queries with proper indexing
- Implement connection pooling
- Minimize blocking operations
- Use async/await patterns for I/O operations
- Optimize vector search operations
- Implement proper caching strategies
- Monitor memory usage
- Use pagination for large datasets
- Implement infinite scrolling for UI
- Optimize asset loading
- Use connection pooling for external APIs
- Implement retry mechanisms with exponential backoff


## Project Status
AI ∞ UI is now in maintenance mode as an open-source reference implementation.
- Active feature development and commercial deployments will continue in private forks maintained by AsgardSystems.AI.
- This public repository will remain available for community reference, learning, and non-commercial experimentation.
- Security patches and critical bug fixes may still be applied here as needed.
- For enterprise/commercial use, partnership inquiries, or to learn about the next-generation platform, please contact Kevin Atkinson or visit https://asgardsystems.ai/.