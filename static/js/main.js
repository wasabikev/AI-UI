let messages = [];


let systemMessages = [];


let model; // This variable stores the selected model name
let activeConversationId = null; // This will keep track of the currently selected conversation
let currentSystemMessage; // Default system message
let currentSystemMessageDescription; // Description of the current system message
let initialTemperature;
let isSaved = false; // Flag to track whether the system message changes have been saved
let activeSystemMessageId = null; // Variable to track the currently active system message ID
let showTemperature = false;  // Tracks the visibility of the temperature settings
let selectedTemperature = 0.7; // Default temperature value


document.addEventListener("DOMContentLoaded", function() {
    // Fetch and process system messages
    fetchAndProcessSystemMessages().then(() => {
        // Populate the system message modal
        populateSystemMessageModal();

        // Check if there's an active conversation and if the chat is empty
        if (!activeConversationId && $('#chat').children().length === 0) {
            // Find the default system message and display it
            const defaultSystemMessage = systemMessages.find(msg => msg.name === "Default System Message");
            if (defaultSystemMessage) {
                displaySystemMessage(defaultSystemMessage);
            } else if (systemMessages.length > 0) {
                // If there's no "Default System Message", display the first one in the list
                displaySystemMessage(systemMessages[0]);
            }
        }
    }).catch(error => {
        console.error('Error during system message fetch and display:', error);
    });
});


function saveWebsiteURL(websiteURL, systemMessageId) {
    fetch(`/api/system-messages/${systemMessageId}/add-website`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ websiteURL: websiteURL }),
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        console.log('Success:', data);
        // Handle success, such as updating the UI or showing a success message
    })
    .catch((error) => {
        console.error('Error:', error);
        // Handle error, such as showing an error message to the user
    });
}





function updateSystemMessageDropdown() {
    let dropdownMenu = document.querySelector('#systemMessageModal .dropdown-menu');
    let dropdownButton = document.getElementById('systemMessageDropdown'); // Button for the dropdown

    if (!dropdownMenu || !dropdownButton) {
        console.error("Required elements not found in the DOM.");
        return;
    }

    // Clear existing dropdown items
    dropdownMenu.innerHTML = '';

    // Repopulate the dropdown menu
    systemMessages.forEach((message, index) => {
        let dropdownItem = document.createElement('button');
        dropdownItem.className = 'dropdown-item';
        dropdownItem.textContent = message.name;
        dropdownItem.onclick = function() {
            // Update the dropdown button text and modal content
            dropdownButton.textContent = this.textContent; // Update the system message dropdown button text
            document.getElementById('systemMessageName').value = message.name || '';
            document.getElementById('systemMessageDescription').value = message.description || '';
            document.getElementById('systemMessageContent').value = message.content || '';
            document.getElementById('systemMessageModal').dataset.messageId = message.id;
            // Update the current system message description
            currentSystemMessageDescription = message.description;
            // Update the temperature display
            updateTemperatureSelectionInModal(message.temperature);
            // Update the model dropdown in the modal and the global model variable
            updateModelDropdownInModal(message.model_name);
            model = message.model_name; // Update the global model variable
        };
        dropdownMenu.appendChild(dropdownItem);
    });
}

function renderMathInElement(element) {
    // Check if the element's content contains LaTeX patterns
    if (element.textContent.match(/\\\(.+?\\\)|\\\[\s\S]+?\\\]/)) {
        // Update the math content to render it
        MathJax.typesetPromise([element]).then(() => {
            console.log('Math content updated in element.');
        }).catch((err) => console.log('Error typesetting math content in element: ', err));
    }
}



function showModalFlashMessage(message, category) { // Usage Example: showModalFlashMessage('System message saved.', 'success');
    var flashContainer = document.getElementById('modal-flash-message-container');
    flashContainer.innerHTML = ''; // Clear previous messages

    var flashMessageDiv = document.createElement('div');
    flashMessageDiv.classList.add('alert', `alert-${category}`, 'text-center');
    flashMessageDiv.textContent = message;

    flashContainer.appendChild(flashMessageDiv);

    // Hide the message after 3 seconds
    setTimeout(function() {
        flashContainer.innerHTML = ''; // Clear the message
    }, 3000);
}


function checkAdminStatus(e) {
    if (!isAdmin) {
        e.preventDefault(); // Prevent the default action
        $.ajax({
            url: "/trigger-flash", // URL to a route that triggers the flash messagepopulateSystemMessageModal
            type: "GET",
            success: function() {
                location.reload(); // Reload the page to display the flash message
            }
        });
    } else {
        window.location.href = '/admin'; // Redirect to admin dashboard if the user is an admin
    }
}

// Function to open the modal and set the user ID and current status
function openStatusModal(userId, currentStatus) {
    // Set the action URL for the form
    document.getElementById('statusUpdateForm').action = `/update-status/${userId}`;

    // Check the radio button that matches the current status
    if (currentStatus === 'Active') {
        document.getElementById('statusActive').checked = true;
    } else if (currentStatus === 'Pending') {
        document.getElementById('statusPending').checked = true;
    } else {
        document.getElementById('statusNA').checked = true;
    }

    // Open the modal
    $('#statusUpdateModal').modal('show');
}

// Function to submit the form
function updateStatus() {
    document.getElementById('statusUpdateForm').submit();
}

