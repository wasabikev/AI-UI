let messages = []; // An array that stores the converstation messages


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
let tempIntelligentSearchState = false; // This will store the temporary intelligent search state

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

        // Add event listeners for the web search toggles
        const enableWebSearchToggle = document.getElementById('enableWebSearch');
        const enableIntelligentSearchToggle = document.getElementById('enableIntelligentSearch');

        enableWebSearchToggle.addEventListener('change', function() {
            tempWebSearchState = this.checked;
            if (!this.checked) {
                enableIntelligentSearchToggle.checked = false;
                tempIntelligentSearchState = false;
                enableIntelligentSearchToggle.disabled = true;
            } else {
                enableIntelligentSearchToggle.disabled = false;
            }
            updateSearchSettings();
        });

        enableIntelligentSearchToggle.addEventListener('change', function() {
            tempIntelligentSearchState = this.checked;
            if (this.checked) {
                enableWebSearchToggle.checked = true;
                tempWebSearchState = true;
            }
            updateSearchSettings();
        });

        
    }).catch(error => {
        console.error('Error during system message fetch and display:', error);
    });
});


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
    
    // Remove timestamp logic completely
    
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

// Simplified connection check - only run when needed
function checkStatusConnection() {
    if (maintainWebSocketConnection && (!statusWebSocket || statusWebSocket.readyState === WebSocket.CLOSED)) {
        console.log('Status connection lost or not established, reconnecting...');
        wsReconnectAttempts = 0;
        wsReconnectDelay = INITIAL_RECONNECT_DELAY;
        //initStatusWebSocket();
    }
}


// Add reconnection attempt counter
let reconnectAttempts = 0;


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

        return newWs;
    } catch (error) {
        console.error('Error creating WebSocket:', error);
        console.log('Error details:', {
            message: error.message,
            stack: error.stack,
            wsUrl: wsUrl
        });
        return null;
    }
}

function handleWebSocketMessage(event) {
    try {
        const data = JSON.parse(event.data);
        console.log('WebSocket message received:', data);

        if (data.type === 'status') {
            if (data.session_id) {  // Initial connection message
                console.log('WebSocket connection confirmed, session ID:', data.session_id);
                currentSessionId = data.session_id;
                return;
            } else if (data.message !== "WebSocket connection established") {  // Skip the initial connection message
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
        statusWebSocket = null; // Ensure cleanup
        return;
    }

    wsReconnectAttempts++;
    console.log(`Attempting to reconnect (${wsReconnectAttempts}/${MAX_WS_RECONNECT_ATTEMPTS})...`);
    
    // Use setTimeout to ensure we're out of the event handler context
    setTimeout(() => {
        if (maintainWebSocketConnection) {
            initStatusWebSocket();
        }
    }, wsReconnectDelay);
    
    // Exponential backoff with max delay of 10 seconds
    wsReconnectDelay = Math.min(wsReconnectDelay * 2, 10000);
}

// Helper function to safely check WebSocket state
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
            //initStatusWebSocket();
        }
    })
    .catch(error => {
        console.error('Session health check failed:', error);
    });
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    clearStatusUpdates();
});

// End WebSocket section

