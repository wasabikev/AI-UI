# orchestration/system_message_orchestrator.py

from datetime import datetime, timezone
from sqlalchemy import select
from models import SystemMessage, get_session
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
