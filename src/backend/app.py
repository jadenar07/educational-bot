# app.py

import httpx, uvicorn, chromadb, time

from typing import Union,List,Any
import sys
import os
import logging
from fastapi import FastAPI,Depends, HTTPException  
from backend.middleware.role_middleware import RoleMiddleware
from starlette.requests import Request

# from router.semanticRouter import process_query
from router.semanticRouter import create_router
from backend.modelsPydantic import (
    QueryResponse, QueryRequest, UpdateChannelInfo, UpdateChatHistory, 
    UpdateGuildInfo, UpdateMemberInfo, UpdateChannelList
)
from services.queryLangchain import fetchGptResponse
from services.nlpTools import TextProcessor
from databases.chroma.crudChroma import CRUD
from databases.chroma.modelsChroma import (
    generate_embedding, ChatHistory, GuildInfo, ChannelInfo, MemberInfoChannel, ChannelList
)
from databases.postgres.crudPostgres import PostgresCRUD
from utlis.prompts import PROMPTS
from .modelsPydantic import UserCreate, UserResponse

# This tells FastAPI how to get and return your Postgres connection
def get_db():
    db = postgres_crud.get_connection()
    try:
        yield db
    finally:
        postgres_crud.return_connection(db)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()
crud = CRUD()
postgres_crud = PostgresCRUD()
semantic_router = create_router(crud)
app.add_middleware(RoleMiddleware, audience="your-audience")

