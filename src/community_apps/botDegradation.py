import logging
import time
from collections import deque

logger = logging.getLogger(__name__)


# user facing fallback messages based on bot state and failure reason
FALLBACK_MESSAGES = {
    "offline": "The bot is currently offline and cannot process commands. Please try again later.",
    "maintenance": "The bot is undergoing scheduled maintenance. Commands are temporarily disabled.",
    "api_error": "The server encountered an error processing your request. Please try again shortly.",
    "timeout": "The request timed out. The server may be under heavy load. Please try again in a moment.",
    "degraded": "The bot is running in limited mode. Some features may be unavailable.",
}


def get_fallback_message(state, flags=None):
    if flags and flags.get("maintenance_mode"):
        return FALLBACK_MESSAGES["maintenance"]
    return FALLBACK_MESSAGES.get(state, FALLBACK_MESSAGES["offline"])


# buffers commands during downtime so maintainers can review what users tried
class CommandBuffer:
    def __init__(self, max_size=100):
        self._buffer = deque(maxlen=max_size)

    def add(self, user_name, user_id, command, args=None):
        self._buffer.append({
            "timestamp": time.time(),
            "user_name": user_name,
            "user_id": user_id,
            "command": command,
            "args": args,
            "reason": "command_blocked",
        })
        logger.info(f"Buffered rejected command: /{command} from {user_name}")

    def get_all(self):
        return list(self._buffer)

    def clear(self):
        self._buffer.clear()

    def count(self):
        return len(self._buffer)


command_buffer = CommandBuffer()


# sends alerts to a designated admin channel when failures occur
class AdminAlerts:
    def __init__(self):
        self._bot = None
        self._admin_channel_id = None

    def configure(self, bot, admin_channel_id):
        self._bot = bot
        self._admin_channel_id = admin_channel_id
        logger.info(f"Admin alerts configured for channel {admin_channel_id}")

    async def send_alert(self, message):
        if not self._bot or not self._admin_channel_id:
            return
        try:
            channel = self._bot.get_channel(self._admin_channel_id)
            if channel:
                await channel.send(f"Bot Alert: {message}")
            logger.warning(f"ALERT: {message}")
            
        except Exception as e:
            logger.error(f"Failed to send admin alert: {e}")

    async def alert_state_change(self, old_state, new_state):
        await self.send_alert(f"State changed: {old_state} to {new_state}")

    async def alert_handshake_failure(self, attempt, max_retries):
        await self.send_alert(f"Handshake failed after {attempt}/{max_retries} attempts")

    async def alert_heartbeat_failure(self, error):
        await self.send_alert(f"Heartbeat failure: {error}")

    async def alert_api_failure(self, route, error):
        await self.send_alert(f"API call to /{route} failed: {error}")


admin_alerts = AdminAlerts()