function updateSearchSettings() {
    // Only send an update if the temporary state differs from the current system message state
    if (tempWebSearchState !== currentSystemMessage.enable_web_search || tempIntelligentSearchState !== false) {
        fetch(`/api/system-messages/${activeSystemMessageId}/toggle-search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                enableWebSearch: tempWebSearchState,
                enableIntelligentSearch: tempIntelligentSearchState
            }),
        })
        .then(response => response.json())
        .then(data => {
            console.log('Search settings updated:', data);
            // Update the current system message with the new settings
            currentSystemMessage.enable_web_search = data.enableWebSearch;
            // Note: We're not storing enableIntelligentSearch in the model
        })
        .catch((error) => {
            console.error('Error updating search settings:', error);
            // Revert the toggles to their previous state on error
            initializeSearchToggles(currentSystemMessage);
        });
    }
}

function initializeSearchToggles(systemMessage) {
    const enableWebSearchToggle = document.getElementById('enableWebSearch');
    const enableIntelligentSearchToggle = document.getElementById('enableIntelligentSearch');

    // Set the web search toggle based on the saved setting
    enableWebSearchToggle.checked = systemMessage.enable_web_search;
    tempWebSearchState = systemMessage.enable_web_search;

    // Always start with intelligent search disabled
    enableIntelligentSearchToggle.checked = false;
    tempIntelligentSearchState = false;

    // Enable or disable the intelligent search toggle based on web search setting
    enableIntelligentSearchToggle.disabled = !systemMessage.enable_web_search;
}

document.getElementById('enableWebSearch').addEventListener('change', function() {
    tempWebSearchState = this.checked;
    console.log('Temporary web search state updated:', tempWebSearchState);
});



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

// Functions related to the file upload feature

// Add in CSRF protection for the AJAX request. This function will be used to get the CSRF token from the meta tag. (Addtional updates needed)
function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
}

function removeFile(fileId) {
    if (!confirm('Are you sure you want to remove this file?')) {
        return;
    }
    const fileListError = document.getElementById('fileListError');
    const fileUploadStatus = document.getElementById('fileUploadStatus');

    fetch(`/remove_file/${fileId}`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json'
        },
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            fileUploadStatus.textContent = 'File removed successfully';
            fileUploadStatus.style.display = 'inline';
            setTimeout(() => {
                fileUploadStatus.style.display = 'none';
            }, 3000);
            fetchFileList(activeSystemMessageId);
        } else {
            throw new Error(data.error || 'Failed to remove file');
        }
    })
    .catch(error => {
        console.error('Error removing file:', error);
        fileListError.textContent = `Failed to remove file: ${error.message}`;
        fileListError.style.display = 'block';
        setTimeout(() => {
            fileListError.style.display = 'none';
        }, 5000);
    });
}

function uploadFile() {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.txt,.pdf,.docx'; // Add or modify accepted file types as needed
    
    const fileUploadStatus = document.getElementById('fileUploadStatus');
    const fileListError = document.getElementById('fileListError');
    
    fileInput.onchange = function(e) {
        const file = e.target.files[0];
        if (file) {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('system_message_id', activeSystemMessageId);

            // Show "File upload in progress" message
            fileUploadStatus.textContent = 'File upload in progress...';
            fileUploadStatus.style.display = 'inline';
            fileListError.style.display = 'none'; // Hide any previous error messages

            fetch('/upload_file', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => Promise.reject(err));
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Show "File upload complete" message
                    fileUploadStatus.textContent = 'File upload complete';
                    setTimeout(() => {
                        fileUploadStatus.style.display = 'none';
                    }, 3000); // Hide the message after 3 seconds
                    fetchFileList(activeSystemMessageId);
                    updateMoreFilesIndicator();
                } else {
                    throw new Error(data.error || 'Unknown error occurred');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                fileUploadStatus.textContent = 'File upload failed';
                fileUploadStatus.style.display = 'inline';
                fileListError.textContent = 'Failed to upload file: ' + (error.error || error.message);
                fileListError.style.display = 'block';
                
                setTimeout(() => {
                    fileUploadStatus.style.display = 'none';
                    fileListError.style.display = 'none';
                }, 5000); // Hide both messages after 5 seconds
            });
        }
    };

    fileInput.click();
}

function initializeAndUpdateFileList(systemMessageId) {
    console.log('Initializing and updating file list for system message ID:', systemMessageId);
    
    // Clear existing file list
    const fileList = document.getElementById('fileList');
    if (fileList) {
        fileList.innerHTML = '';
    }

    // Fetch and display the file list
    fetchFileList(systemMessageId);

    // Update the more files indicator
    updateMoreFilesIndicator();
}


function fetchFileList(systemMessageId) {
    const fileList = document.getElementById('fileList');
    const noFilesMessage = document.getElementById('noFilesMessage');
    const fileListError = document.getElementById('fileListError');
    const fileListContainer = document.getElementById('fileListContainer');
    if (!fileListContainer) {
        console.error('File list container not found');
        return;
    }
    const moreFilesIndicator = document.getElementById('moreFilesIndicator');

    // Reset all displays
    fileList.innerHTML = '';
    fileList.style.display = 'none';
    noFilesMessage.style.display = 'none';
    fileListError.style.display = 'none';
    moreFilesIndicator.style.display = 'none';

    fetch(`/get_files/${systemMessageId}`)
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(files => {
        console.log('Received files:', files); // Debug log
        if (files && files.length > 0) {
            files.forEach(file => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item d-flex justify-content-between align-items-center';
                fileItem.innerHTML = `
                    <span class="file-name">${file.name}</span>
                    <div class="file-actions">
                        <button class="btn btn-sm btn-primary" onclick="viewOriginalFile('${file.id}')">View Original</button>
                        <button class="btn btn-sm btn-info" onclick="viewProcessedText('${file.id}')">View Processed</button>
                        <button class="btn btn-sm btn-danger" onclick="removeFile('${file.id}')">Remove</button>
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
        updateMoreFilesIndicator();
    })
    .catch(error => {
        console.error('Error fetching file list:', error);
        fileListError.textContent = `Error fetching file list: ${error.message}`;
        fileListError.style.display = 'block';
        updateMoreFilesIndicator();
    });

    // Add scroll event listener to show/hide indicator based on scroll position
    fileListContainer.addEventListener('scroll', () => {
        if (fileListContainer.scrollHeight > fileListContainer.clientHeight) {
            if (fileListContainer.scrollTop + fileListContainer.clientHeight >= fileListContainer.scrollHeight - 20) {
                moreFilesIndicator.style.display = 'none';
            } else {
                moreFilesIndicator.style.display = 'block';
            }
        }
    });
}

function viewOriginalFile(fileId) {
    const url = `/view_original_file/${fileId}`;
    window.open(url, '_blank');
}

function viewProcessedText(fileId) {
    fetch(`/view_processed_text/${fileId}`)
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
            // Create a new window or tab with the processed text
            const newWindow = window.open('', '_blank');
            newWindow.document.write(`<pre>${text}</pre>`);
            newWindow.document.close();
        })
        .catch(error => {
            console.error('Error viewing processed text:', error);
            alert(error.message || 'Error viewing processed text. Please try again.');
        });
}


function updateMoreFilesIndicator() {
    const fileListContainer = document.getElementById('fileListContainer');
    const moreFilesIndicator = document.getElementById('moreFilesIndicator');
    
    if (fileListContainer && moreFilesIndicator) {
        if (fileListContainer.scrollHeight > fileListContainer.clientHeight) {
            if (fileListContainer.scrollTop + fileListContainer.clientHeight >= fileListContainer.scrollHeight - 20) {
                moreFilesIndicator.style.display = 'none';
            } else {
                moreFilesIndicator.style.display = 'block';
            }
        } else {
            moreFilesIndicator.style.display = 'none';
        }
    }
}

function handleAddFileButtonClick() {
    // Open the modal and switch to the filesGroup
    openModalAndShowGroup('filesGroup');

    // Additional logic can be added here if there are any specific actions needed
    // For example, clearing any previously selected files or resetting file input fields
    resetFileInput();
}

function resetFileInput() {
    // Reset the file input field
    var fileInput = document.getElementById('fileInput');
    fileInput.value = "";  // Clear any previously selected file
}



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
}

function updateWebsiteControls() {
    const addWebsiteButton = document.getElementById('submitWebsiteButton');
    const removeWebsiteButton = document.getElementById('removeWebsiteButton');
    const indexWebsiteButton = document.getElementById('indexWebsiteButton');

    if (activeWebsiteId) {
        // Hide the Add Website button and show the Remove and Index buttons
        addWebsiteButton.style.display = 'none';
        removeWebsiteButton.style.display = 'inline-block';
        indexWebsiteButton.style.display = 'visible';
    } else {
        // Show the Add Website button and hide the Remove and Index buttons
        addWebsiteButton.style.display = 'inline-block';
        removeWebsiteButton.style.display = 'none';
        indexWebsiteButton.style.display = 'hidden';
    }
}

