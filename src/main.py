import asyncio, uvicorn, sys, os, discord, subprocess
from discord.ext import commands
from community_apps.getMessageDiscord import DiscordBot
from backend.app import app as fastapi_app
from router.RouteMap import ThreadSafeMap
from community_apps.discordHelper import get_from_app
from utlis.config import DISCORD_TOKEN
import httpx
from router.utterances import UTTERANCES

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

# Function to run FastAPI server
async def run_fastapi():
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

# Function to run the Discord bot
async def run_discord_bot():
    await bot.start(DISCORD_TOKEN)

async def wait_for_backend(timeout=10):
    start = asyncio.get_event_loop().time()
    while True:
        try:
            resp = await get_from_app("health")
            if resp.status_code == 200:
                return
        except Exception:
            pass

        if asyncio.get_event_loop().time() - start > timeout:
            raise RuntimeError("Backend never became ready")

        await asyncio.sleep(0.5)


# Main function to run both FastAPI and Discord bot concurrently
async def main():
    routes = ThreadSafeMap()

    fastapi_task = asyncio.create_task(run_fastapi())

    await wait_for_backend()

    response = await get_from_app("collections")
    if not response or response.status_code != 200:
        raise RuntimeError("Failed to load collections from backend")

    collections_data = response.json()
    collections = collections_data.get("collections", collections_data)

    if isinstance(collections, list):
        for collection in collections:
            name = collection.get("name")
            description = collection.get("description")

            if not name or not description:
                continue
            utterances = await UTTERANCES.get(name) or []
            await routes.set(name, utterances)

    # Send the routes map to backend to set up semantic router
    async with httpx.AsyncClient() as client:
        await client.post("http://localhost:8000/setup_routes", json=routes._map)

    discord_bot.set_routes(routes)

    discord_task = asyncio.create_task(run_discord_bot())

    # Run both tasks concurrently
    await asyncio.gather(fastapi_task, discord_task)

    # Main instance of the map

    

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

