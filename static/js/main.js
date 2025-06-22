// main.js

let messages = []; // An array that stores the converstation messages

window.systemMessages = [];  // Make it explicitly global
let systemMessages = []; // An array that stores the system message


let model; // This variable stores the selected model name
let activeConversationId = window.APP_DATA?.conversationId ?? null // This keeps track of the currently selected conversation.
let currentSystemMessage; // Stores the currently selected system message.
let currentSystemMessageDescription; // Stores the description of the current system message.
let initialTemperature; // Stores the initial temperature setting.
let isSaved = false; // Flag to track whether the system message changes have been saved
let activeSystemMessageId = null; // Variable to track the currently active system message ID
let showTemperature = false;  // Tracks the visibility of the temperature settings
let selectedTemperature = 0.7; // Default temperature value
let activeWebsiteId = null;  // This will store the currently active website ID for the Websites Group
let tempWebSearchState = false; // This will store the temporary web search state
let tempDeepSearchState = false; // This will store the temporary deep search state

// Safely initialize APP_DATA related variables
const APP_DATA = window.APP_DATA || {};
const isAdmin = APP_DATA.isAdmin || false;
let currentSessionId = APP_DATA?.sessionId ?? null;  // Session ID will be provided by server for speed optimization and to avoid duplicate status updates


// Constants for WebSocket management
const MAX_WS_RECONNECT_ATTEMPTS = 5;
const INITIAL_RECONNECT_DELAY = 1000;
const HEALTH_CHECK_INTERVAL = 30000; // 30 seconds
let wsReconnectAttempts = 0;
let wsReconnectDelay = INITIAL_RECONNECT_DELAY;
let maintainWebSocketConnection = false;
let statusWebSocket = null;
let statusUpdateContainer = null;
let healthCheckInterval = null;

// variables to manage pagination of converstation list
let isLoadingConversations = false;
let currentPage = 1;
let hasMoreConversations = true;

// Variable to manage the direct file attachment feature (Context Files)
let attachedContextFiles = new Map(); // Store temporary file attachments: Map<fileId, {name, size, type, tokenCount, content}>

const AVAILABLE_MODELS = [
    { api: "gpt-3.5-turbo", display: "GPT-3.5" },
    { api: "gpt-4o-2024-08-06", display: "GPT-4o" },
    { api: "gpt-4.1", display: "GPT-4.1" },
    { api: "gpt-4.1-mini", display: "GPT-4.1 Mini" },
    { api: "gpt-4.1-nano", display: "GPT-4.1 Nano" },
    { api: "o3-mini", display: "o3-mini (Fast)", reasoning: "low" },
    { api: "o3-mini", display: "o3-mini (Balanced)", reasoning: "medium" },
    { api: "o3-mini", display: "o3-mini (Deep)", reasoning: "high" },
    // Removed: { api: "claude-3-opus-20240229", display: "Claude 3 Opus" },
    { api: "claude-3-5-sonnet-20241022", display: "Claude 3.5 Sonnet" },
    { api: "claude-3-7-sonnet-20250219", display: "Claude 3.7 Sonnet", supportsExtendedThinking: true },
    {
        api: "claude-3-7-sonnet-20250219",
        display: "Claude 3.7 Sonnet (Ext)",
        extendedThinking: true,
        thinkingBudget: 12000
    },
    // New Claude 4 models:
    { api: "claude-sonnet-4-20250514", display: "Claude Sonnet 4" },
    { api: "claude-opus-4-20250514", display: "Claude Opus 4" },
    { api: "gemini-2.0-pro-exp-02-05", display: "Gemini 2.5 Pro" },
    { api: "gemini-2.0-flash", display: "Gemini 2.0 Flash" },
    // Removed: { api: "llama3.1-8b", display: "Llama 3.1 (8B)" },
    { api: "llama-3.3-70b", display: "Llama 3.3 (70B)" },
    { api: "deepSeek-r1-distill-llama-70B", display: "DeepSeek R1 (70B)" }
];


// Helper function to create dropdown items
function createModelDropdownItem(modelItem, onClick) {
    const item = $('<button>')
        .addClass('dropdown-item')
        .text(modelItem.display)
        .attr('data-api-name', modelItem.api);

    // Add any additional model-specific attributes
    if (modelItem.reasoning) {
        item.attr('data-reasoning', modelItem.reasoning);
    }
    if (modelItem.extendedThinking) {
        item.attr('data-extended-thinking', true);
        item.attr('data-thinking-budget', modelItem.thinkingBudget);
    }

    // Attach click handler if provided
    if (onClick) {
        item.on('click', onClick);
    }

    return item;
}

// Function to initialize the main model dropdown
function initializeModelDropdown() {
    const mainDropdownButton = $('#dropdownMenuButton');
    const dropdownMenu = mainDropdownButton.next('.dropdown-menu');

    if (!dropdownMenu.length) {
        console.error("Model dropdown menu not found");
        return;
    }

    // Clear existing items
    dropdownMenu.empty();

    // Add model options to dropdown
    AVAILABLE_MODELS.forEach(modelItem => {
        const onClick = function(e) {
            e.preventDefault();
            e.stopPropagation();

            // Update button text and data
            mainDropdownButton.text(modelItem.display);
            model = modelItem.api;

            // Update any model-specific attributes
            if (modelItem.reasoning) {
                mainDropdownButton.attr('data-reasoning', modelItem.reasoning);
            } else {
                mainDropdownButton.removeAttr('data-reasoning');
            }

            // Hide dropdown manually
            dropdownMenu.removeClass('show');
            mainDropdownButton.attr('aria-expanded', 'false');

            // Update the current model button if it exists
            $('.current-model-btn').text(modelItem.display);

            // Update the model display in the chat interface
            const systemMessageElement = $('.chat-entry.system.system-message');
            if (systemMessageElement.length) {
                systemMessageElement.find('.model-name').text(modelItem.display);
            }

            console.log('Model changed to:', model);
        };

        dropdownMenu.append(createModelDropdownItem(modelItem, onClick));
    });

    // Dropdown toggle functionality
    mainDropdownButton.on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        dropdownMenu.toggleClass('show');
        $(this).attr('aria-expanded', dropdownMenu.hasClass('show'));
    });

    // Close dropdown when clicking outside
    $(document).on('click', function(e) {
        if (!$(e.target).closest('.dropdown').length) {
            dropdownMenu.removeClass('show');
            mainDropdownButton.attr('aria-expanded', 'false');
        }
    });
}

// Add this function to handle extended thinking related listeners
function setupExtendedThinkingListeners() {
    const extendedThinkingToggle = document.getElementById('extended-thinking-toggle');
    const budgetSlider = document.getElementById('thinking-budget-slider');

    if (extendedThinkingToggle) {
        // Remove existing listeners to prevent duplicates
        extendedThinkingToggle.removeEventListener('change', handleExtendedThinkingToggleChange);
        extendedThinkingToggle.addEventListener('change', handleExtendedThinkingToggleChange);
    }

    if (budgetSlider) {
        // Remove existing listeners to prevent duplicates
        budgetSlider.removeEventListener('input', handleBudgetSliderChange);
        budgetSlider.addEventListener('input', handleBudgetSliderChange);
    }
}

// Make sure these handler functions are also defined
function handleExtendedThinkingToggleChange() {
    const isEnabled = this.checked;
    const thinkingBudgetContainer = document.getElementById('thinking-budget-container');
    const modalModelDropdownButton = document.getElementById('modalModelDropdownButton');
    const budgetSlider = document.getElementById('thinking-budget-slider');
    const budgetValueDisplay = document.getElementById('thinking-budget-value');

    thinkingBudgetContainer.style.display = isEnabled ? 'block' : 'none';

    if (isEnabled) {
        const budget = budgetSlider.value || 12000; // Use current or default
        modalModelDropdownButton.dataset.extendedThinking = 'true';
        modalModelDropdownButton.dataset.thinkingBudget = budget;
        budgetValueDisplay.textContent = budget;
    } else {
        delete modalModelDropdownButton.dataset.extendedThinking;
        delete modalModelDropdownButton.dataset.thinkingBudget;
    }
    
    isSaved = false;
    console.log("Extended thinking toggled:", isEnabled, "Budget:", modalModelDropdownButton.dataset.thinkingBudget);
}

function handleBudgetSliderChange() {
    const budget = this.value;
    document.getElementById('thinking-budget-value').textContent = budget;
    document.getElementById('modalModelDropdownButton').dataset.thinkingBudget = budget;
    isSaved = false;
    console.log("Thinking budget changed:", budget);
}

// Update the populateModelDropdownInModal function to properly handle the setup
function populateModelDropdownInModal() {
    const modalModelDropdownMenu = document.querySelector('#systemMessageModal .model-dropdown-container .dropdown-menu');
    const modalModelDropdownButton = document.getElementById('modalModelDropdownButton');

    if (!modalModelDropdownMenu || !modalModelDropdownButton) {
        console.error("Required elements for modal model dropdown not found.");
        return;
    }

    // Clear existing dropdown items
    modalModelDropdownMenu.innerHTML = '';

    // Use the shared AVAILABLE_MODELS list
    AVAILABLE_MODELS.forEach(modelItem => {
        const dropdownItem = createModelDropdownItem(modelItem, function() {
            modalModelDropdownButton.textContent = this.textContent;
            modalModelDropdownButton.dataset.apiName = this.dataset.apiName;

            if (this.dataset.reasoning) {
                modalModelDropdownButton.dataset.reasoning = this.dataset.reasoning;
            } else {
                delete modalModelDropdownButton.dataset.reasoning;
            }

            // Handle extended thinking UI updates
            const isClaudeSonnet = this.dataset.apiName === 'claude-3-7-sonnet-20250219';
            const extendedThinkingSelected = this.dataset.extendedThinking === 'true';
            updateExtendedThinkingUI(isClaudeSonnet, extendedThinkingSelected, this.dataset.thinkingBudget);

            isSaved = false;
        })[0]; // Convert jQuery object to DOM element

        modalModelDropdownMenu.appendChild(dropdownItem);
    });

    // Setup the extended thinking listeners after populating the dropdown
    setupExtendedThinkingListeners();
}



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

        // Add event listeners for the web search toggles - WITH NULL CHECKS
        const enableWebSearchToggle = document.getElementById('enableWebSearch');
        const enableDeepSearchToggle = document.getElementById('enableDeepSearch');

        if (enableWebSearchToggle && enableDeepSearchToggle) {
            console.log('Attaching search toggle listeners'); // Debug log
            
            enableWebSearchToggle.addEventListener('change', function() {
                console.log('Web search toggle changed:', this.checked); // Debug log
                tempWebSearchState = this.checked;
                if (!this.checked) {
                    enableDeepSearchToggle.checked = false;
                    tempDeepSearchState = false;
                    enableDeepSearchToggle.disabled = true;
                } else {
                    enableDeepSearchToggle.disabled = false;
                }
                updateSearchSettings();
            });

            enableDeepSearchToggle.addEventListener('change', function() {
                console.log('Deep search toggle changed:', this.checked); // Debug log
                tempDeepSearchState = this.checked;
                if (this.checked) {
                    enableWebSearchToggle.checked = true;
                    tempWebSearchState = true;
                }
                updateSearchSettings();
            });
        } else {
            console.error('Search toggle elements not found:', {
                enableWebSearch: !!enableWebSearchToggle,
                enableDeepSearch: !!enableDeepSearchToggle
            });
        }

    }).catch(error => {
        console.error('Error during system message fetch and display:', error);
    });
});


// --- Context File Attachment Functions (Direct Chat Attachments) ---

function initializeContextFileAttachment() {
    const attachFileBtn = document.getElementById('attachFileBtn');
    const fileInput = document.getElementById('fileInput'); // Input specifically for context files
    let attachmentMenu = null;

    // Function to position the menu relative to the button
    function positionMenu() {
        if (!attachmentMenu) return;
        const btnRect = attachFileBtn.getBoundingClientRect();
        attachmentMenu.style.position = 'fixed';
        attachmentMenu.style.left = `${btnRect.left}px`;
        attachmentMenu.style.bottom = `${window.innerHeight - btnRect.top + 5}px`;
    }

    // Create and append menu on first click
    function createAttachmentMenu() {
        const template = document.getElementById('attachmentMenuTemplate');
        attachmentMenu = template.firstElementChild.cloneNode(true);
        document.body.appendChild(attachmentMenu);

        // Handle menu item click
        attachmentMenu.querySelector('#uploadFileOption').addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            // Trigger file input click directly
            fileInput.click();
            hideMenu();
        });

        return attachmentMenu;
    }

    function showMenu() {
        if (!attachmentMenu) {
            attachmentMenu = createAttachmentMenu();
        }
        attachmentMenu.classList.add('show');
        positionMenu();
    }

    function hideMenu() {
        if (attachmentMenu) {
            attachmentMenu.classList.remove('show');
        }
    }

    // Toggle menu on button click
    attachFileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        e.preventDefault();

        if (attachmentMenu?.classList.contains('show')) {
            hideMenu();
        } else {
            showMenu();
        }
    });

    // Hide menu when clicking outside
    document.addEventListener('click', () => hideMenu());

    // Handle file selection
    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) {
            setSendButtonState(false); // Disable send button while uploading
            // Immediately add a placeholder and start the upload process
            const placeholderId = addPlaceholderBadge(file);
            await handleContextFileSelection(file, placeholderId);
            setSendButtonState(true); // Re-enable send button after upload
        }
        // Reset the input to allow selecting the same file again
        e.target.value = '';
    });

    // Handle window resize
    window.addEventListener('resize', () => {
        if (attachmentMenu?.classList.contains('show')) {
            positionMenu();
        }
    });
}

