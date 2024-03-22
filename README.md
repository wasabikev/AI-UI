# AI ∞ UI -- A Web Interface for LLM APIs

## Overview

AI ∞ UI is a web-based conversational interface that facilitates interactions with various AI models via LLM APIs. It is designed to support pair-programming activities, particularly with a Large Language Model (LLM) as an assistant.

## Features

- **Persisted Conversations**: Conversations are stored in a database, allowing for historical review and continuation of discussions.
- **Real-time Chat**: Immediate communication with AI models, simulating a real-time conversation.
- **Conversation Management**: Users can create, read, update, and delete conversations.
- **Multiple AI Models**: The interface supports switching between different AI models, including OpenAI and Anthropic models, to cater to diverse conversational needs. (More models to come later)
- **Interactive UI**: A user-friendly interface with a chat box and messaging system that ensures a seamless conversational flow.
- **Admin Dashboard**: An admin interface for user management and system message configuration.
- **Rich Text Interaction**: Supports Markdown, code snippets with syntax highlighting, and LaTeX content, enabling rich text interactions within the chat interface.
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
- **main.js**: Client-side logic for handling UI events, API calls, and dynamic content updates.
- **chat.html**: The main chat interface template that users interact with.
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


### models.py

- `Conversation`: Represents a conversation with fields such as title, history, and token count.
- `User`: Represents a user with fields for username, email, and password.
- `SystemMessage`: Represents a system message that can be used as a template or preset response.

### Modal-Based User Interface Guidelines

- In our project, we prioritize a modal-based approach for user interfaces when requesting input or displaying information that requires user interaction. This approach ensures a consistent, accessible, and user-friendly experience across the application. 
- Use Modals for User Input: Whenever the application requires input from the user, whether it's form submission, settings configuration, or any other input-driven task, use a modal window. This includes actions like adding or editing data, confirming decisions, or any interaction that benefits from focused attention.
- For future iterations and feature implementations, we strongly encourage maintaining the modal-based approach for user interfaces. This consistency is key to providing an intuitive and pleasant user experience across our application.

## Feature Roadmap

### TriFusion Query

Status: Under development

Objective: Enhance the chatbot's capability to provide insightful and contextually relevant responses by leveraging a unique combination of three distinct database methodologies: relational, vector, and graph databases. This feature, named "TriFusion Query," aims to unify structured data querying, semantic search, and relationship exploration into a single, powerful query mechanism.

Functional Spec:

Relational Database Integration: Utilize a relational database (e.g., PostgreSQL) to store and manage structured data extracted from targeted websites. This will support complex queries, ensuring data integrity and transactional support for retrieving specific facts and structured information.

Vector Database Incorporation: Implement a vector database to store text content from websites as vector representations, enabling efficient semantic search and similarity-based retrieval. This will allow the chatbot to provide contextually relevant responses based on the semantic similarity of user queries to stored data.

Graph Database Utilization: Employ a graph database to represent the relationships between different entities extracted from websites, such as articles, authors, and categories. This will enable the exploration of interconnected data, uncovering hidden patterns and recommending related content based on the relational context.

Query Fusion Mechanism: Develop a sophisticated query fusion mechanism that, upon receiving a user query, simultaneously leverages the relational, vector, and graph databases. This mechanism will parse the query, identify relevant keywords and entities, and retrieve data from all three databases. The aggregated data will then be used to generate comprehensive, accurate, and insightful responses.

System Prompt Integration: Ensure that the "TriFusion Query" feature is seamlessly integrated into the system prompt, allowing for dynamic adjustment of query parameters, including targeted system prompts and temperature settings. This will enable the customization of chatbot responses to achieve the desired level of creativity, specificity, and relevance.

Anticipated Benefits:

- Enhanced accuracy and relevance of chatbot responses through semantic search capabilities and structured data retrieval.
- Improved user experience by providing comprehensive answers that leverage interconnected data and insights.
- Increased flexibility and adaptability of the chatbot in addressing a wide range of user queries with contextually rich responses.

Development Milestones:

- Relational Database Schema Design: Define and implement the schema for storing structured data from websites.
- Vector Representation Processing: Select and integrate natural language processing (NLP) models for generating vector representations of text content.
- Graph Database Structure Implementation: Design and create the graph database structure to represent the relationships between extracted entities.
- Query Fusion Mechanism Development: Develop the core logic for the query fusion mechanism that combines data retrieval from all three databases.
- Integration and Testing: Integrate the "TriFusion Query" feature into the existing system, followed by thorough testing to ensure accuracy and efficiency.

Target Completion Date: TBD


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

**Note**: This README is intended for use by the LLM providing pair-programming assistance and may include specific instructions or details pertinent to that role.