function fetchAndProcessSystemMessages() {
    return new Promise((resolve, reject) => {
        fetch('/api/system_messages')
            .then(response => response.json())
            .then(data => {
                systemMessages = data; // Update the systemMessages array

                // Populate system message modal here
                populateSystemMessageModal(); // Ensure this is called after systemMessages are set

                // If there's no active system message, set it to the default
                if (!activeSystemMessageId) {
                    const defaultSystemMessage = systemMessages.find(msg => msg.name === "Default System Message");
                    if (defaultSystemMessage) {
                        // Set the activeSystemMessageId
                        activeSystemMessageId = defaultSystemMessage.id;
                    }
                }

                // Find the active system message
                const activeSystemMessage = systemMessages.find(msg => msg.id === activeSystemMessageId);
                if (activeSystemMessage) {
                    // Display the active system message description in the UI
                    displaySystemMessage(activeSystemMessage);
                } else {
                    // If there's no active system message, display the description of the first system message in the UI
                    displaySystemMessage(systemMessages[0]);
                }

                resolve(); // Resolve the promise after system messages are processed
            })
            .catch(error => {
                console.error('Error fetching system messages:', error);
                reject(error); // Reject the promise if there's an error
            });
    });
}





// Add this code to the beginning of your script
document.querySelectorAll('input[name="temperatureOptions"]').forEach(radio => {
    radio.addEventListener('change', function() {
        selectedTemperature = parseFloat(this.value);
        console.log("Temperature changed via radio button to:", selectedTemperature);
    });
});


$('#systemMessageModal').on('hide.bs.modal', function (event) {
    // Check if the changes were not saved
    if (!isSaved) {
        console.log("Modal closed without saving. Restoring initial states where necessary.");

        // Revert temperature only if not saved
        selectedTemperature = initialTemperature;
        updateTemperatureSelectionInModal(initialTemperature);

        // Revert other UI changes here (if any were made)
        if (activeSystemMessageId) {
            const activeSystemMessage = systemMessages.find(msg => msg.id === activeSystemMessageId);
            if (activeSystemMessage) {
                document.getElementById('systemMessageName').value = activeSystemMessage.name;
                document.getElementById('systemMessageDescription').value = activeSystemMessage.description;
                document.getElementById('systemMessageContent').value = activeSystemMessage.content;
                document.getElementById('modalModelDropdownButton').dataset.apiName = activeSystemMessage.model_name;
                document.getElementById('systemMessageDropdown').textContent = activeSystemMessage.name;
                console.log("Modal content reset to active system message:", activeSystemMessage.name);
            }
        }
    } else {
        console.log("Changes were saved, no need to revert.");
    }

    // Reset the isSaved flag and any other flags or data attributes
    isSaved = false;
    $(this).removeData('targetGroup');

    // Cleanup UI changes
    $(this).find('.modal-dialog').css('height', 'auto');
    $('.modal-content-group').addClass('hidden');  // Ensure all groups are hidden by default
});





document.getElementById('saveSystemMessageChanges').addEventListener('click', function() {
    console.log("Before saving system message, selectedTemperature:", selectedTemperature);
    const messageName = document.getElementById('systemMessageName').value.trim();
    const messageDescription = document.getElementById('systemMessageDescription').value;
    const messageContent = document.getElementById('systemMessageContent').value;
    const modelName = document.getElementById('modalModelDropdownButton').dataset.apiName;
    const temperature = selectedTemperature;

    const messageId = document.getElementById('systemMessageModal').dataset.messageId;

    // Check if a system message with the same name already exists when creating a new message
    if (!messageId) {
        const existingMessage = systemMessages.find(message => message.name.toLowerCase() === messageName.toLowerCase());
        if (existingMessage) {
            showModalFlashMessage("Please select a different name. That name is already in use.", "warning");
            return; // Stop the function from proceeding further
        }
    }

    if (messageId) {
        // Updating an existing system message
        $.ajax({
            url: `/system-messages/${messageId}`,
            method: 'PUT',
            contentType: 'application/json',
            data: JSON.stringify({
                name: messageName,
                description: messageDescription,
                content: messageContent,
                model_name: modelName,
                temperature: selectedTemperature
            }),
            success: function(response) {
                console.log('System message updated successfully:', response);

                // Set the isSaved flag to true here to indicate changes were saved
                isSaved = true;

                // Set the activeSystemMessageId to the ID of the system message that was just saved
                activeSystemMessageId = messageId;

                // Update the global model variable
                model = modelName;
                console.log('Global model variable updated to:', model);

                // Fetch and process system messages
                fetchAndProcessSystemMessages().then(() => {
                    // Update the selected temperature and the temperature display
                    selectedTemperature = temperature;
                    console.log("Temperature after AJAX response:", selectedTemperature);
                    updateTemperatureDisplay();

                    // Update the model dropdown on the main page
                    $('#dropdownMenuButton').text(modelNameMapping(modelName));

                    // Update the system message display with the updated system message object
                const updatedSystemMessage = {
                    id: messageId,
                    name: messageName,
                    description: messageDescription,
                    content: messageContent,
                    model_name: modelName,
                    temperature: temperature
                };
                displaySystemMessage(updatedSystemMessage);

                    $('#systemMessageModal').modal('hide');
                });
            },
            error: function(error) {
                console.error('Error updating system message:', error);
            }
        });
    } else {
        // Creating a new system message
        $.ajax({
            url: `/system-messages`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                name: messageName,
                description: messageDescription,
                content: messageContent,
                model_name: modelName,
                temperature: temperature
            }),
            success: function(response) {
                console.log('System message created successfully:', response);

                // Fetch the updated list of system messages
                fetchAndProcessSystemMessages().then(() => {
                    // Assuming response contains the new system message ID, update activeSystemMessageId
                    activeSystemMessageId = response.id;

                    // Update the system message display with the updated system message object
                const updatedSystemMessage = {
                    id: messageId,
                    name: messageName,
                    description: messageDescription,
                    content: messageContent,
                    model_name: modelName,
                    temperature: temperature
                };
                displaySystemMessage(updatedSystemMessage);

                    // Close the modal
                    $('#systemMessageModal').modal('hide');
                });
            },
            error: function(error) {
                console.error('Error creating system message:', error);
            }
        });
    }
});


