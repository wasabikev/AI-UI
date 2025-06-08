# folder_utils.py

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_utils import Ltree
from models import Folder, Conversation, User

async def create_root_folder(session: AsyncSession, user_id: int, name: str = "Root") -> Folder:
    """Create a root folder for a user."""
    # Check if user already has a root folder
    stmt = select(Folder).where(
        Folder.user_id == user_id,
        Folder.path == Ltree('0')
    )
    result = await session.execute(stmt)
    existing_root = result.scalars().first()
    
    if existing_root:
        return existing_root
    
    # Create new root folder
    root_folder = Folder(
        name=name,
        path=Ltree('0'),  # Root path is just '0'
        user_id=user_id
    )
    session.add(root_folder)
    await session.flush()  # Flush to get the ID
    
    return root_folder

async def create_folder(session: AsyncSession, user_id: int, name: str, parent_id: int) -> Folder:
    """Create a new folder under the specified parent."""
    # Get parent folder
    stmt = select(Folder).where(
        Folder.id == parent_id,
        Folder.user_id == user_id  # Security check
    )
    result = await session.execute(stmt)
    parent = result.scalars().first()
    
    if not parent:
        raise ValueError("Parent folder not found or access denied")
    
    # Create new path by appending new ID to parent path
    # We'll get the ID after flush
    new_folder = Folder(
        name=name,
        user_id=user_id,
        # Temporary path, will update after flush
        path=Ltree('0')
    )
    session.add(new_folder)
    await session.flush()  # Flush to get the ID
    
    # Now update the path with the correct ID
    new_path = f"{parent.path}.{new_folder.id}"
    new_folder.path = Ltree(new_path)
    
    return new_folder

async def get_folder_tree(session: AsyncSession, user_id: int):
    """Get the entire folder tree for a user."""
    stmt = select(Folder).where(
        Folder.user_id == user_id
    ).order_by(Folder.path)
    
    result = await session.execute(stmt)
    folders = result.scalars().all()
    
    # Convert to tree structure
    folder_dict = {folder.id: {
        'id': folder.id,
        'name': folder.name,
        'path': str(folder.path),
        'children': []
    } for folder in folders}
    
    root = None
    for folder in folders:
        if str(folder.path) == '0':  # Root folder
            root = folder_dict[folder.id]
            continue
            
        # Get parent ID from path
        path_parts = str(folder.path).split('.')
        if len(path_parts) > 1:
            parent_id = int(path_parts[-2])  # Second to last element
            if parent_id in folder_dict:
                folder_dict[parent_id]['children'].append(folder_dict[folder.id])
    
    return root

async def get_folder_contents(session: AsyncSession, user_id: int, folder_id: int):
    """Get all conversations in a folder."""
    # Verify folder exists and belongs to user
    stmt = select(Folder).where(
        Folder.id == folder_id,
        Folder.user_id == user_id
    )
    result = await session.execute(stmt)
    folder = result.scalars().first()
    
    if not folder:
        raise ValueError("Folder not found or access denied")
    
    # Get conversations in this folder
    stmt = select(Conversation).where(
        Conversation.user_id == user_id,
        Conversation.folder_id == folder_id
    ).order_by(Conversation.updated_at.desc())
    
    result = await session.execute(stmt)
    conversations = result.scalars().all()
    
    return {
        'folder': folder.to_dict(),
        'conversations': [conv.to_dict() for conv in conversations]
    }

async def rename_folder(session: AsyncSession, user_id: int, folder_id: int, new_name: str):
    """Rename a folder."""
    # Get the folder
    stmt = select(Folder).where(
        Folder.id == folder_id,
        Folder.user_id == user_id  # Security check
    )
    result = await session.execute(stmt)
    folder = result.scalars().first()
    
    if not folder:
        raise ValueError("Folder not found or access denied")
    
    # Update the name
    folder.name = new_name
    
    return folder

