# Bot Handshake Protocol

## Overview
The Discord bot and FastAPI backend authenticate via a shared secret handshake at startup. Once connected, the bot sends heartbeats to maintain its session and receive system information. If the backend goes down or revokes the session, the bot automatically degrades and then rehandshakes when the backend recovers.

## Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/bot/handshake` | Shared secret in body | Establish session |
| POST | `/bot/heartbeat` | `x-bot-session` header | Maintain session and receive flags |
| GET | `/bot/status` | `x-bot-session` header | View active bot sessions |

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `BOT_SHARED_SECRET` | Shared secret for handshake authentication | `fallback-secret` |
| `DISCORD_TOKEN` | Discord bot token | Required |

## Configuration Constants

Defined in `src/utlis/botProtocolConfig.py`:

| Constant | Value | Purpose |
|----------|-------|---------|
| `SESSION_TTL` | 10 minutes | Session token lifetime |
| `HEARTBEAT_INTERVAL` | 30 seconds | Time between heartbeats |
| `FLAGS` | `{maintenance_mode, read_only, version_mismatch}` | System flags broadcast to bot |

## Bot States

The bot operates in one of three states defined in `BotState` enum:

| State | Meaning | 
|-------|---------|
| `CONNECTED` | Handshake successful, heartbeats are working |
| `DEGRADED` | API responded but maintenance_mode is on or a heartbeat/API error occurred |
| `OFFLINE` | Handshake failed or session revoked |


## Failure States & Recovery

### Handshake Failure
- Bot retries up to 5 times with exponential backoff (1s, 2s, 4s, 8s, 16s)
- After all retries fail, bot enters `OFFLINE` state
- Heartbeat loop continues to retry handshake every 30s

### Session Revocation (401)
- Triggered when another handshake for the same `bot_id` creates a new session
- Bot detects 401 on next heartbeat or API call
- Automatically re-handshakes to get a new token

### Session Expiry
- Sessions expire after 10 minutes without heartbeat
- Middleware returns 401, bot re-handshakes


## Error Codes

Defined in `BotProtocolErrorCode`:

| Code | When |
|------|------|
| `INVALID_SECRET` | Handshake with wrong shared secret |
| `SESSION_EXPIRED` | Token past TTL |
| `SESSION_REVOKED` | Session explicitly revoked (re-handshake by same bot_id) |
| `INVALID_SESSION_TOKEN` | Unknown token |
| `BOT_ID_MISMATCH` | Heartbeat bot_id doesn't match session's bot_id |
| `API_MAINTENANCE` | Handshake during maintenance mode |


## File Map

| File | Purpose |
|------|---------|
| `src/backend/botRouter.py` | API endpoints (handshake, heartbeat, status) |
| `src/backend/botMiddleware.py` | Session validation middleware |
| `src/backend/sessionManager.py` | Session store |
| `src/backend/modelsPydantic.py` | Request/response models and error codes |
| `src/utlis/botProtocolConfig.py` | Protocol configuration (TTL, interval, secret, flags) |
| `src/community_apps/botControlPlane.py` | Bot side state machine and control plane client |
| `src/community_apps/getMessageDiscord.py` | Discord bot commands with control plane integration |
| `src/community_apps/discordHelper.py` | Discord helper using control plane for API calls |
