# app.py
import httpx, uvicorn, chromadb, time
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from typing import Union, List
from utlis.pdf_helpers import read_text_file
from database.modelsChroma import generate_embedding
import sys
import os
import logging

# from router.semanticRouter import process_query
from router.semanticRouter import create_router
from backend.modelsPydantic import (
    QueryResponse, QueryRequest, UpdateChannelInfo, UpdateChatHistory, 
    UpdateGuildInfo, UpdateMemberInfo, UpdateChannelList, CollectionCreate
)
from services.queryLangchain import fetchGptResponse
from services.nlpTools import TextProcessor
from database.crudChroma import CRUD
from database.modelsChroma import (
    generate_embedding, ChatHistory, GuildInfo, ChannelInfo, MemberInfoChannel, ChannelList
)
from utlis.prompts import PROMPTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()
crud = CRUD()
semantic_router = create_router(crud)

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

# likely don't need
@app.post('/collections')
async def create_collection(payload: CollectionCreate):
    name = payload.name
    if not name:
        raise HTTPException(status_code=400, detail="Missing 'name'")
    result = await crud.create_collection(
        name=name,
        description=payload.description,
        metadata=payload.metadata,
    )
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    info = await crud.get_collection_info(name)
    if isinstance(info, dict) and info.get("error"):
        raise HTTPException(status_code=404, detail=info["error"])
    return info

@app.get('/collections')
async def list_collections():
    result = await crud.list_collections()
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@app.get('/collections/{name}')
async def get_collection(name: str):
    info = await crud.get_collection_info(name)
    if isinstance(info, dict) and info.get("error"):
        raise HTTPException(status_code=404, detail=info["error"])
    return info

@app.delete('/collections/{name}')
async def delete_collection(name: str):
    result = await crud.delete_collection(name)
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result

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
    
# @app.post('/upload_materials')
# async def upload_course_materials(collection_name: str):
#     try:
#         collection = await crud.create_collection(collection_name)
#         # data = await crud.save_pdfs(file_path, collection_name)

#         data =  

#         # save the data to the database in chunks of ten documents
#         chunk_size = 10
#         for i in range(0, len(data), chunk_size):
#             await crud.save_to_db(data[i:i+chunk_size])

#         return {"message": "PDFs loaded successfully."}
    
#     except Exception as e:
#         logging.error(f"app.py: Error with loading PDFs: {e}")
#         return {"message": "Failed to load PDFs."}

@app.post("/upload_pdfs")
async def upload_multiple_pdfs(files: List[UploadFile] = File(...), collection_name: str = Form(...), user: str = Form(...)):
    """
    Handles the upload of multiple PDF files.
    """

    for file in files:
        if file.content_type != "application/pdf":
            # Optional: Add content type validation
            raise HTTPException(status_code=400, detail=f"Invalid file type for {file.filename}. Only PDFs are allowed.")
        try:
            text = await read_text_file(file)
            file_embeddings = await generate_embedding(text)

            # lets make it so they have to enter the collection name to upload a pdf
            pdf = (text, file_embeddings)
            data = await crud.save_pdfs_from_discord(user,collection_name, pdf)

            chunk_size = 10
            for i in range(0, len(data), chunk_size):
                await crud.save_to_db(data[i:i+chunk_size])

            return {"message": "PDFs saved successfully."}
        except Exception as e:
            logging.error(f"app.py: Error with loading PDFs: {e}")
            return {"message": "Failed to save PDFs."}

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
