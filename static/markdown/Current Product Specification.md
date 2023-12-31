# Product Specification Document 

## 1. Introduction

### Purpose of the Document

- The document aims to provide a clear understanding of the application's components, functionalities, and workflows, facilitating efficient development, pair-programming, and collaboration.

### Scope of the Application

- The application is a conversational web interface that allows users to interact with various AI models for different purposes, ranging from general conversation to specialized assistance in programming and systems design.
- Key features include persistent chat history, real-time AI responses, conversation management, support for multiple AI models, temperature control, and an interactive user interface.


### Target Audience

- The document is tailored for use as a reference document for an LLM to assist with pair-programming.


## 2. Key Components Overview

### Backend - Flask Server

- **Functionality**: Manages server-side logic, API routes, and interactions with the OpenAI API.
- **Key Responsibilities**:
  - Handling API requests and responses.
  - Managing conversation state and history.
  - Integrating with external APIs, primarily the OpenAI API.
- **Language and Frameworks**: Written in Python, using the Flask framework.
- **Main File**: `app.py`.

### Frontend - User Interface

- **Functionality**: Handles the presentation layer of the application, providing the user interface.
- **Key Responsibilities**:
  - Making API calls to the backend to load conversations and submit user input.
  - Dynamically rendering UI components like messages, chat boxes, and conversation lists.
  - Managing user interactions, including message sending, system message selection, and temperature.
- **Technologies**: HTML for structure, CSS for styling, and JavaScript for client-side logic.
- **Main Files**: `static/js/main.js` for JavaScript and `templates/chat.html` for HTML templates.

### Database - Data Storage

- **Functionality**: Stores and manages data related to conversations, users, folders, and other entities.
- **Key Responsibilities**:
  - Persisting conversation histories and user data.
  - Providing data to the backend for processing and response generation.
  - Managing relationships between different data entities, such as users, conversations, and folders.
- **Technology**: PostgreSQL database, accessed using SQLAlchemy ORM for Python.
- **Schema**: Includes models like `Conversation`, `User`, `Folder`, `CodeAbstract`, and `ChangesLog`.

### Additional Components

- **Client-Side Libraries**: 
  - `marked.min.js` for Markdown rendering.
  - `prism.js` for syntax highlighting in chat interfaces.
- **Stylesheet**: `static/css/styles.css` for custom styling of the web application.


---

## 3. Backend Details

### app.py - Flask Server Code

#### Overview
- `app.py` serves as the backbone of the application's backend, built using Flask.
- It handles API routes, integrates with the OpenAI API, manages conversation states and history, and interacts with the PostgreSQL database.

#### Key Functions

1. **API Route Handlers**
   - `home()`: Renders the chat interface.
   - `chat()`: Manages the chat functionality, including receiving user messages, generating AI responses, and maintaining conversation history.
   - `get_conversations()`: Retrieves a list of all conversations, sorted by last updated.
   - `get_conversation()`: Fetches a specific conversation based on its ID.
   - `update_conversation_title()`: Allows updating the title of a conversation.
   - `delete_conversation()`: Enables deletion of a specific conversation.
   - `clear_db()`: CLI command to clear the database.
   - `get_folders()`, `create_folder()`, `get_folder_conversations()`, `create_conversation_in_folder()`: Manage folders and conversations within them.
   - `get_active_conversation()`: Retrieves the active conversation ID stored in the session.

2. **Database Integration**
   - Utilizes SQLAlchemy and Flask-Migrate for database operations.
   - Manages models such as `Folder` and `Conversation`.

3. **Error Handling and Logging**
   - Implements logging with different levels, using RotatingFileHandler for log file management.
   - Error handling in API routes, returning appropriate HTTP status codes and error messages.

4. **Session Management**
   - Uses Flask's session management to track the current conversation.

5. **OpenAI API Integration**
   - Connects with the OpenAI API for chat completions.
   - Handles the generation of conversation summaries using GPT-3.5-turbo model.

6. **Environment Configuration**
   - Configures database URI, CORS, and secret key through environment variables.

7. **Summary Generation**
   - Implements `generate_summary()` function to create conversation titles based on chat history.

8. **Token Management**
   - Extracts and manages token data related to OpenAI API responses for billing and monitoring purposes.

#### Error Handling and Logging
- Detailed logging for each API request and response.
- Error catching and handling within each route, with structured error responses.

#### Security and Data Protection
- The use of environment variables for sensitive data like database URI and secret keys.
- Implementation of CORS policy for cross-origin resource sharing.

---

## 4. Frontend Details

### static/js/main.js - Client-Side JavaScript

