from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import uuid
import json
import os
import logging

from utlis.botProtocolConfig import SESSION_TTL

logger = logging.getLogger(__name__)

SESSIONS_FILE = "local_chromadb/sessions.json"


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
        self._load_from_file()

    # load sessions from JSON file in db on startup
    def _load_from_file(self):
        
        if not os.path.exists(SESSIONS_FILE):
            return
        
        try:
            with open(SESSIONS_FILE, "r") as f:
                data = json.load(f)
            
            now = datetime.now()
            for token, session_dict in data.items():
                expires_at = datetime.fromisoformat(session_dict["expires_at"])
                
                # Skip expired sessions
                if expires_at < now:
                    continue
                
                session = SessionData(
                    bot_id=session_dict["bot_id"],
                    version=session_dict["version"],
                    capabilities=session_dict["capabilities"],
                    expires_at=expires_at,
                )

                session.created_at = datetime.fromisoformat(session_dict["created_at"])

                if session_dict.get("last_heartbeat"):
                    session.last_heartbeat = datetime.fromisoformat(session_dict["last_heartbeat"])

                session.last_latency = session_dict.get("last_latency")
                session.stats = session_dict.get("stats", {})
                session.revoked = session_dict.get("revoked", False)
                
                self.sessions[token] = session
        except Exception as e:
            logger.warning(f"Could not load sessions from file: {e}")
    def _save_to_file(self):
        """Save sessions to JSON file"""
        try:
            os.makedirs(os.path.dirname(SESSIONS_FILE) or ".", exist_ok=True)
            
            data = {}
            for token, session in self.sessions.items():
                data[token] = {
                    "bot_id": session.bot_id,
                    "version": session.version,
                    "capabilities": session.capabilities,
                    "created_at": session.created_at.isoformat(),
                    "expires_at": session.expires_at.isoformat(),
                    "last_heartbeat": session.last_heartbeat.isoformat() if session.last_heartbeat else None,
                    "last_latency": session.last_latency,
                    "stats": session.stats,
                    "revoked": session.revoked,
                }
            
            with open(SESSIONS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save sessions to file: {e}")


    def create_session(self, bot_id: str, version: str, capabilities: list[str]) -> str:
        # revoke any existing session for this bot_id to prevent multiple active sessions per bot
        for token, session in list(self.sessions.items()):
            if session.bot_id == bot_id and not session.revoked:
                session.revoked = True

        expires_at = datetime.now() + self.session_ttl
        session = SessionData(bot_id=bot_id, version=version, capabilities=capabilities, expires_at=expires_at)
        
        token = str(uuid.uuid4())
        self.sessions[token] = session
        
        self._save_to_file()
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
            self._save_to_file()
            return "expired"

        return "valid"


    def revoke_session(self, token: str):
        session = self.get_session(token)
        if session:
            session.revoked = True
            self._save_to_file()


    def update_heartbeat(self, token: str, latency: float, stats: Optional[Dict[str, Any]] = None):
        session = self.get_session(token)
        if not session:
            return

        session.last_heartbeat = datetime.now()
        session.last_latency = latency
        # refresh session expiration on heartbeat to keep active session alive
        session.expires_at = datetime.now() + self.session_ttl

        if stats:
            session.stats.update(stats)
        
        self._save_to_file()


    def cleanup_expired_sessions(self):
        now = datetime.now()
        expired_tokens = [token for token, session in self.sessions.items() if session.expires_at < now]

        for token in expired_tokens:
            self.sessions.pop(token, None)
        
        if expired_tokens:
            self._save_to_file()


    def get_active_sessions(self) -> Dict[str, SessionData]:
        return {token: session for token, session in self.sessions.items()
            if not session.revoked and session.expires_at > datetime.now()
        }