@app.post('/channel_query') #, response_model=QueryResponse
async def channel_query(request: QueryRequest):
    try:
        query_embedding = await generate_embedding(request.query)
        collection_name = f"chat_history_{request.channel_id}"
        relevant_docs = await crud.get_data_by_similarity(collection_name, query_embedding, top_k=5)
        channel_info = await crud.get_data_by_id(f"channel_info_{request.guild_id}", [request.channel_id])

        content = relevant_docs.get('documents')[0]
        data = channel_info.get('metadatas')[0]

        logging.info(f"Relevant messages: {content}")
        logging.info(f"Channel info: {data}")

        # combine the relevant messages and channel info
        combined_data = {
            'relevant_messages': content,
            'channel_info': channel_info
        }

        answer = await fetchGptResponse(request.query, PROMPTS['channel_summarizer'], combined_data)
        logging.info(f"Answer: {answer}")
        return {'answer': answer}

    except Exception as e:
        logging.error(f"Error with channel related question: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/resource_query') #, response_model=QueryResponse
async def resource_query(request: QueryRequest):
    try:
        # response = await process_query(crud, request)
        response = await semantic_router.process_query(request)

        if response is None:
            raise ValueError("Process_query returned none")

        return response

    except Exception as e:
        logging.error(f"Error with course material related question: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    
@app.post('/update_chat_history')
async def update_chat_history(request: UpdateChatHistory):
    all_messages = request.all_messages
    total_messages = sum([len(messages) for messages in all_messages.values()])
    chat_history = []
    for _, channel_messages in all_messages.items():
        for message in channel_messages:
            message_info = {
                "channel_id": message.channel_id,
                "channel_name": message.channel_name,
                "message_id": message.message_id,
                "author": message.author,
                "author_id": message.author_id,
                "content": message.content,
                "timestamp": message.timestamp,
                "profanity_score": message.profanity_score
            }
            # Pass the chat history to modelsChroma to get document and embedding
            try:
                chat_info = ChatHistory(message_info)
                document, embedding = await chat_info.to_document()
            except Exception as e:
                logging.error(f"Error with updating chat history: {e}")
            
            chat_history.append({
                "collection_name": f"chat_history_{message_info.get('channel_id')}",
                "document": document,
                "embedding": embedding
            })

    # Save chat history to Chromadb
    try:
        await crud.save_to_db(chat_history)
    except Exception as e:
        logging.error(f"Error with saving chat history: {e}")

    logging.info(f"Update complete, {total_messages} messages from {len(all_messages)} channels are loaded to the database.")
    return {"status": "Update complete"}

@app.post('/update_info')
async def update_info(request: Union[UpdateGuildInfo, UpdateChannelInfo, UpdateMemberInfo, UpdateChannelList]):
    try:
        if isinstance(request, UpdateGuildInfo):
            collection_name = "guild_info"
            info = GuildInfo(request.model_dump())

        elif isinstance(request, UpdateChannelInfo):
            collection_name = f"channel_info_{request.guild_id}"
            info = ChannelInfo(request.model_dump())
        
        elif isinstance(request, UpdateMemberInfo):
            collection_name = f"member_info_{request.channel_id}"
            info = MemberInfoChannel(request.model_dump())
        
        elif isinstance(request, UpdateChannelList):
            collection_name = f"channel_list_{request.guild_id}"
            info = ChannelList(request.model_dump())
        
        document, embedding = await info.to_document()
        data = {
            "collection_name": collection_name,
            "document": document,
            "embedding": embedding
        }
        await crud.save_to_db([data])

    except Exception as e:
        logging.error(f"Error with updating guild info: {e}")

    logging.info(f"Info updated for {collection_name}")
    return {"status": "Update complete"}

@app.post('/load_course_materials')
async def load_course_materials():
    file_path = "./data/pdf_files"
    collection_name = "course_materials"
    try:
        data = await crud.save_pdfs(file_path, collection_name)

        # save the data to the database in chunks of ten documents
        chunk_size = 10
        for i in range(0, len(data), chunk_size):
            await crud.save_to_db(data[i:i+chunk_size])

        return {"message": "PDFs loaded successfully."}
    
    except Exception as e:
        logging.error(f"app.py: Error with loading PDFs: {e}")
        return {"message": "Failed to load PDFs."}
@app.post("/api/users", response_model = UserResponse)
async def create_discord_user(user_data: UserCreate, db: Any = Depends(get_db)):
    existing_user = postgres_crud.get_user(db=db, username=user_data.username)
    #Check if user already exists
    if existing_user.get("success") == True:
        logging.info(f"User {user_data.username} already exists. Returning existing record.")
        # Return ONLY the "data" dictionary, which holds the real user info FastAPI wants
        return existing_user["data"]
    #Use the class method to create the user
    new_user = postgres_crud.create_user(
        db=db, 
        username=user_data.username,
        email=user_data.email,
        role=user_data.role,
        default_collection=user_data.default_collection
    )
    if new_user.get("success") == True:
        logging.info(f"Successfully created new user: {user_data.username}")
        # Your create_user function only returns the new ID inside "data". 
        # To satisfy UserResponse, we quickly fetch the full user object we just created!
        new_user_id = new_user["data"]
        return postgres_crud.get_user(db=db, user_id=new_user_id)["data"]
    
    # 4. If creation failed for some reason, throw a proper HTTP error
    raise HTTPException(status_code=400, detail=new_user.get("error", "Failed to create user"))
@app.get("/api/users/{username}", response_model=UserResponse)
async def get_discord_user(username: str, db: Any = Depends(get_db)):
    """Fetches a specific user by their Discord username."""
    user = postgres_crud.get_user(db=db, username=username)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # get_user might return a list of candidates based on your code, so we grab the first one
    return user[0] if isinstance(user, list) else user


@app.post("/api/users/batch", response_model=List[UserResponse])
async def create_users_batch(users_data: List[UserCreate], db: Any = Depends(get_db)):
    """Handles creating multiple users at once (Batch Operations)."""
    processsed_users = []
    
    for user_data in users_data:
        existing_user = postgres_crud.get_user(db=db, username=user_data.username)
        
        if existing_user.get("success") == True:
            # If it returns a list, grab the first candidate
            processsed_users.append(existing_user["data"])
        else:
            new_user = postgres_crud.create_user(
                db=db, 
                username=user_data.username,
                email=user_data.email,
                role=user_data.role,
                default_collection=user_data.default_collection
            )
            if new_user.get("success")==True:
                new_user_id = new_user["data"]
                full_new_user = postgres_crud.get_user(db=db, user_id= new_user_id)
                if full_new_user.get("success") == True: 
                    processsed_users.append(full_new_user["data"])
            else:
                logging.error(f"Failed to create user {user_data.username}: {new_user.get('error')}")
            
    logging.info(f"Batch processed {len(processsed_users)} out of {len(users_data)} users.")
    return processsed_users
@app.post("/query")
async def query_endpoint(request: Request, body: QueryRequest):
    user_role = getattr(request.state, "user_role", "student")  # fallback to student
    response = await semantic_router.process_query(body, role=user_role)
    return response

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