function updateTemperatureSelectionInModal(temperature) {
    console.log("Updating temperature in modal to:", temperature);
    selectedTemperature = temperature;
    document.querySelectorAll('input[name="temperatureOptions"]').forEach(radio => {
        radio.checked = parseFloat(radio.value) === parseFloat(temperature);
    });
    updateTemperatureDisplay(); // Update the display to reflect the change
}

// Function to populate the system message modal
function populateSystemMessageModal() {
    let dropdownMenu = document.querySelector('#systemMessageModal .dropdown-menu');
    let dropdownButton = document.getElementById('systemMessageDropdown'); // Button for the dropdown

    if (!dropdownMenu || !dropdownButton) {
        console.error("Required elements not found in the DOM.");
        return;
    }

    // Clear existing dropdown items
    dropdownMenu.innerHTML = '';

    // Add each system message to the dropdown
    console.log('Populating system message modal...');
    systemMessages.forEach((message, index) => {
        console.log('System message:', message);
        console.log(`System message [${message.name}] temperature:`, message.temperature); 
        let dropdownItem = document.createElement('button');
        dropdownItem.className = 'dropdown-item';
        dropdownItem.textContent = message.name;
        dropdownItem.onclick = function() {
            // Update the dropdown button text and modal content
            dropdownButton.textContent = this.textContent; // Update the system message dropdown button text
            console.log(`Setting name: ${message.name}`);
            document.getElementById('systemMessageName').value = message.name || '';
            console.log(`Current name value in input: ${document.getElementById('systemMessageName').value}`);
            document.getElementById('systemMessageDescription').value = message.description || '';
            document.getElementById('systemMessageContent').value = message.content || '';
            document.getElementById('systemMessageModal').dataset.messageId = message.id;
            // Update the current system message description
            currentSystemMessageDescription = message.description;
            // Update the temperature display
            console.log(`Dropdown item clicked for [${message.name}], setting temperature to:`, message.temperature);
            initialTemperature = message.temperature;
            selectedTemperature = message.temperature;
            updateTemperatureSelectionInModal(message.temperature);
            // Update the model dropdown in the modal and the global model variable
            updateModelDropdownInModal(message.model_name);
            model = message.model_name; // Update the global model variable
            console.log('Model updated to:', model);

            editSystemMessage = message; // Set the editSystemMessage variable to the selected system message
        };
        dropdownMenu.appendChild(dropdownItem);
    });

    // Pre-select and display the default system message only if there's no active system message
    if (!activeSystemMessageId) {
        const defaultSystemMessage = systemMessages.find(msg => msg.name === "Default System Message");
        if (defaultSystemMessage) {
            dropdownButton.textContent = defaultSystemMessage.name;
            document.getElementById('systemMessageDescription').value = defaultSystemMessage.description || '';
            document.getElementById('systemMessageContent').value = defaultSystemMessage.content || '';
            document.getElementById('systemMessageModal').dataset.messageId = defaultSystemMessage.id;

            // Set the temperature to the default system message's temperature
            initialTemperature = defaultSystemMessage.temperature;
            updateTemperatureSelectionInModal(initialTemperature);

            // Update the model variable and display the system message
            model = defaultSystemMessage.model_name;
            displaySystemMessage(defaultSystemMessage);
        }
    }    
}

function updateTemperatureDisplay() {
    // Get the value of the currently selected temperature
    const selectedTemperatureValue = document.querySelector('input[name="temperatureOptions"]:checked').value;

    // Get the short description for the selected temperature
    const selectedTemperatureDescription = temperatureDescriptions[selectedTemperatureValue];

    // Update the temperature display
    document.getElementById('temperatureDisplay').textContent = 'Temperature: ' + selectedTemperatureDescription;
}

function displaySystemMessage(systemMessage) {
    // Remove existing system messages
    $('.chat-entry.system.system-message').remove();

    // Update the UI with the system message description, model name, and temperature
    let systemMessageButton = createSystemMessageButton();
    const modelDisplayName = modelNameMapping(model);
    const temperatureDisplay = systemMessage.temperature;
    const descriptionContent = `<span class="no-margin">${renderOpenAI(systemMessage.description)}</span>`;
    const renderedContent = `
    <div class="chat-entry system system-message">
        <strong>System:</strong>${systemMessageButton}${descriptionContent}<br>
        <strong>Model:</strong> <span class="model-name">${modelDisplayName}</span> <strong>Temperature:</strong> ${temperatureDisplay}°
    </div>`;

    // Update the UI
    $('#chat').prepend(renderedContent);

    // Update the message in the 'messages' array with the content
    if (messages.length > 0 && messages[0].role === "system") {
        messages[0].content = systemMessage.content;
    } else {
        // If there's no existing system message at the start of the array, add it
        messages.unshift({
            role: "system",
            content: systemMessage.content
        });
    }
}