document.getElementById('submitWebsiteButton').addEventListener('click', function() {
    const websiteURL = document.getElementById('websiteURL').value;

    if (!websiteURL) {
        alert('Please enter a valid URL.');
        return;
    }

    if (!activeSystemMessageId) {
        alert('System message ID is required.');
        return;
    }

    addWebsite(websiteURL, activeSystemMessageId).then(response => {
        if (response.success) {
            activeWebsiteId = response.website.id; // Set the active website ID
            updateWebsiteControls(); // Update UI controls
            // Repopulate the input field with the name of the newly added website
            document.getElementById('websiteURL').value = response.website.url;
            alert('Website added successfully.');
            // Reload the websites for the current system message to update the sidebar
            loadWebsitesForSystemMessage(activeSystemMessageId);
            // Display the details of the newly added website
            displayWebsiteDetails(response.website);
        } else {
            alert('Error adding website: ' + response.message);
        }
    }).catch(error => {
        console.error('Error:', error);
        alert('An error occurred while adding the website.');
    });
});


function addWebsite(url, systemMessageId) {
    console.log("Adding website with URL:", url, "and system message ID:", systemMessageId);
    return fetch('/add-website', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ url: url, system_message_id: systemMessageId })
    })
    .then(response => response.json());
}



function loadWebsitesForSystemMessage(systemMessageId) {
    $.ajax({
        url: `/get-websites/${systemMessageId}`,
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            const sidebar = document.getElementById('modal-sidebar');
            if (!sidebar) {
                console.error("Sidebar element not found in the DOM.");
                return;
            }

            sidebar.innerHTML = '';

            const websites = Array.isArray(response) ? response : response.websites;

            if (websites && websites.length > 0) {
                websites.forEach(website => {
                    const div = document.createElement('div');
                    div.className = 'website-item';
                    
                    const textSpan = document.createElement('span');
                    textSpan.textContent = website.url;
                    textSpan.title = website.url; // Add the title attribute with the full URL
                    div.appendChild(textSpan);

                    const settingsButton = document.createElement('button');
                    settingsButton.className = 'websiteSettings-button';
                    settingsButton.innerHTML = '<i class="fas fa-wrench"></i>';
                    settingsButton.addEventListener('click', function() {
                        openModalAndShowGroup('websitesGroup');
                        document.getElementById('websiteURL').value = website.url; // Display the website URL in the input field
                        activeWebsiteId = website.id; // Set the active website ID
                        updateWebsiteControls(); // Update UI controls
                        displayWebsiteDetails(website); // Display website details
                    });
                    div.appendChild(settingsButton);

                    sidebar.appendChild(div);
                });
            } else {
                sidebar.textContent = 'No websites for this system message.';
                activeWebsiteId = null; // Clear the active website ID
                clearWebsiteDetails(); // Clear the website details
                updateWebsiteControls(); // Update UI controls
            }
        },
        error: function(xhr) {
            console.error('Failed to fetch websites:', xhr.responseText);
            if (sidebar) {
                sidebar.textContent = 'Failed to load websites.';
            }
        }
    });
}



function displayWebsiteDetails(website) {
    document.getElementById('indexingStatus').textContent = website.indexing_status || 'N/A';
    document.getElementById('indexedAt').textContent = website.indexed_at || 'N/A';
    document.getElementById('lastError').textContent = website.last_error || 'N/A';
    document.getElementById('indexingFrequency').textContent = website.indexing_frequency || 'N/A';
    document.getElementById('createdAt').textContent = website.created_at ? formatDate(website.created_at) : 'N/A';
    document.getElementById('updatedAt').textContent = website.updated_at ? formatDate(website.updated_at) : 'N/A';

    // Show the Index Website button
    document.getElementById('indexWebsiteButton').style.visibility = 'visible';
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString(); // Customize the format as needed
}


function clearWebsiteDetails() {
    document.getElementById('indexingStatus').textContent = 'N/A';
    document.getElementById('indexingFrequency').textContent = 'N/A';
    document.getElementById('websiteURL').value = '';

    // Hide the Index Website button
    document.getElementById('indexWebsiteButton').style.visibility = 'hidden';
}


