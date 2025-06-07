# orchestration/status.py

import uuid
import asyncio
import time
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

import logging
logger = logging.getLogger(__name__)


@dataclass
class SessionStatus:
    user_id: int
    session_id: str
    message: str
    last_updated: float
    expires_at: float
    websocket: Optional[object] = None
    active: bool = False


class StatusUpdateManager:
    PING_INTERVAL = 30  # seconds
    SESSION_TIMEOUT = 3600  # 1 hour in seconds
    CLEANUP_INTERVAL = 300  # 5 minutes

    def __init__(self):
        self._sessions: Dict[str, SessionStatus] = {}
        self._cleanup_lock = asyncio.Lock()
        self._last_cleanup = time.time()
        self.connection_count = 0
        self.locks = {}
        self.initial_messages_sent = set()


    def _generate_session_id(self, user_id: int) -> str:
        """Generate a unique session ID combining user_id and UUID."""
        return f"{user_id}-{uuid.uuid4()}"

    def create_session(self, user_id: int) -> str:
        """Create a new session and return its ID."""
        session_id = self._generate_session_id(user_id)
        current_time = time.time()
        
        self._sessions[session_id] = SessionStatus(
            user_id=user_id,
            session_id=session_id,
            message="Session initialized",
            last_updated=current_time,
            expires_at=current_time + self.SESSION_TIMEOUT
        )
        
        self._cleanup_expired_sessions()
        return session_id

    async def register_connection(self, session_id: str, websocket) -> bool:
        """Register a WebSocket connection for a session."""
        async with self._cleanup_lock:
            if session_id not in self._sessions:
                return False

            session = self._sessions[session_id]
            
            # Only increment if session wasn't already active
            if not session.active:
                self.connection_count += 1

            self._sessions[session_id] = SessionStatus(
                user_id=session.user_id,
                session_id=session_id,
                message="Connected to status updates",
                last_updated=time.time(),
                expires_at=time.time() + self.SESSION_TIMEOUT,
                websocket=websocket,
                active=True
            )

            self.locks[session_id] = asyncio.Lock()
            
            # Send initial connection message with session ID
            try:
                await websocket.send(json.dumps({
                    'type': 'status',
                    'status': 'connected',
                    'session_id': session_id,
                    'timestamp': datetime.now().isoformat()
                }))
            except Exception as e:
                logger.error(f"Error sending initial connection message: {str(e)}")
                return False

            logger.debug(f"WebSocket connection registered for session ID: {session_id}. Active connections: {self.connection_count}")
            return True

    async def send_status_update(self, session_id: str, message: str, status: str = None) -> bool:
        """
        Send a status update to a session.
        
        Args:
            session_id: The session ID
            message: Status message to send
            status: Optional status type (e.g. 'error')
        """
        if session_id not in self._sessions or not self._sessions[session_id].active:
            return False

        session = self._sessions[session_id]
        current_time = time.time()

        # Update session status
        self._sessions[session_id] = SessionStatus(
            user_id=session.user_id,
            session_id=session_id,
            message=message,
            last_updated=current_time,
            expires_at=current_time + self.SESSION_TIMEOUT,
            websocket=session.websocket,
            active=session.active
        )

        # Send WebSocket update
        lock = self.locks.get(session_id)
        if lock:
            async with lock:
                try:
                    status_data = {
                        'type': 'status',
                        'message': message,
                        'timestamp': datetime.now().isoformat(),
                        'id': str(uuid.uuid4())
                    }
                    if status:
                        status_data['status'] = status
                    await session.websocket.send(json.dumps(status_data))
                    return True
                except Exception as e:
                    logger.error(f"Error sending status update: {str(e)}")
                    await self.remove_connection(session_id)
                    return False

        return False

    async def send_ping(self, session_id: str) -> bool:
        """Send a ping message to keep the connection alive."""
        if session_id not in self._sessions or not self._sessions[session_id].active:
            return False

        session = self._sessions[session_id]
        try:
            ping_data = {
                'type': 'ping',
                'timestamp': datetime.now().isoformat()
            }
            await session.websocket.send(json.dumps(ping_data))
            return True
        except Exception as e:
            logger.debug(f"Error sending ping: {str(e)}")
            await self.remove_connection(session_id)
            return False

    async def remove_connection(self, session_id: str) -> None:
        """Remove a session's WebSocket connection."""
        async with self._cleanup_lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                
                # Only decrement if session was active
                if session.active:
                    self.connection_count = max(0, self.connection_count - 1)
                
                # Only try to close the WebSocket if it's not being called from the WebSocket handler
                # Check the call stack to determine if we're in the WebSocket handler
                import inspect
                caller_frame = inspect.currentframe().f_back
                caller_function_name = caller_frame.f_code.co_name if caller_frame else ""
                
                if session.websocket and caller_function_name != "ws_chat_status":
                    try:
                        await session.websocket.close(1000, "Connection closed normally")
                    except Exception as e:
                        logger.debug(f"Error closing websocket: {str(e)}")

                # Update session to inactive state
                self._sessions[session_id] = SessionStatus(
                    user_id=session.user_id,
                    session_id=session_id,
                    message=session.message,
                    last_updated=time.time(),
                    expires_at=session.expires_at,
                    websocket=None,
                    active=False
                )

                self.locks.pop(session_id, None)
                self.initial_messages_sent.discard(session_id)
                logger.debug(f"WebSocket connection removed for session ID: {session_id}. Active connections: {self.connection_count}")

    # helper function to update status
    async def update_status(self, message: str, session_id: str, status: str = None):
        """
        Args:
            message: Status message to send
            session_id: WebSocket session ID
            status: Optional status type (e.g. 'error')
        """
        try:
            await self.send_status_update(
                session_id=session_id,
                message=message,
                status=status
            )
        except Exception as e:
            logger.error(f"Error sending status update: {str(e)}")


    def _cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions."""
        current_time = time.time()
        
        if current_time - self._last_cleanup < self.CLEANUP_INTERVAL:
            return

        expired_sessions = [
            session_id for session_id, session in self._sessions.items()
            if current_time > session.expires_at
        ]
        
        for session_id in expired_sessions:
            del self._sessions[session_id]

        self._last_cleanup = current_time