#### Overview
- `main.js` handles the client-side logic of the web application.
- It manages user interactions, API calls to the backend, and dynamic updates to the user interface.

#### Key Functions and Features

1. **System Message Management**
   - Handles predefined system messages for different assistant roles.
   - Provides functionality to display and select system messages.

2. **Model Management**
   - Manages the selection of AI models.
   - Dynamically updates the UI based on model selection.

3. **Conversation Handling**
   - Manages conversation data including messages and conversation IDs.
   - Implements `loadConversation()` to fetch and display conversation history.
   - Handles CRUD operations for conversations.

4. **UI Updates and Interactions**
   - Dynamically updates conversation lists, system messages, and chat UI.
   - Implements modal functionalities for system message selection.
   - Manages the display of conversation controls (edit, delete, title).

5. **Markdown Rendering and Syntax Highlighting**
   - Implements Markdown rendering and syntax highlighting in chat messages using `marked` and `Prism` libraries.
   - Enhances readability and presentation of chat content.

6. **Form Handling and User Input**
   - Manages user input through form submissions.
   - Implements functionality for sending messages and handling form data.

7. **Session Management**
   - Checks for active conversations in the session.
   - Manages session-related functionalities like clearing session data.

8. **Temperature Settings**
   - Manages the temperature for each conversation.
   - Modal provides a list of temperatures to choose from with descriptions and use cases.

9. **Error Handling and Feedback**
   - Implements error handling for API calls and user interactions.
   - Provides user feedback through UI updates and console logs.

#### UI Components

- System Message Button: Allows users to select and change system messages.
- Conversation List: Displays a list of conversations with CRUD options.
- Chat Interface: Handles the display and submission of chat messages.
- Model Dropdown: Enables switching between different AI models.
- Title Editing and Deletion: Provides options to edit and delete conversation titles.

#### JavaScript Libraries Used
- **Marked**: For Markdown rendering in chat messages.
- **Prism**: For syntax highlighting of code snippets in chat messages.

#### Security and Data Handling
- Ensures secure handling of user data and inputs.
- Implements client-side validations and checks for data integrity.

---

## 5. Database Schema and Interaction

### Overview
- The database for the application is structured to store and manage data related to conversations, users, folders, code abstracts, and change logs.
- It uses SQLAlchemy as the ORM (Object-Relational Mapping) tool for interacting with the database.

### Database Models

#### Folder
- Represents a grouping entity for conversations.
- **Attributes**:
  - `id`: Unique identifier (Primary Key).
  - `title`: Name of the folder.
  - `conversations`: Relationship to `Conversation` model, represents conversations in the folder.

#### Conversation
- Stores details of each conversation.
- **Attributes**:
  - `id`: Unique identifier (Primary Key).
  - `title`: Title of the conversation.
  - `history`: JSON formatted history of the conversation.
  - `token_count`: Count of tokens used in the conversation.
  - `folder_id`: References `Folder` model (Foreign Key).
  - `user_id`: References `User` model (Foreign Key).
  - `created_at`, `updated_at`: Timestamps for creation and last update.
  - `model_name`: Name of the AI model used.
  - Additional fields like `sentiment`, `tags`, `language`, `status`, `rating`, `confidence`, `intent`, `entities`.
  - `code_abstracts`: Relationship to `CodeAbstract` model.

#### CodeAbstract
- Captures code-related abstracts from conversations.
- **Attributes**:
  - `id`: Unique identifier (Primary Key).
  - `conversation_id`: References `Conversation` model (Foreign Key).
  - `file_name`: Name of the file associated with the abstract.
  - `code_abstract`: Text of the code abstract.
  - `last_updated`: Timestamp for the last update.
  - `file_type`: Type of the file.

#### ChangesLog
- Tracks changes made to code abstracts.
- **Attributes**:
  - `id`: Unique identifier (Primary Key).
  - `abstract_id`: References `CodeAbstract` model (Foreign Key).
  - `change_description`: Description of the change.
  - `change_timestamp`: Timestamp of the change.
  - `change_type`: Type of change (e.g., addition, modification, deletion).

#### User
- Manages user information.
- **Attributes**:
  - `id`: Unique identifier (Primary Key).
  - `username`: Unique username.
  - `email`: Unique email address.
  - `password_hash`: Hashed password.
  - `conversations`: Relationship to `Conversation` model.

### Database Interactions

- **CRUD Operations**: 
  - The application performs create, read, update, and delete (CRUD) operations on these models.
  - These operations are facilitated by SQLAlchemy's query interface.
  
- **Relationships and Foreign Keys**:
  - Foreign keys are used to establish relationships between different models (e.g., between `Conversation` and `Folder`).
  - These relationships enable efficient data retrieval and integrity.

