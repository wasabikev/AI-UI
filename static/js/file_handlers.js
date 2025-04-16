// File attachment handling
let attachedFiles = new Map(); // Store file metadata

// Handle file selection
document.getElementById('fileInput').addEventListener('change', async function(e) {
    const files = e.target.files;
    if (!files.length) return;

    const previewContainer = document.getElementById('attachedFilesPreview');
    previewContainer.classList.remove('d-none');

    for (const file of files) {
        try {
            // Upload file to temp storage
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/upload_temp_file', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Upload failed');
            
            const data = await response.json();
            
            // Store file metadata
            attachedFiles.set(data.file_id, {
                originalName: file.name,
                tempPath: data.file_path,
                size: file.size,
                type: file.type
            });

            // Add preview badge
            const badge = document.createElement('span');
            badge.className = 'badge badge-info mr-2';
            badge.innerHTML = `
                ${file.name} 
                <button type="button" class="close ml-2" data-file-id="${data.file_id}">
                    <span>&times;</span>
                </button>
            `;
            previewContainer.appendChild(badge);

            // Handle remove button click
            badge.querySelector('.close').addEventListener('click', async function() {
                const fileId = this.dataset.fileId;
                await removeAttachedFile(fileId);
                badge.remove();
                if (previewContainer.children.length === 0) {
                    previewContainer.classList.add('d-none');
                }
            });

        } catch (error) {
            console.error('Error handling file:', error);
            showError(`Failed to upload file: ${file.name}`);
        }
    }

    // Clear input
    e.target.value = '';
});

// Handle paperclip button click
document.getElementById('attachFileBtn').addEventListener('click', function() {
    document.getElementById('fileInput').click();
});

// Handle form submission with files
const originalSubmitHandler = window.handleSubmit;
window.handleSubmit = async function(event) {
    event.preventDefault();
    
    const messageInput = document.getElementById('user_input');
    const message = messageInput.value.trim();
    
    // Prepare files data if any
    const filesData = [];
    for (const [fileId, metadata] of attachedFiles) {
        filesData.push({
            file_id: fileId,
            original_name: metadata.originalName,
            temp_path: metadata.tempPath
        });
    }

    try {
        // Add files to message data
        const messageData = {
            message: message,
            files: filesData
        };

        // Clear files after successful submission
        await originalSubmitHandler(event, messageData);
        clearAttachedFiles();
        
    } catch (error) {
        console.error('Error submitting message with files:', error);
        showError('Failed to send message with attachments');
    }
};

// Utility functions
async function removeAttachedFile(fileId) {
    try {
        await fetch(`/remove_temp_file/${fileId}`, { method: 'DELETE' });
        attachedFiles.delete(fileId);
    } catch (error) {
        console.error('Error removing file:', error);
    }
}

function clearAttachedFiles() {
    const previewContainer = document.getElementById('attachedFilesPreview');
    previewContainer.innerHTML = '';
    previewContainer.classList.add('d-none');
    attachedFiles.clear();
}

function showError(message) {
    // Add error notification logic here
    console.error(message);
}