document.getElementById('delete-system-message-btn').addEventListener('click', function() {
    const messageId = document.getElementById('systemMessageModal').dataset.messageId;

    if (messageId) {
        if (confirm('Are you sure you want to delete this system message?')) {
            $.ajax({
                url: `/system-messages/${messageId}`,
                method: 'DELETE',
                success: function(response) {
                    console.log('System message deleted successfully:', response);

                    // Show the flash message in the modal
                    showModalFlashMessage('System message has been deleted', 'success');

                    // Find and set the System Default Message as the active message
                    const defaultSystemMessage = systemMessages.find(msg => msg.name === "Default System Message");
                    if (defaultSystemMessage) {
                        activeSystemMessageId = defaultSystemMessage.id;
                        document.getElementById('systemMessageName').value = defaultSystemMessage.name;
                        document.getElementById('systemMessageDescription').value = defaultSystemMessage.description;
                        document.getElementById('systemMessageContent').value = defaultSystemMessage.content;
                        document.getElementById('modalModelDropdownButton').dataset.apiName = defaultSystemMessage.model_name;
                        selectedTemperature = defaultSystemMessage.temperature;
                        updateTemperatureSelectionInModal(defaultSystemMessage.temperature);
                        updateModelDropdownInModal(defaultSystemMessage.model_name);
                    } else {
                        console.error('Default System Message not found');
                    }
                },
                error: function(error) {
                    console.error('Error deleting system message:', error);
                    showModalFlashMessage('Error deleting system message', 'danger');
                }
            });
        }
    } else {
        console.error('System message ID not found for deletion');
        showModalFlashMessage('System message ID not found', 'danger');
    }
});


document.getElementById('new-system-message-btn').addEventListener('click', function() {
    // Clear all the fields in the modal
    document.getElementById('systemMessageName').value = '';
    document.getElementById('systemMessageDescription').value = '';
    document.getElementById('systemMessageContent').value = '';

    // Clear the messageId from the modal's data attributes
    document.getElementById('systemMessageModal').dataset.messageId = '';

    // Set the model to GPT-3.5
    document.getElementById('modalModelDropdownButton').textContent = 'GPT-3.5';
    document.getElementById('modalModelDropdownButton').dataset.apiName = 'gpt-3.5-turbo';

    // Set the temperature to .07
    document.querySelector('input[name="temperatureOptions"][value="0.7"]').checked = true;
    updateTemperatureDisplay();
});

$(window).on('load', function () {
    // Fetch the current model_name from the backend when the page loads
    $.ajax({
        url: '/get-current-model',
        method: 'GET',
        success: function(response) {
            const apiModelName = response.model_name;
            const userFriendlyModelName = modelNameMapping(apiModelName);

            // Set the model variable to the actual model name used for API calls
            model = apiModelName;
            
            // Update the model dropdown on the main page with the user-friendly name
            $('#dropdownMenuButton').text(userFriendlyModelName);
            $('#dropdownMenuButton').show();

                // After successfully setting the model, call updateConversationList
                updateConversationList();
        },
        error: function(error) {
            console.error('Error fetching current model:', error);
        }
    });
});


document.querySelectorAll('input[name="temperatureOptions"]').forEach((radioButton) => {
    radioButton.addEventListener('change', updateTemperatureDisplay);
});

// Mapping between temperature values and their short descriptions
const temperatureDescriptions = {
    '0': '0 (Zero) - Deterministic',
    '0.3': '0.3 - Low Variability',
    '0.7': '0.7 - Balanced Creativity',
    '1.0': '1.0 - High Creativity',
    '1.5': '1.5 - Experimental'
};




// Helper function to map model names to their display values
function modelNameMapping(modelName) {
    console.log("Input model name:", modelName);
    let mappedName;
    switch(modelName) {
        case "gpt-3.5-turbo": mappedName = "GPT-3.5"; break;
        case "gpt-4-0613": mappedName = "GPT-4 (8k)"; break;
        case "gpt-4-1106-preview": mappedName = "GPT-4 (1106)"; break;
        case "gpt-4-turbo-2024-04-09": mappedName = "GPT-4 (Turbo)"; break;
        case "claude-3-opus-20240229": mappedName = "Claude 3 (Opus)"; break;
        case "gemini-1.5-pro": mappedName = "Gemini 1.5 Pro"; break;
        default: mappedName = "Unknown Model"; break;
    }
    console.log("Mapped model name:", mappedName);
    return mappedName;
}

// Function to populate the model dropdown in the modal
function populateModelDropdownInModal() {
    const modalModelDropdownMenu = document.querySelector('#systemMessageModal .model-dropdown-container .dropdown-menu');

    if (!modalModelDropdownMenu) {
        console.error("Required elements not found in the DOM.");
        return;
    }

    // Clear existing dropdown items
    modalModelDropdownMenu.innerHTML = '';

    // Define the available models
    const models = ["gpt-3.5-turbo", "gpt-4-0613", "gpt-4-1106-preview","gpt-4-turbo-2024-04-09","claude-3-opus-20240229","gemini-1.5-pro"];
    console.log("Available models:", models);

    // Add each model to the dropdown
    models.forEach((modelItem) => {
        let dropdownItem = document.createElement('button');
        dropdownItem.className = 'dropdown-item';
        dropdownItem.textContent = modelNameMapping(modelItem);
        dropdownItem.dataset.apiName = modelItem;
        dropdownItem.onclick = function() {
            // Update the dropdown button text and modal content
            let dropdownButton = document.getElementById('modalModelDropdownButton');
            dropdownButton.textContent = this.textContent;
            dropdownButton.dataset.apiName = this.dataset.apiName;
            console.log('Model selected in modal:', this.dataset.apiName);

            // Update the global model variable
            model = this.dataset.apiName;
            console.log('Global model variable updated to:', model);
        };
        
        modalModelDropdownMenu.appendChild(dropdownItem);
    });
}



