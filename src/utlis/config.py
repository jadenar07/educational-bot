import os
from dotenv import load_dotenv

# Load .env file if it exists (for local development)
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_PATH = os.getenv("DB_PATH")
PROFANITY_THRESHOLD = float(os.getenv("PROFANITY_THRESHOLD","0.7"))
DISTANCE_THRESHOLD = float(os.getenv("DISTANCE_THRESHOLD","0.25"))

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_NAME = os.getenv("POSTGRES_DB", "educational-bot")

# Data directory for persisting utterances and other runtime data
# Defaults to XDG_DATA_HOME, then user's home/.local/share/educational-bot, then ./data
DATA_DIR = os.getenv(
    "DATA_DIR",
    os.getenv(
        "XDG_DATA_HOME",
        os.path.join(os.path.expanduser("~"), ".local", "share", "educational-bot")
    )
)

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

def require_openai_api_key() -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for OpenAI operations")
    return OPENAI_API_KEY


def require_discord_token() -> str:
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is required to start the Discord bot")
    return DISCORD_TOKEN


def require_db_path() -> str:
    if not DB_PATH:
        raise RuntimeError("DB_PATH is required for database operations")
    return DB_PATH