import os
from dotenv import load_dotenv

# Load .env file if it exists (for local development)
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_PATH = os.getenv("DB_PATH", "./local_chromadb")  # Default for CI
PROFANITY_THRESHOLD = float(os.getenv("PROFANITY_THRESHOLD", 0.7))
DISTANCE_THRESHOLD = float(os.getenv("DISTANCE_THRESHOLD", 0.25))

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN is not set in environment variables or .env file")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in environment variables or .env file")

if not DB_PATH:
    raise ValueError("DB_PATH is not set in environment variables or .env file")