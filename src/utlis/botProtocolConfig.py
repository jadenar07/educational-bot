from datetime import timedelta
import os

SESSION_TTL = timedelta(minutes=10)
HEARTBEAT_INTERVAL = 30 
BOT_SHARED_SECRET = os.getenv("BOT_SHARED_SECRET", "fallback-secret")

FLAGS = {
    "maintenance_mode": False,
    "read_only": False,
    "version_mismatch": False
}