function updateModelDropdownInModal(modelName) {
    const userFriendlyModelName = modelNameMapping(modelName);
    const modelDropdownButton = document.getElementById('modalModelDropdownButton');
    
    modelDropdownButton.textContent = userFriendlyModelName;
    modelDropdownButton.dataset.apiName = modelName;
}


// Example usage when a system message is selected or modal is opened
updateModelDropdownInModal('GPT-3.5'); // Update with the actual model name

$('#systemMessageModal').on('show.bs.modal', function () {
    const targetGroup = $(this).data('targetGroup');
    console.log("Modal show event - target group:", targetGroup);

    // Hide all groups
    $('.modal-content-group').addClass('hidden');

    // Show the selected group
    $('#' + targetGroup).removeClass('hidden');

    // Setup the dropdown for selecting the model.
    populateModelDropdownInModal();

    // Set the system message name if there's an active system message
    if (activeSystemMessageId) {
        const activeSystemMessage = systemMessages.find(msg => msg.id === activeSystemMessageId);
        if (activeSystemMessage) {
            document.getElementById('systemMessageName').value = activeSystemMessage.name;
            console.log("System message name set to:", activeSystemMessage.name);
            // Ensure the model dropdown is set to the correct model
            updateModelDropdownInModal(activeSystemMessage.model_name);
        }
    } else {
        // Optionally set a default name if no active message is found
        document.getElementById('systemMessageName').value = "Default Name";
        console.log("No active system message. Setting default name.");
        // Set a default model or handle the case where no model is set
        updateModelDropdownInModal("default-model-name"); // Adjust "default-model-name" as needed
    }
});

$('#systemMessageModal').on('hidden.bs.modal', function () {
    // Hide all content groups
    $('.modal-content-group').addClass('hidden');

    // Reset any specific flags or settings
    $(this).removeData('targetGroup');
});


// Event listener for the system message button in the chat interface
document.addEventListener('click', function(event) {
    if (event.target && event.target.closest('#systemMessageButton')) {
        // Set the target group to 'systemMessageContentGroup'
        $('#systemMessageModal').data('targetGroup', 'systemMessageContentGroup');

        // Show the modal
        $('#systemMessageModal').modal('show');
    }
});

// Reset modal to default state on close
$('#systemMessageModal').on('hidden.bs.modal', function () {
    // Hide all content groups
    $('.modal-content-group').addClass('hidden');

    // Reset any specific flags or settings
    $(this).removeData('targetGroup'); // Remove the data attribute for safety
});

function openModalAndShowGroup(targetGroup) {
    console.log("Opening modal with target group:", targetGroup);

    // Hide all groups in the modal
    $('.modal-content-group').addClass('hidden');

    // Show the selected group
    $('#' + targetGroup).removeClass('hidden');

    // Open the modal
    $('#systemMessageModal').modal('show');
}

function toggleContentGroup(groupID) {
    // Hide all groups
    const groups = document.querySelectorAll('.modal-content-group');
    groups.forEach(group => {
        group.classList.add('hidden');
    });

    // Show the selected group
    const selectedGroup = document.getElementById(groupID);
    if (selectedGroup) {
        selectedGroup.classList.remove('hidden');
    }
}

function createSystemMessageButton() {
    return `<button class="btn btn-sm" id="systemMessageButton" style="color: white;"><i class="fa-solid fa-gear"></i></button>`;
}

document.addEventListener('click', function(event) {
    if (event.target && event.target.id === 'add-system-message-btn') {
        // Logic to handle adding a new system message
    }
});


// Add event listener to model dropdown to handle model changes
document.addEventListener('change', function(event) {
    if (event.target && event.target.id === 'model-dropdown') {
        // Logic to handle model change
        let selectedModel = systemMessages[event.target.value];
        // Pass the entire system message object instead of just the content
        displaySystemMessage(selectedModel);
        // Additional logic to switch the conversation to the selected model
    }
});

document.addEventListener('click', function(event) {
    if (event.target && event.target.id === 'add-system-message-btn') {
        // Logic to handle adding a new system message
    }
});







function copyCodeToClipboard(button) {
    const codeBlock = button.closest('.code-block').querySelector('pre code');
    const range = document.createRange();
    window.getSelection().removeAllRanges(); // Clear current selection
    range.selectNode(codeBlock);
    window.getSelection().addRange(range); // Select the code block's content

    try {
        document.execCommand('copy'); // Copy the selection to clipboard
        button.textContent = 'Copied!'; // Optional: Provide user feedback
    } catch (err) {
        console.error('Failed to copy code: ', err);
        button.textContent = 'Failed to copy'; // Optional: Provide user feedback on failure
    }

    window.getSelection().removeAllRanges(); // Clear selection
}

