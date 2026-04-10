import asyncio
import time
import logging
import httpx
from enum import Enum

from utlis.botProtocolConfig import BOT_SHARED_SECRET, HEARTBEAT_INTERVAL

logger = logging.getLogger(__name__)

# all three states the bot can be in
class BotState(Enum):
    OFFLINE = "OFFLINE"
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"

# control plane for managing bot state, session, and communication
class BotControlPlane:
    def __init__(self, bot_id="discord-bot-1", version="1.0.0", capabilities=None, base_url="http://localhost:8000"):
        
        self.bot_id = bot_id
        self.version = version
        self.capabilities = capabilities or ["query", "moderation"]

        self.base_url = base_url

        self.session_token = None
        self.state = BotState.OFFLINE
        self.flags = {}
        self.heartbeat_interval = HEARTBEAT_INTERVAL

        self._heartbeat_task = None

    # perform handshake to establish session and start heartbeat loop
    async def handshake(self, max_retries=5, base_delay=1.0):
        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(f"{self.base_url}/bot/handshake",
                        json={
                        "bot_id": self.bot_id,
                        "version": self.version,
                        "capabilities": self.capabilities,
                        "shared_secret": BOT_SHARED_SECRET,
                    })

                if response.status_code == 200:
                    data = response.json()
                    self.session_token = data["session_token"]
                    self.heartbeat_interval = data.get("interval", HEARTBEAT_INTERVAL)
                    self.flags = data.get("flags", {})
                    self.state = BotState.CONNECTED
                    logger.info(f"Handshake success (attempt {attempt})")
                    return True

                logger.warning(f"Handshake failed (attempt {attempt}): status_code={response.status_code}")

            except httpx.RequestError as e:
                logger.error(f"Handshake connection error (attempt {attempt}): {e}")

            # exponential backoff before retrying
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))

        self.state = BotState.OFFLINE
        logger.error("Handshake failed after all retries")
        return False
    
    # heartbeat loop that runs in background to maintain session and update bot state
    async def _heartbeat_loop(self):
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            
            # if offline try to re-handshake before sending heartbeat
            if self.state == BotState.OFFLINE:
                if not await self.handshake():
                    continue

            try:
                start = time.monotonic()
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(f"{self.base_url}/bot/heartbeat",
                        json={
                        "bot_id": self.bot_id, 
                        "latency": 0},
                        headers={"x-bot-session": self.session_token},
                    )
                # calculate latency based on how long heartbeat request takes
                latency = round((time.monotonic() - start) * 1000, 2)

                if response.status_code == 200:
                    self.flags = response.json().get("flags", {})

                    if self.flags.get("maintenance_mode"):
                        self.state = BotState.DEGRADED
                    else:
                        self.state = BotState.CONNECTED
                    logger.info(f"Heartbeat ok: latency={latency}ms")

                elif response.status_code == 401:
                    logger.warning("Heartbeat 401: re-handshaking")
                    self.session_token = None
                    self.state = BotState.OFFLINE
                    await self.handshake()

                else:
                    self.state = BotState.DEGRADED

            except httpx.RequestError as e:
                logger.error(f"Heartbeat error: {e}")
                self.state = BotState.DEGRADED

    def start_heartbeat(self):
        if not self._heartbeat_task or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def stop_heartbeat(self):
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

    # helper method to make authenticated api calls with automatic rehandshake
    async def api_call(self, route, data):
        if not self.session_token:
            if not await self.handshake():
                return None

        headers = {"x-bot-session": self.session_token}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(f"{self.base_url}/{route}", json=data, headers=headers)

            # auto rehandshake on 401
            if response.status_code == 401:
                if await self.handshake():
                    headers["x-bot-session"] = self.session_token
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        response = await client.post(f"{self.base_url}/{route}", json=data, headers=headers)

            return response

        except httpx.RequestError as e:
            logger.error(f"API call error on /{route}: {e}")
            self.state = BotState.DEGRADED
            return None
        
    # check if bot is allowed to execute commands based on current state and flags
    def is_command_allowed(self):
        if self.state == BotState.OFFLINE:
            return False
        if self.flags.get("maintenance_mode"):
            return False
        return True


control_plane = BotControlPlane()
