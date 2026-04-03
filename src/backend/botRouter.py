import logging
from fastapi import APIRouter, Header, HTTPException

from backend.modelsPydantic import (
    BotHandshakeRequest, BotHandshakeResponse,
    BotHeartbeatRequest, BotHeartbeatResponse,
    BotProtocolErrorCode, BotProtocolErrorResponse,
)
from backend.sessionManager import SessionManager
from utlis.botProtocolConfig import BOT_SHARED_SECRET, HEARTBEAT_INTERVAL, FLAGS

logger = logging.getLogger(__name__)
router = APIRouter()
session_manager = SessionManager()


@router.post("/bot/handshake", response_model=BotHandshakeResponse)
async def handshake(request: BotHandshakeRequest):

    if request.shared_secret != BOT_SHARED_SECRET:
        logger.warning(f"Handshake failed: invalid secret for bot_id={request.bot_id}")

        raise HTTPException(status_code=401, detail=BotProtocolErrorResponse(
            error_code=BotProtocolErrorCode.INVALID_SECRET,
            message="Invalid shared secret",
        ).model_dump())

    if FLAGS.get("maintenance_mode"):
        logger.info(f"Handshake rejected: maintenance mode for bot_id={request.bot_id}")

        raise HTTPException(status_code=503, detail=BotProtocolErrorResponse(
            error_code=BotProtocolErrorCode.API_MAINTENANCE,
            message="API is in maintenance mode",
            retry_after=60,
        ).model_dump())

    token = session_manager.create_session(request.bot_id, request.version, request.capabilities)
    session = session_manager.get_session(token)
    logger.info(f"Handshake success for bot_id={request.bot_id}")

    return BotHandshakeResponse(
        session_token=token,
        expires_at=session.expires_at,
        interval=HEARTBEAT_INTERVAL,
        flags=FLAGS,
    )


@router.post("/bot/heartbeat", response_model=BotHeartbeatResponse)
async def heartbeat(request: BotHeartbeatRequest, x_bot_session: str = Header(...)):

    if not session_manager.validate_session(x_bot_session):
        logger.warning(f"Heartbeat rejected: invalid session for bot_id={request.bot_id}")

        raise HTTPException(status_code=401, detail=BotProtocolErrorResponse(
            error_code=BotProtocolErrorCode.INVALID_SESSION_TOKEN,
            message="Session invalid or expired. Re-handshake required.",
        ).model_dump())

    session = session_manager.get_session(x_bot_session)
    if session.bot_id != request.bot_id:
        logger.warning(f"Heartbeat rejected: bot_id mismatch for token_bot={session.bot_id} req_bot={request.bot_id}")

        raise HTTPException(status_code=403, detail=BotProtocolErrorResponse(
            error_code=BotProtocolErrorCode.INVALID_SESSION_TOKEN,
            message="bot_id does not match session",
        ).model_dump())

    session_manager.update_heartbeat(x_bot_session, request.latency, request.stats)
    logger.info(f"Heartbeat ok: bot_id={request.bot_id} latency={request.latency}ms")

    return BotHeartbeatResponse(bot_id=request.bot_id, flags=FLAGS)


@router.get("/bot/status")
async def status():
    active = session_manager.get_active_sessions()
    return {
          "active_bots": [
            {
                "bot_id": s.bot_id,
                "version": s.version,
                "last_heartbeat": s.last_heartbeat,
                "last_latency": s.last_latency,
            }
            for s in active.values()
        ],
    }