// Function to add a temporary placeholder badge during upload
function addPlaceholderBadge(file) {
    const container = document.getElementById('attachedFilesPreview');
    container.classList.remove('d-none'); // Ensure container is visible

    // Always use the context-pills container
    let pillsContainer = container.querySelector('.context-pills');
    if (!pillsContainer) {
        pillsContainer = document.createElement('div');
        pillsContainer.className = 'd-flex flex-wrap gap-1 context-pills';
        container.appendChild(pillsContainer);
    }

    const placeholderId = `placeholder-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    const placeholderBadge = document.createElement('span');
    placeholderBadge.id = placeholderId;
    placeholderBadge.className = 'badge bg-secondary d-inline-flex align-items-center me-1';
    placeholderBadge.style.minWidth = '200px'; // Give it some minimum width for the progress bar
    placeholderBadge.innerHTML = `
        <span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
        <span class="upload-status">Preparing ${escapeHtml(file.name)}...</span>
    `;

    pillsContainer.appendChild(placeholderBadge);
    return placeholderId;
}


// Function to add a persistent error badge
function addErrorBadge(errorMessage) {
    const container = document.getElementById('attachedFilesPreview');
    if (!container) {
        console.error("Cannot add error badge: attachedFilesPreview container not found!");
        return;
    }
    container.classList.remove('d-none');

    let pillsContainer = container.querySelector('.context-pills');
    if (!pillsContainer) {
        pillsContainer = document.createElement('div');
        pillsContainer.className = 'd-flex flex-wrap gap-1 context-pills';
        container.appendChild(pillsContainer);
    }

    const errorBadge = document.createElement('span');
    errorBadge.className = 'badge bg-danger d-inline-flex align-items-center me-1';
    errorBadge.innerHTML = `
        <i class="fas fa-exclamation-triangle me-1"></i>
        ${escapeHtml(errorMessage)}
        <button type="button" class="btn-close btn-close-white ms-2" onclick="this.parentElement.remove(); checkPreviewContainerVisibility();" style="font-size: 0.5em;"></button>
    `;
    pillsContainer.appendChild(errorBadge);
}


// Helper function to check and hide the preview container if empty
function checkPreviewContainerVisibility() {
    const container = document.getElementById('attachedFilesPreview');
    if (!container) return;

    const pillsContainer = container.querySelector('.context-pills');
    const hasContent = pillsContainer && pillsContainer.children.length > 0;
    if (hasContent) {
        container.classList.remove('d-none');
    } else {
        container.classList.add('d-none');
    }
}


async function handleContextFileSelection(file, placeholderId) {
    // Basic validation
    const maxSize = 25 * 1024 * 1024; // 25MB
    if (file.size > maxSize) {
        // Update placeholder badge with error
        const placeholderBadge = document.getElementById(placeholderId);
        if (placeholderBadge) {
            placeholderBadge.className = 'badge bg-danger d-inline-flex align-items-center me-1';
            placeholderBadge.innerHTML = `
                <i class="fas fa-exclamation-triangle me-1"></i>
                Error: File exceeds 25MB limit
                <button type="button" class="btn-close btn-close-white ms-2" onclick="this.parentElement.remove(); checkPreviewContainerVisibility();" style="font-size: 0.5em;"></button>
            `;
        }
        return;
    }

    // Start upload and processing immediately
    await uploadContextFile(file, placeholderId);
}

async function uploadContextFile(file, placeholderId) {
    setSendButtonState(false); // Disable send button while uploading
    const formData = new FormData();
    formData.append('file', file);

    // Get the placeholder badge to update during upload
    const placeholderBadge = document.getElementById(placeholderId);
    
    try {
        // Create a progress indicator inside the placeholder badge
        if (placeholderBadge) {
            placeholderBadge.innerHTML = `
                <span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
                <span class="upload-status">Uploading ${escapeHtml(file.name)}...</span>
                <div class="progress mt-1" style="height: 4px; width: 100%;">
                    <div class="progress-bar" role="progressbar" style="width: 0%"></div>
                </div>
            `;
        }

        // Add console logging for debugging
        console.log(`Starting upload for file: ${file.name}`);

        // Create a custom XMLHttpRequest to track upload progress
        const xhr = new XMLHttpRequest();
        
        // Set up a promise to handle the XHR response
        const uploadPromise = new Promise((resolve, reject) => {
            xhr.open('POST', '/upload-temp-file');
            
            xhr.upload.addEventListener('progress', (event) => {
                if (event.lengthComputable) {
                    const percentComplete = Math.round((event.loaded / event.total) * 100);
                    console.log(`Upload progress: ${percentComplete}%`);
                    
                    // Update progress bar
                    const progressBar = placeholderBadge?.querySelector('.progress-bar');
                    const statusText = placeholderBadge?.querySelector('.upload-status');
                    
                    if (progressBar) {
                        progressBar.style.width = `${percentComplete}%`;
                    }
                    
                    if (statusText && percentComplete < 100) {
                        statusText.textContent = `Uploading ${escapeHtml(file.name)}: ${percentComplete}%`;
                    } else if (statusText) {
                        statusText.textContent = `Loading ${escapeHtml(file.name)}...`;
                        // Add processing animation class
                        statusText.classList.add('processing-animation');
                    }
                }
            });
            
            xhr.onload = function() {
                console.log(`XHR onload triggered. Status: ${xhr.status}`);
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        console.log('Received response:', response);
                        resolve(response);
                    } catch (e) {
                        console.error('Error parsing response:', e);
                        reject(new Error('Invalid JSON response from server'));
                    }
                } else {
                    console.error(`Error response: ${xhr.status} ${xhr.statusText}`);
                    try {
                        const errorData = JSON.parse(xhr.responseText);
                        reject(new Error(errorData.error || `Upload failed: ${xhr.statusText}`));
                    } catch (e) {
                        reject(new Error(`Upload failed: ${xhr.status} ${xhr.statusText}`));
                    }
                }
            };
            
            xhr.onerror = function(e) {
                console.error('XHR error:', e);
                reject(new Error('Network error during upload'));
            };
        });
        
        // Send the form data
        xhr.send(formData);
        console.log('Form data sent');
        
        // Wait for the upload to complete
        const result = await uploadPromise;
        console.log('Upload complete, result:', result);

        // At this point, the file has been uploaded and processed by the server
        // Update the placeholder to show completion
        if (placeholderBadge) {
            console.log('Updating placeholder badge to show completion');
            placeholderBadge.innerHTML = `
                <i class="fas fa-check-circle me-1"></i>
                <span class="upload-status">Processed ${escapeHtml(file.name)}</span>
            `;
            
            // Add a short delay before removing the placeholder and adding the permanent badge
            setTimeout(() => {
                console.log('Removing placeholder and adding permanent badge');
                // Remove placeholder badge
                placeholderBadge.remove();
                
                // Store context file info
                attachedContextFiles.set(result.fileId, {
                    name: result.filename,
                    size: result.size,
                    type: result.mime_type,
                    tokenCount: result.tokenCount,
                    content: result.extractedText
                });
                
                // Update the UI with the permanent badge
                updateContextFilesPreview();
            }, 1000); // 1 second delay to show completion
        } else {
            console.log('Placeholder badge not found, storing file info directly');
            // If placeholder is gone, just store the file info
            attachedContextFiles.set(result.fileId, {
                name: result.filename,
                size: result.size,
                type: result.mime_type,
                tokenCount: result.tokenCount,
                content: result.extractedText
            });
            updateContextFilesPreview();
        }
    } catch (error) {
        console.error('Context file upload failed:', error);
        
        // Remove the placeholder if it exists
        if (placeholderBadge) {
            placeholderBadge.remove();
        }
        
        addErrorBadge(`Upload failed for ${escapeHtml(file.name)}: ${error.message}`);
        updateContextFilesPreview();
        setSendButtonState(true); // Always re-enable after upload finishes or errors
    }
}

async function removeContextFile(fileId) {
    try {
        const response = await fetch(`/remove-temp-file/${fileId}`, { // Endpoint for temporary context files
            method: 'DELETE'
        });

        if (!response.ok) {
            // Try to parse JSON error first
            let errorMsg = `Removal failed: ${response.status}`;
            try {
                const errorData = await response.json();
                errorMsg = errorData.error || errorMsg;
            } catch(e) { /* Ignore parsing error, use status */ }
            throw new Error(errorMsg);
        }

        const result = await response.json();

        if (result.success) {
            attachedContextFiles.delete(fileId);
            updateContextFilesPreview(); // Update preview pills
        } else {
            throw new Error(result.error || 'Removal failed');
        }
    } catch (error) {
        console.error('Context file removal failed:', error);
        addErrorBadge(`Failed to remove context file: ${error.message}`);
        // Ensure container visibility is checked after adding error badge
        checkPreviewContainerVisibility();
    }
}

function updateContextFilesPreview() {
    const container = document.getElementById('attachedFilesPreview');
    if (!container) {
        console.error("attachedFilesPreview container not found!");
        return;
    }
    let pillsContainer = container.querySelector('.context-pills');
    if (!pillsContainer) {
        pillsContainer = document.createElement('div');
        pillsContainer.className = 'd-flex flex-wrap gap-1 context-pills';
        container.appendChild(pillsContainer);
    }
    // Remove all current file badges (not error badges)
    // We'll identify permanent file badges by their id attribute
    [...pillsContainer.children].forEach(child => {
        if (child.id && child.id.startsWith('context-file-')) {
            child.remove();
        }
    });

    // Add all current attached files as permanent badges
    attachedContextFiles.forEach((fileInfo, fileId) => {
        const pill = document.createElement('span');
        pill.id = `context-file-${fileId}`;
        pill.className = 'badge bg-info d-inline-flex align-items-center me-1';
        pill.innerHTML = `
            <i class="fa fa-paperclip me-1"></i>
            ${escapeHtml(fileInfo.name)} (${fileInfo.tokenCount ? fileInfo.tokenCount + ' tokens' : '...'})
            <button type="button" class="btn-close btn-close-white ms-2"
                    onclick="removeContextFile('${fileId}')"
                    style="font-size: 0.5em;">
            </button>
        `;
        pillsContainer.appendChild(pill);
    });
    checkPreviewContainerVisibility();
}


function getAttachedContextFilesContent() {
    let content = '';
    for (const [fileId, fileInfo] of attachedContextFiles) {
        if (fileInfo.content) {
            content += `\n\nContent from attached file "${fileInfo.name}":\n${fileInfo.content}`;
        }
    }
    return content;
}

function setSendButtonState(isEnabled, message = null) {
    const sendBtn = $('.btn-send');
    if (isEnabled) {
        sendBtn.prop('disabled', false);
        sendBtn.html('<i class="fas fa-paper-plane"></i>');
        $('#send-wait-message').remove(); // Remove any wait message
    } else {
        sendBtn.prop('disabled', true);
        sendBtn.html('<span class="spinner-border spinner-border-sm mr-1"></span> <span>Wait for file...</span>');
        // Optionally show a message below the input
        if (!$('#send-wait-message').length) {
            $('<div id="send-wait-message" class="text-warning mt-2" style="font-size:0.95em;">File is uploading. Please wait...</div>')
                .insertAfter('#chat-form');
        }
    }
}


// --- End Context File Attachment Functions ---


// --- Shared Upload Status/Progress Functions ---

function showUploadStatus(message, alertClass) {
    const statusElement = document.getElementById('uploadStatus'); // Generic status element
    statusElement.className = `alert ${alertClass}`;
    statusElement.textContent = message;
    statusElement.classList.remove('d-none');
}

function showUploadProgress(percent) {
    const progressArea = document.getElementById('uploadProgressArea'); // Generic progress element
    const progressBar = document.getElementById('uploadProgressBar');
    const progressText = document.getElementById('uploadProgressText');

    progressArea.classList.remove('d-none');
    progressBar.style.width = `${percent}%`;
    progressBar.setAttribute('aria-valuenow', percent);
    progressText.textContent = `${percent}%`;
}

function hideUploadProgress() {
    const progressArea = document.getElementById('uploadProgressArea');
    if (progressArea) {
        progressArea.classList.add('d-none');
    }
}

function resetUploadProgress() {
    hideUploadProgress();
    const statusElement = document.getElementById('uploadStatus');
    if (statusElement) {
        statusElement.classList.add('d-none');
    }
}

// --- End Shared Upload Status/Progress Functions ---


// --- WebSocket Status Update Functions ---

function createStatusUpdateContainer() {
    if (!statusUpdateContainer) {
        statusUpdateContainer = $('<div class="chat-entry status-message">')
            .append('<i class="fas fa-robot"></i> ');
        $('#chat').append(statusUpdateContainer);
        $('#chat').scrollTop($('#chat')[0].scrollHeight);
    }
    return statusUpdateContainer;
}

function addStatusUpdate(message) {
    console.log('Adding status update:', message);
    const container = createStatusUpdateContainer();

    let statusContentContainer = container.find('.status-content');
    if (statusContentContainer.length === 0) {
        statusContentContainer = $('<div class="status-content"></div>');
        container.append(statusContentContainer);
    }

    const baseMessage = message.replace(/\.+$/, '');
    const messageSpan = $('<span>').text(baseMessage);
    const dotsSpan = $('<span class="animated-dots">...</span>');

    statusContentContainer.fadeOut(200, function() {
        statusContentContainer.empty()
            .append(messageSpan)
            .append(dotsSpan)
            .fadeIn(200);
    });

    $('#chat').scrollTop($('#chat')[0].scrollHeight);

    return container;
}

function clearStatusUpdates() {
    console.log('Clearing status updates');

    if (statusUpdateContainer) {
        statusUpdateContainer.fadeOut(300, function() {
            $(this).remove();
            statusUpdateContainer = null;
        });
    }

    cleanupWebSocketSession();
}

function checkStatusConnection() {
    if (maintainWebSocketConnection && (!statusWebSocket || statusWebSocket.readyState === WebSocket.CLOSED)) {
        console.log('Status connection lost or not established, reconnecting...');
        wsReconnectAttempts = 0;
        wsReconnectDelay = INITIAL_RECONNECT_DELAY;
    }
}

let reconnectAttempts = 0; // Renamed from wsReconnectAttempts for clarity? No, keep wsReconnectAttempts

function initStatusWebSocket() {
    console.log('initStatusWebSocket called');

    if (!maintainWebSocketConnection) {
        console.log('WebSocket connection not needed at this time');
        return null;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/chat/status`;

    console.log('Attempting new WebSocket connection to:', wsUrl);

    try {
        const newWs = new WebSocket(wsUrl);

        newWs.onopen = function(event) {
            console.log('WebSocket connection opened');
            wsReconnectAttempts = 0;
            wsReconnectDelay = INITIAL_RECONNECT_DELAY;
        };

        newWs.onmessage = handleWebSocketMessage;

        newWs.onerror = function(error) {
            console.error('WebSocket error:', error);
            if (error.message) {
                console.error('Error message:', error.message);
            }
        };

        newWs.onclose = function(event) {
            console.log('WebSocket closed:', event.code, event.reason);
            if (maintainWebSocketConnection) {
                handleWebSocketReconnect();
            }
        };

        statusWebSocket = newWs;
        return newWs;

    } catch (error) {
        console.error('Error creating WebSocket:', error);
        statusWebSocket = null;
        return null;
    }
}

function handleWebSocketMessage(event) {
    try {
        const data = JSON.parse(event.data);
        console.log('WebSocket message received:', data);

        if (data.type === 'status') {
            if (data.session_id) {
                console.log('WebSocket connection confirmed, session ID:', data.session_id);
                currentSessionId = data.session_id;
                return;
            } else if (data.message !== "WebSocket connection established") {
                addStatusUpdate(data.message);
            }
        }
    } catch (e) {
        console.error('Error processing WebSocket message:', e);
    }
}

function handleWebSocketError(error) {
    console.error('WebSocket error:', error);
    console.log('WebSocket readyState:', statusWebSocket?.readyState);
}

function handleWebSocketClose(event) {
    console.log('WebSocket connection closed:', event);
    if (maintainWebSocketConnection) {
        handleWebSocketReconnect();
    }
}

function handleWebSocketReconnect() {
    if (!maintainWebSocketConnection) {
        console.log('Reconnection cancelled - connection no longer needed');
        return;
    }

    if (wsReconnectAttempts >= MAX_WS_RECONNECT_ATTEMPTS) {
        console.error('Max reconnection attempts reached');
        maintainWebSocketConnection = false;
        statusWebSocket = null;
        return;
    }

    wsReconnectAttempts++;
    console.log(`Attempting to reconnect (${wsReconnectAttempts}/${MAX_WS_RECONNECT_ATTEMPTS})...`);

    setTimeout(() => {
        if (maintainWebSocketConnection) {
            initStatusWebSocket();
        }
    }, wsReconnectDelay);

    wsReconnectDelay = Math.min(wsReconnectDelay * 2, 10000);
}

function isWebSocketActive(ws) {
    return ws &&
           typeof ws.readyState !== 'undefined' &&
           ws.readyState !== WebSocket.CLOSED &&
           ws.readyState !== WebSocket.CLOSING;
}

function cleanupWebSocketSession() {
    maintainWebSocketConnection = false;
    currentSessionId = null;

    if (statusWebSocket && statusWebSocket.readyState !== WebSocket.CLOSED) {
        console.log('Closing existing WebSocket connection');
        try {
            statusWebSocket.close(1000, "Session cleanup");
        } catch (e) {
            console.error('Error during WebSocket cleanup:', e);
        }
        statusWebSocket = null;
    }

    if (healthCheckInterval) {
        clearInterval(healthCheckInterval);
        healthCheckInterval = null;
    }
}

function checkSessionHealth() {
    if (!currentSessionId) return;

    fetch('/ws/chat/status/health', {
        headers: {
            'X-Session-ID': currentSessionId
        }
    })
    .then(response => response.json())
    .then(data => {
        if (!data.session_valid) {
            console.log('Session invalid, reinitializing...');
            cleanupWebSocketSession();
        }
    })
    .catch(error => {
        console.error('Session health check failed:', error);
    });
}

window.addEventListener('beforeunload', function() {
    clearStatusUpdates();
});

// --- End WebSocket Status Update Functions ---


// --- Search Settings Functions ---

function updateSearchSettings() {
    // Only send an update if the temporary state differs from the current system message state
    if (tempWebSearchState !== currentSystemMessage.enable_web_search || tempDeepSearchState !== false) {
        fetch(`/api/system-messages/${activeSystemMessageId}/toggle-search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                enableWebSearch: tempWebSearchState,
                enableDeepSearch: tempDeepSearchState
            }),
        })
        .then(response => response.json())
        .then(data => {
            console.log('Search settings updated:', data);
            // Update the current system message with the new settings
            currentSystemMessage.enable_web_search = data.enableWebSearch;
            currentSystemMessage.enable_deep_search = data.enableDeepSearch;
        })
        .catch((error) => {
            console.error('Error updating search settings:', error);
            // Revert the toggles to their previous state on error
            initializeSearchToggles(currentSystemMessage);
        });
    }
}

function initializeSearchToggles(systemMessage) {
    console.log('initializeSearchToggles called with:', systemMessage.name, 'web_search:', systemMessage.enable_web_search);
    
    const enableWebSearchToggle = document.getElementById('enableWebSearch');
    const enableDeepSearchToggle = document.getElementById('enableDeepSearch');

    // Set the web search toggle based on the saved setting
    enableWebSearchToggle.checked = !!systemMessage.enable_web_search;
    tempWebSearchState = !!systemMessage.enable_web_search;

    // Set deep search toggle from system message
    enableDeepSearchToggle.checked = !!systemMessage.enable_deep_search;
    tempDeepSearchState = !!systemMessage.enable_deep_search;

    // CHANGE: Don't disable deep search toggle - let it be clickable always
    // enableDeepSearchToggle.disabled = !systemMessage.enable_web_search;
    enableDeepSearchToggle.disabled = false;
    
    console.log('Toggle states set - web:', enableWebSearchToggle.checked, 'deep:', enableDeepSearchToggle.checked, 'disabled:', enableDeepSearchToggle.disabled);
}






// --- End Search Settings Functions ---


// --- Website Indexing Functions (Modal) ---

document.getElementById('indexWebsiteButton').addEventListener('click', function() {
    const websiteId = activeWebsiteId; // Use the global variable for the active website ID

    // Make an API call to fetch the website details based on the websiteId
    fetch(`/get-website/${websiteId}`)
        .then(response => {
            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error("Website not found. Please check the website ID.");
                } else {
                    throw new Error(`Failed to fetch website details: ${response.status} (${response.statusText})`);
                }
            }
            return response.json();
        })
        .then(data => {
            const url = data.website.url; // Get the URL of the website from the response

            // Make the API call to index the website
            fetch('/index-website', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: url }), // fetch the URL from database
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Failed to load resource: the server responded with a status of ${response.status} (${response.statusText})`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    document.getElementById('indexingStatus').innerText = 'Indexed';
                    document.getElementById('indexedAt').innerText = new Date().toISOString();
                } else {
                    document.getElementById('lastError').innerText = data.message;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                // Display the error message to the user
                document.getElementById('lastError').innerText = error.message;
            });
        })
        .catch(error => {
            console.error('Error fetching website details:', error);
            // Display an error message to the user
            document.getElementById('lastError').innerText = error.message;
        });
});

// --- End Website Indexing Functions ---


// --- Vector File Functions (RAG/Semantic Search in Modal) ---

function getCsrfToken() {
    const tokenElement = document.querySelector('meta[name="csrf-token"]');
    return tokenElement ? tokenElement.getAttribute('content') : null;
}

function removeVectorFile(fileId) {
    console.log('removeVectorFile called with fileId:', fileId, 'Type:', typeof fileId);
    
    // Clean up the file ID using regex to remove leading non-alphanumeric chars (except hyphen) and trim
    let cleanFileId = String(fileId).replace(/^[^a-zA-Z0-9-]+/, '').trim();
    console.log('Cleaned fileId:', cleanFileId);
    
    if (!confirm('Are you sure you want to remove this vector file?')) {
        return;
    }
    const fileListError = document.getElementById('fileListError'); // Error display for vector files
    const fileUploadStatus = document.getElementById('fileUploadStatus'); // Status display for vector files

    fetch(`/remove_file/${cleanFileId}`, { // Use cleaned ID
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json'
            // 'X-CSRFToken': getCsrfToken() // Add CSRF if needed
        },
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.error || `Network response was not ok: ${response.status}`) });
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            fileUploadStatus.textContent = 'Vector file removed successfully';
            fileUploadStatus.style.display = 'inline';
            setTimeout(() => {
                fileUploadStatus.style.display = 'none';
            }, 3000);
            fetchVectorFileList(activeSystemMessageId); // Refresh the vector file list
        } else {
            throw new Error(data.error || 'Failed to remove vector file');
        }
    })
    .catch(error => {
        console.error('Error removing vector file:', error);
        fileListError.textContent = `Failed to remove vector file: ${error.message}`;
        fileListError.style.display = 'block';
        setTimeout(() => {
            fileListError.style.display = 'none';
        }, 5000);
    });
}

