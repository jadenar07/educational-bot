import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_PATH = os.getenv("DB_PATH")
PROFANITY_THRESHOLD = float(os.getenv("PROFANITY_THRESHOLD"))
DISTANCE_THRESHOLD = float(os.getenv("DISTANCE_THRESHOLD"))

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

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN is not set in .env file")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in .env file")

if not DB_PATH:
    raise ValueError("DB_PATH is not set in .env file")

if not PROFANITY_THRESHOLD:
    raise ValueError("PROFANITY_THRESHOLD is not set in .env file")

if not DISTANCE_THRESHOLD:
    raise ValueError("DISTANCE_THRESHOLD is not set in .env file")