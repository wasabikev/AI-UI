# AI ∞ UI -- A Web Interface for LLM APIs

## Overview

AI ∞ UI is a web-based conversational interface that facilitates crafting and architecting layered (multi-system) AI orchestration. The AI ∞ UI system provides an interface to leverage a range of tools and models.
A core function of AI ∞ UI is to provide an interface for AI-assisted programming (or AI-driven programming) with various AI models via LLM APIs. It is designed to support collaborative coding activities between a human and an AI, with the AI generating the majority of the code based on the human's guidance and high-level decisions.

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


## Key Components

- **Backend**: The server is built with Flask and handles API routes, database interactions, and communication with LLM APIs.
- **Frontend**: The frontend is developed using HTML, CSS, JavaScript, Bootstrap, and additional libraries such as Prism.js and Marked.js for enhanced functionality.
- **Database**: PostgreSQL is used for storing user data, conversation history, and system messages.

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

- `get_response_from_model(model, messages, temperature)': Routes the request to the appropriate API based on the selected model (OpenAI or Anthropic).
- `chat()`: Endpoint for processing and responding to user messages from AI models
- `get_conversations()`: Retrieves a list of conversations for the current user.
- `get_conversation()`: Fetches details of a specific conversation.
- `update_conversation_title()`: Endpoint to update a conversation's title.
- `delete_conversation()`: Endpoint to remove a conversation from the database.

### main.js

- `updateConversationList()`: Refreshes the conversation list in the sidebar.
- `loadConversation()`: Loads messages from a selected conversation into the chat interface.
- `sendMessage()`: Sends user input to the server for processing and appends the AI's response to the chat.
- `renderOpenAI(content)`: Processes and renders Markdown, code snippets, and LaTeX content within the chat interface.
- `updateSystemMessageDropdown()`, `populateSystemMessageModal()`, `updateModelDropdownInModal(modelName)`: Functions related to system message management, allowing for the customization of automated responses.
- `updateTemperatureDisplay()`, `toggleTemperatureSettings()`: Functions for managing the temperature setting and model selection, providing flexibility in AI interactions.
- `createMessageElement(message)`, `updateConversationList()`, `loadConversation(conversationId)`: Functions for dynamically updating the UI and handling real-time user interactions.
- `saveWebsiteURL(websiteURL, systemMessageId)`: Saves a website URL associated with a particular system message to the backend. Handles POST request and error management.
- `updateModelDropdownInModal(modelName)`: Updates the model dropdown in the system message modal to reflect the selected model name.
- `toggleTemperatureSettings(shouldShowTemperature)`: Toggles the visibility of temperature settings in the system message modal based on user interaction.
- `updateModelDropdownInModal(modelName)`: Updates the model dropdown in the system message modal to reflect the selected model name, ensuring the UI is synchronized with the backend model settings.
- `populateModelDropdownInModal()`: Populates the model dropdown in the system message modal with available AI models, allowing users to select different models dynamically.
- Additionally, `main.js` handles dynamic text area resizing, admin dashboard access, database view access, and flash message timeout functionalities as linked with events in `chat.html`.



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

## Feature Roadmap
**Support for Additional AI Models**: Integrate more models from different providers to enhance versatility.
**Expansion of System Message Modal**: Enhance the system message modal to serve as a central hub for orchestrating various layers of interaction, including but not limited to system messages, temperature settings, and the integration of controls for adding websites, files, graph databases, and advanced AI parameters like top-k settings.
**Enhanced Security Features**: Implement advanced authentication and authorization features to secure user interactions.


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