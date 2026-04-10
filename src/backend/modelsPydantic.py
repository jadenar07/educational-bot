# modelsPydantic.py
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class QueryRequest(BaseModel):
    guild_id: int
    channel_id: int
    query: str

class QueryResponse(BaseModel):
    answer: str

class Message(BaseModel):
    channel_id: int
    channel_name: str
    message_id: int
    author: str
    author_id: int
    content: str
    timestamp: str
    profanity_score: float

class UpdateChatHistory(BaseModel):
    all_messages: Dict[int, List[Message]]

class UpdateGuildInfo(BaseModel):
    guild_id: int
    guild_name: str
    guild_purpose: Optional[str] = "null"
    number_of_channels: int
    number_of_members: int
    profanity_score: Optional[float] = 0.0

class UpdateChannelInfo(BaseModel):
    channel_id: int
    guild_id: int
    channel_name: str
    channel_purpose: Optional[str] = "null"
    number_of_messages: int
    number_of_members: int
    last_message_timestamp: Optional[str] = "null"
    first_message_timestamp: Optional[str] = "null"
    profanity_score: Optional[float] = 0.0

class UpdateMemberInfo(BaseModel):
    user_id: int
    channel_id: int
    channel_list_id: str
    user_name: str
    user_description: Optional[str] = "null"
    message_sent: int
    profanity_score: Optional[float] = 0.0

class UpdateChannelList(BaseModel):
    user_id: int
    user_name: str
    guild_id: int
    channel_ids: List[int]


# Bot Models 
class BotHandshakeRequest(BaseModel):
    bot_id: str #incase instance id has words in it
    version: str
    capabilities: List[str] 
    shared_secret: str


class BotHandshakeResponse(BaseModel):
    session_token: str
    expires_at: datetime
    interval: int  # recommended heartbeat interval in seconds
    flags: Dict[str, bool] = Field(default_factory=dict)

# bot heartbeat model request
class BotHeartbeatRequest(BaseModel):
    bot_id: str
    latency: float
    stats: Optional[Dict[str, Any]] = None

# bot heartbeat model resposne
class BotHeartbeatResponse(BaseModel):
    bot_id: str
    flags: Dict[str, bool] = Field(default_factory=dict)
    required_version: Optional[str] = None


# error codes for handshake/heartbeat failures
class BotProtocolErrorCode:
    INVALID_SECRET = "INVALID_SECRET"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_REVOKED = "SESSION_REVOKED"
    INVALID_SESSION_TOKEN = "INVALID_SESSION_TOKEN"
    BOT_ID_MISMATCH = "BOT_ID_MISMATCH"
    BOT_VERSION_MISMATCH = "BOT_VERSION_MISMATCH"
    API_MAINTENANCE = "API_MAINTENANCE"
    API_UNAVAILABLE = "API_UNAVAILABLE"
    HEARTBEAT_TIMEOUT = "HEARTBEAT_TIMEOUT"

# the reponse model for errors in the bot protocol
class BotProtocolErrorResponse(BaseModel):
    error_code: str
    message: str
    retry_after: Optional[int] = None