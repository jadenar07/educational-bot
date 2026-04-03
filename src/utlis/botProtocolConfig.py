from datetime import timedelta

SESSION_TTL = timedelta(minutes=10)
HEARTBEAT_INTERVAL = 30 

FLAGS = {
    "maintenance_mode": False,
    "read_only": False,
    "version_mismatch": False
}