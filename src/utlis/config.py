import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_PATH = os.getenv("DB_PATH")
PROFANITY_THRESHOLD = float(os.getenv("PROFANITY_THRESHOLD"))
DISTANCE_THRESHOLD = float(os.getenv("DISTANCE_THRESHOLD"))

POSTGRES_USER = ("POSTGRES_USER","postgres")
POSTGRES_PASSWORD = ("POSTGRES_PASSWORD","your_password")
POSTGRES_HOST = os.getenv("POSTGRES_HOST","localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT","5432")
POSTGRES_NAME = ("POSTGRES_NAME","educational_bot")

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

if not POSTGRES_USER:
    raise ValueError("POSTGRES_USER is not set in .env file")

if not POSTGRES_PASSWORD:
    raise ValueError("POSTGRES_PASSWORD is not set in .env file")

if not POSTGRES_HOST:
    raise ValueError("POSTGRES_HOST is not set in .env file")

if not POSTGRES_PORT:
    raise ValueError("POSTGRES_PORT is not set in .env file")

if not POSTGRES_NAME:
    raise ValueError("POSTGRES_NAME is not set in .env file")
 
 
 