function createMessageElement(message) {
    // Handle the system message differently to include the model name and temperature
    if (message.role === 'system') {
        let systemMessageContent = renderOpenAI(message.content);
        // Prepare the display content for system message
        const systemMessageHTML = `
            <div class="chat-entry system system-message">
                <strong>System:</strong> ${systemMessageContent}<br>
                <strong>Model:</strong> ${modelNameMapping(model)} &nbsp; <strong>Temperature:</strong> ${selectedTemperature.toFixed(2)}
            </div>`;
        return $(systemMessageHTML);
    } else {
        const prefix = message.role === 'user' ? '<i class="far fa-user"></i> ' : '<i class="fas fa-robot"></i> ';
        const messageClass = message.role === 'user' ? 'user-message' : 'bot-message';
        let processedContent;
        if (message.role === 'user') {
            // Escape HTML entities in user input to prevent rendering
            processedContent = escapeHtml(message.content);
        } else {
            // Use renderOpenAI to process both Markdown and code
            processedContent = renderOpenAI(message.content);
        }
        const messageHTML = `<div class="chat-entry ${message.role} ${messageClass}">${prefix}${processedContent}</div>`;
        return $(messageHTML);
    }
}

// Function to render Markdown and code snippets
function renderMarkdownAndCode(content) {
    console.log('renderMarkdownAndCode called with content:', content);

    // Normalize newlines to ensure consistent handling across different environments
    content = content.replace(/\r\n/g, '\n');

    // Step 1: Correctly identify and temporarily replace code blocks with placeholders
    let codeBlockCounter = 0;
    const codeBlocks = [];
    const codeBlockRegex = /```(\w*)\s*([\s\S]+?)\s*```/g;

    // Replace code blocks with placeholders and store their content in an array
    let safeContent = content.replace(codeBlockRegex, function(match, lang, code) {
        console.log(`Code block found: Language: ${lang}, Code: ${code.substring(0, 30)}...`);
        const index = codeBlockCounter++;
        codeBlocks[index] = { lang, code };
        return `%%%CODE_BLOCK_${index}%%%`;
    });

    // Step 2: Process Markdown using marked on content outside of code blocks
    safeContent = marked.parse(safeContent);

    // Step 3: Re-insert code blocks into the processed Markdown content
    safeContent = safeContent.replace(/%%%CODE_BLOCK_(\d+)%%%/g, function(match, index) {
        const { lang, code } = codeBlocks[index];
        return processCodeSnippet(lang, code);
    });

    console.log('Processed content with Markdown and code:', safeContent);
    return safeContent;
}

function processCodeSnippet(lang, code) {
    const languageClass = lang ? `language-${lang}` : 'language-plaintext';
    const displayLang = lang || "CODE";
    const escapedCode = escapeHtml(code.trim());

    return `
    <div class="code-block">
        <div class="code-block-header">
            <span class="code-type">${displayLang.toUpperCase()}</span>
            <button class="copy-code" onclick="copyCodeToClipboard(this)"><i class="fas fa-clipboard"></i> Copy code</button>
        </div>
        <pre><code class="${languageClass}">${escapedCode}</code></pre>
    </div>
    `;
}


// Enhanced HTML escaping function
function escapeHtml(html) {
    return html
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function renderOpenAI(content) {
    console.log('renderOpenAI called with content:', content);

    // Process the content to handle markdown and code
    content = renderMarkdownAndCode(content);

    // Process lists
    content = handleLists(content);

    console.log('Final processed content:', content);
    return content;
}


function handleLists(content) {
    // Process unordered lists
    content = content.replace(/^(?:\s*)-\s+(.+)/gm, '<ul><li>$1</li></ul>');
    content = content.replace(/(<ul><li>[\s\S]+?<\/li>)/gm, function(match) {
        if (!/^\s*<\/?ul>/.test(match)) {
            return '<ul>' + match + '</ul>';
        }
        return match;
    });
    content = content.replace(/<\/ul>\s*<ul>/g, '');

    // Process ordered lists
    content = content.replace(/^(?:\s*)(\d+\.)\s+(.+)/gm, '<li>$2</li></ul>');
    content = content.replace(/(<ul><li>[\s\S]+?<\/li>)/gm, function(match) {
        if (!/^\s*<\/?ol>/.test(match)) {
            return '<ol>' + match + '</ol>';
        }
        return match;
    });
    content = content.replace(/<\/ol>\s*<ol>/g, '');

    return content;
}



function updateConversationList() {
    console.log('Starting to update conversation list...');
    fetch('/api/conversations')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log(`Received ${data.length} conversations from server.`);

            // Prepare new HTML content for conversation list
            let newConversationListContent = '';
            // Add each conversation to the new content.
            data.forEach((conversation, index) => {
                const temperatureInfo = (typeof conversation.temperature !== 'undefined' && conversation.temperature !== null) ? `${conversation.temperature}°` : 'N/A°';
                newConversationListContent += `
                    <div class="conversation-item" data-id="${conversation.id}">
                        <div class="conversation-title">${conversation.title}</div>
                        <div class="conversation-meta">
                            <span class="model-name" title="AI Model used for this conversation">${conversation.model_name}</span>
                            <span class="temperature-info" title="Temperature setting">${temperatureInfo}</span>
                        </div>
                    </div>
                `;
            });
            
            // Replace conversation list content with new content
            $('#conversation-list').html(newConversationListContent);
            console.log('Conversation list updated.');

            // Add click event handlers to the conversation elements.
            $('.conversation-item').click(function() {
                const conversationId = $(this).data('id');
                console.log(`Loading conversation with id: ${conversationId}`);
                
                // Update the URL to reflect the conversation being loaded
                window.history.pushState({}, '', `/c/${conversationId}`);

                // Load the conversation data
                loadConversation(conversationId);
            });
        })
        .catch(error => {
            console.error(`Error updating conversation list: ${error}`);
        });
}



