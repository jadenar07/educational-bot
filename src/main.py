import asyncio, uvicorn, sys, os, discord, subprocess
from discord.ext import commands
from community_apps.getMessageDiscord import DiscordBot
from backend.app import app as fastapi_app
import httpx
import logging
from utlis.config import DISCORD_TOKEN


# temp
from databases.chroma.crudChroma import CRUD

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Define bot and command prefix
'''could use Intents.all() instead of Intents.default()'''
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Initialize your Discord bot class 
discord_bot = DiscordBot(bot)
FASTAPI_URL= "http://127.0.0.1:8000"

@bot.event
async def on_ready():
    """This is Triggered when the bot successfully boots up. Runs the Batch Sync."""
    logging.info(f"Logged in as {bot.user}. Starting batch user sync...")
    
    users_to_sync = []
    
    # Loop through all members in all servers the bot is connected to
    for guild in bot.guilds:
        for member in guild.members:
            if not member.bot: # Ignore other bots
                users_to_sync.append({
                    "username": str(member.id),
                    "email": f"{member.id}@discord.local",
                    "role": "student",
                    "default_collection": "general"
                })
    
    # Send the batch to FastAPI
    if users_to_sync:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{FASTAPI_URL}/api/users/batch", 
                    json=users_to_sync,
                    timeout=30.0 
                )
                if response.status_code == 200:
                    logging.info(f"Batch sync complete! Synced {len(users_to_sync)} users.")
                else:
                    logging.error(f"Batch sync returned status: {response.status_code}")
            except Exception as e:
                logging.error(f"Batch sync failed to connect to API: {e}")


@bot.event
async def on_member_join(member):
    """This is Triggered automatically when a new user joins the Discord server."""
    logging.info(f"New member joined: {member.name}. Sending to API...")
    
    if member.bot:
        return # Don't register other bots
        
    user_payload = {
        "username": str(member.id),
        "email": f"{member.id}@discord.local", 
        "role": "student", 
        "default_collection": "general"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{FASTAPI_URL}/api/users", json=user_payload)
            if response.status_code == 200:
                logging.info(f"Successfully registered {member.name} in PostgreSQL.")
            else:
                logging.error(f"Failed to register user. Status: {response.status_code}")
        except Exception as e:
            logging.error(f"Could not connect to FastAPI backend: {e}")



# Function to run FastAPI server
async def run_fastapi():
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8000, log_level="info", reload=True)
    server = uvicorn.Server(config)
    await server.serve()

# Function to run the Discord bot
async def run_discord_bot():
    await bot.start(DISCORD_TOKEN)

# Main function to run both FastAPI and Discord bot concurrently
async def main():
    fastapi_task = asyncio.create_task(run_fastapi())
    discord_task = asyncio.create_task(run_discord_bot())

    # Run both tasks concurrently
    await asyncio.gather(fastapi_task, discord_task)

# Entry point
if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print("Shutting down...")


# async def load_pdfs():
#     # print current working directory
#     crud = CRUD()
#     await crud.save_pdfs("./src/services/pdf_files", "course_materials")


# if __name__ == "__main__":
#     asyncio.run(load_pdfs())


'''
this, along with the !update function, should be moved to a separate file
responsible for model initialization
'''

