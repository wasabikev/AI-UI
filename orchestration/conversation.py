# orchestration/conversation.py

from sqlalchemy import select, func
from datetime import datetime, timezone
from models import Conversation, Folder, get_session

class ConversationOrchestrator:
    def __init__(self, logger):
        self.logger = logger

    async def get_all_conversations_as_dicts(self):
        """
        Fetch all conversations from the database and return as list of dicts.
        Admin/debug use only.
        """
        async with get_session() as session:
            result = await session.execute(select(Conversation))
            conversations = result.scalars().all()
            return [c.to_dict() for c in conversations]

    async def get_conversations(self, user_id, page=1, per_page=20):
        """
        Paginated list of conversations for a user.
        """
        async with get_session() as session:
            count_query = select(func.count()).select_from(
                select(Conversation)
                .filter(Conversation.user_id == user_id)
                .subquery()
            )
            count_result = await session.execute(count_query)
            total_count = count_result.scalar()

            query = (
                select(Conversation)
                .filter(Conversation.user_id == user_id)
                .order_by(Conversation.updated_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
            result = await session.execute(query)
            conversations = result.scalars().all()
            conversations_dict = [{
                "id": c.id, 
                "title": c.title,
                "model_name": c.model_name,
                "token_count": c.token_count,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                "temperature": c.temperature
            } for c in conversations]
            return {
                "conversations": conversations_dict,
                "total": total_count,
                "page": page,
                "per_page": per_page,
                "total_pages": (total_count + per_page - 1) // per_page
            }


    async def get_conversation_dict(self, conversation_id):
        """
        Fetch a conversation by ID and return as dict (for API).
        """
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return None
        # Use safe_json_loads if you want to avoid import, else just use json.loads
        import json
        def safe_json_loads(json_string, default=None):
            if json_string is None:
                return default
            try:
                return json.loads(json_string)
            except Exception:
                return default
        return {
            "id": conversation.id,
            "title": conversation.title,
            "history": safe_json_loads(conversation.history, default=[]),
            "token_count": conversation.token_count,
            "total_tokens": conversation.token_count,
            "model_name": conversation.model_name,
            "temperature": conversation.temperature,
            "vector_search_results": safe_json_loads(conversation.vector_search_results),
            "generated_search_queries": safe_json_loads(conversation.generated_search_queries),
            "web_search_results": safe_json_loads(conversation.web_search_results),
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
            "sentiment": conversation.sentiment,
            "tags": conversation.tags,
            "language": conversation.language,
            "status": conversation.status,
            "rating": conversation.rating,
            "confidence": conversation.confidence,
            "intent": conversation.intent,
            "entities": safe_json_loads(conversation.entities),
            "prompt_template": conversation.prompt_template
        }

    async def get_conversation(self, conversation_id):
        """
        Fetch a conversation by ID.
        """
        async with get_session() as session:
            result = await session.execute(
                select(Conversation).filter_by(id=conversation_id)
            )
            conversation = result.scalar_one_or_none()
            return conversation

    async def update_title(self, conversation_id, new_title):
        """
        Update the title of a conversation.
        """
        async with get_session() as session:
            result = await session.execute(
                select(Conversation).filter_by(id=conversation_id)
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                return None
            conversation.title = new_title
            conversation.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await session.commit()
            return conversation

    async def delete_conversation(self, conversation_id):
        """
        Delete a conversation by ID.
        """
        async with get_session() as session:
            result = await session.execute(
                select(Conversation).filter_by(id=conversation_id)
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                return False
            await session.delete(conversation)
            await session.commit()
            return True

    async def create_conversation(self, title, folder_id, user_id):
        """
        Create a new conversation in a folder.
        """
        async with get_session() as session:
            # Check folder exists
            folder_result = await session.execute(
                select(Folder).filter_by(id=folder_id)
            )
            folder = folder_result.scalar_one_or_none()
            if not folder:
                return None
            new_conversation = Conversation(
                title=title,
                folder_id=folder_id,
                user_id=user_id
            )
            session.add(new_conversation)
            await session.commit()
            await session.refresh(new_conversation)
            return new_conversation

    async def get_folders(self):
        """
        Return all folder titles.
        """
        async with get_session() as session:
            result = await session.execute(select(Folder))
            folders = result.scalars().all()
            return [folder.title for folder in folders]

    async def create_folder(self, title):
        """
        Create a new folder.
        """
        async with get_session() as session:
            new_folder = Folder(title=title)
            session.add(new_folder)
            await session.commit()
            await session.refresh(new_folder)
            return new_folder

    async def get_folder_conversations(self, folder_id):
        """
        Get all conversation titles in a folder.
        """
        async with get_session() as session:
            result = await session.execute(
                select(Conversation).filter_by(folder_id=folder_id)
            )
            conversations = result.scalars().all()
            return [conversation.title for conversation in conversations]

    # Add more orchestration methods as needed
