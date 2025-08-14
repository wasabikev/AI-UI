# orchestration/system_message_orchestrator.py

from datetime import datetime, timezone
from sqlalchemy import select, or_, and_
from models import SystemMessage, get_session, User
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict, List, Tuple, Optional

class SystemMessageOrchestrator:
    """
    Orchestrator for all business logic related to SystemMessage management.
    """

    def __init__(self, logger):
        self.logger = logger

    async def create(self, data: Dict[str, Any], current_user: User) -> Tuple[Dict[str, Any], int]:
        """
        Create a new SystemMessage.
        """
        try:
            # Validation - only name is required
            name = data.get('name')
            if not name:
                return {'error': 'Name is required.'}, 400

            async with get_session() as session:
                current_time = datetime.now(timezone.utc).replace(tzinfo=None)
                new_system_message = SystemMessage(
                    name=name,
                    content=data.get('content', ''),  # Default to empty string if not provided
                    description=data.get('description', ''),
                    model_name=data.get('model_name', ''),
                    temperature=data.get('temperature', 0.7),
                    created_by=current_user.id,  # Always assign to current user
                    created_at=current_time,
                    updated_at=current_time,
                    enable_web_search=data.get('enable_web_search', False),
                    enable_time_sense=data.get('enable_time_sense', False)
                )
                session.add(new_system_message)
                await session.commit()
                await session.refresh(new_system_message)
                self.logger.info(f"Created new system message: {name} (id={new_system_message.id}) for user {current_user.id}")
                return new_system_message.to_dict(), 201
        except Exception as e:
            self.logger.error(f"Error creating system message: {str(e)}")
            return {'error': str(e)}, 500

    async def get_all(self, user_id: Optional[int] = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        Retrieve all system messages for a user plus system defaults.
        If user_id is None, returns all messages (admin view).
        """
        try:
            async with get_session() as session:
                query = select(SystemMessage)
                
                if user_id is not None:
                    # Get user's messages and system defaults (where created_by is NULL)
                    query = query.where(
                        or_(
                            SystemMessage.created_by == user_id,
                            SystemMessage.created_by.is_(None)  # System defaults
                        )
                    )
                
                query = query.order_by(SystemMessage.name)
                result = await session.execute(query)
                system_messages = result.scalars().all()
                
                # Ensure default exists
                if user_id is not None:
                    default_exists = any(msg.name == "Default System Message" for msg in system_messages)
                    if not default_exists:
                        default_msg = await self._ensure_default_exists(session)
                        if default_msg:
                            system_messages = list(system_messages) + [default_msg]
                
                messages_list = []
                for msg in system_messages:
                    msg_dict = msg.to_dict()
                    msg_dict['is_default'] = msg.created_by is None  # Flag system defaults
                    msg_dict['is_editable'] = msg.created_by == user_id if user_id else True  # Can user edit this?
                    messages_list.append(msg_dict)
                
                self.logger.info(f"Fetched {len(messages_list)} system messages for user {user_id}.")
                return messages_list, 200
        except Exception as e:
            self.logger.error(f"Error fetching system messages: {str(e)}")
            return [{'error': str(e)}], 500

    async def _ensure_default_exists(self, session: AsyncSession) -> Optional[SystemMessage]:
        """
        Ensure a default system message exists.
        """
        try:
            # Check if there's a system default (created_by = NULL)
            result = await session.execute(
                select(SystemMessage).where(
                    and_(
                        SystemMessage.name == "Default System Message",
                        SystemMessage.created_by.is_(None)
                    )
                )
            )
            default_msg = result.scalar_one_or_none()
            
            if not default_msg:
                # Create a system default if it doesn't exist
                from config import get_config
                config = get_config()
                
                current_time = datetime.now(timezone.utc).replace(tzinfo=None)
                default_msg = SystemMessage(
                    name="Default System Message",
                    content=config.DEFAULT_SYSTEM_MESSAGE,
                    description="Default system message for general conversations",
                    model_name="gpt-4o-2024-08-06",
                    temperature=0.7,
                    created_by=None,  # NULL means it's a system default
                    created_at=current_time,
                    updated_at=current_time,
                    enable_web_search=False,
                    enable_deep_search=False,
                    enable_time_sense=True
                )
                session.add(default_msg)
                await session.commit()
                await session.refresh(default_msg)
                self.logger.info("Created default system message")
            
            return default_msg
        except Exception as e:
            self.logger.error(f"Error ensuring default exists: {str(e)}")
            return None

    async def update(self, message_id: int, data: Dict[str, Any], current_user: User) -> Tuple[Dict[str, Any], int]:
        """
        Update an existing system message.
        Users can update their own messages, admins can update any message.
        """
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(SystemMessage).filter_by(id=message_id)
                )
                system_message = result.scalar_one_or_none()

                if not system_message:
                    return {'error': 'System message not found'}, 404

                # Check permissions
                if system_message.created_by is None:
                    # System defaults can only be updated by admins
                    if not current_user.is_admin:
                        return {'error': 'Only admins can update system defaults'}, 403
                elif system_message.created_by != current_user.id and not current_user.is_admin:
                    # Users can only update their own messages (unless admin)
                    return {'error': 'You can only update your own system messages'}, 403

                # Update fields
                system_message.name = data.get('name', system_message.name)
                system_message.content = data.get('content', system_message.content)
                system_message.description = data.get('description', system_message.description)
                system_message.model_name = data.get('model_name', system_message.model_name)
                system_message.temperature = data.get('temperature', system_message.temperature)
                system_message.enable_web_search = data.get('enable_web_search', system_message.enable_web_search)
                system_message.enable_time_sense = data.get('enable_time_sense', system_message.enable_time_sense)
                system_message.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

                await session.commit()
                await session.refresh(system_message)
                self.logger.info(f"Updated system message {message_id} by user {current_user.id}")
                return system_message.to_dict(), 200
        except Exception as e:
            self.logger.error(f"Error updating system message: {str(e)}")
            return {'error': str(e)}, 500

    async def delete(self, message_id: int, current_user: User) -> Tuple[Dict[str, Any], int]:
        """
        Delete a system message.
        Users can delete their own messages, admins can delete any non-default message.
        """
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(SystemMessage).filter_by(id=message_id)
                )
                system_message = result.scalar_one_or_none()

                if not system_message:
                    return {'error': 'System message not found'}, 404

                # Prevent deletion of system defaults
                if system_message.created_by is None:
                    return {'error': 'Cannot delete system default messages'}, 403
                
                # Prevent deletion of the default message by name as well
                if system_message.name == "Default System Message":
                    return {'error': 'Cannot delete the default system message'}, 403

                # Check permissions
                if system_message.created_by != current_user.id and not current_user.is_admin:
                    return {'error': 'You can only delete your own system messages'}, 403

                await session.delete(system_message)
                await session.commit()
                self.logger.info(f"Deleted system message {message_id} by user {current_user.id}")
                return {'message': 'System message deleted successfully'}, 200
        except Exception as e:
            self.logger.error(f"Error deleting system message: {str(e)}")
            return {'error': str(e)}, 500

    async def get_by_id(self, message_id: int, user_id: Optional[int] = None) -> Tuple[Optional[Dict[str, Any]], int]:
        """
        Retrieve a single system message by ID.
        If user_id is provided, checks if user has access to this message.
        """
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(SystemMessage).filter_by(id=message_id)
                )
                system_message = result.scalar_one_or_none()
                if not system_message:
                    return {'error': 'System message not found'}, 404
                
                # Check access permissions if user_id provided
                if user_id is not None:
                    if system_message.created_by is not None and system_message.created_by != user_id:
                        return {'error': 'Access denied'}, 403
                
                msg_dict = system_message.to_dict()
                msg_dict['is_default'] = system_message.created_by is None
                return msg_dict, 200
        except Exception as e:
            self.logger.error(f"Error fetching system message by id: {str(e)}")
            return {'error': str(e)}, 500
    
    async def toggle_search(
        self,
        system_message_id: int,
        enable_web_search: bool,
        enable_deep_search: bool,
        current_user: User,
    ) -> Tuple[dict, int]:
        """
        Toggle web search settings for a system message.
        """
        try:
            async with get_session() as session:
                # Get the system message
                result = await session.execute(
                    select(SystemMessage).filter_by(id=system_message_id)
                )
                system_message = result.scalar_one_or_none()

                if not system_message:
                    return {'error': 'System message not found'}, 404

                # Check permissions - user must be admin or owner
                if system_message.created_by is None and not current_user.is_admin:
                    return {'error': 'Only admins can modify system defaults'}, 403
                elif system_message.created_by is not None and system_message.created_by != current_user.id and not current_user.is_admin:
                    return {'error': 'You can only modify your own system messages'}, 403

                # Update the search settings
                system_message.enable_web_search = enable_web_search
                system_message.enable_deep_search = enable_deep_search
                system_message.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

                await session.commit()

                self.logger.info(
                    f"Search settings updated for system message {system_message_id} by user {current_user.id}"
                )

                return {
                    'message': 'Search settings updated successfully',
                    'enableWebSearch': system_message.enable_web_search,
                    'enableDeepSearch': system_message.enable_deep_search,
                    'updatedAt': system_message.updated_at.isoformat()
                }, 200

        except Exception as e:
            self.logger.error(f"Error in toggle_search: {str(e)}")
            return {
                'error': 'Failed to update search settings',
                'details': str(e)
            }, 500

    async def get_default_model_name(self, default_message_name: str) -> Tuple[Dict[str, Any], int]:
        """
        Get the model name from the default system message.
        """
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(SystemMessage).filter_by(name=default_message_name)
                )
                default_message = result.scalar_one_or_none()
                if default_message:
                    return {'model_name': default_message.model_name}, 200
                else:
                    return {'error': 'Default system message not found'}, 404
        except Exception as e:
            self.logger.error(f"Error getting default model name: {str(e)}")
            return {'error': str(e)}, 500