function triggerVectorFileUpload() {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.txt,.pdf,.docx'; // Accepted types for vectorization

    const fileUploadStatus = document.getElementById('fileUploadStatus'); // Status display for vector files
    const fileListError = document.getElementById('fileListError'); // Error display for vector files

    fileInput.onchange = function(e) {
        const file = e.target.files[0];
        if (file) {
            if (!activeSystemMessageId) {
                fileListError.textContent = 'Error: No active system message selected.';
                fileListError.style.display = 'block';
                setTimeout(() => { fileListError.style.display = 'none'; }, 5000);
                return;
            }

            const formData = new FormData();
            formData.append('file', file);
            formData.append('system_message_id', activeSystemMessageId);

            fileUploadStatus.textContent = 'Vector file upload in progress...';
            fileUploadStatus.style.display = 'inline';
            fileListError.style.display = 'none';

            fetch('/upload_file', { // Endpoint for vector search files
                method: 'POST',
                body: formData
                // headers: { 'X-CSRFToken': getCsrfToken() } // Add CSRF if needed
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => Promise.reject(err)).catch(() => Promise.reject({ error: `Upload failed: ${response.statusText}` }));
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    fileUploadStatus.textContent = 'Vector file upload complete';
                    setTimeout(() => {
                        fileUploadStatus.style.display = 'none';
                    }, 3000);
                    fetchVectorFileList(activeSystemMessageId); // Refresh list
                    updateVectorFileMoreIndicator();
                } else {
                    throw new Error(data.error || 'Unknown error occurred during vector file upload');
                }
            })
            .catch(error => {
                console.error('Error uploading vector file:', error);
                fileUploadStatus.textContent = 'Vector file upload failed';
                fileUploadStatus.style.display = 'inline';
                fileListError.textContent = 'Failed to upload vector file: ' + (error.error || error.message || 'Unknown error');
                fileListError.style.display = 'block';

                setTimeout(() => {
                    fileUploadStatus.style.display = 'none';
                    fileListError.style.display = 'none';
                }, 5000);
            });
        }
    };

    fileInput.click(); // Trigger the file selection dialog
}

function initializeAndUpdateVectorFileList(systemMessageId) {
    console.log('Initializing and updating vector file list for system message ID:', systemMessageId);

    const fileList = document.getElementById('fileList'); // Element displaying vector files
    if (fileList) {
        fileList.innerHTML = '';
    }

    fetchVectorFileList(systemMessageId);
    updateVectorFileMoreIndicator();
}

function fetchVectorFileList(systemMessageId) {
    const fileList = document.getElementById('fileList'); // Element for vector files
    const noFilesMessage = document.getElementById('noFilesMessage'); // Element for vector files
    const fileListError = document.getElementById('fileListError'); // Element for vector files
    const fileListContainer = document.getElementById('fileListContainer'); // Container for vector files
    if (!fileListContainer || !fileList || !noFilesMessage || !fileListError) {
        console.error('One or more vector file list elements not found in the DOM');
        return;
    }
    const moreFilesIndicator = document.getElementById('moreFilesIndicator'); // Indicator for vector files
    if (!moreFilesIndicator) {
        console.error('More vector files indicator not found');
        return;
    }

    // Reset displays
    fileList.innerHTML = '';
    fileList.style.display = 'none';
    noFilesMessage.style.display = 'none';
    fileListError.style.display = 'none';
    moreFilesIndicator.style.display = 'none';

    fetch(`/get_files/${systemMessageId}`) // Endpoint to get vector files
    .then(response => {
        if (!response.ok) {
            throw new Error(`Network response was not ok: ${response.status}`);
        }
        return response.json();
    })
    .then(files => {
        console.log('Received vector files:', files);
        if (files && files.length > 0) {
            files.forEach(file => {
                console.log('Processing file object:', file);
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item d-flex justify-content-between align-items-center';
                
                // Log the raw ID and type
                console.log('Raw file ID:', file.id, 'Type:', typeof file.id);
                
                // Clean and escape the ID
                const cleanFileId = String(file.id).trim();
                const fileIdEscaped = CSS.escape(cleanFileId);
                
                console.log('Cleaned file ID:', cleanFileId);
                console.log('Escaped file ID:', fileIdEscaped);
                
                fileItem.innerHTML = `
                    <span class="file-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</span>
                    <div class="file-actions">
                        <button class="btn btn-sm btn-primary" onclick="viewOriginalVectorFile('${cleanFileId}')" title="View Original File">View Original</button>
                        <button class="btn btn-sm btn-info" onclick="viewProcessedVectorFileText('${cleanFileId}')" title="View Processed Text">View Processed</button>
                        <button class="btn btn-sm btn-danger" onclick="removeVectorFile('${cleanFileId}')" title="Remove File"><i class="fas fa-trash-alt"></i></button>
                    </div>
                `;
                fileList.appendChild(fileItem);
            });
            fileList.style.display = 'block';
            noFilesMessage.style.display = 'none';
        } else {
            fileList.style.display = 'none';
            noFilesMessage.style.display = 'block';
        }
        fileListContainer.style.display = 'block';
        updateVectorFileMoreIndicator();
    })
    .catch(error => {
        console.error('Error fetching vector file list:', error);
        fileListError.textContent = `Error fetching vector file list: ${error.message}`;
        fileListError.style.display = 'block';
        fileListContainer.style.display = 'block';
        updateVectorFileMoreIndicator();
    });

    // Add scroll listener for the vector file list
    fileListContainer.removeEventListener('scroll', updateVectorFileMoreIndicator);
    fileListContainer.addEventListener('scroll', updateVectorFileMoreIndicator);
}

function viewOriginalVectorFile(fileId) {
    const url = `/view_original_file/${fileId}`; // Endpoint for original vector file
    window.open(url, '_blank');
}

function viewProcessedVectorFileText(fileId) {
    fetch(`/view_processed_text/${fileId}`) // Endpoint for processed vector file text
        .then(response => {
            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('Processed text not available');
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.text();
        })
        .then(text => {
            const newWindow = window.open('', '_blank');
            if (newWindow) {
                newWindow.document.write(`<pre>${escapeHtml(text)}</pre>`);
                newWindow.document.close();
            } else {
                alert('Could not open new window. Please check your popup blocker settings.');
            }
        })
        .catch(error => {
            console.error('Error viewing processed vector file text:', error);
            alert(error.message || 'Error viewing processed text. Please try again.');
        });
}

function updateVectorFileMoreIndicator() {
    const fileListContainer = document.getElementById('fileListContainer'); // Container for vector files
    const moreFilesIndicator = document.getElementById('moreFilesIndicator'); // Indicator for vector files

    if (fileListContainer && moreFilesIndicator) {
        const isScrollable = fileListContainer.scrollHeight > fileListContainer.clientHeight;
        const isAtBottom = fileListContainer.scrollTop + fileListContainer.clientHeight >= fileListContainer.scrollHeight - 5;

        if (isScrollable && !isAtBottom) {
            moreFilesIndicator.style.display = 'block';
        } else {
            moreFilesIndicator.style.display = 'none';
        }
    } else {
        if (moreFilesIndicator) moreFilesIndicator.style.display = 'none';
    }
}

function handleAddVectorFileButtonClick() {
    // Button click handler in the modal's file group (for vector files)
    triggerVectorFileUpload(); // Use the renamed function
}

// --- End Vector File Functions ---


// --- General Utility Functions ---

function resetFileInput() {
    // Reset the file input field used for temporary context file attachments
    var fileInput = document.getElementById('fileInput'); // ID for context file input
    if (fileInput) {
        fileInput.value = "";
    }
    // No persistent input element for vector files (it's created dynamically)
}

// --- End General Utility Functions ---


// --- Website Management Functions (Modal) ---

function handleAddWebsiteButtonClick() {
    // Switch to the websitesGroup
    openModalAndShowGroup('websitesGroup');

    // Clear active website ID and website details
    activeWebsiteId = null;
    clearWebsiteDetails();
    updateWebsiteControls();
}

function openModalAndShowGroup(groupID) {
    // Hide all content groups
    $('.modal-content-group').addClass('hidden');

    // Show the selected group
    $('#' + groupID).removeClass('hidden');

    // If opening the files group (vector files), ensure the list is updated
    if (groupID === 'filesGroup' && activeSystemMessageId) {
        fetchVectorFileList(activeSystemMessageId); // Use renamed function
    }
    // If opening the websites group, ensure the website list is updated
    if (groupID === 'websitesGroup' && activeSystemMessageId) {
        loadWebsitesForSystemMessage(activeSystemMessageId);
    }
}

function updateWebsiteControls() {
    const addWebsiteButton = document.getElementById('submitWebsiteButton');
    const removeWebsiteButton = document.getElementById('removeWebsiteButton');
    const indexWebsiteButton = document.getElementById('indexWebsiteButton');

    if (!addWebsiteButton || !removeWebsiteButton || !indexWebsiteButton) {
        console.error("Website control buttons not found");
        return;
    }


    if (activeWebsiteId) {
        // Hide the Add Website button and show the Remove and Index buttons
        addWebsiteButton.style.display = 'none';
        removeWebsiteButton.style.display = 'inline-block';
        indexWebsiteButton.style.visibility = 'visible'; // Use visibility to maintain layout
    } else {
        // Show the Add Website button and hide the Remove and Index buttons
        addWebsiteButton.style.display = 'inline-block';
        removeWebsiteButton.style.display = 'none';
        indexWebsiteButton.style.visibility = 'hidden'; // Use visibility to maintain layout
    }
}

document.getElementById('submitWebsiteButton').addEventListener('click', function() {
    const websiteURLInput = document.getElementById('websiteURL');
    const websiteURL = websiteURLInput.value.trim(); // Trim whitespace

    if (!websiteURL) {
        alert('Please enter a valid URL.');
        return;
    }

    // Basic URL validation (optional, enhance as needed)
    try {
        new URL(websiteURL);
    } catch (_) {
        alert('Invalid URL format. Please include http:// or https://');
        return;
    }


    if (!activeSystemMessageId) {
        alert('System message ID is required. Please select a system message first.');
        return;
    }

    addWebsite(websiteURL, activeSystemMessageId).then(response => {
        if (response.success && response.website) {
            activeWebsiteId = response.website.id; // Set the active website ID
            updateWebsiteControls(); // Update UI controls
            // Repopulate the input field with the URL of the newly added website
            websiteURLInput.value = response.website.url;
            alert('Website added successfully.');
            // Reload the websites for the current system message to update the sidebar
            loadWebsitesForSystemMessage(activeSystemMessageId);
            // Display the details of the newly added website
            displayWebsiteDetails(response.website);
        } else {
            alert('Error adding website: ' + (response.message || 'Unknown error'));
        }
    }).catch(error => {
        console.error('Error adding website:', error);
        alert('An error occurred while adding the website.');
    });
});


function addWebsite(url, systemMessageId) {
    console.log("Adding website with URL:", url, "and system message ID:", systemMessageId);
    return fetch('/add-website', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
            // Add CSRF token if needed: 'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ url: url, system_message_id: systemMessageId })
    })
    .then(response => {
        if (!response.ok) {
            // Try to parse error from JSON, otherwise use status text
            return response.json().then(err => { throw new Error(err.message || `Failed to add website: ${response.statusText}`) });
        }
        return response.json();
    });
}



function loadWebsitesForSystemMessage(systemMessageId) {
    const sidebar = document.getElementById('modal-sidebar');
    if (!sidebar) {
        console.error("Website sidebar element not found in the DOM.");
        return;
    }

    // Clear existing content and show loading state
    sidebar.innerHTML = '<div class="text-center p-2">Loading websites...</div>';

    $.ajax({
        url: `/get-websites/${systemMessageId}`,
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            sidebar.innerHTML = ''; // Clear loading state

            const websites = Array.isArray(response) ? response : (response.websites || []);

            if (websites && websites.length > 0) {
                websites.forEach(website => {
                    const div = document.createElement('div');
                    div.className = 'website-item d-flex justify-content-between align-items-center p-1'; // Added padding

                    const textSpan = document.createElement('span');
                    textSpan.textContent = website.url;
                    textSpan.title = website.url; // Add the title attribute with the full URL
                    textSpan.style.overflow = 'hidden'; // Prevent long URLs from breaking layout
                    textSpan.style.textOverflow = 'ellipsis';
                    textSpan.style.whiteSpace = 'nowrap';
                    textSpan.style.flexGrow = '1'; // Allow span to take available space
                    textSpan.style.marginRight = '5px'; // Space before button
                    div.appendChild(textSpan);

                    const settingsButton = document.createElement('button');
                    settingsButton.className = 'btn btn-sm btn-outline-secondary websiteSettings-button'; // Use Bootstrap classes
                    settingsButton.innerHTML = '<i class="fas fa-wrench"></i>';
                    settingsButton.title = 'Website Settings'; // Tooltip
                    settingsButton.addEventListener('click', function(e) {
                        e.stopPropagation(); // Prevent triggering other clicks if nested
                        openModalAndShowGroup('websitesGroup');
                        document.getElementById('websiteURL').value = website.url; // Display the website URL
                        activeWebsiteId = website.id; // Set the active website ID
                        updateWebsiteControls(); // Update UI controls
                        displayWebsiteDetails(website); // Display website details
                    });
                    div.appendChild(settingsButton);

                    sidebar.appendChild(div);
                });
            } else {
                sidebar.innerHTML = '<div class="text-center p-2">No websites added yet.</div>'; // More user-friendly message
            }
        },
        error: function(xhr) {
            console.error('Failed to fetch websites:', xhr.status, xhr.responseText);
            if (sidebar) {
                sidebar.innerHTML = '<div class="text-center p-2 text-danger">Failed to load websites.</div>'; // Error message
            }
        }
    });
}



function displayWebsiteDetails(website) {
    document.getElementById('indexingStatus').textContent = website.indexing_status || 'N/A';
    document.getElementById('indexedAt').textContent = website.indexed_at ? formatDate(website.indexed_at) : 'N/A';
    document.getElementById('lastError').textContent = website.last_error || 'N/A';
    document.getElementById('indexingFrequency').textContent = website.indexing_frequency || 'N/A';
    document.getElementById('createdAt').textContent = website.created_at ? formatDate(website.created_at) : 'N/A';
    document.getElementById('updatedAt').textContent = website.updated_at ? formatDate(website.updated_at) : 'N/A';

    // Ensure the Index Website button is visible when details are displayed
    const indexButton = document.getElementById('indexWebsiteButton');
    if (indexButton) {
        indexButton.style.visibility = 'visible';
    }
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    try {
        const date = new Date(dateString);
        // Check if date is valid
        if (isNaN(date.getTime())) {
            return 'Invalid Date';
        }
        return date.toLocaleString(); // Customize the format as needed
    } catch (e) {
        console.error("Error formatting date:", dateString, e);
        return 'Invalid Date';
    }
}


function clearWebsiteDetails() {
    const websiteURLInput = document.getElementById('websiteURL');
    if (websiteURLInput) websiteURLInput.value = '';

    const indexingStatusEl = document.getElementById('indexingStatus');
    if (indexingStatusEl) indexingStatusEl.textContent = 'N/A';

    const indexedAtEl = document.getElementById('indexedAt');
    if (indexedAtEl) indexedAtEl.textContent = 'N/A';

    const lastErrorEl = document.getElementById('lastError');
    if (lastErrorEl) lastErrorEl.textContent = 'N/A';

    const indexingFrequencyEl = document.getElementById('indexingFrequency');
    if (indexingFrequencyEl) indexingFrequencyEl.textContent = 'N/A';

    const createdAtEl = document.getElementById('createdAt');
    if (createdAtEl) createdAtEl.textContent = 'N/A';

    const updatedAtEl = document.getElementById('updatedAt');
    if (updatedAtEl) updatedAtEl.textContent = 'N/A';

    // Hide the Index Website button
    const indexButton = document.getElementById('indexWebsiteButton');
    if (indexButton) {
        indexButton.style.visibility = 'hidden';
    }
}


function removeWebsite(websiteId) {
    if (!confirm('Are you sure you want to remove this website? This will also delete associated indexed data.')) {
        return;
    }

    // AJAX call to the server to remove the website
    $.ajax({
        url: '/remove-website/' + websiteId,
        type: 'DELETE',
        // Add CSRF token if needed: headers: { 'X-CSRFToken': getCsrfToken() },
        success: function(response) {
            alert('Website removed successfully');
            activeWebsiteId = null; // Clear the active website ID
            clearWebsiteDetails(); // Clear the website details form
            updateWebsiteControls(); // Update UI buttons (show Add, hide Remove/Index)
            loadWebsitesForSystemMessage(activeSystemMessageId); // Refresh the list of websites in the sidebar
        },
        error: function(xhr) {
            console.error('Error removing website:', xhr.status, xhr.responseText);
            alert('Error removing website: ' + (xhr.responseJSON?.message || xhr.responseText || 'Unknown error'));
        }
    });
}

// Listener for the Remove Website button
document.getElementById('removeWebsiteButton').addEventListener('click', function() {
    if (activeWebsiteId) {
        removeWebsite(activeWebsiteId);
    } else {
        alert('No website selected to remove.');
    }
});

function reindexWebsite(websiteId) {
    // Check if a website ID is provided
    if (!websiteId) {
        alert('No website selected to re-index.');
        return;
    }

    // Show some indication that re-indexing is starting
    const indexButton = document.getElementById('indexWebsiteButton');
    const originalText = indexButton.innerText;
    indexButton.innerText = 'Re-indexing...';
    indexButton.disabled = true;


    // AJAX call to the server to re-index the website
    $.ajax({
        url: '/reindex-website/' + websiteId,
        type: 'POST',
        // Add CSRF token if needed: headers: { 'X-CSRFToken': getCsrfToken() },
        success: function(response) {
            alert('Website re-indexing initiated successfully.');
            // Optionally update the status display immediately or wait for backend update
            document.getElementById('indexingStatus').textContent = 'Re-indexing Initiated';
        },
        error: function(xhr) {
            console.error('Error re-indexing website:', xhr.status, xhr.responseText);
            alert('Error re-indexing website: ' + (xhr.responseJSON?.message || xhr.responseText || 'Unknown error'));
        },
        complete: function() {
            // Restore button state
            indexButton.innerText = originalText;
            indexButton.disabled = false;
        }
    });
}

// Assuming the 'indexWebsiteButton' is used for both initial indexing and re-indexing
// We might rename it or adjust its behavior based on the current state.
// Let's attach the reindex function to the same button for now.
document.getElementById('indexWebsiteButton').addEventListener('click', function() {
    if (activeWebsiteId) {
        // Check the current status - if already indexed, confirm re-indexing
        const currentStatus = document.getElementById('indexingStatus').textContent;
        if (currentStatus && currentStatus.toLowerCase() !== 'pending' && currentStatus.toLowerCase() !== 'n/a') {
            if (confirm('This website seems to be indexed already. Do you want to re-index it?')) {
                reindexWebsite(activeWebsiteId);
            }
        } else {
            // If not indexed or status unknown, proceed with indexing/re-indexing
            reindexWebsite(activeWebsiteId);
        }
    } else {
        alert('No website selected to index.');
    }
});