function removeWebsite(websiteId) {
    if (!confirm('Are you sure you want to remove this website?')) {
        return;
    }

    // AJAX call to the server to remove the website
    $.ajax({
        url: '/remove-website/' + websiteId,
        type: 'DELETE',
        success: function(response) {
            alert('Website removed successfully');
            activeWebsiteId = null; // Clear the active website ID
            clearWebsiteDetails(); // Clear the website details
            updateWebsiteControls(); // Update UI controls
            loadWebsitesForSystemMessage(activeSystemMessageId); // Refresh the list of websites
        },
        error: function(xhr) {
            alert('Error removing website: ' + xhr.responseText);
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
    // AJAX call to the server to re-index the website
    $.ajax({
        url: '/reindex-website/' + websiteId,
        type: 'POST',
        success: function(response) {
            alert('Website re-indexing initiated');
        },
        error: function(xhr) {
            alert('Error re-indexing website: ' + xhr.responseText);
        }
    });
}

function loadWebsites() {
    $.ajax({
        url: '/get-websites',
        type: 'GET',
        success: function(response) {
            // Code to display the websites in the UI
            // Example: update a table or list in your HTML
        },
        error: function(xhr) {
            alert('Error fetching websites: ' + xhr.responseText);
        }
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

            // Set the active system message ID globally
            activeSystemMessageId = message.id;
            // Load websites for the newly selected system message
            loadWebsitesForSystemMessage(activeSystemMessageId);
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

function updateTemperatureSelectionInModal(temperature) {
    console.log("Updating temperature in modal to:", temperature);
    selectedTemperature = temperature;
    document.querySelectorAll('input[name="temperatureOptions"]').forEach(radio => {
        radio.checked = parseFloat(radio.value) === parseFloat(temperature);
    });
    updateTemperatureDisplay(); // Update the display to reflect the change
}

function populateSystemMessageModal() {
    let dropdownMenu = document.querySelector('#systemMessageModal .dropdown-menu');
    let dropdownButton = document.getElementById('systemMessageDropdown');

    if (!dropdownMenu || !dropdownButton) {
        console.error("Required elements not found in the DOM.");
        return;
    }

    dropdownMenu.innerHTML = '';

    console.log('Populating system message modal...');
    systemMessages.forEach((message) => {
        let dropdownItem = document.createElement('button');
        dropdownItem.className = 'dropdown-item';
        dropdownItem.textContent = message.name;
        dropdownItem.onclick = function() {
            dropdownButton.textContent = this.textContent;
            document.getElementById('systemMessageName').value = message.name || '';
            document.getElementById('systemMessageDescription').value = message.description || '';
            document.getElementById('systemMessageContent').value = message.content || '';
            document.getElementById('systemMessageModal').dataset.messageId = message.id;
            document.getElementById('enableWebSearch').checked = message.enable_web_search;

            currentSystemMessageDescription = message.description;
            initialTemperature = message.temperature;
            selectedTemperature = message.temperature;
            model = message.model_name;
            activeSystemMessageId = message.id;

            updateTemperatureSelectionInModal(message.temperature);
            updateModelDropdownInModal(message.model_name);
            loadWebsitesForSystemMessage(message.id);
            fetchFileList(message.id);
        };
        dropdownMenu.appendChild(dropdownItem);
    });

    if (!activeSystemMessageId && systemMessages.length > 0) {
        const defaultSystemMessage = systemMessages.find(msg => msg.name === "Default System Message") || systemMessages[0];
        activeSystemMessageId = defaultSystemMessage.id;
        loadWebsitesForSystemMessage(defaultSystemMessage.id);
        dropdownButton.textContent = defaultSystemMessage.name;
        document.getElementById('systemMessageName').value = defaultSystemMessage.name;
        document.getElementById('systemMessageDescription').value = defaultSystemMessage.description || '';
        document.getElementById('systemMessageContent').value = defaultSystemMessage.content || '';
        document.getElementById('systemMessageModal').dataset.messageId = defaultSystemMessage.id;
        document.getElementById('enableWebSearch').checked = defaultSystemMessage.enable_web_search;
        initialTemperature = defaultSystemMessage.temperature;
        updateTemperatureSelectionInModal(initialTemperature);
        updateModelDropdownInModal(defaultSystemMessage.model_name);
        model = defaultSystemMessage.model_name;
        
        fetchFileList(defaultSystemMessage.id);
    }

    // Reset the isSaved flag
    isSaved = false;
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
    const enableWebSearch = document.getElementById('enableWebSearch').checked; // Get the actual state of the checkbox

    const messageId = document.getElementById('systemMessageModal').dataset.messageId;

    // Check if a system message with the same name already exists when creating a new message
    if (!messageId) {
        const existingMessage = systemMessages.find(message => message.name.toLowerCase() === messageName.toLowerCase());
        if (existingMessage) {
            showModalFlashMessage("Please select a different name. That name is already in use.", "warning");
            return;
        }
    }

    const messageData = {
        name: messageName,
        description: messageDescription,
        content: messageContent,
        model_name: modelName,
        temperature: temperature,
        enable_web_search: enableWebSearch
    };

    const url = messageId ? `/system-messages/${messageId}` : '/system-messages';
    const method = messageId ? 'PUT' : 'POST';

    $.ajax({
        url: url,
        method: method,
        contentType: 'application/json',
        data: JSON.stringify(messageData),
        success: function(response) {
            console.log('System message saved successfully:', response);

            // Set the isSaved flag to true
            isSaved = true;

            // Update the global model variable
            model = modelName;
            console.log('Global model variable updated to:', model);

            // Update the selected temperature and the temperature display
            selectedTemperature = temperature;
            console.log("Temperature after AJAX response:", selectedTemperature);
            updateTemperatureDisplay();

            // Update the model dropdown on the main page
            $('#dropdownMenuButton').text(modelNameMapping(modelName));

            // Close the modal
            $('#systemMessageModal').modal('hide');

            // Fetch and process system messages, then update the UI
            fetchAndProcessSystemMessages().then(() => {
                // Find the updated or new message in the refreshed systemMessages array
                const updatedMessage = systemMessages.find(msg => msg.id === (response.id || messageId));
                if (updatedMessage) {
                    // Set the activeSystemMessageId
                    activeSystemMessageId = updatedMessage.id;
                    // Display the updated system message
                    displaySystemMessage(updatedMessage);
                } else {
                    console.error('Could not find the updated system message in the array');
                }
            });
        },
        error: function(error) {
            console.error('Error saving system message:', error);
            showModalFlashMessage("Error saving system message", "danger");
        }
    });
});

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
    <div class="chat-entry system system-message" data-system-message-id="${systemMessage.id}">
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

    // Set the activeSystemMessageId
    activeSystemMessageId = systemMessage.id;
    console.log('Active System Message ID set to:', activeSystemMessageId);
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

// New system message button actions
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

    // Set the temperature to 0.7
    document.querySelector('input[name="temperatureOptions"][value="0.7"]').checked = true;
    updateTemperatureDisplay();

    // Clear the sidebar
    const sidebar = document.getElementById('modal-sidebar');
    if (sidebar) {
        sidebar.innerHTML = ''; // Clear existing content
    }

    // Clear active website ID and website details
    activeWebsiteId = null;
    clearWebsiteDetails();
    updateWebsiteControls();

    // Switch to the systemMessageContentGroup
    switchToSystemMessageContentGroup();
});

function switchToSystemMessageContentGroup() {
    // Hide all content groups
    const contentGroups = document.querySelectorAll('.modal-content-group');
    contentGroups.forEach(group => group.classList.add('hidden'));

    // Show the systemMessageContentGroup
    const systemMessageContentGroup = document.getElementById('systemMessageContentGroup');
    if (systemMessageContentGroup) {
        systemMessageContentGroup.classList.remove('hidden');
    }
}

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
function modelNameMapping(modelName, reasoningEffort) {
    console.log("Input model name:", modelName, "Reasoning effort:", reasoningEffort);
    let mappedName;
    switch(modelName) {
        case "gpt-3.5-turbo": mappedName = "GPT-3.5"; break;
        case "gpt-4-turbo-2024-04-09": mappedName = "GPT-4 (Turbo)"; break;
        case "gpt-4o-2024-08-06": mappedName = "GPT-4o"; break;
        case "o3-mini": 
            switch(reasoningEffort) {
                case "low": mappedName = "o3-mini (Fast)"; break;
                case "medium": mappedName = "o3-mini (Balanced)"; break;
                case "high": mappedName = "o3-mini (Deep)"; break;
                default: mappedName = "o3-mini"; break;
            }
            break;
        case "claude-3-opus-20240229": mappedName = "Claude 3 (Opus)"; break;
        case "claude-3-5-sonnet-20241022": mappedName = "Claude 3.5 (Sonnet)"; break;
        case "gemini-pro": mappedName = "Gemini Pro"; break;
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
    const models = ["gpt-3.5-turbo","gpt-4-turbo-2024-04-09","gpt-4o-2024-08-06","claude-3-opus-20240229","claude-3-5-sonnet-20241022","gemini-pro"];
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

    // Fetch the latest system messages data
    fetchAndProcessSystemMessages().then(() => {
        // Setup the dropdown for selecting the model.
        populateModelDropdownInModal();

        let activeSystemMessage;
        if (activeSystemMessageId) {
            activeSystemMessage = systemMessages.find(msg => msg.id === activeSystemMessageId);
        } else if (systemMessages.length > 0) {
            // If no active message, use the first one (or the default one if it exists)
            activeSystemMessage = systemMessages.find(msg => msg.name === "Default System Message") || systemMessages[0];
            activeSystemMessageId = activeSystemMessage.id;
        }

        if (activeSystemMessage) {
            // Populate all fields with the active system message data
            document.getElementById('systemMessageName').value = activeSystemMessage.name;
            document.getElementById('systemMessageDescription').value = activeSystemMessage.description;
            document.getElementById('systemMessageContent').value = activeSystemMessage.content;
            document.getElementById('enableWebSearch').checked = activeSystemMessage.enable_web_search;
            updateModelDropdownInModal(activeSystemMessage.model_name);
            updateTemperatureSelectionInModal(activeSystemMessage.temperature);

            console.log("System message data loaded:", activeSystemMessage.name);

            // Load websites for the active system message
            loadWebsitesForSystemMessage(activeSystemMessageId);

            // Fetch and display file list for the active system message
            fetchFileList(activeSystemMessageId);
        } else {
            // Handle the case where no system messages are available
            console.log("No system messages available. Setting default values.");
            document.getElementById('systemMessageName').value = "New System Message";
            document.getElementById('systemMessageDescription').value = "";
            document.getElementById('systemMessageContent').value = "";
            document.getElementById('enableWebSearch').checked = false;
            updateModelDropdownInModal("gpt-3.5-turbo"); // Set a default model
            updateTemperatureSelectionInModal(0.7); // Set a default temperature
        }

        // Reset the isSaved flag
        isSaved = false;
    }).catch(error => {
        console.error("Error loading system messages:", error);
        showModalFlashMessage("Error loading system messages", "danger");
    });
});

$('#systemMessageModal').on('shown.bs.modal', function () {
    updateMoreFilesIndicator();
    
    // If there's an active system message, initialize and update the file list
    if (activeSystemMessageId) {
        initializeAndUpdateFileList(activeSystemMessageId);
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
    $(this).removeData('targetGroup');

    // Clear active website ID and website details
    activeWebsiteId = null;
    clearWebsiteDetails();
    updateWebsiteControls();

    // Reset the temporary web search state
    tempWebSearchState = false;
    
    // Reset the UI to reflect the actual saved state
    if (activeSystemMessageId) {
        const activeMessage = systemMessages.find(msg => msg.id === activeSystemMessageId);
        if (activeMessage) {
            document.getElementById('systemMessageName').value = activeMessage.name;
            document.getElementById('systemMessageDescription').value = activeMessage.description;
            document.getElementById('systemMessageContent').value = activeMessage.content;
            document.getElementById('enableWebSearch').checked = activeMessage.enable_web_search;
            updateModelDropdownInModal(activeMessage.model_name);
            updateTemperatureSelectionInModal(activeMessage.temperature);
        }
    } else {
        // Clear all fields if no active message
        document.getElementById('systemMessageName').value = '';
        document.getElementById('systemMessageDescription').value = '';
        document.getElementById('systemMessageContent').value = '';
        document.getElementById('enableWebSearch').checked = false;
        updateModelDropdownInModal('gpt-3.5-turbo'); // Set to default model
        updateTemperatureSelectionInModal(0.7); // Set to default temperature
    }

    // Reset the isSaved flag
    isSaved = false;
});

// Handles switching between different layers of orchestration within the modal.
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
    if (message.role === 'system') {
        // Handle system messages
        let systemMessageContent = message.content;

        // Extract and format vector search results
        const vectorSearchRegex = /<Added Context Provided by Vector Search>([\s\S]*?)<\/Added Context Provided by Vector Search>/g;
        let vectorSearchResults = [];
        let match;

        while ((match = vectorSearchRegex.exec(systemMessageContent)) !== null) {
            let content = match[1].trim();
            if (content !== "Empty Response") {
                vectorSearchResults.push(`<br><strong>Added context from vector search on files:</strong><br> ${escapeHtml(content)}<br>`);
            }
        }

        // Extract and format web search results
        const webSearchRegex = /<Added Context Provided by Web Search>([\s\S]*?)<\/Added Context Provided by Web Search>/g;
        let webSearchResults = [];

        while ((match = webSearchRegex.exec(systemMessageContent)) !== null) {
            let content = match[1].trim();
            if (content !== "No web search results") {
                // Convert URLs to clickable links
                content = content.replace(
                    /(https?:\/\/[^\s]+)/g, 
                    '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
                );
                webSearchResults.push(`<br><strong>Added context from web search:</strong><br>${content}<br>`);
            }
        }

        // Remove vector search and web search tags from the system message
        systemMessageContent = systemMessageContent.replace(vectorSearchRegex, '').replace(webSearchRegex, '').trim();

        // Render the main system message content
        let renderedContent = renderOpenAI(systemMessageContent);

        // Combine the main content with vector search and web search results
        let fullContent = renderedContent + vectorSearchResults.join('') + webSearchResults.join('');

        const systemMessageHTML = `
            <div class="chat-entry system system-message">
                <strong>System:</strong> ${fullContent}<br>
                <strong>Model:</strong> ${modelNameMapping(model)} &nbsp; <strong>Temperature:</strong> ${selectedTemperature.toFixed(2)}
            </div>`;
        return $(systemMessageHTML);
    } else {
        // Handle user and assistant messages as before
        const prefix = message.role === 'user' ? '<i class="far fa-user"></i> ' : '<i class="fas fa-robot"></i> ';
        const messageClass = message.role === 'user' ? 'user-message' : 'bot-message';
        let processedContent;
        if (message.role === 'user') {
            processedContent = escapeHtml(message.content);
        } else {
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



function updateConversationList(page = 1, append = false) {
    if (isLoadingConversations) return;
    
    console.log(`Updating conversation list - Page: ${page}, Append: ${append}`);
    isLoadingConversations = true;

    // Show loading indicator
    if (!append) {
        $('#conversation-list').append('<div id="conversation-loading" class="text-center p-2">Loading conversations...</div>');
    }

    fetch(`/api/conversations?page=${page}&per_page=20`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log(`Received ${data.conversations.length} conversations from server.`);
            
            // Remove loading indicator
            $('#conversation-loading').remove();

            // Update pagination state
            hasMoreConversations = page < data.total_pages;
            currentPage = page;

            // Prepare new HTML content
            let newContent = '';
            data.conversations.forEach(conversation => {
                const temperatureInfo = (typeof conversation.temperature !== 'undefined' && conversation.temperature !== null) 
                    ? `${conversation.temperature}°` 
                    : 'N/A°';
                
                newContent += `
                    <div class="conversation-item" data-id="${conversation.id}">
                        <div class="conversation-title">${conversation.title}</div>
                        <div class="conversation-meta">
                            <span class="model-name" title="AI Model used for this conversation">
                                ${conversation.model_name}
                            </span>
                            <span class="temperature-info" title="Temperature setting">
                                ${temperatureInfo}
                            </span>
                        </div>
                    </div>
                `;
            });

            // Update the conversation list
            if (append) {
                $('#conversation-list').append(newContent);
            } else {
                $('#conversation-list').html(newContent);
            }

            // Add click handlers to new conversation items
            $('.conversation-item').off('click').on('click', function() {
                const conversationId = $(this).data('id');
                console.log(`Loading conversation with id: ${conversationId}`);
                window.history.pushState({}, '', `/c/${conversationId}`);
                loadConversation(conversationId);
            });

            // Setup infinite scroll if there are more conversations
            if (hasMoreConversations) {
                setupInfiniteScroll();
            }

        })
        .catch(error => {
            console.error(`Error updating conversation list: ${error}`);
            $('#conversation-loading').html('Error loading conversations. <a href="#" onclick="updateConversationList(1, false)">Retry</a>');
        })
        .finally(() => {
            isLoadingConversations = false;
        });
}

// Add infinite scroll functionality
function setupInfiniteScroll() {
    const conversationList = document.getElementById('conversation-list');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && hasMoreConversations && !isLoadingConversations) {
                updateConversationList(currentPage + 1, true);
            }
        });
    }, { threshold: 0.5 });

    // Observe the last conversation item
    const lastConversation = conversationList.lastElementChild;
    if (lastConversation) {
        observer.observe(lastConversation);
    }
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
            console.log('Parsed JSON data from conversation:', data);

            // Existing code for updating UI elements...
            $('#conversation-title').text(data.title);
            messages = data.history;
            const modelName = data.model_name;
            $('.current-model-btn').text(modelNameMapping(modelName));
            model = modelName;
            selectedTemperature = data.temperature || 0.3;
            const tokens = {
                prompt_tokens: 'NA',
                completion_tokens: 'NA',
                total_tokens: data.token_count || 'NA'
            };
            showConversationControls(data.title || "AI ∞ UI", tokens);
            activeConversationId = conversationId;

            // Clear the chat
            $('#chat').empty();

            // Repopulate the chat with messages and search results
            data.history.forEach((message, index) => {
                let messageElement;
                if (message.role === 'assistant') {
                    // For assistant messages, we need to add the search results before the message
                    displayVectorSearchResults(data.vector_search_results);
                    displayGeneratedSearchQueries(data.generated_search_queries);
                    displayWebSearchResults(data.web_search_results);

                    const renderedContent = renderOpenAIWithFootnotes(message.content, true);
                    messageElement = $('<div class="chat-entry bot bot-message">')
                        .append('<i class="fas fa-robot"></i> ')
                        .append(renderedContent);
                } else {
                    messageElement = createMessageElement(message);
                }
                $('#chat').append(messageElement);
            });

            // Existing code for MathJax and Prism...
            setTimeout(function() {
                MathJax.typesetPromise().then(() => {
                    console.log('MathJax has finished typesetting.');
                }).catch((err) => console.log('Error typesetting math content: ', err));
            }, 0);
            Prism.highlightAll();

            // Scroll to the bottom after populating the chat
            const chatContainer = document.getElementById('chat');
            chatContainer.scrollTop = chatContainer.scrollHeight;
        })
        .catch(error => {
            console.error(`Error fetching conversation with id: ${conversationId}. Error: ${error}`);
        });
}

