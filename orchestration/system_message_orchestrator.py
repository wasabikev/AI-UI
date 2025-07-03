# orchestration/system_message_orchestrator.py

from datetime import datetime, timezone
from sqlalchemy import select
from models import SystemMessage, get_session, User
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict, List, Tuple, Optional

class SystemMessageOrchestrator:
    """
    Orchestrator for all business logic related to SystemMessage management.
    """

    def __init__(self, logger):
        self.logger = logger

    async def create(self, data: Dict[str, Any], current_user) -> Tuple[Dict[str, Any], int]:
        """
        Create a new SystemMessage.
        """
        try:
            # Validation
            name = data.get('name')
            content = data.get('content')
            if not name or not content:
                return {'error': 'Name and content are required.'}, 400

            async with get_session() as session:
                current_time = datetime.now(timezone.utc).replace(tzinfo=None)
                new_system_message = SystemMessage(
                    name=name,
                    content=content,
                    description=data.get('description', ''),
                    model_name=data.get('model_name', ''),
                    temperature=data.get('temperature', 0.7),
                    created_by=current_user.id,
                    created_at=current_time,
                    updated_at=current_time,
                    enable_web_search=data.get('enable_web_search', False),
                    enable_time_sense=data.get('enable_time_sense', False)
                )
                session.add(new_system_message)
                await session.commit()
                await session.refresh(new_system_message)
                self.logger.info(f"Created new system message: {name} (id={new_system_message.id})")
                return new_system_message.to_dict(), 201
        except Exception as e:
            self.logger.error(f"Error creating system message: {str(e)}")
            return {'error': str(e)}, 500

    async def get_all(self) -> Tuple[List[Dict[str, Any]], int]:
        """
        Retrieve all system messages.
        """
        try:
            async with get_session() as session:
                result = await session.execute(select(SystemMessage))
                system_messages = result.scalars().all()
                messages_list = [msg.to_dict() for msg in system_messages]
                self.logger.info(f"Fetched {len(messages_list)} system messages.")
                return messages_list, 200
        except Exception as e:
            self.logger.error(f"Error fetching system messages: {str(e)}")
            return [{'error': str(e)}], 500

    async def update(self, message_id: int, data: Dict[str, Any], current_user) -> Tuple[Dict[str, Any], int]:
        """
        Update an existing system message.
        """
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(SystemMessage).filter_by(id=message_id)
                )
                system_message = result.scalar_one_or_none()

                if not system_message:
                    return {'error': 'System message not found'}, 404

                # Only allow admins to update
                if not await current_user.check_admin():
                    return {'error': 'Unauthorized'}, 401

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
                self.logger.info(f"Updated system message {message_id}")
                return system_message.to_dict(), 200
        except Exception as e:
            self.logger.error(f"Error updating system message: {str(e)}")
            return {'error': str(e)}, 500

    async def delete(self, message_id: int, current_user) -> Tuple[Dict[str, Any], int]:
        """
        Delete a system message.
        """
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(SystemMessage).filter_by(id=message_id)
                )
                system_message = result.scalar_one_or_none()

                if not system_message:
                    return {'error': 'System message not found'}, 404

                if not await current_user.check_admin():
                    return {'error': 'Unauthorized'}, 401

                await session.delete(system_message)
                await session.commit()
                self.logger.info(f"Deleted system message {message_id}")
                return {'message': 'System message deleted successfully'}, 200
        except Exception as e:
            self.logger.error(f"Error deleting system message: {str(e)}")
            return {'error': str(e)}, 500

    async def get_by_id(self, message_id: int) -> Tuple[Optional[Dict[str, Any]], int]:
        """
        Retrieve a single system message by ID.
        """
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(SystemMessage).filter_by(id=message_id)
                )
                system_message = result.scalar_one_or_none()
                if not system_message:
                    return {'error': 'System message not found'}, 404
                return system_message.to_dict(), 200
        except Exception as e:
            self.logger.error(f"Error fetching system message by id: {str(e)}")
            return {'error': str(e)}, 500
    
    async def toggle_search(
        self,
        system_message_id: int,
        enable_web_search: bool,
        enable_deep_search: bool,
        current_user,
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

                # Get current user from database
                user_result = await session.execute(
                    select(User).filter_by(id=int(current_user.auth_id))
                )
                current_user_obj = user_result.scalar_one_or_none()

                if not current_user_obj:
                    return {'error': 'User not found'}, 404

                # Check permissions
                if not current_user_obj.is_admin and system_message.created_by != current_user_obj.id:
                    return {'error': 'Unauthorized to modify this system message'}, 403

                # Update the search settings
                system_message.enable_web_search = enable_web_search
                system_message.enable_deep_search = enable_deep_search
                system_message.updated_at = datetime.now(timezone.utc)

                await session.commit()

                self.logger.info(
                    f"Search settings updated for system message {system_message_id} by user {current_user_obj.id}"
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

