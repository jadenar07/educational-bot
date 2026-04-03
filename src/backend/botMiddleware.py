import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from backend.modelsPydantic import BotProtocolErrorCode

logger = logging.getLogger(__name__)


class BotSessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, session_manager):
        super().__init__(app)
        self.session_manager = session_manager

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path.startswith("/bot") and (path != "/bot/handshake") and (path != "/bot/status"):
            x_bot_session = request.headers.get("x-bot-session")
            
            if not x_bot_session:
                logger.warning(f"Missing x-bot-session header for path={path}")
                return JSONResponse(status_code=401, content={
                    "error_code": BotProtocolErrorCode.INVALID_SESSION_TOKEN,
                    "message": "Missing x-bot-session header",
                })
            
            if not self.session_manager.validate_session(x_bot_session):
                logger.warning(f"Invalid/expired session for path={path}")
                return JSONResponse(status_code=401, content={
                    "error_code": BotProtocolErrorCode.SESSION_EXPIRED,
                    "message": "Session invalid or expired. Re-handshake required.",
                })

        return await call_next(request)