function displayVectorSearchResults(results) {
    if (results && results !== "No results found") {
        const vectorSearchDiv = $('<div class="chat-entry vector-search">')
            .append('<img src="/static/images/PineconeIcon.png" alt="Pinecone Icon" class="pinecone-icon"> ')
            .append('<strong>Semantic Search Results:</strong> ')
            .append($('<span>').text(results));
        $('#chat').append(vectorSearchDiv);
    } else {
        const noVectorResultsDiv = $('<div class="chat-entry vector-search">')
            .append('<img src="/static/images/PineconeIcon.png" alt="Pinecone Icon" class="pinecone-icon"> ')
            .append('<strong>Semantic Search Results:</strong> ')
            .append($('<span>').text("No results found"));
        $('#chat').append(noVectorResultsDiv);
    }
}

function displayGeneratedSearchQueries(queries) {
    if (queries) {
        const generatedQueryDiv = $('<div class="chat-entry generated-query">');
        
        generatedQueryDiv.append('<img src="/static/images/SearchIcon.png" alt="Search Icon" class="search-icon"> ');
        generatedQueryDiv.append('<strong>Generated Search Queries:</strong> ');
        
        const queryList = $('<ul class="query-list">');
        
        if (Array.isArray(queries)) {
            // Handle array of queries
            queries.forEach((query) => {
                queryList.append($('<li>').text(query));
            });
        } else if (typeof queries === 'string') {
            // Handle single query string
            queryList.append($('<li>').text(queries));
        }
        
        generatedQueryDiv.append(queryList);
        $('#chat').append(generatedQueryDiv);
    }
}

