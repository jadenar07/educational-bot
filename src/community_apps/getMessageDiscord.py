import json, os, discord, logging, httpx, time, asyncio
from discord.ext import commands
from discord import app_commands
from profanity_check import predict, predict_prob

from utlis.config import DISCORD_TOKEN, PROFANITY_THRESHOLD
from community_apps.discordHelper import (
    send_to_app, update_message, get_channels_and_messages, message_filter, available_commands,
    store_guild_info, store_channel_info, store_member_info, store_channel_list, get_parameters,
    profanity_checker, get_from_app
)
from backend.modelsPydantic import Message, UpdateChatHistory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class DiscordBot:
    def __init__(self, bot):
        self.bot = bot
        self.tree = bot.tree
        self.approved_channels = set()
        self.message_global = None
        self.attachments = None
        self.setup_bot()

    def setup_bot(self):
        @self.bot.event
        async def on_ready():
            await self.tree.sync()
            logging.info(f'We have logged in as {self.bot.user}')

        @self.bot.event
        async def on_message(message):
            if message.author == self.bot.user:
                return

            if message.content:
                logging.info(f"Direct content access: {message.content}")
                self.message_global = message       

                try:
                    profanity_scores = await profanity_checker([message.content])
                    profanity_score = profanity_scores[0]
                    
                    if profanity_score > PROFANITY_THRESHOLD:
                        try:
                            await message.delete()
                            warning_message = f"{message.author.mention} your message is removed due to high profanity score: {int(profanity_score*100)}"
                            await message.channel.send(warning_message)
                        except Exception as e:
                            logging.error(f"Error with deleting message: {e}")

                    if profanity_score > PROFANITY_THRESHOLD or await message_filter(message, self.bot.user):
                        message_info = await get_parameters(message)
                        asyncio.create_task(update_message(message_info, self.bot.user))

                except Exception as e:
                    logging.error(f"Error with updating parameters: {e}")

            if message.content.startswith('!'): 
                await message.channel.send("Use / to access commands, and /info to see available commands.")
            
            await self.bot.process_commands(message)


        @self.tree.command(name="setup", description="Use ONCE to set up the server information and update chat history")
        async def setup(interaction: discord.Interaction):
            await self.update_server_info(interaction)

        @self.tree.command(name="info", description="Show available commands")
        async def info(interaction: discord.Interaction):
            await interaction.response.send_message(await available_commands())

        @self.tree.command(name="invite", description="Invite the bot to the channel")
        async def invite(interaction: discord.Interaction):
            self.approved_channels.add(interaction.channel.id)
            await interaction.response.send_message(f"Bot invited to this channel: {interaction.channel.name}")
            await interaction.followup.send(await available_commands())

        @self.tree.command(name="remove", description="Remove the bot from the channel")
        async def remove(interaction: discord.Interaction):
            self.approved_channels.remove(interaction.channel.id)
            await interaction.response.send_message("Bot removed from this channel. \nType << /invite >> to add the bot back.")

        @self.tree.command(name="load", description="Use ONCE to load course materials from course website")
        async def load_pdf(interaction: discord.Interaction):
            await interaction.response.send_message("Loading PDFs from the course website...")
            response = await send_to_app("load_course_materials", data={})
            if response.status_code == 200:
                await interaction.followup.send("PDFs loaded successfully.")
            else:
                await interaction.followup.send("Failed to load PDFs.")
        
        @self.bot.command(name="upload")
        async def upload(ctx, collection: str):
            # Only respond to messages with attachments
            pdf_attachments = [
                a for a in ctx.message.attachments
                if a.content_type == "application/pdf" or a.filename.endswith(".pdf")
            ]
            if not pdf_attachments:
                await ctx.send("Please attach one or more PDF files to your message.")
                return

            files = []
            for attachment in pdf_attachments:
                file_bytes = await attachment.read()
                files.append(("files", (attachment.filename, file_bytes, "application/pdf")))

            form_data = {
                "collection_name": collection,
                "user": str(ctx.author.id)
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/upload_pdfs",
                    files=files,
                    data=form_data
                )

            if response.status_code == 200:
                await ctx.send("PDFs uploaded and processed successfully.")
            else:
                await ctx.send(f"Failed to upload PDFs: {response.text}")

        @self.tree.command(name="resource", description="Query for resources")
        @app_commands.describe(query="The query you want to ask")
        async def resource(interaction: discord.Interaction, query: str):
            await self.handle_query(interaction, 'resource_query', query)

        @self.tree.command(name="channel", description="Query for channel information")
        @app_commands.describe(query="The query you want to ask")
        async def channel(interaction: discord.Interaction, query: str):
            await self.handle_query(interaction, 'channel_query', query)
        
        @self.tree.command(name="create_collection", description="Create a collection to store material")
        @app_commands.describe(collection_name="The name for your material")
        async def create_collection(interaction: discord.Interaction, collection_name: str):
            
            response = await send_to_app('/collections', {'name': collection_name})
            if response and response.status_code == 200:
                await interaction.followup.send(f"Collection `{collection_name}` created successfully.")
            else:
                await interaction.followup.send(f"Failed to create collection `{collection_name}`.")

        @self.tree.command(name="get_collections", description="Retrieve all of the existing collections")
        async def get_collections(interaction: discord.Interaction):
            await interaction.response.send_message("Fetching collections...")  # Initial response
            response = await get_from_app('collections')
            if response and response.status_code == 200:
                collections_data = response.json()
                # If your backend returns {'collections': [...], 'total_count': ...}
                collections = collections_data.get('collections', collections_data)
                if isinstance(collections, list):
                    formatted = "\n".join(
                        [
                            f"**{c.get('name', 'Unnamed')}**"
                            + (f"\n  Description: {c.get('description')}" if c.get('description') else "")
                            + (f"\n  Docs: {c.get('document_count', 0)}" if 'document_count' in c else "")
                            for c in collections
                        ]
                    )
                else:
                    formatted = str(collections)
                await interaction.followup.send(f"**Collections:**\n{formatted}")
            else:
                await interaction.followup.send("Failed to retrieve collections.")
            
        @self.tree.command(name="get_collection_info", description="Retrieve all of the material of collection")
        @app_commands.describe(collection_name="The name for the collection")
        async def get_collection_info(interaction: discord.Interaction, collection_name: str):
            await interaction.response.send_message("Fetching collection...")  # Initial response
            response = await get_from_app(f'collections/{collection_name}')
            if response and response.status_code == 200:
                collection = response.json()
                if "error" in collection:
                    await interaction.followup.send(collection["error"])
                    return

                # Format the collection info nicely
                formatted = (
                    f"**Collection:** {collection.get('name', 'Unnamed')}\n"
                    f"{'**Description:** ' + collection['description'] if collection.get('description') else ''}\n"
                    f"**Docs:** {collection.get('document_count', 0)}\n"
                    f"{'**Created:** ' + str(collection['created_at']) if collection.get('created_at') else ''}\n"
                    f"{'**Metadata:** ' + str(collection['metadata']) if collection.get('metadata') else ''}"
                    f"{'**Doc_Info:** ' + str(collection['sample_documents']) if collection.get('sample_documents') else ''}\n"

                )

                await interaction.followup.send(formatted)
            else:
                await interaction.followup.send("Failed to retrieve collection info.")

    async def update_server_info(self, interaction: discord.Interaction):
        logging.info("Updating server information and chat history to ChromaDB...")
        guild = interaction.guild

        if not guild:
            logging.info("This command can only be used in a server.")
            await interaction.response.send_message("This command can only be used in a server.")
            return
        else:
            logging.info(f"Updating server information for {guild.name}")
            await interaction.response.send_message("Updating server information...")

        try:
            all_channels, all_messages = await get_channels_and_messages(guild, self.bot.user)
            await update_message(all_messages, self.bot.user)

            logging.info(f"There are a total of {len(all_channels)} channels in {guild.name}")
            member_channels = {}
            total_messages = 0
            score_sum = 0
            for channel in all_channels:
                channel_messages = all_messages[channel.id]
                channel_info = await store_channel_info(channel, guild.id, channel_messages)
                await send_to_app('update_info', channel_info)

                total_messages += channel_info['number_of_messages']
                score_sum += channel_info['profanity_score'] * channel_info['number_of_messages']

                logging.info(f"There are a total of {len(channel.members)} members in {channel.name}")
                for member in channel.members:
                    if member not in member_channels:
                        member_channels[member] = []

                    member_info = await store_member_info(channel, member, channel_messages, guild.id)

                    if member_info:
                        member_channels[member].append(channel)
                        await send_to_app('update_info', member_info)

            await interaction.followup.send("Channel and member information updated.")

            for member, channels in member_channels.items():
                logging.info(f"Updating channel list for {member.name}")
                channel_list = await store_channel_list(member, guild, channels)
                await send_to_app('update_info', channel_list)

            average_score = score_sum / total_messages if total_messages else 0
            guild_info = await store_guild_info(guild, average_score)
            await send_to_app('update_info', guild_info)

            logging.info("Guild information updated.")
            await interaction.followup.send("Guild information updated.")

        except Exception as e:
            logging.error(f"Error with updating server information: {e}")
            await interaction.followup.send("Failed to update server information.")

    async def handle_query(self, interaction: discord.Interaction, query_type, query): 
        current_author = interaction.user
        logging.info(f"Received {query_type} command")
        logging.info(f"Query: {query}")

        data = {
            'guild_id': interaction.guild.id,
            'channel_id': interaction.channel.id,
            'query': query
        }

        await interaction.response.send_message(f"/{query_type} {query}")
        
        # Calculate profanity score for the query
        profanity_scores = await profanity_checker([query])
        profanity_score = profanity_scores[0]

        # Process and update the message to the database
        message_info = await get_parameters({
            "content": query,
            "author": current_author,
            "channel": interaction.channel,
            "guild": interaction.guild,
            "id": interaction.id,
            "created_at": interaction.created_at
        })

        if profanity_score > PROFANITY_THRESHOLD:
            await interaction.followup.send(f"{current_author.mention} your query has a high profanity score: {int(profanity_score*100)}")
            return

        asyncio.create_task(update_message(message_info, self.bot.user))
        
        response = await send_to_app(query_type, data)

        if response.status_code == 200:
            if isinstance(response.json().get('answer', {}), str):
                result = response.json().get('answer', {})
                sources = []
            else:
                response_json = response.json()
                result = response_json.get('answer', {}).get('result', 'No result found')
                sources = response_json.get('answer', {}).get('sources', [])

            formatted_sources = '\n'.join([f"{source}" for source in sources])
            combined_result = result + (f"\n\nSources:\n{formatted_sources}" if sources else "")

            await interaction.followup.send(combined_result)
        else:
            await interaction.followup.send("Failed to get response from LLM.")

    async def process_pdf(self, interaction):
        pdf_attachments = [
            a for a in interaction.attachments
            if a.content_type == "application/pdf" or a.filename.endswith(".pdf")
        ]
        if not pdf_attachments:
            await interaction.response.send_message("Please attach a PDF file to upload.")
            return []

        return pdf_attachments



        
 