# file_utils.py

import os

def get_user_folder(app, user_id):
    return os.path.join(app.config['BASE_UPLOAD_FOLDER'], str(user_id))

def get_system_message_folder(app, user_id, system_message_id):
    return os.path.join(get_user_folder(app, user_id), str(system_message_id))

def get_uploads_folder(app, user_id, system_message_id):
    return os.path.join(get_system_message_folder(app, user_id, system_message_id), 'uploads')

def get_processed_texts_folder(app, user_id, system_message_id):
    return os.path.join(get_system_message_folder(app, user_id, system_message_id), 'processed_texts')

def get_llmwhisperer_output_folder(app, user_id, system_message_id):
    return os.path.join(get_system_message_folder(app, user_id, system_message_id), 'llmwhisperer_output')

def ensure_folder_exists(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

def get_file_path(app, user_id, system_message_id, filename, folder_type):
    if folder_type == 'uploads':
        folder = get_uploads_folder(app, user_id, system_message_id)
    elif folder_type == 'processed_texts':
        folder = get_processed_texts_folder(app, user_id, system_message_id)
    elif folder_type == 'llmwhisperer_output':  
        folder = get_llmwhisperer_output_folder(app, user_id, system_message_id)
    else:
        raise ValueError(f"Invalid folder type: {folder_type}")
    
    ensure_folder_exists(folder)
    return os.path.join(folder, filename)