function displayWebSearchResults(results) {
    if (results && results !== "No web search performed") {
        const webSearchDiv = $('<div class="chat-entry web-search">')
            .append('<img src="/static/images/BraveIcon.png" alt="Brave Icon" class="brave-icon"> ')
            .append('<strong>Web Search Results:</strong> ')
            .append(renderOpenAI(results));
        $('#chat').append(webSearchDiv);
    } else {
        const noWebResultsDiv = $('<div class="chat-entry web-search">')
            .append('<img src="/static/images/BraveIcon.png" alt="Brave Icon" class="brave-icon"> ')
            .append('<strong>Web Search Results:</strong> ')
            .append($('<span>').text("No results found"));
        $('#chat').append(noWebResultsDiv);
    }
}



//Record the default height 
var defaultHeight = $('#user_input').css('height');


function renderOpenAIWithFootnotes(content, enableWebSearch) {
    console.log('Content received:', content);
    console.log('Enable web search:', enableWebSearch);

    // Check if content is undefined or not a string
    if (typeof content !== 'string') {
        console.error('Invalid content received:', content);
        return 'Error: Invalid response from server';
    }

    if (!enableWebSearch) {
        return renderOpenAI(content);
    }

    // Split the content into main text and sources
    let [mainText, sources] = content.split(/Sources?:/i, 2);

    if (!sources) {
        console.warn('No sources found in the content');
        return renderOpenAI(content);
    }

    // Parse sources
    let sourcesList = $('<ol class="sources-list">');
    let sourcesMap = {};
    sources.trim().split('\n').forEach((source, index) => {
        console.log(`Processing source ${index}:`, source);
        if (source && source.trim()) {
            let match = source.match(/\[(\d+)\]\s*(.*)/);
            if (match) {
                let [, index, url] = match;
                sourcesMap[index] = url.trim();
                sourcesList.append($('<li>').append($('<a>').attr('href', url.trim()).attr('target', '_blank').text(url.trim())));
            } else {
                console.warn(`Invalid source format:`, source);
            }
        }
    });

    // Render main text with hyperlinked footnotes
    let renderedContent = mainText.replace(/\[(\d+)\]/g, (match, p1) => {
        let url = sourcesMap[p1];
        return url ? `<a href="${url}" class="footnote" target="_blank">[${p1}]</a>` : match;
    });
    renderedContent = renderOpenAI(renderedContent);

    // Add sources section
    let sourcesSection = $('<div class="sources-section">')
        .append('<h4>Sources:</h4>')
        .append(sourcesList);

    return renderedContent + sourcesSection[0].outerHTML;
}