function loadWebsites() {
    // This function seems generic and might be intended for a different context (e.g., an admin page).
    // The function `loadWebsitesForSystemMessage` is used within the modal context.
    // Keeping this function as is, assuming it might be used elsewhere.
    $.ajax({
        url: '/get-websites', // This endpoint might fetch *all* websites, not specific to a system message
        type: 'GET',
        success: function(response) {
            // Code to display the websites in the UI
            // Example: update a table or list in your HTML
            console.log("Loaded all websites (example):", response);
        },
        error: function(xhr) {
            console.error('Error fetching all websites:', xhr.status, xhr.responseText);
            alert('Error fetching websites: ' + xhr.responseText);
        }
    });
}

// --- End Website Management Functions ---


// --- System Message Modal & Related Functions ---

function updateSystemMessageDropdown() {
    let dropdownMenu = document.querySelector('#systemMessageModal .dropdown-menu');
    let dropdownButton = document.getElementById('systemMessageDropdown'); // Button for the dropdown

    if (!dropdownMenu || !dropdownButton) {
        console.error("Required elements for system message dropdown not found in the DOM.");
        return;
    }

    // Clear existing dropdown items
    dropdownMenu.innerHTML = '';

    // Repopulate the dropdown menu
    systemMessages.forEach((message) => { // Use the globally fetched systemMessages
        let dropdownItem = document.createElement('button');
        dropdownItem.className = 'dropdown-item';
        dropdownItem.textContent = message.name;
        dropdownItem.dataset.messageId = message.id; // Store ID for easy access

        dropdownItem.onclick = function() {
            const selectedMessageId = this.dataset.messageId;
            const selectedMessage = systemMessages.find(msg => msg.id == selectedMessageId); // Use == for type coercion if needed, or ensure types match

            if (!selectedMessage) {
                console.error("Selected system message not found in array:", selectedMessageId);
                return;
            }

            // Update the dropdown button text and modal content
            dropdownButton.textContent = selectedMessage.name; // Update the system message dropdown button text
            document.getElementById('systemMessageName').value = selectedMessage.name || '';
            document.getElementById('systemMessageDescription').value = selectedMessage.description || '';
            document.getElementById('systemMessageContent').value = selectedMessage.content || '';
            document.getElementById('systemMessageModal').dataset.messageId = selectedMessage.id; // Set ID on modal
            document.getElementById('enableWebSearch').checked = selectedMessage.enable_web_search;
            document.getElementById('enableTimeSense').checked = selectedMessage.enable_time_sense;

            // Update the current system message description (if needed globally)
            currentSystemMessageDescription = selectedMessage.description;
            // Update the temperature display
            updateTemperatureSelectionInModal(selectedMessage.temperature);
            // Update the model dropdown in the modal and the global model variable
            updateModelDropdownInModal(selectedMessage.model_name);
            model = selectedMessage.model_name; // Update the global model variable

            // Set the active system message ID globally
            activeSystemMessageId = selectedMessage.id;
            // Load websites and vector files for the newly selected system message
            loadWebsitesForSystemMessage(activeSystemMessageId);
            fetchVectorFileList(activeSystemMessageId); // Use renamed function

            // Reset save flag as content has changed
            isSaved = false;
        };
        dropdownMenu.appendChild(dropdownItem);
    });
}

function renderMathInElement(element) {
    if (!element || typeof element.textContent !== 'string') return;

    // Check if the element's content contains LaTeX patterns more robustly
    // Looks for $...$, $$...$$, \(...\), \[...\]
    if (element.textContent.match(/(\$|\\\(|\\\[).*?(\$|\\\)|\\\])/)) {
        // Use MathJax's typesetting queue
        MathJax.typesetPromise([element]).then(() => {
            console.log('Math content updated in element:', element);
        }).catch((err) => console.error('Error typesetting math content in element: ', err));
    }
}



function showModalFlashMessage(message, category) { // Usage Example: showModalFlashMessage('System message saved.', 'success');
    var flashContainer = document.getElementById('modal-flash-message-container');
    if (!flashContainer) {
        console.error("Modal flash container not found");
        return;
    }

    flashContainer.innerHTML = ''; // Clear previous messages

    var flashMessageDiv = document.createElement('div');
    // Use Bootstrap alert classes
    flashMessageDiv.className = `alert alert-${category} alert-dismissible fade show m-2`; // Added margin
    flashMessageDiv.setAttribute('role', 'alert');
    flashMessageDiv.textContent = message;

    // Add a close button
    var closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'btn-close';
    closeButton.setAttribute('data-bs-dismiss', 'alert');
    closeButton.setAttribute('aria-label', 'Close');
    flashMessageDiv.appendChild(closeButton);


    flashContainer.appendChild(flashMessageDiv);

    // Automatically hide the message after 5 seconds (increased duration)
    setTimeout(function() {
        // Use Bootstrap 4's jQuery plugin to close the alert
        $(flashMessageDiv).alert('close');
    }, 5000);
}


function checkAdminStatus(e) {
    if (!isAdmin) {
        e.preventDefault(); // Prevent the default action (e.g., navigating to /admin)
        // Trigger a flash message on the server side and reload to show it
        $.ajax({
            url: "/trigger-flash", // URL to a route that triggers the flash message
            type: "GET",
            success: function() {
                location.reload(); // Reload the page to display the flash message
            },
            error: function(xhr) {
                console.error("Failed to trigger flash message:", xhr.responseText);
                // Fallback: show a simple alert
                alert("You do not have permission to access this page.");
            }
        });
    } else {
        // If admin, allow the default action (or redirect explicitly if needed)
        // window.location.href = '/admin'; // Uncomment if explicit redirect is always desired
    }
}

// Function to open the modal and set the user ID and current status (for admin user management)
function openStatusModal(userId, currentStatus) {
    // Set the action URL for the form
    const statusForm = document.getElementById('statusUpdateForm');
    if (statusForm) {
        statusForm.action = `/update-status/${userId}`;
    } else {
        console.error("Status update form not found");
        return;
    }


    // Check the radio button that matches the current status
    // Ensure radio buttons exist before trying to check them
    const statusActiveRadio = document.getElementById('statusActive');
    const statusPendingRadio = document.getElementById('statusPending');
    const statusNARadio = document.getElementById('statusNA');

    if (!statusActiveRadio || !statusPendingRadio || !statusNARadio) {
        console.error("Status radio buttons not found");
        return;
    }


    if (currentStatus === 'Active') {
        statusActiveRadio.checked = true;
    } else if (currentStatus === 'Pending') {
        statusPendingRadio.checked = true;
    } else {
        // Default to N/A or another state if applicable
        statusNARadio.checked = true;
    }

    $('#systemMessageModal').modal('show'); // Show the modal using Bootstrap 4's modal method
}

// Function to submit the status update form
function updateStatus() {
    const statusForm = document.getElementById('statusUpdateForm');
    if (statusForm) {
        statusForm.submit();
    } else {
        console.error("Status update form not found, cannot submit.");
    }
}

function updateTemperatureSelectionInModal(temperature) {
    console.log("Updating temperature in modal to:", temperature);
    // Ensure temperature is a number for comparison
    const tempValue = parseFloat(temperature);
    if (isNaN(tempValue)) {
        console.warn("Invalid temperature value received:", temperature, ". Using default.");
        selectedTemperature = 0.7; // Default to a sensible value
    } else {
        selectedTemperature = tempValue;
    }

    document.querySelectorAll('input[name="temperatureOptions"]').forEach(radio => {
        // Compare float values carefully
        radio.checked = Math.abs(parseFloat(radio.value) - selectedTemperature) < 0.01;
    });
    updateTemperatureDisplay(); // Update the display text to reflect the change
}

function populateSystemMessageModal() {
    let dropdownMenu = document.querySelector('#systemMessageModal .dropdown-menu');
    let dropdownButton = document.getElementById('systemMessageDropdown');

    if (!dropdownMenu || !dropdownButton) {
        console.error("Required elements for populating system message modal not found.");
        return;
    }

    dropdownMenu.innerHTML = ''; // Clear previous items

    console.log('Populating system message modal dropdown...');
    if (!systemMessages || systemMessages.length === 0) {
        console.warn("No system messages available to populate modal.");
        dropdownButton.textContent = 'No Messages'; // Indicate no messages
        // Optionally disable fields or show a message in the modal body
        return;
    }


    systemMessages.forEach((message) => {
        let dropdownItem = document.createElement('button');
        dropdownItem.className = 'dropdown-item';
        dropdownItem.textContent = message.name;
        dropdownItem.dataset.messageId = message.id; // Store ID

        dropdownItem.onclick = function() {
            const selectedMessageId = this.dataset.messageId;
            const selectedMessage = systemMessages.find(msg => msg.id == selectedMessageId);

            if (!selectedMessage) {
                console.error("Selected message not found:", selectedMessageId);
                return;
            }


            dropdownButton.textContent = selectedMessage.name;
            document.getElementById('systemMessageName').value = selectedMessage.name || '';
            document.getElementById('systemMessageDescription').value = selectedMessage.description || '';
            document.getElementById('systemMessageContent').value = selectedMessage.content || '';
            document.getElementById('systemMessageModal').dataset.messageId = selectedMessage.id;
            document.getElementById('enableWebSearch').checked = selectedMessage.enable_web_search;
            document.getElementById('enableTimeSense').checked = selectedMessage.enable_time_sense;

            currentSystemMessageDescription = selectedMessage.description;
            initialTemperature = selectedMessage.temperature; // Store initial temp for revert logic
            selectedTemperature = selectedMessage.temperature; // Set current selected temp
            model = selectedMessage.model_name; // Set current model
            activeSystemMessageId = selectedMessage.id; // Set active ID

            updateTemperatureSelectionInModal(selectedMessage.temperature);
            updateModelDropdownInModal(selectedMessage.model_name);
            loadWebsitesForSystemMessage(selectedMessage.id);
            fetchVectorFileList(selectedMessage.id); // Use renamed function

            isSaved = false; // Reset save flag
        };
        dropdownMenu.appendChild(dropdownItem);
    });

    // Set initial state if no active message ID is set yet
    if (!activeSystemMessageId && systemMessages.length > 0) {
        const defaultSystemMessage = systemMessages.find(msg => msg.name === "Default System Message") || systemMessages[0];
        if (defaultSystemMessage) {
            activeSystemMessageId = defaultSystemMessage.id;

            // Populate fields with default message data
            dropdownButton.textContent = defaultSystemMessage.name;
            document.getElementById('systemMessageName').value = defaultSystemMessage.name;
            document.getElementById('systemMessageDescription').value = defaultSystemMessage.description || '';
            document.getElementById('systemMessageContent').value = defaultSystemMessage.content || '';
            document.getElementById('systemMessageModal').dataset.messageId = defaultSystemMessage.id;
            document.getElementById('enableWebSearch').checked = defaultSystemMessage.enable_web_search;
            document.getElementById('enableTimeSense').checked = defaultSystemMessage.enable_time_sense;
            initialTemperature = defaultSystemMessage.temperature;
            selectedTemperature = initialTemperature;
            model = defaultSystemMessage.model_name;

            updateTemperatureSelectionInModal(initialTemperature);
            updateModelDropdownInModal(defaultSystemMessage.model_name);
            loadWebsitesForSystemMessage(defaultSystemMessage.id);
            fetchVectorFileList(defaultSystemMessage.id); // Use renamed function
        }
    }

    // Reset the isSaved flag whenever the modal is populated
    isSaved = false;
}

function fetchAndProcessSystemMessages(forceActiveId = null) {
    return new Promise((resolve, reject) => {
        fetch('/api/system_messages')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
             })
            .then(data => {
                systemMessages = data;
                console.log("System messages:", systemMessages);

                let messageToDisplay = null;
                let idToUse = forceActiveId || activeSystemMessageId;

                if (idToUse) {
                    messageToDisplay = systemMessages.find(msg => msg.id == idToUse);
                }
                if (!messageToDisplay) {
                    messageToDisplay = systemMessages.find(msg => msg.name === "Default System Message");
                    if (messageToDisplay) {
                        activeSystemMessageId = messageToDisplay.id;
                    } else if (systemMessages.length > 0) {
                        messageToDisplay = systemMessages[0];
                        activeSystemMessageId = messageToDisplay.id;
                    }
                } else {
                    activeSystemMessageId = messageToDisplay.id;
                }

                if (messageToDisplay) {
                    displaySystemMessage(messageToDisplay);
                    initializeSearchToggles(messageToDisplay);
                } else {
                    $('#chat').prepend('<div class="chat-entry system system-message text-danger">No system messages configured.</div>');
                }

                resolve();
            })
            .catch(error => {
                console.error('Error fetching system messages:', error);
                $('#chat').prepend(`<div class="chat-entry system system-message text-danger">Error loading system messages: ${error.message}</div>`);
                reject(error);
            });
    });
}






// Add this code to the beginning of your script
document.querySelectorAll('input[name="temperatureOptions"]').forEach(radio => {
    radio.addEventListener('change', function() {
        // Update selectedTemperature when a radio button is changed *by the user*
        if (this.checked) {
            selectedTemperature = parseFloat(this.value);
            console.log("Temperature changed via radio button to:", selectedTemperature);
            updateTemperatureDisplay(); // Update the text display as well
            isSaved = false; // Mark changes as unsaved
        }
    });
});


$('#systemMessageModal').on('hide.bs.modal', function (event) {
    // Remove focus from any element within the modal to prevent accessibility issues
    const focusedElement = document.activeElement;
    if (this.contains(focusedElement)) {
        focusedElement.blur();
        console.log("Blurred focused element inside modal during hide.");
    }

    // Check if the changes were not saved
    if (!isSaved) {
        console.log("Modal closed without saving. Restoring initial states.");

        // Find the currently active system message to revert to its state
        const activeSystemMessage = systemMessages.find(msg => msg.id === activeSystemMessageId);

        if (activeSystemMessage) {
            // Revert temperature to the initial value of the active message
            selectedTemperature = activeSystemMessage.temperature;
            updateTemperatureSelectionInModal(activeSystemMessage.temperature);

            // Revert other fields in the modal to match the active message
            document.getElementById('systemMessageName').value = activeSystemMessage.name;
            document.getElementById('systemMessageDescription').value = activeSystemMessage.description;
            document.getElementById('systemMessageContent').value = activeSystemMessage.content;
            document.getElementById('enableWebSearch').checked = activeSystemMessage.enable_web_search;
            document.getElementById('enableTimeSense').checked = activeSystemMessage.enable_time_sense;
            updateModelDropdownInModal(activeSystemMessage.model_name); // Revert model dropdown
            document.getElementById('systemMessageDropdown').textContent = activeSystemMessage.name; // Revert dropdown button text

            console.log("Modal content reset to active system message:", activeSystemMessage.name);
        } else {
            // Handle case where no active message is found (e.g., after deletion)
            // Reset to default values or clear fields
            console.log("No active system message found, cannot revert precisely.");
            // Optionally clear fields or set to a default state here
        }
    } else {
        console.log("Changes were saved, no need to revert.");
        // If saved, the UI should already reflect the saved state.
        // We might still need to update the main chat display if the active message changed.
        const activeMsg = systemMessages.find(msg => msg.id === activeSystemMessageId);
        if (activeMsg) displaySystemMessage(activeMsg);
    }

    // Reset the isSaved flag for the next time the modal opens
    isSaved = false;
    $(this).removeData('targetGroup'); // Clear any stored target group

    // Ensure all modal content groups are hidden
    $('.modal-content-group').addClass('hidden');
    // Optionally, ensure the default group is shown if needed upon reopening
    // $('#systemMessageContentGroup').removeClass('hidden');
});





document.getElementById('saveSystemMessageChanges').addEventListener('click', function() {
    const saveButton = this;
    const messageName = document.getElementById('systemMessageName').value.trim();
    const messageDescription = document.getElementById('systemMessageDescription').value;
    const messageContent = document.getElementById('systemMessageContent').value;
    const modelDropdownButton = document.getElementById('modalModelDropdownButton');
    const modelName = modelDropdownButton.dataset.apiName;
    const temperature = selectedTemperature;
    const enableWebSearch = document.getElementById('enableWebSearch').checked;
    const enableTimeSense = document.getElementById('enableTimeSense').checked;
    const messageId = activeSystemMessageId;

    // Basic validation
    if (!messageName) {
        showModalFlashMessage("System message name cannot be empty.", "warning");
        return;
    }
    if (!modelName) {
        showModalFlashMessage("Please select a model.", "warning");
        return;
    }
    const existingMessage = systemMessages.find(message =>
        message.name.toLowerCase() === messageName.toLowerCase() && message.id != messageId
    );
    if (existingMessage) {
        showModalFlashMessage("A system message with this name already exists. Please choose a different name.", "warning");
        return;
    }
    const messageData = {
        name: messageName,
        description: messageDescription,
        content: messageContent,
        model_name: modelName,
        temperature: temperature,
        enable_web_search: enableWebSearch,
        enable_time_sense: enableTimeSense
    };
    const url = messageId ? `/system-messages/${messageId}` : '/system-messages';
    const method = messageId ? 'PUT' : 'POST';

    saveButton.disabled = true;
    saveButton.textContent = 'Saving...';

    $.ajax({
        url: url,
        method: method,
        contentType: 'application/json',
        data: JSON.stringify(messageData),
        success: function(response) {
            console.log('Ajax success - response received:', response);
            isSaved = true;
            const savedMessageId = response.id || messageId;
            console.log('Saved/Updated message ID:', savedMessageId);
            
            let updatedMessage = null;
            if (messageId) {
                const idx = systemMessages.findIndex(msg => msg.id == savedMessageId);
                console.log('Found message index:', idx);
                if (idx !== -1) {
                    systemMessages[idx] = {...systemMessages[idx], ...response};
                    updatedMessage = systemMessages[idx];
                    console.log('Updated existing message:', updatedMessage);
                }
            } else {
                updatedMessage = response;
                systemMessages.push(updatedMessage);
                console.log('Added new message:', updatedMessage);
            }
            
            if (updatedMessage) {
                console.log('Updating UI with message:', updatedMessage);
                activeSystemMessageId = updatedMessage.id;
                displaySystemMessage(updatedMessage);
                $('#dropdownMenuButton').text(modelNameMapping(updatedMessage.model_name));
                initializeSearchToggles(updatedMessage);
            }
            
            console.log('About to hide modal...');
            // Try both approaches to ensure modal hiding
            try {
                $('#systemMessageModal').modal('hide');
                console.log('Modal hide called via jQuery');
            } catch (e) {
                console.error('Error hiding modal via jQuery:', e);
            }
            
            console.log('Starting background refresh...');
            fetchAndProcessSystemMessages(updatedMessage.id).then(() => {
                console.log('Background refresh complete');
            });
        },
        error: function(xhr) {
            console.error('Ajax error:', xhr);
            let errorMsg = "Unknown error saving system message";
            try {
                errorMsg = xhr.responseJSON?.error || xhr.responseText || errorMsg;
            } catch (e) {
                errorMsg = xhr.responseText || errorMsg;
            }
            showModalFlashMessage(`Error: ${errorMsg}`, "danger");
        },
        complete: function() {
            console.log('Ajax complete - resetting button state');
            saveButton.disabled = false;
            saveButton.textContent = 'Save Changes';
        }
    });

});









