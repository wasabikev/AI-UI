# orchestration/websocket_manager.py

import asyncio
import json
import time
from datetime import datetime
from quart import websocket
from quart_auth import current_user

class WebSocketManager:
    def __init__(self, status_manager, logger):
        self.status_manager = status_manager
        self.logger = logger

    async def handle_ws_chat_status(self):
        """WebSocket endpoint for status updates."""
        user_id = int(current_user.auth_id)
        session_id = self.status_manager.create_session(user_id)
        self.logger.info(f"WebSocket connection initiated for session {session_id}")

        try:
            # Verify authentication
            if not current_user.is_authenticated:
                self.logger.warning(f"Unauthorized WebSocket connection attempt for session {session_id}")
                return

            # Get user and verify status
            user = await current_user.get_user()
            if not user or user.status != 'Active':
                self.logger.warning(f"Inactive or invalid user attempted WebSocket connection: {session_id}")
                return

            # Register the websocket connection
            self.logger.info(f"Registering WebSocket connection for session {session_id}")
            success = await self.status_manager.register_connection(session_id, websocket._get_current_object())

            if not success:
                self.logger.error(f"Failed to register WebSocket connection for session {session_id}")
                return

            # Send initial connection message
            self.logger.info(f"Sending initial connection message for session {session_id}")
            await self.status_manager.send_status_update(
                session_id=session_id,
                message="WebSocket connection established"
            )

            # Main message loop
            while True:
                try:
                    message = await websocket.receive()
                    self.logger.debug(f"Received WebSocket message for session {session_id}: {message}")

                    if not message:
                        continue

                    try:
                        data = json.loads(message)
                        if data.get('type') == 'ping':
                            await websocket.send(json.dumps({
                                'type': 'pong',
                                'timestamp': datetime.now().isoformat(),
                                'session_id': session_id
                            }))
                    except json.JSONDecodeError:
                        continue

                except asyncio.CancelledError:
                    self.logger.info(f"WebSocket connection cancelled for session {session_id}")
                    break

        except Exception as e:
            self.logger.error(f"Error in WebSocket connection: {str(e)}")
            self.logger.exception("Full traceback:")
        finally:
            await self.cleanup_ws_connection(session_id)

    async def cleanup_ws_connection(self, session_id):
        """Cleanup logic for WebSocket connection."""
        try:
            self.logger.info(f"Cleaning up WebSocket connection for session {session_id}")
            # Update the connection state in status_manager without trying to close the WebSocket
            if session_id in self.status_manager._sessions:
                session = self.status_manager._sessions[session_id]

                # Only decrement if session was active
                if session.active:
                    self.status_manager.connection_count = max(0, self.status_manager.connection_count - 1)

                # Update session to inactive state without closing the WebSocket
                from orchestration.status import SessionStatus
                self.status_manager._sessions[session_id] = SessionStatus(
                    user_id=session.user_id,
                    session_id=session_id,
                    message=session.message,
                    last_updated=time.time(),
                    expires_at=session.expires_at,
                    websocket=None,
                    active=False
                )

                self.status_manager.locks.pop(session_id, None)
                self.status_manager.initial_messages_sent.discard(session_id)

            self.logger.info(f"WebSocket cleanup complete for session {session_id}")
        except Exception as cleanup_error:
            self.logger.error(f"Error during WebSocket cleanup: {str(cleanup_error)}")

    async def periodic_ping(self, connection_id):
        """Periodically send ping messages to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(self.status_manager.PING_INTERVAL)
                if not await self.status_manager.send_ping(connection_id):
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Error in periodic ping: {str(e)}")