- **Database Migrations**:
  - Flask-Migrate is used for handling database migrations, ensuring schema changes are versioned and tracked.

### Data Integrity and Indexing

- The database schema ensures data integrity with constraints like primary keys and foreign keys.
- Indexing may be applied on frequently queried fields for improved performance (e.g., on `user_id` in `Conversation`).

### Security Considerations

- User passwords are stored as hashes for security.
- Database access and queries are managed securely through SQLAlchemy to prevent SQL injection attacks.

---

## 6. AI Model Integration

### Overview

- The application leverages OpenAI's models for generating conversational responses and other AI-driven functionalities.
- It supports the integration of multiple AI models, allowing dynamic switching based on user preferences or requirements.

### Model Selection and Switching

- **Dynamic Model Switching**: The application is designed to switch seamlessly between different AI models. This is managed via the backend (`app.py`) and frontend (`main.js`) components.
- **Model Configuration**: The model name (e.g., `gpt-3.5-turbo`) is configurable, and changes in model selection are reflected in real-time during user interactions.
- **User Interface**: The frontend provides an interface for users to select different models, enhancing the flexibility and user experience.

### AI Model Capabilities

- **Conversational Responses**: The primary use of AI models is to generate conversational responses to user inputs, ensuring a fluid and natural interaction.
- **Summary Generation**: AI models are also used to generate summaries for conversations, helping in creating concise and relevant titles based on the conversation content.
- **Custom Role Definitions**: The system supports custom role definitions for different AI models, enabling specialized assistance based on the defined role.

### Integration Strategy

- **API Interactions**: Integration with OpenAI models is facilitated through API requests from the backend. The `app.py` file handles the logic for sending user inputs to the AI model and receiving the generated responses.
- **Handling AI Responses**: The backend processes AI responses, including managing token counts and formatting responses before sending them to the frontend.
- **Data Usage and Optimization**: The application tracks the usage of tokens in conversations to monitor and optimize the cost associated with using OpenAI's API.

### Security and Privacy

- **API Key Management**: The OpenAI API key is securely managed using environment variables to ensure security and confidentiality.
- **Data Handling**: Care is taken to handle user data and AI responses securely, maintaining user privacy and data integrity.

### Future Enhancements

- **Model Performance Monitoring**: Plans to include monitoring tools to track the performance of different AI models in real-time.
- **Expansion of AI Capabilities**: Exploring the integration of additional AI functionalities such as language translation, sentiment analysis, and entity recognition.

---

## 7. Security and Privacy

### Overview

- The application incorporates several security and privacy measures to protect user data and ensure compliance with relevant data protection laws and regulations.

### Data Protection and Privacy

- **Encryption**: Sensitive data, such as user passwords, are securely hashed and stored. This prevents unauthorized access to plain text credentials.
- **Secure Data Storage**: User data, including conversation history and personal information, is stored securely in the database. Access controls are in place to ensure that data is only accessible by authorized entities.
- **Privacy Compliance**: The application is designed to comply with data protection regulations such as GDPR and CCPA, ensuring user data is handled responsibly.

### API Security

- **API Key Management**: OpenAI API keys and other sensitive credentials are securely managed using environment variables. This prevents hard-coding of keys in the source code.
- **Secure API Requests**: API interactions, especially with the OpenAI API, are conducted over secure channels. Input validation is performed to prevent injection attacks.

### Session Management

- **Secure Session Handling**: User sessions are managed securely using Flask’s built-in session management capabilities. Session data is encrypted and tamper-proof.
- **Session Timeout**: Implementing session timeouts to prevent unauthorized access to user sessions if left idle.

### Cross-Origin Resource Sharing (CORS)

- **CORS Policy**: A CORS policy is implemented to restrict cross-origin requests, preventing unauthorized domains from interacting with the application.

### Error Handling

- **Secure Error Responses**: The application is designed to handle errors gracefully, ensuring that sensitive information is not exposed through error messages or logs.

### Logging and Monitoring

- **Activity Logs**: The application maintains logs of key activities, especially for transactions involving sensitive data. These logs are crucial for auditing and identifying potential security breaches.
- **Monitoring**: Regular monitoring of the application for unusual activities or potential security threats.

### Data Access and User Consent

- **User Consent for Data Usage**: The application seeks user consent for collecting and using personal data, adhering to privacy laws.
- **Minimal Data Collection**: Only essential data required for the functionality of the application is collected and stored.

### Security Audits and Updates

- **Regular Security Audits**: Conducting periodic security audits to identify and address vulnerabilities.
- **Software Updates**: Keeping all software components up-to-date with the latest security patches.

---