function updateTemperatureDisplay() {
    // Find the checked radio button
    const checkedRadio = document.querySelector('input[name="temperatureOptions"]:checked');

    if (checkedRadio) {
        const selectedValue = checkedRadio.value;
        // Get the short description for the selected temperature
        const selectedTemperatureDescription = temperatureDescriptions[selectedValue] || `${selectedValue}° - Custom`; // Fallback for unexpected values

        // Update the temperature display element (assuming one exists, e.g., in the modal or main UI)
        const tempDisplayElement = document.getElementById('temperatureDisplay'); // Example ID
        if (tempDisplayElement) {
            tempDisplayElement.textContent = 'Temperature: ' + selectedTemperatureDescription;
        }
        // Also update the display next to the radio buttons in the modal
        const modalTempDisplay = document.getElementById('modalTemperatureValueDisplay'); // Example ID
         if (modalTempDisplay) {
             modalTempDisplay.textContent = selectedTemperatureDescription;
         }

    } else {
        console.warn("No temperature radio button selected.");
        // Handle case where nothing is selected (e.g., display default or N/A)
        const tempDisplayElement = document.getElementById('temperatureDisplay');
        if (tempDisplayElement) {
            tempDisplayElement.textContent = 'Temperature: N/A';
        }
         const modalTempDisplay = document.getElementById('modalTemperatureValueDisplay');
         if (modalTempDisplay) {
             modalTempDisplay.textContent = 'N/A';
         }
    }
}

function displaySystemMessage(systemMessage) {
    if (!systemMessage) {
        console.warn("displaySystemMessage called with null or undefined message.");
        return;
    }

    // Remove existing system messages from the chat display
    $('.chat-entry.system.system-message').remove();

    // Update global variables based on the system message being displayed
    currentSystemMessage = systemMessage; // Store the full object
    currentSystemMessageDescription = systemMessage.description;
    model = systemMessage.model_name; // Update global model variable
    selectedTemperature = systemMessage.temperature; // Update global temperature
    activeSystemMessageId = systemMessage.id; // Ensure active ID is set

    // Create the button to open the settings modal
    let systemMessageButton = createSystemMessageButton();

    // Get display names and values
    const modelDisplayName = modelNameMapping(model); // Use the mapping function
    const temperatureDisplay = systemMessage.temperature.toFixed(1); // Format temperature

    // Render the description using Markdown/HTML renderer
    // Use DOMPurify if description can contain user-generated HTML/Markdown
    const descriptionContent = `<span class="no-margin">${renderOpenAI(systemMessage.description || '')}</span>`; // Ensure description is not null

    // Create feature indicators (Web Search, Time Sense)
    const featureIndicators = [];
    if (systemMessage.enable_web_search) {
        featureIndicators.push('<span class="feature-indicator" title="Web Search Enabled"><i class="fas fa-search"></i></span>');
    }
    if (systemMessage.enable_time_sense) {
        featureIndicators.push('<span class="feature-indicator" title="Time Sense Enabled"><i class="fas fa-clock"></i></span>');
    }

    const featuresDisplay = featureIndicators.length > 0 ?
        `<span class="feature-indicators ml-4" style="margin-left: 15px;">${featureIndicators.join('&nbsp;&nbsp;')}</span>` : '';

    // Construct the HTML for the system message display in the chat
    const renderedContent = `
    <div class="chat-entry system system-message" data-system-message-id="${systemMessage.id}">
        <strong>System:</strong>${systemMessageButton}${descriptionContent}<br>
        <strong>Model:</strong> <span class="model-name">${modelDisplayName}</span>
        <strong>Temp:</strong> ${temperatureDisplay}°${featuresDisplay}
    </div>`;

    // Prepend the system message to the chat interface
    $('#chat').prepend(renderedContent);

    // Update the `messages` array (used for sending to backend)
    // IMPORTANT: Only update if we're not in a loaded conversation
    if (!activeConversationId) {
        // Ensure the first message is always the system message content
        if (messages.length > 0 && messages[0].role === "system") {
            messages[0].content = systemMessage.content; // Update existing system message
        } else {
            // If no system message exists at the start, add it
            messages.unshift({
                role: "system",
                content: systemMessage.content
            });
        }
        console.log("System message added to messages array for new conversation");
    } else {
        console.log("Loaded conversation - not modifying messages array");
    }

    // Update both model dropdown buttons and ensure visibility
    const mainDropdownButton = $('#dropdownMenuButton');
    const currentModelBtn = $('.current-model-btn');
    
    // Update text for both buttons
    mainDropdownButton.text(modelDisplayName);
    currentModelBtn.text(modelDisplayName);
    
    // Ensure the current-model-btn is visible
    currentModelBtn.css('display', 'inline-block');
    
    // Update data attributes if needed
    currentModelBtn.attr('data-model', model);
    
    // Make sure the dropdown is properly initialized
    if (typeof bootstrap !== 'undefined') {
        const dropdownElement = document.querySelector('.model-dropdown');
        if (dropdownElement && !dropdownElement.dataset.bootstrapDropdown) {
            new bootstrap.Dropdown(dropdownElement);
        }
    }

    // Initialize search toggles based on this system message
    initializeSearchToggles(systemMessage);

    console.log('Displayed System Message:', systemMessage.name, 'ID:', activeSystemMessageId);
}




document.getElementById('delete-system-message-btn').addEventListener('click', function() {
    const messageId = document.getElementById('systemMessageModal').dataset.messageId;

    if (messageId) {
        // Check if trying to delete the "Default System Message"
        const messageToDelete = systemMessages.find(msg => msg.id == messageId);
        if (messageToDelete && messageToDelete.name === "Default System Message") {
            showModalFlashMessage("The 'Default System Message' cannot be deleted.", "warning");
            return;
        }


        if (confirm('Are you sure you want to delete this system message? This action cannot be undone.')) {
            // Disable button while deleting
            this.disabled = true;
            this.textContent = 'Deleting...';

            $.ajax({
                url: `/system-messages/${messageId}`,
                method: 'DELETE',
                // Add CSRF token if needed: headers: { 'X-CSRFToken': getCsrfToken() },
                success: function(response) {
                    console.log('System message deleted successfully:', response);

                    // Show success message in the modal
                    showModalFlashMessage('System message has been deleted.', 'success');

                    // Fetch the updated list of system messages
                    fetchAndProcessSystemMessages().then(() => {
                        // Find and set the "Default System Message" as the active message in the modal
                        const defaultSystemMessage = systemMessages.find(msg => msg.name === "Default System Message");
                        if (defaultSystemMessage) {
                            activeSystemMessageId = defaultSystemMessage.id; // Update global active ID

                            // Update modal fields to show the default message
                            document.getElementById('systemMessageDropdown').textContent = defaultSystemMessage.name;
                            document.getElementById('systemMessageName').value = defaultSystemMessage.name;
                            document.getElementById('systemMessageDescription').value = defaultSystemMessage.description || '';
                            document.getElementById('systemMessageContent').value = defaultSystemMessage.content || '';
                            document.getElementById('systemMessageModal').dataset.messageId = defaultSystemMessage.id; // Update modal ID
                            document.getElementById('enableWebSearch').checked = defaultSystemMessage.enable_web_search;
                            document.getElementById('enableTimeSense').checked = defaultSystemMessage.enable_time_sense;
                            updateTemperatureSelectionInModal(defaultSystemMessage.temperature);
                            updateModelDropdownInModal(defaultSystemMessage.model_name);
                            model = defaultSystemMessage.model_name; // Update global model
                            selectedTemperature = defaultSystemMessage.temperature; // Update global temp

                            // Load associated data for the default message
                            loadWebsitesForSystemMessage(defaultSystemMessage.id);
                            fetchVectorFileList(defaultSystemMessage.id); // Use renamed function

                            // Display the default message in the main chat UI
                            displaySystemMessage(defaultSystemMessage);

                        } else {
                            console.error('Default System Message not found after deletion.');
                            // Handle case where default is missing (e.g., clear modal fields)
                            // Maybe close the modal or show an error?
                        }

                        // Re-populate the dropdown in the modal with the updated list
                        populateSystemMessageModal(); // This re-populates the dropdown

                        // Close the modal after a short delay to allow user to see the flash message
                        setTimeout(() => {
                             $('#systemMessageModal').modal('show');
                        }, 2000); // 2 seconds delay


                    }).catch(error => {
                        console.error("Error refreshing system messages after delete:", error);
                        showModalFlashMessage('System message deleted, but failed to refresh list.', 'warning');
                    });

                },
                error: function(xhr) {
                    console.error('Error deleting system message:', xhr.status, xhr.responseText);
                    const errorMsg = xhr.responseJSON?.error || xhr.responseText || "Unknown error deleting system message";
                    showModalFlashMessage(`Error: ${errorMsg}`, 'danger');
                },
                complete: function() {
                    // Re-enable button
                    const deleteButton = document.getElementById('delete-system-message-btn');
                    deleteButton.disabled = false;
                    deleteButton.textContent = 'Delete';
                }
            });
        }
    } else {
        console.error('System message ID not found for deletion');
        showModalFlashMessage('Could not determine which system message to delete.', 'danger');
    }
});

// New system message button actions
document.getElementById('new-system-message-btn').addEventListener('click', function() {
    // Clear all the input fields in the modal
    document.getElementById('systemMessageName').value = '';
    document.getElementById('systemMessageDescription').value = '';
    document.getElementById('systemMessageContent').value = '';

    // Clear the messageId from the modal's data attributes to indicate creation mode
    document.getElementById('systemMessageModal').dataset.messageId = '';

    // Reset dropdown button text
    document.getElementById('systemMessageDropdown').textContent = 'Select System Message';


    // Set the model to a default (e.g., GPT-3.5)
    const defaultModelApi = 'gpt-3.5-turbo';
    updateModelDropdownInModal(defaultModelApi); // Update button text and data attribute
    model = defaultModelApi; // Update global model variable if needed immediately

    // Set the temperature to a default (e.g., 0.7)
    const defaultTemp = 0.7;
    updateTemperatureSelectionInModal(defaultTemp); // Update radio buttons and display
    selectedTemperature = defaultTemp; // Update global temperature variable

    // Reset checkboxes to default (e.g., false)
    document.getElementById('enableWebSearch').checked = false;
    document.getElementById('enableTimeSense').checked = false;


    // Clear the sidebar (websites list)
    const sidebar = document.getElementById('modal-sidebar');
    if (sidebar) {
        sidebar.innerHTML = '<div class="text-center p-2">Add websites after saving.</div>'; // Clear existing content
    }

    // Clear the vector file list
    const fileList = document.getElementById('fileList');
    const noFilesMessage = document.getElementById('noFilesMessage');
    const fileListError = document.getElementById('fileListError');
    if (fileList) fileList.innerHTML = '';
    if(noFilesMessage) noFilesMessage.style.display = 'block'; // Show 'no files' message
    if(fileListError) fileListError.style.display = 'none'; // Hide errors


    // Clear active website ID and website details form
    activeWebsiteId = null;
    clearWebsiteDetails();
    updateWebsiteControls(); // Update buttons (show Add, hide Remove/Index)

    // Ensure the main content group is visible
    switchToSystemMessageContentGroup();

    // Reset save flag
    isSaved = false;

    // Focus the name input field
    document.getElementById('systemMessageName').focus();
});

function switchToSystemMessageContentGroup() {
    // Hide all content groups within the modal
    const contentGroups = document.querySelectorAll('#systemMessageModal .modal-content-group');
    contentGroups.forEach(group => group.classList.add('hidden'));

    // Show the systemMessageContentGroup
    const systemMessageContentGroup = document.getElementById('systemMessageContentGroup');
    if (systemMessageContentGroup) {
        systemMessageContentGroup.classList.remove('hidden');
    } else {
        console.error("systemMessageContentGroup not found in modal.");
    }
}

$(window).on('load', function () {
    // Rely on fetchAndProcessSystemMessages in DOMContentLoaded to set initial state.
});


document.querySelectorAll('input[name="temperatureOptions"]').forEach((radioButton) => {
    // Add listener to update display text when user changes selection
    radioButton.addEventListener('change', updateTemperatureDisplay);
});

// Mapping between temperature values and their short descriptions
const temperatureDescriptions = {
    '0': '0° - Deterministic',
    '0.3': '0.3° - Low Variability',
    '0.7': '0.7° - Balanced',
    '1.0': '1.0° - Creative',
    '1.5': '1.5° - Experimental'
};




// Helper function to map model names to their display values
function modelNameMapping(modelName, reasoningEffort, extendedThinking) {
    // Find the matching model in our shared list
    const modelEntry = AVAILABLE_MODELS.find(m => 
        m.api === modelName && 
        (!reasoningEffort || m.reasoning === reasoningEffort) &&
        (!extendedThinking || m.extendedThinking === extendedThinking)
    );

    if (modelEntry) {
        return modelEntry.display;
    }

    // Fallback to the original name if not found
    return modelName || "Unknown Model";
}

function populateModelDropdownInModal() {
    const modalModelDropdownMenu = document.querySelector('#systemMessageModal .model-dropdown-container .dropdown-menu');
    const modalModelDropdownButton = document.getElementById('modalModelDropdownButton');

    if (!modalModelDropdownMenu || !modalModelDropdownButton) {
        console.error("Required elements for modal model dropdown not found.");
        return;
    }

    // Clear existing dropdown items
    modalModelDropdownMenu.innerHTML = '';

    // Use the shared AVAILABLE_MODELS list
    AVAILABLE_MODELS.forEach(modelItem => {
        const dropdownItem = createModelDropdownItem(modelItem, function() {
            modalModelDropdownButton.textContent = this.textContent;
            modalModelDropdownButton.dataset.apiName = this.dataset.apiName;

            if (this.dataset.reasoning) {
                modalModelDropdownButton.dataset.reasoning = this.dataset.reasoning;
            } else {
                delete modalModelDropdownButton.dataset.reasoning;
            }

            // Handle extended thinking UI updates
            const isClaudeSonnet = this.dataset.apiName === 'claude-3-7-sonnet-20250219';
            const extendedThinkingSelected = this.dataset.extendedThinking === 'true';
            updateExtendedThinkingUI(isClaudeSonnet, extendedThinkingSelected, this.dataset.thinkingBudget);

            isSaved = false;
        })[0]; // Convert jQuery object to DOM element

        modalModelDropdownMenu.appendChild(dropdownItem);
    });

    // Re-attach extended thinking related event listeners
    setupExtendedThinkingListeners();
}

// Helper function for extended thinking UI updates
function updateExtendedThinkingUI(isClaudeSonnet, extendedThinkingEnabled, budget) {
    const extendedThinkingContainer = document.getElementById('extended-thinking-toggle-container');
    const thinkingBudgetContainer = document.getElementById('thinking-budget-container');
    const extendedThinkingToggle = document.getElementById('extended-thinking-toggle');
    const budgetSlider = document.getElementById('thinking-budget-slider');
    const budgetValueDisplay = document.getElementById('thinking-budget-value');
    const modalModelDropdownButton = document.getElementById('modalModelDropdownButton');

    if (isClaudeSonnet) {
        extendedThinkingContainer.style.display = 'block';
        extendedThinkingToggle.checked = extendedThinkingEnabled;

        if (extendedThinkingEnabled) {
            thinkingBudgetContainer.style.display = 'block';
            const defaultBudget = budget || 12000;
            budgetSlider.value = defaultBudget;
            budgetValueDisplay.textContent = defaultBudget;
            modalModelDropdownButton.dataset.extendedThinking = 'true';
            modalModelDropdownButton.dataset.thinkingBudget = defaultBudget;
        } else {
            thinkingBudgetContainer.style.display = 'none';
            delete modalModelDropdownButton.dataset.extendedThinking;
            delete modalModelDropdownButton.dataset.thinkingBudget;
        }
    } else {
        extendedThinkingContainer.style.display = 'none';
        thinkingBudgetContainer.style.display = 'none';
        delete modalModelDropdownButton.dataset.extendedThinking;
        delete modalModelDropdownButton.dataset.thinkingBudget;
    }
}



// Handler for the extended thinking toggle change
function handleExtendedThinkingToggleChange() {
    const isEnabled = this.checked;
    const thinkingBudgetContainer = document.getElementById('thinking-budget-container');
    const modalModelDropdownButton = document.getElementById('modalModelDropdownButton');
    const budgetSlider = document.getElementById('thinking-budget-slider');
    const budgetValueDisplay = document.getElementById('thinking-budget-value');

    thinkingBudgetContainer.style.display = isEnabled ? 'block' : 'none';

    if (isEnabled) {
        const budget = budgetSlider.value || 12000; // Use current or default
        modalModelDropdownButton.dataset.extendedThinking = 'true';
        modalModelDropdownButton.dataset.thinkingBudget = budget;
        budgetValueDisplay.textContent = budget; // Ensure display matches
    } else {
        delete modalModelDropdownButton.dataset.extendedThinking;
        delete modalModelDropdownButton.dataset.thinkingBudget;
    }
    isSaved = false; // Mark changes as unsaved
    console.log("Extended thinking toggled:", isEnabled, "Budget:", modalModelDropdownButton.dataset.thinkingBudget);
}

// Handler for the budget slider change
function handleBudgetSliderChange() {
    const budget = this.value;
    document.getElementById('thinking-budget-value').textContent = budget;
    document.getElementById('modalModelDropdownButton').dataset.thinkingBudget = budget;
    isSaved = false; // Mark changes as unsaved
    console.log("Thinking budget changed:", budget);
}