async def move_folder(session: AsyncSession, user_id: int, folder_id: int, new_parent_id: int):
    """Move a folder to a new parent."""
    # Get the folder to move
    stmt = select(Folder).where(
        Folder.id == folder_id,
        Folder.user_id == user_id  # Security check
    )
    result = await session.execute(stmt)
    folder = result.scalars().first()
    
    if not folder:
        raise ValueError("Folder not found or access denied")
    
    # Check if it's the root folder
    if str(folder.path) == '0':
        raise ValueError("Cannot move the root folder")
    
    # Get the new parent
    stmt = select(Folder).where(
        Folder.id == new_parent_id,
        Folder.user_id == user_id  # Security check
    )
    result = await session.execute(stmt)
    new_parent = result.scalars().first()
    
    if not new_parent:
        raise ValueError("New parent folder not found or access denied")
    
    # Check if new parent is a descendant of the folder (would create a cycle)
    if str(new_parent.path).startswith(f"{folder.path}."):
        raise ValueError("Cannot move a folder to its own descendant")
    
    # Get all descendants of the folder
    old_path = str(folder.path)
    # Use the ltree_isparent function for PostgreSQL compatibility
    stmt = select(Folder).where(
        Folder.user_id == user_id,
        func.ltree_isparent(Ltree(old_path), Folder.path)
    )
    result = await session.execute(stmt)
    descendants = result.scalars().all()
    
    # Update the folder's path
    new_path = f"{new_parent.path}.{folder.id}"
    folder.path = Ltree(new_path)
    
    # Update all descendants' paths
    for descendant in descendants:
        if descendant.id != folder.id:  # Skip the folder itself
            descendant_path = str(descendant.path)
            relative_path = descendant_path[len(old_path):]  # Get the part after the old path
            descendant.path = Ltree(f"{new_path}{relative_path}")
    
    return folder

async def delete_folder(session: AsyncSession, user_id: int, folder_id: int, move_conversations_to: int = None):
    """
    Delete a folder and optionally move its conversations to another folder.
    If move_conversations_to is None, conversations will be moved to root folder.
    """
    # Get the folder to delete
    stmt = select(Folder).where(
        Folder.id == folder_id,
        Folder.user_id == user_id  # Security check
    )
    result = await session.execute(stmt)
    folder = result.scalars().first()
    
    if not folder:
        raise ValueError("Folder not found or access denied")
    
    # Check if it's the root folder
    if str(folder.path) == '0':
        raise ValueError("Cannot delete the root folder")
    
    # Get all descendants of the folder
    # Use the ltree_isparent function for PostgreSQL compatibility
    stmt = select(Folder).where(
        Folder.user_id == user_id,
        func.ltree_isparent(Ltree(str(folder.path)), Folder.path)
    )
    result = await session.execute(stmt)
    descendants = result.scalars().all()
    
    # Get all conversations in this folder and its descendants
    folder_ids = [folder.id] + [d.id for d in descendants]
    stmt = select(Conversation).where(
        Conversation.user_id == user_id,
        Conversation.folder_id.in_(folder_ids)
    )
    result = await session.execute(stmt)
    conversations = result.scalars().all()
    
    # Determine where to move conversations
    if move_conversations_to is not None:
        # Verify the target folder exists and belongs to the user
        stmt = select(Folder).where(
            Folder.id == move_conversations_to,
            Folder.user_id == user_id
        )
        result = await session.execute(stmt)
        target_folder = result.scalars().first()
        
        if not target_folder:
            raise ValueError("Target folder not found or access denied")
    else:
        # Get root folder
        stmt = select(Folder).where(
            Folder.user_id == user_id,
            Folder.path == Ltree('0')
        )
        result = await session.execute(stmt)
        target_folder = result.scalars().first()
    
    # Move conversations
    for conversation in conversations:
        conversation.folder_id = target_folder.id
    
    # Delete all descendants and the folder itself
    for descendant in sorted(descendants, key=lambda d: len(str(d.path)), reverse=True):
        await session.delete(descendant)
    
    # Delete the folder itself
    await session.delete(folder)
    
    return True

async def move_conversation(session: AsyncSession, user_id: int, conversation_id: int, folder_id: int):
    """Move a conversation to a different folder."""
    # Verify conversation exists and belongs to user
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id
    )
    result = await session.execute(stmt)
    conversation = result.scalars().first()
    
    if not conversation:
        raise ValueError("Conversation not found or access denied")
    
    # Verify folder exists and belongs to user
    stmt = select(Folder).where(
        Folder.id == folder_id,
        Folder.user_id == user_id
    )
    result = await session.execute(stmt)
    folder = result.scalars().first()
    
    if not folder:
        raise ValueError("Folder not found or access denied")
    
    # Move the conversation
    conversation.folder_id = folder.id
    
    return conversation

async def get_folder_by_id(session: AsyncSession, user_id: int, folder_id: int):
    """Get a folder by ID, ensuring it belongs to the user."""
    stmt = select(Folder).where(
        Folder.id == folder_id,
        Folder.user_id == user_id
    )
    result = await session.execute(stmt)
    folder = result.scalars().first()
    
    if not folder:
        raise ValueError("Folder not found or access denied")
    
    return folder

async def get_user_folders(session: AsyncSession, user_id: int):
    """Get all folders for a user as a flat list."""
    stmt = select(Folder).where(
        Folder.user_id == user_id
    ).order_by(Folder.path)
    
    result = await session.execute(stmt)
    folders = result.scalars().all()
    
    return [folder.to_dict() for folder in folders]