$('#edit-title-btn').click(function() {
    const newTitle = prompt('Enter new conversation title:', $('#conversation-title').text());
    if (newTitle) {
        $.ajax({
            url: `/api/conversations/${activeConversationId}/update_title`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ title: newTitle }),
            success: function(response) {
                $('#conversation-title').text(newTitle);
                
                // Update the title in the sidebar
                const targetConversationItem = $(`.conversation-item[data-id="${activeConversationId}"] .conversation-title`);
                
                // Log for debugging purposes
                console.log('Attempting to update sidebar title for conversation ID:', activeConversationId);
                console.log('Targeted element:', targetConversationItem);
                
                targetConversationItem.text(newTitle);
            },
            error: function(error) {
                console.error("Error updating title:", error);
            }
        });
    }
});


$('#delete-conversation-btn').click(function() {
    const confirmation = confirm('Are you sure you want to delete this conversation? This action cannot be undone.');
    if (confirmation) {
        $.ajax({
            url: `/api/conversations/${activeConversationId}`,
            method: 'DELETE',
            success: function(response) {
                // Upon successful deletion, redirect to the main URL.
                window.location.href = '/';
            },
            error: function(error) {
                console.error("Error deleting conversation:", error);
            }
        });
    }
});



// This function shows the conversation controls (title, rename and delete buttons)
function showConversationControls(title = "AI &infin; UI", tokens = {prompt: 0, completion: 0, total: 0}) {
    // Update the title
    console.log("Inside showConversationControls function. Title:", title);
    console.log("Inside showConversationControls. Tokens:", tokens);

    $("#conversation-title").html(title);
    $("#conversation-title, #edit-title-btn, #delete-conversation-btn").show();

    // Update token data
    $("#prompt-tokens").text(`Prompt Tokens: ${tokens.prompt_tokens}`);
    $("#completion-tokens").text(`Completion Tokens: ${tokens.completion_tokens}`);
    $("#total-tokens").text(`Total Tokens: ${tokens.total_tokens}`);
}


// This function fetches and displays a conversation.
function loadConversation(conversationId) {
    console.log(`Fetching conversation with id: ${conversationId}...`);
    fetch(`/conversations/${conversationId}`)
        .then(response => {
            console.log('Response received for conversation fetch', response);
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Update the conversation title in the UI
            $('#conversation-title').text(data.title);

            // Update the messages array with the conversation history
            console.log('Parsed JSON data from conversation:', data);

            messages = data.history;
            console.log(`Received conversation data for id: ${conversationId}`);
            console.log('Token Count:', data.token_count);
            console.log("Retrieved model name:", data.model_name); // Log the retrieved model name

            // Update the dropdown display based on the model name from the conversation
            const modelName = data.model_name;
            $('.current-model-btn').text(modelNameMapping(modelName));
            // Also update the global model variable
            model = modelName;

            // Retrieve and handle the temperature setting
            selectedTemperature = data.temperature || 0.3; // Use the temperature from the data, or default to 0.3 if it's null/undefined

            // Update the token data in the UI for restored conversations
            const tokens = {
                prompt_tokens: 'NA',
                completion_tokens: 'NA',
                total_tokens: data.token_count || 'NA'
            };
            showConversationControls(data.title || "AI ∞ UI", tokens);

            // Save this conversation id as the active conversation
            activeConversationId = conversationId;

            // Clear the chat
            $('#chat').empty();

            // Add each message to the chat. Style the messages based on their role.
            data.history.forEach(message => {
                const messageElement = createMessageElement(message);
                $('#chat').append(messageElement);
            });

            // After all messages are added to the DOM, call MathJax to typeset the entire chat container
            // We use setTimeout to delay the call to MathJax.typesetPromise to ensure the DOM is fully updated
            setTimeout(function() {
                MathJax.typesetPromise().then(() => {
                    console.log('MathJax has finished typesetting.');
                }).catch((err) => console.log('Error typesetting math content: ', err));
            }, 0); // You can increase the delay if needed, but sometimes even a delay of 0 is enough

            Prism.highlightAll(); // Highlight code blocks after adding content to the DOM

            // Important! Update the 'messages' array with the loaded conversation history
            messages = data.history;

            console.log(`Chat updated with messages from conversation id: ${conversationId}`);

            // Scroll to the bottom after populating the chat
            const chatContainer = document.getElementById('chat');
            chatContainer.scrollTop = chatContainer.scrollHeight;
        })
        .catch(error => {
            console.error(`Error fetching conversation with id: ${conversationId}. Error: ${error}`);
        });
}




//Record the default height 
var defaultHeight = $('#user_input').css('height');