function updateModelDropdownInModal(modelName) {
    // Find the corresponding model display name and details
    // This needs access to the same model list definition used in populateModelDropdownInModal
    // For simplicity, we'll just use the mapping function for the button text for now.
    // A more robust approach would involve finding the model object from the list.

    const userFriendlyModelName = modelNameMapping(modelName); // Get display name
    const modelDropdownButton = document.getElementById('modalModelDropdownButton');

    if (modelDropdownButton) {
        modelDropdownButton.textContent = userFriendlyModelName;
        modelDropdownButton.dataset.apiName = modelName; // Store the API name

        // Reset/clear reasoning and extended thinking attributes initially
        delete modelDropdownButton.dataset.reasoning;
        delete modelDropdownButton.dataset.extendedThinking;
        delete modelDropdownButton.dataset.thinkingBudget;

        // Hide related UI elements initially
        const extendedThinkingContainer = document.getElementById('extended-thinking-toggle-container');
        const thinkingBudgetContainer = document.getElementById('thinking-budget-container');
        if (extendedThinkingContainer) extendedThinkingContainer.style.display = 'none';
        if (thinkingBudgetContainer) thinkingBudgetContainer.style.display = 'none';


        // If the model is Claude 3.7 Sonnet, potentially show extended thinking controls
        // This requires knowing if the *saved* state has extended thinking enabled.
        // We need the full system message object here.
        const activeMsg = systemMessages.find(msg => msg.id === activeSystemMessageId);
        if (activeMsg && modelName === 'claude-3-7-sonnet-20250219') {
             // Check if the saved message has extended thinking enabled (need backend to provide this)
             // Assuming a property like `activeMsg.extended_thinking_enabled` exists
             const isExtendedEnabledSaved = activeMsg.extended_thinking_enabled || false; // Default to false if property missing
             const savedBudget = activeMsg.thinking_budget || 12000;

             if (extendedThinkingContainer) extendedThinkingContainer.style.display = 'block'; // Show toggle
             const toggle = document.getElementById('extended-thinking-toggle');
             if (toggle) toggle.checked = isExtendedEnabledSaved;

             if (isExtendedEnabledSaved && thinkingBudgetContainer) {
                 thinkingBudgetContainer.style.display = 'block'; // Show budget slider
                 const slider = document.getElementById('thinking-budget-slider');
                 const valueDisplay = document.getElementById('thinking-budget-value');
                 if (slider) slider.value = savedBudget;
                 if (valueDisplay) valueDisplay.textContent = savedBudget;
                 modelDropdownButton.dataset.extendedThinking = 'true';
                 modelDropdownButton.dataset.thinkingBudget = savedBudget;
             }
        }

        // If the model is o3-mini, potentially set reasoning attribute
        // Requires knowing the saved reasoning effort.
        // Assuming a property like `activeMsg.reasoning_effort` exists
        if (activeMsg && modelName === 'o3-mini' && activeMsg.reasoning_effort) {
            modelDropdownButton.dataset.reasoning = activeMsg.reasoning_effort;
            // Update button text to include reasoning effort
            modelDropdownButton.textContent = modelNameMapping(modelName, activeMsg.reasoning_effort);
        }


    } else {
        console.error("Modal model dropdown button not found.");
    }
}


// Example usage when a system message is selected or modal is opened
// updateModelDropdownInModal('gpt-3.5-turbo'); // Update with the actual model name from the selected system message

$('#systemMessageModal').on('show.bs.modal', function (event) {
    // Determine the target group from the trigger element or default
    const triggerButton = event.relatedTarget; // Button that triggered the modal
    let targetGroup = $(triggerButton).data('target') || $(this).data('targetGroup') || 'systemMessageContentGroup'; // Default to content group
    console.log("Modal show event - target group:", targetGroup);

    // Hide all groups first
    $('.modal-content-group').addClass('hidden');
    // Show the target group
    $('#' + targetGroup).removeClass('hidden');

    // Store the target group in case needed later
    $(this).data('targetGroup', targetGroup);


    // Fetch the latest system messages data (or use cached if fresh enough)
    fetchAndProcessSystemMessages().then(() => {
        // Setup the dropdown for selecting the model *after* system messages are loaded
        populateModelDropdownInModal(); // Populates the model choices

        // Determine the active system message to display/edit
        let activeSystemMessage;
        if (activeSystemMessageId) {
            activeSystemMessage = systemMessages.find(msg => msg.id === activeSystemMessageId);
        }
        // If no active ID or message not found, try default, then first
        if (!activeSystemMessage) {
            activeSystemMessage = systemMessages.find(msg => msg.name === "Default System Message") || (systemMessages.length > 0 ? systemMessages[0] : null);
            if (activeSystemMessage) {
                activeSystemMessageId = activeSystemMessage.id; // Update active ID
                displaySystemMessage(activeSystemMessage);
            }
        }


        if (activeSystemMessage) {
            // Populate all fields with the active system message data
            document.getElementById('systemMessageDropdown').textContent = activeSystemMessage.name; // Update dropdown button
            document.getElementById('systemMessageName').value = activeSystemMessage.name;
            document.getElementById('systemMessageDescription').value = activeSystemMessage.description || '';
            document.getElementById('systemMessageContent').value = activeSystemMessage.content || '';
            document.getElementById('systemMessageModal').dataset.messageId = activeSystemMessage.id; // Set ID on modal

            initializeSearchToggles(activeSystemMessage); // Initialize search toggles based on the message

            document.getElementById('enableTimeSense').checked = activeSystemMessage.enable_time_sense;

            // Update model and temperature controls based on the active message
            updateModelDropdownInModal(activeSystemMessage.model_name); // Sets modal dropdown state
            updateTemperatureSelectionInModal(activeSystemMessage.temperature); // Sets modal temp state
            initialTemperature = activeSystemMessage.temperature; // Store initial temp for revert

            console.log("System message data loaded into modal:", activeSystemMessage.name);

            // Load associated websites and vector files for the active system message
            loadWebsitesForSystemMessage(activeSystemMessageId);
            fetchVectorFileList(activeSystemMessageId); // Use renamed function
        } else {
            // Handle the case where no system messages are available at all
            console.log("No system messages available. Setting modal to default 'new' state.");
            document.getElementById('new-system-message-btn').click(); // Simulate clicking 'new' button
        }

        // Reset the isSaved flag each time the modal is shown
        isSaved = false;

    }).catch(error => {
        console.error("Error loading system messages for modal:", error);
        showModalFlashMessage("Error loading system message data.", "danger");
        // Optionally disable save button or close modal
    });
});

$('#systemMessageModal').on('shown.bs.modal', function () {
    // This runs after the modal is fully visible and transitions complete
    updateVectorFileMoreIndicator(); // Use renamed function

    // Focus the first relevant input field based on the visible group
    const visibleGroup = $('.modal-content-group:not(.hidden)').first();
    if (visibleGroup.length) {
        // Exclude Bootstrap 4 close button (.close), not .btn-close (Bootstrap 5)
        const firstInput = visibleGroup.find('input:not([type=hidden]), textarea, select, button:not(.close)').first();
        if (firstInput.length) {
            firstInput.focus();
        }
    }
});



// Event listener for the system message button in the chat interface
document.addEventListener('click', function(event) {
    // Use closest to handle clicks on the icon inside the button
    const systemButton = event.target.closest('#systemMessageButton');
    if (systemButton) {
        // Set the target group to 'systemMessageContentGroup' when clicking the gear icon
        $('#systemMessageModal').data('targetGroup', 'systemMessageContentGroup');

        $('#systemMessageModal').modal('show');
    }
});

// Reset modal to default state on close (handled by 'hide.bs.modal' listener already)
$('#systemMessageModal').on('hidden.bs.modal', function () {
    // This event fires after the modal has finished hiding
    console.log("System message modal hidden.");

    // Hide all content groups to ensure clean state for next open
    $('.modal-content-group').addClass('hidden');

    // Clear active website ID and website details form
    activeWebsiteId = null;
    clearWebsiteDetails();
    updateWebsiteControls();

    // The 'hide.bs.modal' listener should handle reverting unsaved changes.
});

// Handles switching between different layers of orchestration within the modal.
function openModalAndShowGroup(targetGroup) {
    console.log("Switching modal view to target group:", targetGroup);

    // Hide all groups in the modal first
    $('#systemMessageModal .modal-content-group').addClass('hidden');

    // Show the selected group
    $('#' + targetGroup).removeClass('hidden');

    // Update associated data if needed (e.g., refresh file/website list)
    if (targetGroup === 'filesGroup' && activeSystemMessageId) {
        fetchVectorFileList(activeSystemMessageId); // Use renamed function
        updateVectorFileMoreIndicator(); // Use renamed function
    }
    if (targetGroup === 'websitesGroup' && activeSystemMessageId) {
        loadWebsitesForSystemMessage(activeSystemMessageId);
    }


    // If the modal isn't already shown, show it using Bootstrap 4 method.
    var modalElement = $('#systemMessageModal'); // Use jQuery selector
    if (!modalElement.hasClass('show')) { // Check if modal is visible using jQuery
        modalElement.modal('show'); // Show modal using jQuery plugin
    }

    // Store the currently shown group
    $('#systemMessageModal').data('targetGroup', targetGroup);
}

// This function seems redundant with openModalAndShowGroup, but kept for compatibility if called elsewhere.
function toggleContentGroup(groupID) {
    console.warn("toggleContentGroup is deprecated; use openModalAndShowGroup instead.");
    openModalAndShowGroup(groupID);
}

function createSystemMessageButton() {
    // Returns the HTML for the gear icon button in the chat display
    return `<button class="btn btn-sm btn-link p-0 ms-2" id="systemMessageButton" title="System Message Settings" style="color: white; text-decoration: none; vertical-align: middle;"><i class="fa-solid fa-gear"></i></button>`;
}

document.addEventListener('click', function(event) {
    // Example: Listener for a hypothetical "Add System Message" button *outside* the modal
    if (event.target && event.target.id === 'add-new-system-message-main-ui-btn') { // Example ID
        // Logic to handle adding a new system message, likely opens the modal in 'new' state
        $('#new-system-message-btn').click(); // Trigger the modal's 'new' button logic
        $('#systemMessageModal').modal('show');

    }
});

// --- End System Message Modal & Related Functions ---


// --- Chat Message Rendering & Handling ---

function copyCodeToClipboard(button) {
    const codeBlock = button.closest('.code-block');
    if (!codeBlock) return;
    const codeElement = codeBlock.querySelector('pre code');
    if (!codeElement) return;

    const codeToCopy = codeElement.textContent; // Get text content directly

    navigator.clipboard.writeText(codeToCopy).then(() => {
        button.innerHTML = '<i class="fas fa-check"></i> Copied!'; // Use innerHTML to include icon
        button.classList.add('copied'); // Add class for styling feedback
        setTimeout(() => {
            button.innerHTML = '<i class="fas fa-clipboard"></i> Copy code'; // Restore original text/icon
            button.classList.remove('copied');
        }, 2000); // Reset after 2 seconds
    }).catch(err => {
        console.error('Failed to copy code using navigator.clipboard: ', err);
        button.textContent = 'Error';
        // Fallback using document.execCommand (less reliable)
        try {
            const range = document.createRange();
            window.getSelection().removeAllRanges();
            range.selectNode(codeElement);
            window.getSelection().addRange(range);
            document.execCommand('copy');
            window.getSelection().removeAllRanges();
            button.innerHTML = '<i class="fas fa-check"></i> Copied!';
            button.classList.add('copied');
             setTimeout(() => {
                button.innerHTML = '<i class="fas fa-clipboard"></i> Copy code';
                button.classList.remove('copied');
            }, 2000);
        } catch (execErr) {
            console.error('Fallback execCommand failed: ', execErr);
            button.textContent = 'Failed';
        }
    });
}


function createMessageElement(message) {
    let messageElement;
    const role = message.role;
    let content = message.content || ''; // Ensure content is a string

    if (role === 'system') {
        // System messages are now handled by displaySystemMessage function,
        // but this could be a fallback or handle different types of system messages.
        // Let's assume this handles informational system messages added during the chat.

        // Example: Render context added messages differently
        const vectorSearchRegex = /<Added Context Provided by Vector Search>([\s\S]*?)<\/Added Context Provided by Vector Search>/g;
        const webSearchRegex = /<Added Context Provided by Web Search>([\s\S]*?)<\/Added Context Provided by Web Search>/g;

        let vectorSearchResults = [];
        let webSearchResults = [];
        let match;

        // Extract Vector Search Results
        while ((match = vectorSearchRegex.exec(content)) !== null) {
            let context = match[1].trim();
            if (context && context !== "Empty Response") {
                vectorSearchResults.push(`<div class="context-block vector-context"><strong>Vector Search Context:</strong><br>${escapeHtml(context)}</div>`);
            }
        }
        content = content.replace(vectorSearchRegex, '').trim(); // Remove tag

        // Extract Web Search Results
        while ((match = webSearchRegex.exec(content)) !== null) {
            let context = match[1].trim();
            if (context && context !== "No web search results") {
                // Convert URLs to clickable links within the web search context
                context = context.replace(
                    /(https?:\/\/[^\s]+)/g,
                    '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
                );
                webSearchResults.push(`<div class="context-block web-context"><strong>Web Search Context:</strong><br>${context}</div>`); // Render context directly
            }
        }
        content = content.replace(webSearchRegex, '').trim(); // Remove tag

        // Render remaining system message content (if any)
        let renderedContent = content ? renderOpenAI(content) : '';

        // Combine everything
        let fullContent = renderedContent + vectorSearchResults.join('') + webSearchResults.join('');

        if (fullContent) {
             messageElement = $(`
                <div class="chat-entry system system-info">
                    <i class="fas fa-info-circle"></i> ${fullContent}
                </div>`);
        } else {
            // Don't create an element if there's no content after processing
            return null;
        }

    } else if (role === 'user') {
        const prefix = '<i class="far fa-user"></i> ';
        // Escape user input thoroughly before displaying
        const processedContent = escapeHtml(content);
        messageElement = $(`<div class="chat-entry user user-message">${prefix}${processedContent}</div>`);

    } else if (role === 'assistant') {
        const prefix = '<i class="fas fa-robot"></i> ';
        // Render assistant response using Markdown, code highlighting, etc.
        // Footnote handling might be done here or within renderOpenAI/renderOpenAIWithFootnotes
        const processedContent = renderOpenAI(content); // Assuming renderOpenAI handles markdown, code, etc.
        messageElement = $(`<div class="chat-entry assistant bot-message">${prefix}${processedContent}</div>`);

    } else {
        // Handle unknown roles or provide a default rendering
        console.warn(`Unknown message role: ${role}`);
        const prefix = '<i class="fas fa-question-circle"></i> ';
        const processedContent = escapeHtml(content);
        messageElement = $(`<div class="chat-entry unknown ${role}-message">${prefix}${processedContent}</div>`);
    }

    return messageElement; // Return the jQuery object (or null)
}


// Function to render Markdown and code snippets
function renderMarkdownAndCode(content) {
    // console.log('renderMarkdownAndCode called with content:', content ? content.substring(0, 50) + '...' : 'null');
    if (typeof content !== 'string') return ''; // Handle non-string input

    // Normalize newlines to ensure consistent handling across different environments
    content = content.replace(/\r\n/g, '\n');

    // Use marked library for Markdown parsing
    // Configure marked options (optional, customize as needed)
    marked.setOptions({
        renderer: new marked.Renderer(),
        highlight: function(code, lang) {
            // Use Prism.js for syntax highlighting
            const language = Prism.languages[lang] ? lang : 'clike'; // Default to clike if lang not found
            if (Prism.languages[language]) {
                return Prism.highlight(code, Prism.languages[language], language);
            } else {
                return escapeHtml(code); // Fallback to escaped code if language not supported
            }
        },
        pedantic: false,
        gfm: true,
        breaks: false, // Consider true if you want single newlines to be <br>
        sanitize: false, // IMPORTANT: Sanitize HTML later if needed, marked's sanitize is deprecated
        smartLists: true,
        smartypants: false,
        xhtml: false
    });

    // Parse the content using marked
    let htmlContent = marked.parse(content);

    // Post-processing: Add copy buttons to code blocks generated by marked/prism
    // Marked with Prism highlighting typically generates <pre><code class="language-...">...</code></pre>
    // We need to wrap this and add the header/button.
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = htmlContent;

    tempDiv.querySelectorAll('pre > code[class*="language-"]').forEach((codeElement) => {
        const preElement = codeElement.parentElement;
        if (preElement && preElement.tagName === 'PRE') {
            // Extract language
            const langMatch = codeElement.className.match(/language-(\w+)/);
            const lang = langMatch ? langMatch[1] : 'code'; // Default language name
            const displayLang = lang.toUpperCase();

            // Create the code block wrapper
            const codeBlockWrapper = document.createElement('div');
            codeBlockWrapper.className = 'code-block';

            // Create the header
            const header = document.createElement('div');
            header.className = 'code-block-header';
            header.innerHTML = `
                <span class="code-type">${displayLang}</span>
                <button class="copy-code btn btn-sm btn-outline-secondary" onclick="copyCodeToClipboard(this)">
                    <i class="fas fa-clipboard"></i> Copy code
                </button>
            `;

            // Insert wrapper and move pre element inside
            preElement.parentNode.insertBefore(codeBlockWrapper, preElement);
            codeBlockWrapper.appendChild(header);
            codeBlockWrapper.appendChild(preElement); // Move the original <pre> inside
        }
    });

    // Get the final HTML with added copy buttons
    htmlContent = tempDiv.innerHTML;


    // IMPORTANT: Sanitize the final HTML if the original Markdown could contain malicious content
    // htmlContent = DOMPurify.sanitize(htmlContent); // Uncomment if DOMPurify is included and needed

    // console.log('Processed HTML content:', htmlContent ? htmlContent.substring(0, 100) + '...' : '');
    return htmlContent;
}


// Enhanced HTML escaping function
function escapeHtml(unsafe) {
    if (typeof unsafe !== 'string') {
        // Handle non-string inputs gracefully, e.g., convert to string or return empty
        unsafe = String(unsafe);
    }
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
 }

function renderOpenAI(content) {
    // console.log('renderOpenAI called with content:', content ? content.substring(0, 50) + '...' : 'null');
    if (typeof content !== 'string') return ''; // Handle non-string input

    // Process the content to handle markdown and code blocks (which includes highlighting)
    let processedContent = renderMarkdownAndCode(content);

    // Footnote handling (if applicable and not done elsewhere)
    // Example: Replace [^1] with links if footnotes are parsed separately
    // processedContent = processedContent.replace(/\[\^(\d+)\]/g, '<sup class="footnote-ref">[$1]</sup>');

    // console.log('Final processed content for renderOpenAI:', processedContent ? processedContent.substring(0, 100) + '...' : '');
    return processedContent;
}

// --- End Chat Message Rendering & Handling ---


// --- Conversation List & Loading ---

