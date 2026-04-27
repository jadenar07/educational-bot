# crudChroma.py
import chromadb, uuid, os, urllib.parse, asyncio, logging, time


from utlis.config import DB_PATH
from databases.chroma.modelsChroma import generate_embedding
from services.getPdfs import read_hyperlinks, match_filenames_to_urls
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader

class CRUD():
    def __init__(self):
        self.client = chromadb.PersistentClient(path = DB_PATH)
        
    async def save_to_db(self, data):
        for item in data:
            collection_name, document, embedding = item['collection_name'], item['document'], item['embedding']

            # Change collection_name to type str since it was an int, but has to
            # be a str in order to be used as a collection name
            collection_name = str(collection_name)

            # Note that collection_name is equivalent to channel_id
            collection = await asyncio.to_thread(self.client.get_or_create_collection, collection_name)

            await asyncio.to_thread(collection.upsert,
                # Same for id, has to be a str
                ids=[str(document.metadata['id'])],
                documents=[document.page_content],
                embeddings=[embedding],
                metadatas=[document.metadata]
            )

            print(f"'{document.page_content}' is added to the collection {collection_name}")

    async def get_data_by_similarity(self, collection_name, query_embedding, top_k=10):
        start = time.perf_counter()
        try:
            # Generate the embedding for the query
            print(f"Retrieving documents for the collection: {collection_name}")

            # Get or create the collection if it doesn't exist
            collection = await asyncio.to_thread(self.client.get_or_create_collection, collection_name)
            print(f"Collection retrieved: {collection}")

            # Query the collection
            results = await asyncio.to_thread(
                collection.query,
                query_embeddings=[query_embedding],
                n_results=top_k
            )

            logging.info(f"get_data_by_similarity {collection_name} took {(time.perf_counter() - start) * 1000:.2f}ms")
            return results

        except Exception as e:
            print(f"Error with retrieving relevant history: {e}")
            return []

    async def get_data_by_id(self, collection_name, ids):
        # convert ids to str
        ids = [str(id) for id in ids]
        start = time.perf_counter()
        try:
            collection = await asyncio.to_thread(self.client.get_or_create_collection, collection_name)
            results = await asyncio.to_thread(
                collection.get,
                ids=ids,
                # where={"style": "style1"}
            )

            logging.info(f"get_data_by_id {collection_name} took {(time.perf_counter() - start) * 1000:.2f}ms")
            return results

        except Exception as e:
            print(f"Error with retrieving data by id: {e}")
            return []

    async def list_collections(self):
        start = time.perf_counter()
        try:
            collections = await asyncio.to_thread(self.client.list_collections)
            logging.info(f"list_collections took {(time.perf_counter() - start) * 1000:.2f}ms")
            return collections
        except Exception as e:
            print(f"Error with listing collections: {e}")
            return []

    async def delete_collection(self, name):
        start = time.perf_counter()
        try:
            await asyncio.to_thread(self.client.delete_collection, name=name)
            logging.info(f"delete_collection {name} took {(time.perf_counter() - start) * 1000:.2f}ms")
        except Exception as e:
            print(f"Error with deleting collection: {e}")
            raise

    async def get_all_documents(self, collection_name):
        start = time.perf_counter()
        try:
            collection = await asyncio.to_thread(self.client.get_or_create_collection, collection_name)
            results = await asyncio.to_thread(collection.get)
            logging.info(f"get_all_documents {collection_name} took {(time.perf_counter() - start) * 1000:.2f}ms")
            return results
        except Exception as e:
            print(f"Error with retrieving all documents: {e}")
            return []
    
    async def save_pdfs(self, file_path, collection_name):
        # Use file_path as-is (already absolute from caller)
        if not file_path:
            file_path = '/app/pdfs'
        
        print(f"Saving PDFs from {file_path} to collection {collection_name}")
        logging.info(f"save_pdfs: Looking for PDFs at {file_path}")
        
        # Check if directory exists
        if not os.path.exists(file_path):
            error_msg = f"Directory not found: {file_path}"
            print(f"crudChroma.py: Error with loading PDFs: {error_msg}")
            logging.error(f"crudChroma.py: {error_msg}")
            return []  # Return empty list instead of None
        
        # Get the files
        try:
            loader = DirectoryLoader(file_path, glob = "*.pdf", show_progress = True)
            docs = loader.load()
            logging.info(f"save_pdfs: Successfully loaded {len(docs)} PDF documents")

        except Exception as e:
            print(f"crudChroma.py: Error with loading PDFs: {e}")
            logging.error(f"crudChroma.py: Error with loading PDFs from {file_path}: {e}")
            return []  # Return empty list instead of None
        

        # split the text 
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size = 1000, 
            chunk_overlap = 200
        )

        # get docs, ids, and filenames (for metadata purposes)
        docs = text_splitter.split_documents(docs)
        ids = [str(uuid.uuid4()) for _ in range(len(docs))]

        # remove the file path and extension from the source
        filenames = [doc.metadata['source'].split('/')[-1].split('.')[0] for doc in docs]

        # get the hyperlinks for the pdfs with filenames
        hyperlinks_file = f"{file_path}/../hyperlinks.csv"
        urls = read_hyperlinks(hyperlinks_file)
        matched_urls = match_filenames_to_urls(filenames, urls)

        for filename, url in matched_urls.items():
            print(f"{filename}: {url}")

        # save the docs in the collection with collection_name
        collection = self.client.get_or_create_collection(collection_name)

        data_to_save = []
        for doc, id, filename in zip(docs, ids, filenames):
            url, text = matched_urls.get(filename, (None, "Description not found"))
            combined_text = f"{text} {doc.page_content}"
            # print the first 50 characters of the combined text
            print(f"Combined text: {combined_text[:50]}...")
            embedding = await generate_embedding(combined_text)
            
            # Format the filename
            filename = urllib.parse.unquote(filename.replace('_', ' '))
            
            if url:
                source = f"[{filename}]({url})"
            else:
                source = filename
            
            # Prepare the metadata for saving
            metadata = {
                "id": id,
                "source": source
            }

            # Add to data to be saved
            data_to_save.append({
                "collection_name": collection_name,
                "document": doc,
                "embedding": embedding,
                "metadata": metadata
            })

        return data_to_save