// This function is called when the user submits the form.
$('#chat-form').on('submit', function (e) {
    console.log('Chat form submitted with user input:', $('#user_input').val());
    e.preventDefault();
    var userInput = $('#user_input').val();

    var userInputDiv = $('<div class="chat-entry user user-message">')
        .append('<i class="far fa-user"></i> ')
        .append($('<span>').text(userInput));

    $('#chat').append(userInputDiv);
    $('#chat').scrollTop($('#chat')[0].scrollHeight);

    messages.push({ "role": "user", "content": userInput });

    var userInputTextarea = $('#user_input');
    userInputTextarea.val('');
    userInputTextarea.css('height', defaultHeight);

    document.getElementById('loading').style.display = 'block';

    let requestPayload = {
        messages: messages,
        model: model,
        temperature: selectedTemperature
    };

    if (activeConversationId !== null) {
        requestPayload.conversation_id = activeConversationId;
    }
    console.log('Sending request payload:', JSON.stringify(requestPayload));

    fetch('/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestPayload)
    })
    .then(response => {
        console.log('Received response from /chat endpoint:', response);

        document.getElementById('loading').style.display = 'none';

        if (!response.ok) {
            return response.text().then(text => {
                throw new Error(text);
            });
        }

        return response.json();
    })
    .then(data => {
        console.log("Complete server response:", data);
        const renderedBotOutput = renderOpenAI(data.chat_output);
        const botMessageDiv = $('<div class="chat-entry bot bot-message">')
            .append('<i class="fas fa-robot"></i> ')
            .append(renderedBotOutput);
        $('#chat').append(botMessageDiv);

        $('#chat').scrollTop($('#chat')[0].scrollHeight);
        messages.push({ "role": "assistant", "content": data.chat_output });

        // Call MathJax to typeset the new message
        MathJax.typesetPromise().then(() => {
            console.log('MathJax has finished typesetting the new message.');
        }).catch((err) => console.log('Error typesetting math content: ', err));

        Prism.highlightAll();
        updateConversationList();

        // Update the URL with the received conversation_id
        window.history.pushState({}, '', `/c/${data.conversation_id}`);

        if (data.conversation_title) {
            console.log("Received conversation_title from server:", data.conversation_title);
            // Log the token usage data
            console.log("Token usage data:", data.usage);
            // Update token data in the UI
            const tokens = data.usage;
            showConversationControls(data.conversation_title, tokens);
        } else {
            console.log("No conversation_title from server. Showing default.");
            showConversationControls();
        }
        console.log('End of chat-form submit function');
    })
    .catch(error => {
        console.error('Error processing chat form submission:', error);
        document.getElementById('loading').style.display = 'none';
    });
});



// This function checks if there's an active conversation in the session.
function checkActiveConversation() {
    fetch('/get_active_conversation')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            const conversationId = data.conversationId;
            if (conversationId) {
                // If there's an active conversation ID in the session, load it
                loadConversation(conversationId);
                // Show the title, rename and delete buttons
                $('#conversation-title, #edit-title-btn, #delete-conversation-btn').show();
            } else {
                // Hide the title, rename and delete buttons
                $('#conversation-title, #edit-title-btn, #delete-conversation-btn').hide();
            }
        })
        .catch(error => {
            console.error('Error checking for active conversation:', error);
            // Optionally hide the elements in case of an error. Depends on your desired behavior.
            $('#conversation-title, #edit-title-btn, #delete-conversation-btn').hide();
        });
}


$(document).ready(function() {  // Document Ready (initialization)
    console.log("Document ready."); // Debug

    // Initialize autosize for the textarea
    autosize($('#user_input'));

    // Set default title
    $("#conversation-title").html("AI &infin; UI");

    // Function to update the temperature modal
    function updateTemperatureModal() {
        document.querySelectorAll('input[name="temperatureOptions"]').forEach(radio => {
            radio.checked = parseFloat(radio.value) === selectedTemperature;
        });
    }

    // Fetch the current model_name from the backend and initialize the application
    $.ajax({
        url: '/get-current-model',
        method: 'GET',
        success: function(response) {
            const apiModelName = response.model_name;
            const userFriendlyModelName = modelNameMapping(apiModelName);
            model = apiModelName; // Set the model variable correctly
            $('#dropdownMenuButton').text(userFriendlyModelName);
        },
        error: function(error) {
            console.error('Error fetching current model:', error);
        }
    });

    // Add click event handler for the "+ New" button
    $('#new-chat-btn').click(function() {
        // Clear the chat area
        $('#chat').empty();
    
        // Clear the conversation title
        $('#conversation-title').text('');
    
        // Reset the messages array
        messages = [];
    
        // Reset the active conversation ID
        activeConversationId = null;
    
        // Navigate to the root URL
        window.location.href = '/';
    });

    // Handler for model dropdown items
    $('.model-dropdown .dropdown-item').on('click', function(event) {
        event.preventDefault(); // Prevent the # appearing in the URL
        $('#dropdownMenuButton').text($(this).text());
        model = $(this).attr('data-model'); // Update the model variable here
        console.log("Dropdown item clicked. Model is now: " + model);

        // Update the displayed model name in the system message section
        $('.chat-entry.system.system-message .model-name').text(modelNameMapping(model));
    });

    // Handler for system settings dropdown items
    $('.settings-dropdown .dropdown-item').on('click', function(event) {
        event.preventDefault();
        const targetGroup = $(this).data('target');
        console.log("Settings dropdown item clicked, target group:", targetGroup);
        
        // Pass the target group to the modal
        $('#systemMessageModal').data('targetGroup', targetGroup);
        $('#systemMessageModal').modal('show');
    });

    // Needed for "Send" to respond to the 'enter' key.
    $('#user_input').keydown(function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); // Still prevent the default to avoid a newline on Enter
            $('#chat-form').submit(); // Submit form when Enter is pressed without Shift
        }
    });
});
    
    // ... other initialization code ...







    // ... other initialization code that should run when the page is fully loaded ...