function updateConversationList(page = 1, append = false) {
    if (isLoadingConversations && append) return; // Prevent multiple simultaneous appends

    console.log(`Updating conversation list - Page: ${page}, Append: ${append}`);
    isLoadingConversations = true;

    const conversationListContainer = $('#conversation-list');
    let loadingIndicator = $('#conversation-loading');

    // Show loading indicator
    if (!append) {
        conversationListContainer.empty(); // Clear list if not appending
        if (loadingIndicator.length === 0) {
            loadingIndicator = $('<div id="conversation-loading" class="text-center p-2">Loading conversations...</div>');
            conversationListContainer.after(loadingIndicator); // Place indicator after the list
        }
        loadingIndicator.html('Loading conversations...').show();
    } else {
        // For append, show loading at the bottom
        if (loadingIndicator.length === 0) {
             loadingIndicator = $('<div id="conversation-loading" class="text-center p-2">Loading more...</div>');
             conversationListContainer.after(loadingIndicator);
        }
         loadingIndicator.html('Loading more...').show();
    }


    fetch(`/api/conversations?page=${page}&per_page=20`) // Adjust per_page as needed
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log(`Received ${data.conversations.length} conversations. Total pages: ${data.total_pages}, Current page: ${page}`);

            // Remove loading indicator
            loadingIndicator.hide();

            // Update pagination state
            hasMoreConversations = page < data.total_pages;
            currentPage = page;

            // Prepare new HTML content
            let newContent = '';
            data.conversations.forEach(conversation => {
                const temperatureInfo = (typeof conversation.temperature !== 'undefined' && conversation.temperature !== null)
                    ? `${conversation.temperature.toFixed(1)}°` // Format temp
                    : 'N/A°';

                // Use modelNameMapping for display
                const modelDisplay = modelNameMapping(conversation.model_name || 'Unknown');
                const title = escapeHtml(conversation.title || 'Untitled Conversation');

                newContent += `
                    <div class="conversation-item" data-id="${conversation.id}" title="Model: ${modelDisplay}, Temp: ${temperatureInfo}">
                        <div class="conversation-title">${title}</div>
                        <div class="conversation-meta">
                            <span class="model-name" title="AI Model: ${modelDisplay}">
                                ${modelDisplay}
                            </span>
                            <span class="temperature-info" title="Temperature: ${temperatureInfo}">
                                ${temperatureInfo}
                            </span>
                        </div>
                    </div>
                `;
            });

            // Update the conversation list
            if (append) {
                conversationListContainer.append(newContent);
            } else {
                conversationListContainer.html(newContent);
            }

            // Re-attach click handlers to *all* conversation items after update
            conversationListContainer.find('.conversation-item').off('click').on('click', function() {
                // Remove active class from previously selected item
                conversationListContainer.find('.conversation-item.active').removeClass('active');
                // Add active class to the clicked item
                $(this).addClass('active');

                const conversationId = $(this).data('id');
                console.log(`Loading conversation with id: ${conversationId}`);
                // Update URL without reloading page
                window.history.pushState({ conversationId: conversationId }, '', `/c/${conversationId}`);
                loadConversation(conversationId);
            });

            // Highlight the currently active conversation if it exists in the list
            if (activeConversationId) {
                 conversationListContainer.find(`.conversation-item[data-id="${activeConversationId}"]`).addClass('active');
            }


            // Setup infinite scroll if there are more conversations
            // Ensure observer is detached before potentially adding a new one
            detachInfiniteScrollObserver(); // Detach previous observer if any
            if (hasMoreConversations) {
                setupInfiniteScroll();
            }

        })
        .catch(error => {
            console.error(`Error updating conversation list: ${error}`);
            loadingIndicator.html('<span class="text-danger">Error loading conversations.</span> <a href="#" onclick="updateConversationList(1, false); return false;">Retry</a>').show();
        })
        .finally(() => {
            isLoadingConversations = false;
        });
}

// Global observer variable
let conversationListObserver = null;

// Function to detach the observer
function detachInfiniteScrollObserver() {
    if (conversationListObserver) {
        conversationListObserver.disconnect();
        conversationListObserver = null;
        // console.log("Infinite scroll observer detached.");
    }
}


// Add infinite scroll functionality
function setupInfiniteScroll() {
    // Detach any existing observer first
    detachInfiniteScrollObserver();

    const conversationList = document.getElementById('conversation-list');
    if (!conversationList) return;

    const lastConversation = conversationList.lastElementChild;
    if (!lastConversation) return; // No items to observe

    // console.log("Setting up infinite scroll observer on:", lastConversation);

    conversationListObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && hasMoreConversations && !isLoadingConversations) {
                // console.log("Last element intersecting, loading more conversations...");
                // Detach observer temporarily to prevent rapid firing while loading
                detachInfiniteScrollObserver();
                updateConversationList(currentPage + 1, true);
            }
        });
    }, {
        root: null, // Use viewport as root
        rootMargin: '0px',
        threshold: 0.1 // Trigger when 10% of the target is visible
     });

    // Observe the last conversation item
    conversationListObserver.observe(lastConversation);
}




$('#edit-title-btn').click(function() {
    const currentTitle = $('#conversation-title').text();
    const newTitle = prompt('Enter new conversation title:', currentTitle);

    if (newTitle && newTitle.trim() !== '' && newTitle !== currentTitle) {
        if (!activeConversationId) {
            alert("Cannot rename. No active conversation selected.");
            return;
        }

        $.ajax({
            url: `/api/conversations/${activeConversationId}/update_title`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ title: newTitle.trim() }),
            // Add CSRF token if needed: headers: { 'X-CSRFToken': getCsrfToken() },
            success: function(response) {
                if (response.success) {
                    const updatedTitle = response.title || newTitle.trim(); // Use title from response if available
                    // Update the main title display
                    $('#conversation-title').text(updatedTitle);

                    // Update the title in the sidebar list
                    const targetConversationItem = $(`.conversation-item[data-id="${activeConversationId}"] .conversation-title`);
                    if (targetConversationItem.length) {
                        targetConversationItem.text(updatedTitle);
                        console.log('Sidebar title updated for conversation ID:', activeConversationId);
                    } else {
                        // If not found, refresh the conversation list (optional fallback)
                        updateConversationList(currentPage, false);
                    }
                } else {
                    alert("Error updating title: " + (response.message || "Unknown error"));
                }
            },
            error: function(xhr) {
                console.error("Error updating title:", xhr.status, xhr.responseText);
                alert("Error updating title: " + (xhr.responseJSON?.message || xhr.responseText || "Unknown error"));
            }
        });
    } else if (newTitle !== null) { // User didn't cancel, but input was empty or same
        console.log("Title not changed.");
    }
});



$('#delete-conversation-btn').click(function() {
    if (!activeConversationId) {
        alert("Cannot delete. No active conversation selected.");
        return;
    }

    const confirmation = confirm('Are you sure you want to delete this conversation? This action cannot be undone.');
    if (confirmation) {
        $.ajax({
            url: `/api/conversations/${activeConversationId}`,
            method: 'DELETE',
            // Add CSRF token if needed: headers: { 'X-CSRFToken': getCsrfToken() },
            success: function(response) {
                // If the success callback is executed, the DELETE request was successful (HTTP 200 OK)
                console.log("Conversation deleted successfully on backend. Response:", response);
                // Redirect to the home page to clear the interface and start fresh
                window.location.href = '/';
            },
            error: function(xhr) {
                console.error("Error deleting conversation:", xhr.status, xhr.responseText);
                alert("Error deleting conversation: " + (xhr.responseJSON?.message || xhr.responseText || "Unknown error"));
            }
        });
    }
});



// This function shows the conversation controls (title, rename and delete buttons) and token counts
function showConversationControls(title = "AI &infin; UI", tokens = null) {
    // Update the title
    console.log("Updating conversation controls. Title:", title);
    $("#conversation-title").text(title || "AI ∞ UI"); // Use text() to prevent potential HTML injection

    // Show title and buttons
    $("#conversation-title, #edit-title-btn, #delete-conversation-btn").show();

    // Update token data if available
    const promptTokensEl = $("#prompt-tokens");
    const completionTokensEl = $("#completion-tokens");
    const totalTokensEl = $("#total-tokens");
    const tokenDisplayContainer = $("#token-display"); // Assuming a container div

    if (tokens && tokens.total_tokens !== undefined) {
        console.log("Updating token display:", tokens);
        promptTokensEl.text(`Prompt: ${tokens.prompt_tokens ?? 'N/A'}`);
        completionTokensEl.text(`Completion: ${tokens.completion_tokens ?? 'N/A'}`);
        totalTokensEl.text(`Total: ${tokens.total_tokens ?? 'N/A'}`);
        tokenDisplayContainer.show(); // Show the token info area
    } else {
        // Hide token info if not available
        tokenDisplayContainer.hide();
        console.log("No token data available, hiding token display.");
    }
}


function loadConversation(conversationId) {
    console.log(`Fetching conversation with id: ${conversationId}...`);
    $('#chat').html('<div class="text-center p-4">Loading conversation...</div>');
    $("#conversation-title, #edit-title-btn, #delete-conversation-btn, #token-display").hide();

    fetch(`/conversations/${conversationId}`)
        .then(response => {
            console.log('Response status for conversation fetch:', response.status);
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.message || `HTTP error! Status: ${response.status}`);
                }).catch(() => {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('Parsed JSON data from conversation:', data);

            if (!data || !data.history) {
                throw new Error("Invalid conversation data received from server.");
            }

            // Update global state
            messages = data.history;
            activeConversationId = conversationId;

            if (data.model_name) {
                let loadedModelObj = AVAILABLE_MODELS.find(m => m.api === data.model_name);
                if (loadedModelObj) {
                    model = loadedModelObj.api;
                    const mainDropdownButton = $('#dropdownMenuButton');
                    mainDropdownButton.text(loadedModelObj.display);

                    // Set attributes as before
                    if (loadedModelObj.reasoning) {
                        mainDropdownButton.attr('data-reasoning', loadedModelObj.reasoning);
                    } else {
                        mainDropdownButton.removeAttr('data-reasoning');
                    }
                    if (loadedModelObj.extendedThinking) {
                        mainDropdownButton.attr('data-extended-thinking', true);
                        mainDropdownButton.attr('data-thinking-budget', loadedModelObj.thinkingBudget);
                    } else {
                        mainDropdownButton.removeAttr('data-extended-thinking');
                        mainDropdownButton.removeAttr('data-thinking-budget');
                    }
                } else {
                    model = data.model_name;
                    // Fallback: prettify the model name for display
                    const prettyName = modelNameMapping(data.model_name) || data.model_name.replace(/[-_]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                    $('#dropdownMenuButton').text(prettyName);
                    $('#dropdownMenuButton').removeAttr('data-reasoning data-extended-thinking data-thinking-budget');
                }
            }

            // Clear the chat area
            $('#chat').empty();

            // First, find and display the system message
            const systemMessage = messages.find(msg => msg.role === 'system');
            if (systemMessage) {
                let systemMessageContent = systemMessage.content;
                
                // Create and display the system message first
                const systemMessageElement = $(`
                    <div class="chat-entry system system-message" data-system-message-id="${data.system_message_id}">
                        <strong>System:</strong>${createSystemMessageButton()}
                        <span class="no-margin">${renderOpenAI(systemMessageContent)}</span><br>
                        <strong>Model:</strong> <span class="model-name">${modelNameMapping(data.model_name)}</span>
                        <strong>Temp:</strong> ${data.temperature}°
                    </div>
                `);
                $('#chat').append(systemMessageElement);

                // After system message, display any search results
                // Extract and display vector search results
                if (data.vector_search_results) {
                    displayVectorSearchResults(data.vector_search_results);
                }

                // Display generated search queries if they exist
                if (data.generated_search_queries) {
                    displayGeneratedSearchQueries(data.generated_search_queries);
                }

                // Display web search results if they exist
                if (data.web_search_results) {
                    displayWebSearchResults(data.web_search_results);
                }
            }

            // Then display the rest of the conversation
            messages.forEach((message) => {
                // Skip the system message as we've already displayed it
                if (message.role !== 'system') {
                    const messageElement = createMessageElement(message);
                    if (messageElement) {
                        $('#chat').append(messageElement);
                    }
                }
            });

            // Update conversation controls and UI
            const tokens = data.usage || {
                prompt_tokens: data.prompt_tokens_total ?? null,
                completion_tokens: data.completion_tokens_total ?? null,
                total_tokens: data.total_tokens ?? data.token_count ?? null
            };
            showConversationControls(data.title || "Untitled Conversation", tokens);

            // Apply syntax highlighting and MathJax
            Prism.highlightAllUnder(document.getElementById('chat'));
            MathJax.typesetPromise().catch(err => console.log('Error typesetting math content: ', err));

            // Scroll to the bottom
            const chatContainer = document.getElementById('chat');
            chatContainer.scrollTop = chatContainer.scrollHeight;

            // Highlight active conversation in sidebar
            $('#conversation-list .conversation-item.active').removeClass('active');
            $(`#conversation-list .conversation-item[data-id="${conversationId}"]`).addClass('active');

        })
        .catch(error => {
            console.error(`Error fetching conversation with id: ${conversationId}. Error: ${error}`);
            $('#chat').html(`<div class="text-center p-4 text-danger">Error loading conversation: ${error.message}</div>`);
            showConversationControls("Error Loading", null);
            activeConversationId = null;
        });
}




function displayVectorSearchResults(results) {
    // Check if results exist and are meaningful
    if (results && results !== "No results found" && results.trim() !== "") {
        const vectorSearchDiv = $('<div class="chat-entry context-block vector-search">') // Added context-block class
            .append('<img src="/static/images/PineconeIcon.png" alt="Pinecone Icon" class="context-icon pinecone-icon"> ') // Added context-icon class
            .append('<strong>Semantic Search:</strong> ')
            .append($('<span class="context-content">').text(results)); // Added context-content span
        $('#chat').append(vectorSearchDiv);
    } else {
        // Optionally display nothing or a subtle message if no results
        console.log("No vector search results to display.");
    }
}

function displayGeneratedSearchQueries(queries) {
    // Check if queries exist and are meaningful
    if (queries && ((Array.isArray(queries) && queries.length > 0) || (typeof queries === 'string' && queries.trim() !== ""))) {
        const generatedQueryDiv = $('<div class="chat-entry context-block generated-query">'); // Added context-block class

        generatedQueryDiv.append('<img src="/static/images/SearchIcon.png" alt="Search Icon" class="context-icon search-icon"> '); // Added context-icon class
        generatedQueryDiv.append('<strong>Generated Queries:</strong> ');

        const queryList = $('<ul class="query-list">');

        if (Array.isArray(queries)) {
            // Handle array of queries
            queries.forEach((query) => {
                if (typeof query === 'string' && query.trim() !== "") {
                    queryList.append($('<li>').text(query.trim()));
                }
            });
        } else if (typeof queries === 'string') {
            // Handle single query string
             queryList.append($('<li>').text(queries.trim()));
        }

        // Only append if the list actually contains items
        if (queryList.children().length > 0) {
            generatedQueryDiv.append(queryList);
            $('#chat').append(generatedQueryDiv);
        } else {
             console.log("Generated search queries were empty after processing.");
        }

    } else {
        console.log("No generated search queries to display.");
    }
}

function displayWebSearchResults(results) {
    // Check if results exist and are meaningful
    if (results && results !== "No web search performed" && results.trim() !== "") {
        const webSearchDiv = $('<div class="chat-entry context-block web-search">') // Added context-block class
            .append('<img src="/static/images/BraveIcon.png" alt="Brave Icon" class="context-icon brave-icon"> ') // Added context-icon class
            .append('<strong>Web Search Results:</strong> ')
            // Render the results using the same function as AI responses to handle potential markdown/links
            .append($('<div class="context-content">').html(renderOpenAI(results))); // Added context-content div
        $('#chat').append(webSearchDiv);
    } else {
        // Optionally display nothing or a subtle message if no results
        console.log("No web search results to display.");
    }
}

// --- End Conversation List & Loading ---


//Record the default height
var defaultHeight = $('#user_input').css('height');


function renderOpenAIWithFootnotes(content, enableWebSearch) {
    // This function seems specific to rendering responses *with* footnotes from web search.
    // It might be better integrated into the main renderOpenAI or createMessageElement logic.
    // For now, keeping it separate but noting potential overlap.

    console.log('renderOpenAIWithFootnotes - Content received:', content ? content.substring(0,50) + '...' : 'null');
    console.log('renderOpenAIWithFootnotes - Enable web search:', enableWebSearch);

    // Check if content is undefined or not a string
    if (typeof content !== 'string') {
        console.error('Invalid content received in renderOpenAIWithFootnotes:', content);
        return '<p class="text-danger">Error: Invalid response content.</p>';
    }

    // If web search wasn't enabled or no sources expected, use the standard renderer
    if (!enableWebSearch) {
        return renderOpenAI(content);
    }

    // Attempt to split the content into main text and sources section
    // Look for "Sources:", "Source:", potentially followed by a newline
    const sourcesRegex = /\n\s*(Sources?):\s*\n/i;
    const parts = content.split(sourcesRegex);
    let mainText = content; // Default to full content
    let sourcesContent = '';

    if (parts.length >= 3) {
        // We expect [mainText, separator, sourcesContent, ...]
        mainText = parts[0].trim();
        sourcesContent = parts.slice(2).join('').trim(); // Join remaining parts if split occurred multiple times
        console.log("Sources section identified:", sourcesContent);
    } else {
        console.warn('No clear "Sources:" section found using regex.');
        // Fallback: Maybe sources are just appended without a clear header?
        // This part is tricky and depends heavily on the exact format from the backend.
        // For now, if regex fails, we assume no structured sources.
        return renderOpenAI(content); // Render without footnote processing
    }


    if (!sourcesContent) {
        console.warn('Sources section was empty.');
        return renderOpenAI(mainText); // Render main text only
    }

    // Parse sources (assuming format like [1] http://...)
    let sourcesList = $('<ol class="sources-list">');
    let sourcesMap = {};
    const sourceLines = sourcesContent.split('\n');

    sourceLines.forEach((line) => {
        line = line.trim();
        if (!line) return; // Skip empty lines

        // Regex to capture [index] url (allowing for variations in spacing)
        let match = line.match(/^\[(\d+)\]\s*(https?:\/\/\S+.*)/);
        if (match) {
            let [, index, url] = match;
            url = url.trim(); // Trim the URL
            sourcesMap[index] = url;
            // Create list item with clickable link
            sourcesList.append(
                $('<li>').append(
                    $('<a>').attr('href', url).attr('target', '_blank').attr('rel', 'noopener noreferrer').text(url)
                )
            );
        } else {
            console.warn(`Could not parse source line format:`, line);
            // Optionally add unparsed lines to the list differently
            // sourcesList.append($('<li>').addClass('unparsed-source').text(line));
        }
    });

    // Render main text, replacing [index] with hyperlinked footnotes
    let renderedContent = mainText.replace(/\[(\d+)\]/g, (match, p1) => {
        let url = sourcesMap[p1];
        // Create a superscript link if URL exists
        return url ? `<sup class="footnote"><a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">[${p1}]</a></sup>` : match; // Keep original if no URL found
    });

    // Render the main content using the standard Markdown/code renderer
    renderedContent = renderOpenAI(renderedContent);

    // Create the sources section HTML if there are parsed sources
    let sourcesSectionHtml = '';
    if (sourcesList.children().length > 0) {
        sourcesSectionHtml = $('<div class="sources-section">')
            .append('<h4>Sources:</h4>')
            .append(sourcesList)[0].outerHTML; // Get outer HTML of the section
    }


    return renderedContent + sourcesSectionHtml; // Combine rendered content and sources section
}