$('#chat-form').on('submit', async function (e) {
    console.log('Chat form submitted with user input:', $('#user_input').val());
    e.preventDefault();
    
    const userInput = $('#user_input').val();
    if (!userInput.trim()) return; // Don't process empty messages

    // Set WebSocket connection maintenance flag
    maintainWebSocketConnection = true;
    statusWebSocket = initStatusWebSocket();

    // Wait briefly for session ID to be set by the server
    const startTime = Date.now();
    while (!currentSessionId && Date.now() - startTime < 2000) {
        await new Promise(resolve => setTimeout(resolve, 100));
    }

    if (!currentSessionId) {
        console.error('Failed to get session ID');
        return;
    }

    if (!messages) {
        messages = [];
    }

    // Immediately clear the input and reset its height
    const userInputTextarea = $('#user_input');
    userInputTextarea.val('');
    userInputTextarea.css('height', defaultHeight);

    // Immediately show the user's message
    const userInputDiv = $('<div class="chat-entry user user-message">')
        .append('<i class="far fa-user"></i> ')
        .append($('<span>').text(userInput));
    $('#chat').append(userInputDiv);
    $('#chat').scrollTop($('#chat')[0].scrollHeight);

    // Add to messages array immediately
    messages.push({ "role": "user", "content": userInput });

    // Show loading indicator
    document.getElementById('loading').style.display = 'block';

    try {
        // Prepare and send the request
        let requestPayload = {
            messages: messages,
            model: model,
            temperature: selectedTemperature,
            system_message_id: activeSystemMessageId,
            enable_web_search: $('#enableWebSearch').is(':checked'),
            enable_intelligent_search: $('#enableIntelligentSearch').is(':checked')
        };

        // Add reasoning_effort parameter for o3-mini model
        if (model === 'o3-mini') {
            const modelElement = $('.dropdown-item[data-model="o3-mini"].active');
            if (modelElement.length) {
                requestPayload.reasoning_effort = modelElement.data('reasoning');
            }
        }

        if (activeConversationId !== null) {
            requestPayload.conversation_id = activeConversationId;
        }

        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Debug': '1',
                'X-Session-ID': currentSessionId
            },
            body: JSON.stringify(requestPayload)
        });

        console.log('Received response from /chat endpoint:', response);
        document.getElementById('loading').style.display = 'none';

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Error response:', {
                status: response.status,
                statusText: response.statusText,
                headers: Object.fromEntries(response.headers.entries()),
                body: errorText
            });
            
            try {
                const errorJson = JSON.parse(errorText);
                throw new Error(JSON.stringify(errorJson, null, 2));
            } catch (e) {
                throw new Error(errorText);
            }
        }

        const data = await response.json();
        console.log("Complete server response:", JSON.stringify(data, null, 2));
        
        // Display vector search results
        if (data.vector_search_results && data.vector_search_results !== "No results found") {
            const vectorSearchDiv = $('<div class="chat-entry vector-search">')
                .append('<img src="/static/images/PineconeIcon.png" alt="Pinecone Icon" class="pinecone-icon"> ')
                .append('<strong>Semantic Search Results:</strong> ')
                .append($('<span>').text(data.vector_search_results));
            $('#chat').append(vectorSearchDiv);
        } else {
            const noVectorResultsDiv = $('<div class="chat-entry vector-search">')
                .append('<img src="/static/images/PineconeIcon.png" alt="Pinecone Icon" class="pinecone-icon"> ')
                .append('<strong>Semantic Search Results:</strong> ')
                .append($('<span>').text("No results found"));
            $('#chat').append(noVectorResultsDiv);
        }

        // Display generated search queries
        if (data.generated_search_queries && Array.isArray(data.generated_search_queries) && data.generated_search_queries.length > 0) {
            console.log("Creating generated query div");
            const generatedQueryDiv = $('<div class="chat-entry generated-query">');
            
            generatedQueryDiv.append('<img src="/static/images/SearchIcon.png" alt="Search Icon" class="search-icon"> ');
            generatedQueryDiv.append('<strong>Generated Search Queries:</strong> ');
            
            const queryList = $('<ul class="query-list">');
            data.generated_search_queries.forEach((query) => {
                queryList.append($('<li>').text(query));
            });
            
            generatedQueryDiv.append(queryList);
            $('#chat').append(generatedQueryDiv);
        }

        // Display web search results
        if (data.web_search_results && data.web_search_results !== "No web search performed") {
            const webSearchDiv = $('<div class="chat-entry web-search">')
                .append('<img src="/static/images/BraveIcon.png" alt="Brave Icon" class="brave-icon"> ')
                .append('<strong>Web Search Results:</strong> ')
                .append(renderOpenAI(data.web_search_results));
            $('#chat').append(webSearchDiv);
        } else if ($('#enableWebSearch').is(':checked')) {
            const noWebResultsDiv = $('<div class="chat-entry web-search">')
                .append('<img src="/static/images/BraveIcon.png" alt="Brave Icon" class="brave-icon"> ')
                .append('<strong>Web Search Results:</strong> ')
                .append($('<span>').text("No results found"));
            $('#chat').append(noWebResultsDiv);
        }

        // Render bot output with footnotes
        const renderedBotOutput = renderOpenAIWithFootnotes(data.chat_output, data.enable_web_search);
        const botMessageDiv = $('<div class="chat-entry bot bot-message">')
            .append('<i class="fas fa-robot"></i> ')
            .append(renderedBotOutput);
        $('#chat').append(botMessageDiv);
        
        // Update messages array
        messages.push({ "role": "assistant", "content": data.chat_output });

        // Update system message if new content exists
        if (data.system_message_content) {
            const systemMessageIndex = messages.findIndex(msg => msg.role === 'system');
            if (systemMessageIndex !== -1) {
                messages[systemMessageIndex].content = data.system_message_content;
            } else {
                messages.unshift({ "role": "system", "content": data.system_message_content });
            }
        }

        // Render content and scroll
        await Promise.all([
            MathJax.typesetPromise().catch(err => console.log('Error typesetting math content: ', err)),
            new Promise(resolve => {
                Prism.highlightAll();
                resolve();
            })
        ]);

        // Scroll to new content
        setTimeout(() => {
            const chatContainer = $('#chat');
            const botMessageDiv = chatContainer.find('.bot-message').last();
            const botMessageTop = botMessageDiv.position().top;
            const containerScrollTop = chatContainer.scrollTop();
            const adjustedScroll = botMessageTop + containerScrollTop - 50;

            chatContainer.animate({
                scrollTop: adjustedScroll
            }, 500);
        }, 100);

        updateConversationList();

        // Update URL and conversation controls
        window.history.pushState({}, '', `/c/${data.conversation_id}`);

        if (data.conversation_title) {
            console.log("Received conversation_title from server:", data.conversation_title);
            const tokens = data.usage;
            showConversationControls(data.conversation_title, tokens);
        } else {
            showConversationControls();
        }

        // Clean up status updates after successful completion
        clearStatusUpdates();

    } catch (error) {
        console.error('Error in chat form processing:', error);
        document.getElementById('loading').style.display = 'none';
        clearStatusUpdates();
    }
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

    // initialize the conversation list with pagination
    updateConversationList(1, false);

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
    
        // Remove active class from all items
        $('.model-dropdown .dropdown-item').removeClass('active');
        // Add active class to clicked item
        $(this).addClass('active');
    
        const modelName = $(this).attr('data-model');
        const reasoningEffort = $(this).attr('data-reasoning');
    
        $('#dropdownMenuButton').text($(this).text());
        model = modelName; // Update the model variable here
        console.log("Dropdown item clicked. Model is now: " + model + 
                    (reasoningEffort ? " with reasoning effort: " + reasoningEffort : ""));

        // Update the displayed model name in the system message section
        $('.chat-entry.system.system-message .model-name').text(modelNameMapping(model, reasoningEffort));
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
