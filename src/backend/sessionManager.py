from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import uuid

from utlis.botProtocolConfig import SESSION_TTL


class SessionData:
    def __init__(self, bot_id: str, version: str, capabilities: list[str], expires_at: datetime):
        self.bot_id = bot_id
        self.version = version
        self.capabilities = capabilities
        self.created_at = datetime.now()
        self.expires_at = expires_at
        self.last_heartbeat: Optional[datetime] = None
        self.last_latency: Optional[float] = None
        self.stats: Dict[str, Any] = {}
        self.revoked: bool = False


class SessionManager:
    def __init__(self, session_ttl: timedelta = SESSION_TTL):
        self.sessions: Dict[str, SessionData] = {}
        self.session_ttl = session_ttl


    def create_session(self, bot_id: str, version: str, capabilities: list[str]) -> str:
        # revoke any existing session for this bot_id to prevent multiple active sessions per bot
        for token, session in list(self.sessions.items()):
            if session.bot_id == bot_id and not session.revoked:
                session.revoked = True

        expires_at = datetime.now() + self.session_ttl
        session = SessionData(bot_id=bot_id, version=version, capabilities=capabilities, expires_at=expires_at)
        
        token = str(uuid.uuid4())
        self.sessions[token] = session

        return token


    def get_session(self, token: str) -> Optional[SessionData]:
        return self.sessions.get(token)


    def validate_session(self, token: str) -> str:
        session = self.get_session(token)

        if not session:
            return "invalid"
        if session.revoked:
            return "revoked"
        if session.expires_at < datetime.now():
            self.sessions.pop(token, None)
            return "expired"

        return "valid"


    def revoke_session(self, token: str):
        session = self.get_session(token)
        if session:
            session.revoked = True


    def update_heartbeat(self, token: str, latency: float, stats: Optional[Dict[str, Any]] = None):
        session = self.get_session(token)
        if not session:
            return

        session.last_heartbeat = datetime.now()
        session.last_latency = latency

        if stats:
            session.stats.update(stats)


    def cleanup_expired_sessions(self):
        now = datetime.now()
        expired_tokens = [token for token, session in self.sessions.items() if session.expires_at < now]

        for token in expired_tokens:
            self.sessions.pop(token, None)


    def get_active_sessions(self) -> Dict[str, SessionData]:
        return {token: session for token, session in self.sessions.items()
            if not session.revoked and session.expires_at > datetime.now()
        }