$('#chat-form').on('submit', async function (e) {
    if ($('.btn-send').prop('disabled')) {
        // Prevent sending while a file is uploading
        e.preventDefault();
        return false;
    }
    console.log('Chat form submitted.');
    e.preventDefault();

    const userInput = $('#user_input').val();
    // Allow empty messages *only if* context files are attached
    if (!userInput.trim() && attachedContextFiles.size === 0) {
        console.log("Empty input and no context files attached. Submission cancelled.");
        return;
    }

    // --- Determine Model Parameters ---
    let reasoningEffort = null;
    let extendedThinking = false;
    let thinkingBudget = null;

    // Find the *active* model configuration from the main dropdown or system message setting
    // Priority: System Message > Main Dropdown (if applicable)
    const currentModelApiName = model; // Use the global 'model' variable set by displaySystemMessage

    // Check if the current model requires special parameters
    if (currentModelApiName === 'o3-mini') {
        // Need to know the reasoning effort associated with the *active system message*
        const activeMsg = systemMessages.find(msg => msg.id === activeSystemMessageId);
        reasoningEffort = activeMsg?.reasoning_effort || 'medium'; // Default if not specified
        console.log(`Using o3-mini with reasoning effort: ${reasoningEffort}`);
    } else if (currentModelApiName === 'claude-3-7-sonnet-20250219') {
        // Need to know if extended thinking is enabled for the *active system message*
        const activeMsg = systemMessages.find(msg => msg.id === activeSystemMessageId);
        // Assuming backend provides these fields for the system message
        extendedThinking = activeMsg?.extended_thinking_enabled || false;
        thinkingBudget = activeMsg?.thinking_budget || 12000; // Default budget
        if (extendedThinking) {
            console.log(`Using Claude 3.7 Sonnet with Extended Thinking. Budget: ${thinkingBudget}`);
        }
    }

    // --- WebSocket Setup ---
    maintainWebSocketConnection = true;
    initStatusWebSocket(); // Initialize connection (will assign to global statusWebSocket)

    // Wait briefly for WebSocket session ID from the server
    const startTime = Date.now();
    while (!currentSessionId && Date.now() - startTime < 3000) { // Increased timeout
        console.log("Waiting for WebSocket session ID...");
        await new Promise(resolve => setTimeout(resolve, 200));
    }

    if (!currentSessionId) {
        console.error('Failed to get WebSocket session ID after 3 seconds. Proceeding without it, but status updates might fail.');
        maintainWebSocketConnection = false; // Disable further WebSocket attempts for this message
    } else {
        console.log("WebSocket Session ID obtained:", currentSessionId);
    }

    // --- Prepare and Display User Message ---
    if (!messages) {
        messages = []; // Initialize if somehow undefined
    }

    // Immediately clear the input and reset its height
    const userInputTextarea = $('#user_input');
    userInputTextarea.val('');
    userInputTextarea.css('height', defaultHeight); // Reset height
    autosize.update(userInputTextarea); // Trigger autosize update

    // Create message content including context file contents
    let messageContentForBackend = userInput.trim();
    let displayContentForUI = messageContentForBackend; // Start with user text

    const attachedFileInfos = []; // For display purposes
    if (attachedContextFiles.size > 0) {
        // Add file contents to the content sent to the backend
        if (messageContentForBackend) {
            messageContentForBackend += '\n\n--- Attached Files Context ---\n';
        } else {
             messageContentForBackend = '--- Attached Files Context ---\n';
        }

        for (const [fileId, fileInfo] of attachedContextFiles) { // Use renamed map
            messageContentForBackend += `\n[File: ${fileInfo.name}]\n`;
            if (fileInfo.content) {
                messageContentForBackend += `${fileInfo.content}\n`;
            }
            attachedFileInfos.push(`[Attached: ${fileInfo.name}]`);
        }
        messageContentForBackend += '\n--- End Attached Files Context ---';

        // Update display content for the UI (show text + file indicators)
        displayContentForUI = (displayContentForUI ? displayContentForUI + '\n' : '') +
            attachedFileInfos.join('\n');
    }

    // Immediately show the user's message in the UI
    const userMessageElement = createMessageElement({ role: 'user', content: displayContentForUI });
    if (userMessageElement) {
        $('#chat').append(userMessageElement);
        $('#chat').scrollTop($('#chat')[0].scrollHeight); // Scroll down
    }


    // Add the full message (with file content) to the messages array for the backend
    messages.push({ "role": "user", "content": messageContentForBackend });

    // --- Show Loading Indicator ---
    document.getElementById('loading').style.display = 'block';

    // --- Prepare and Send Request ---
    try {
        // Get user's timezone from browser
        const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        console.log('User timezone detected:', userTimezone);

        // Prepare payload
        let requestPayload = {
            messages: messages,
            model: currentModelApiName, // Use the determined model
            temperature: selectedTemperature, // Use global temp set by system message
            system_message_id: activeSystemMessageId, // Send active system message ID
            // Search toggles state from the main UI checkboxes
            enable_web_search: $('#enableWebSearch').is(':checked'),
            enable_deep_search: $('#enableDeepSearch').is(':checked'),
            timezone: userTimezone,
            file_ids: Array.from(attachedContextFiles.keys()) // Send IDs of *temporary context* files
        };

        // Add model-specific parameters
        if (reasoningEffort) {
            requestPayload.reasoning_effort = reasoningEffort;
        }
        if (extendedThinking) {
            requestPayload.extended_thinking = true;
            requestPayload.thinking_budget = thinkingBudget;
        }

        // Add conversation ID if continuing an existing conversation
        if (activeConversationId !== null && activeConversationId !== undefined) {
            requestPayload.conversation_id = activeConversationId;
            console.log('Continuing existing conversation:', activeConversationId);
        } else {
            console.log('Starting new conversation - no conversation ID sent');
            console.log('activeConversationId value:', activeConversationId);
            console.log('typeof activeConversationId:', typeof activeConversationId);
        }


        console.log('Sending request to /chat with payload:', {
            ...requestPayload,
            messages: requestPayload.messages.map(m => ({ role: m.role, content: m.content.substring(0, 100) + '...' })) // Log truncated messages
        });
        console.log('Attached context file IDs being sent:', requestPayload.file_ids);


        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Debug': '1', // Keep debug header if needed by backend
                'X-Session-ID': currentSessionId || '' // Send session ID if available
            },
            body: JSON.stringify(requestPayload)
        });

        console.log('Received response from /chat endpoint. Status:', response.status);
        document.getElementById('loading').style.display = 'none'; // Hide loading indicator

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Error response details:', {
                status: response.status,
                statusText: response.statusText,
                headers: Object.fromEntries(response.headers.entries()),
                body: errorText
            });

            // Try to parse JSON error, otherwise use text
            let errorMessage = errorText;
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.error || errorJson.message || JSON.stringify(errorJson);
            } catch (e) {
                // Keep errorText if not JSON
            }
             throw new Error(`Server error (${response.status}): ${errorMessage}`);
        }

        const data = await response.json();
        console.log("Parsed successful server response:", data); // Log less verbosely on success

        // --- Process Successful Response ---

        // Clear temporary context files *after* successful send
        attachedContextFiles.clear(); // Use renamed map
        updateContextFilesPreview(); // Update UI pills using renamed function

        // Add assistant's response to messages array
        if (data.response) {
             messages.push({ "role": "assistant", "content": data.response });
        } else {
            console.warn("No 'response' field found in successful server data.");
        }


        // Update conversation list (might highlight the updated conversation)
        updateConversationList(); // Refresh the list

        // Update URL if it's a new conversation
        if (data.conversation_id && activeConversationId !== data.conversation_id) {
            const previousConversationId = activeConversationId;
            activeConversationId = data.conversation_id;
            window.history.pushState({ conversationId: activeConversationId }, '', `/c/${activeConversationId}`);
            console.log("Conversation ID updated from", previousConversationId, "to", activeConversationId);
            console.log("URL updated to:", `/c/${activeConversationId}`);
        } else if (data.conversation_id) {
            console.log("Received same conversation ID:", data.conversation_id, "- not updating URL");
        } else {
            console.log("No conversation ID received in response");
        }

        // Update conversation title and token counts
        const tokens = data.usage || { total_tokens: data.total_tokens }; // Use new usage field or fallback
        showConversationControls(data.conversation_title || "Untitled Conversation", tokens);

        // Display assistant's message (and potentially context)
        // Clear previous status updates before showing final response/context
        clearStatusUpdates();

        // Display context information if provided
        displayVectorSearchResults(data.vector_search_results);
        displayGeneratedSearchQueries(data.generated_search_queries);
        displayWebSearchResults(data.web_search_results);

        // Display the main assistant response
        if (data.response) {
            const assistantMessageElement = createMessageElement({ role: 'assistant', content: data.response });

            if (assistantMessageElement) {
                $('#chat').append(assistantMessageElement);
                // Apply syntax highlighting and MathJax
                renderMathInElement(assistantMessageElement[0]);
                Prism.highlightAllUnder(assistantMessageElement[0]);
            }
        }

        // Scroll to bottom
        $('#chat').scrollTop($('#chat')[0].scrollHeight);


    } catch (error) {
        console.error('Error during chat form submission or processing:', error);
        document.getElementById('loading').style.display = 'none'; // Hide loading indicator
        clearStatusUpdates(); // Clear any lingering status updates

        // Display error message to the user in the chat
        const errorMessageDiv = $('<div class="chat-entry system error-message">')
            .append('<i class="fas fa-exclamation-triangle"></i> ')
            .append(`Error: ${error.message || "An unexpected error occurred."}`);
        $('#chat').append(errorMessageDiv);
        $('#chat').scrollTop($('#chat')[0].scrollHeight);

        // Optionally revert the user message addition to the 'messages' array
        if (messages.length > 0 && messages[messages.length - 1].role === 'user') {
             // Decide if you want to keep the user message in the array despite the error
             // messages.pop();
        }

    } finally {
         // Ensure WebSocket connection is closed if no longer needed
         // cleanupWebSocketSession(); // Cleanup happens in clearStatusUpdates now
    }
});


// This function checks if there's an active conversation ID stored (e.g., from URL path)
// and loads it. It doesn't rely on a backend session check.
function checkActiveConversation() {
    // Get conversation ID from the URL path (e.g., /c/123)
    const pathParts = window.location.pathname.split('/');
    const conversationIdFromUrl = (pathParts.length >= 3 && pathParts[1] === 'c') ? pathParts[2] : null;

    console.log("Checking for active conversation in URL:", conversationIdFromUrl);

    if (conversationIdFromUrl) {
        // If there's an ID in the URL, load that conversation
        loadConversation(conversationIdFromUrl);
        // Conversation controls will be shown by loadConversation on success
    } else {
        // No conversation ID in URL - ensure it's the base state
        activeConversationId = null;
        messages = []; // Clear message history
        // Ensure the default system message is displayed if chat is empty
        if ($('#chat').children().length === 0) {
             const defaultMsg = systemMessages.find(msg => msg.name === "Default System Message") || systemMessages[0];
             if (defaultMsg) {
                 displaySystemMessage(defaultMsg);
             }
        }
        // Hide conversation-specific controls
        $('#conversation-title').text("AI ∞ UI"); // Reset title
        $('#edit-title-btn, #delete-conversation-btn, #token-display').hide();
        console.log("No active conversation in URL, showing default state.");
    }
}


function resetTokenDisplay() {
    $("#prompt-tokens").text("Prompt Tokens: ");
    $("#completion-tokens").text("Completion Tokens: ");
    $("#total-tokens").text("Total Tokens:");
}

$(document).ready(function() {  // Document Ready (initialization)
    window.addEventListener('popstate', function(event) {
        const pathParts = window.location.pathname.split('/');
        const conversationIdFromUrl = (pathParts.length >= 3 && pathParts[1] === 'c') ? pathParts[2] : null;

        if (conversationIdFromUrl) {
            loadConversation(conversationIdFromUrl);
        } else {
            // Reset to new chat state
            $('#new-chat-btn').click();
        }
    });
    console.log("Document ready."); // Debug

    // Initialize autosize for the textarea
    const userInput = $('#user_input');
    autosize(userInput);
    defaultHeight = userInput.css('height'); // Store initial height after autosize init

    // Set default title (will be overridden if conversation loads)
    $("#conversation-title").text("AI ∞ UI");
    $("#conversation-title, #edit-title-btn, #delete-conversation-btn, #token-display").hide(); // Hide controls initially

    // Initialize model buttons
    const mainDropdownButton = $('#dropdownMenuButton');
    const currentModelBtn = $('.current-model-btn');

    // Initialize both model dropdowns
    initializeModelDropdown();
    populateModelDropdownInModal();

    // Ensure the current-model-btn is visible by default
    currentModelBtn.css('display', 'inline-block');

    // Initialize the modal with Bootstrap 4
    const $modal = $('#systemMessageModal');
    $modal.modal({
        show: false,
        backdrop: 'static',
        keyboard: true
    });

    // Bind modal events
    $modal
        .on('show.bs.modal', function(e) {
            console.log('Modal show event triggered');
        })
        .on('shown.bs.modal', function(e) {
            console.log('Modal shown event triggered');
            updateVectorFileMoreIndicator();

            // Focus the first relevant input field
            const visibleGroup = $('.modal-content-group:not(.hidden)').first();
            if (visibleGroup.length) {
                const firstInput = visibleGroup.find('input:not([type=hidden]), textarea, select, button:not(.close)').first();
                if (firstInput.length) {
                    firstInput.focus();
                }
            }
        })
        .on('hide.bs.modal', function(e) {
            console.log('Modal hide event triggered');
        })
        .on('hidden.bs.modal', function(e) {
            console.log('Modal hidden event triggered');
            // Clean up any temporary states
            $(this).find('form').trigger('reset');
            // Remove any lingering backdrops
            $('.modal-backdrop').remove();
            // Remove modal-open class from body
            $('body').removeClass('modal-open');
        });

    // Add global modal cleanup function
    window.cleanupModal = function() {
        const $body = $('body');
        
        // Remove modal-open class from body
        $body.removeClass('modal-open');
        
        // Remove any lingering backdrop
        $('.modal-backdrop').remove();
        
        // Reset modal state
        $modal
            .removeClass('show')
            .removeAttr('aria-modal')
            .attr('aria-hidden', 'true')
            .css('display', 'none');
    };

    // Fetch system messages first, then initialize dependent components
    fetchAndProcessSystemMessages().then(() => {
        console.log("System messages processed.");

        // Populate the system message modal (dropdowns, etc.)
        populateSystemMessageModal(); // Populates the dropdown list
        populateModelDropdownInModal(); // Populates the model choices within the modal

        // Check URL for an active conversation and load if present
        checkActiveConversation(); // Loads conversation or sets default state

        // Initialize the conversation list sidebar
        updateConversationList(1, false);

        // Initialize the context file attachment functionality (for chat input)
        initializeContextFileAttachment(); // Use renamed function

        // Initialize temperature display in modal (based on initially loaded system message)
        updateTemperatureDisplay();

    }).catch(error => {
        console.error("Initialization failed due to error fetching system messages:", error);
        // Display a prominent error to the user
        $('#chat').prepend('<div class="alert alert-danger">Failed to initialize application settings. Please try refreshing the page.</div>');
    });

    // Add click event handler for the "+ New" button
    $('#new-chat-btn').click(function() {
        console.log("New chat button clicked - resetting all state");

        // IMPORTANT: Clear conversation ID FIRST
        activeConversationId = null;

        // Clear the messages array BEFORE clearing chat
        messages = [];

        // Clear the chat area
        $('#chat').empty();

        // Reset the token display
        resetTokenDisplay();

        // Reset URL to root without page reload
        window.history.pushState({}, '', '/');

        // Clear the conversation title and hide controls
        $('#conversation-title').text("AI ∞ UI");
        $('#edit-title-btn, #delete-conversation-btn, #token-display').hide();

        // Display the default system message (this will add to messages array)
        const defaultMsg = systemMessages.find(msg => msg.name === "Default System Message") || systemMessages[0];
        if (defaultMsg) {
            displaySystemMessage(defaultMsg);
        }

        // Clear temporary context file attachments
        attachedContextFiles.clear();
        updateContextFilesPreview();

        // Fix the upload progress reset with null checks
        try {
            resetUploadProgress();
        } catch (error) {
            console.warn("Error resetting upload progress:", error);
        }

        // Clear the user input area
        const userInputTextarea = $('#user_input');
        userInputTextarea.val('');
        userInputTextarea.css('height', defaultHeight);
        autosize.update(userInputTextarea);

        // Deselect any active conversation in the sidebar
        $('#conversation-list .conversation-item.active').removeClass('active');

        // Force a small delay to ensure state is completely reset
        setTimeout(() => {
            console.log("New chat state verified - activeConversationId:", activeConversationId, "messages length:", messages.length);
        }, 100);

        console.log("New chat initialized - activeConversationId:", activeConversationId, "messages length:", messages.length);
    });

    // Handler for system settings dropdown items (triggering the modal)
    $('.settings-dropdown .dropdown-item').on('click', function(event) {
        event.preventDefault();
        const targetGroup = $(this).data('target');
        console.log("Settings dropdown item clicked, target group:", targetGroup);

        if (targetGroup) {
            // Pass the target group to the modal before showing it
            $('#systemMessageModal').data('targetGroup', targetGroup);
            // Use Bootstrap 4's jQuery modal show
            $('#systemMessageModal').modal('show');
        } else {
            console.warn("Settings dropdown item clicked, but no data-target specified.");
        }
    });

    // Needed for "Send" to respond to the 'enter' key.
    $('#user_input').keydown(function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); // Prevent newline on Enter
            $('#chat-form').submit(); // Submit form
        }
    });

    // Add listener for the semantic file upload button in the modal
    const addSemanticFileBtn = document.getElementById('add-semantic-file-btn');
    if (addSemanticFileBtn) {
        addSemanticFileBtn.addEventListener('click', handleAddVectorFileButtonClick);
    } else {
        console.warn("Button with ID 'add-semantic-file-btn' not found for vector file upload.");
    }
});


    // ... other initialization code ...







    // ... other initialization code that should run when the page is fully loaded ...
