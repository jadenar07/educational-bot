# crudChroma.py
import chromadb, uuid, os, urllib.parse, asyncio, logging
from utlis.config import DB_PATH
from database.modelsChroma import generate_embedding
from services.getPdfs import read_hyperlinks, match_filenames_to_urls
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class CRUD():
    def __init__(self):
        self.client = chromadb.PersistentClient(path = DB_PATH)
        
    async def save_to_db(self, data):
        for item in data:
            collection_name, document, embedding = item['collection_name'], item['document'], item['embedding']

            # Change collection_name to type str since it was an int, but has to
            # be a str in order to be used as a collection namef
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

            logger.info(f"'{document.page_content}' is added to the collection {collection_name}")

    async def get_data_by_similarity(self, collection_name, query_embedding, top_k=10):
        try:
            # Generate the embedding for the query
            logger.info(f"Retrieving documents for the collection: {collection_name}")

            # Get the collection
            collection = self.client.get_collection(collection_name)
            logger.debug(f"Collection retrieved: {collection}")

            # Query the collection
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )

            return results

        except Exception as e:
            logger.error(f"Error with retrieving relevant history: {e}")
            return []
    
    async def get_data_by_id(self, collection_name, ids):
        # convert ids to str
        ids = [str(id) for id in ids]
        try:
            collection = self.client.get_collection(collection_name)
            results = collection.get(
                ids=ids,
                # where={"style": "style1"}
            )

            return results

        except Exception as e:
            logger.error(f"Error with retrieving data by id: {e}")
            return []
    
    async def save_pdfs(self, file_path, collection_name):
        logger.info(f"Saving PDFs from {file_path} to collection {collection_name}")
        # Get the files
        try:
            loader = DirectoryLoader(file_path, glob = "*.pdf", show_progress = True)
            docs = loader.load()

        except Exception as e:
            logger.error(f"crudChroma.py: Error with loading PDFs: {e}")
            return
        

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
            logger.debug(f"{filename}: {url}")

        # save the docs in the collection with collection_name
        collection = self.client.get_or_create_collection(collection_name)

        data_to_save = []
        for doc, id, filename in zip(docs, ids, filenames):
            url, text = matched_urls.get(filename, (None, "Description not found"))
            combined_text = f"{text} {doc.page_content}"
            # print the first 50 characters of the combined text
            logger.info(f"Combined text: {combined_text[:50]}...")
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

    async def get_collection_info(self, name: str):
        # Get information aboput a part icualr collection 
        try:
            collection = self.client.get_collection(name)
            count = collection.count()
            metadata = collection.metadata or {}
            
            return {
                "name": collection.name,
                "description": metadata.get("description"),
                "metadata": metadata,
                "document_count": count,
                "created_at": metadata.get("created_at")
            }
            
        except Exception as e:
            logger.debug(f"Error getting collection info for '{name}': {e}")
            return {"error": f"Collection '{name}' not found"}

    # Collection Management Methods
    async def create_collection(self, name: str, description: str = None, metadata: dict = None):
        """Create a new collection explicitly"""
        try:
            # Check if collection already exists
            try:
                existing_collection = self.client.get_collection(name)
                if existing_collection:
                    return {"error": f"Collection '{name}' already exists"}
            except Exception as e:
                logger.debug(f"Collection '{name}' does not exist, proceeding with creation: {e}")
                pass
            
            # Create the collection
            collection = self.client.create_collection(
                name=name,
                metadata={"description": description, **(metadata or {})}
            )
            
            logger.info(f"Collection '{name}' created successfully")
            return {"message": f"Collection '{name}' created successfully", "collection": collection}
            
        except Exception as e:
            logger.error(f"Error creating collection '{name}': {e}")
            return {"error": str(e)}
    
    async def delete_collection(self, name: str):
        """Deletes a collection"""
        try:
            try:
                collection = self.client.get_collection(name)
                if collection:
                    self.client.delete_collection(name)
                    logger.info(f"Collection '{name}' deleted successfully")
                    return {"message": f"Collection '{name}' deleted successfully"}
            except Exception as e:
                logger.error(f"Collection '{name}' not found: {e}")
                return {"error": f"Collection '{name}' not found"}
                
        except Exception as e:
            logger.error(f"Error deleting collection '{name}': {e}")
            return {"error": str(e)}
    
    async def list_collections(self):
        """List all collections with metadata"""
        try:
            collections = self.client.list_collections()
            collection_list = []
            
            for collection in collections:
                try:
                    # Get collection metadata and count
                    count = collection.count()
                    metadata = collection.metadata or {}
                    
                    collection_info = {
                        "name": collection.name,
                        "description": metadata.get("description"),
                        "metadata": metadata,
                        "document_count": count,
                        "created_at": metadata.get("created_at")
                    }
                    collection_list.append(collection_info)
                    
                except Exception as e:
                    collection_info = {
                        "name": collection.name,
                        "description": None,
                        "metadata": {},
                        "document_count": 0,
                        "created_at": None
                    }
                    collection_list.append(collection_info)
                    logger.error(f"Failed to fully read metadata for collection {collection.name}: {e}")
            return {
                "collections": collection_list,
                "total_count": len(collection_list)
            }
            
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            return {"error": str(e)}

    def validate_collection_name(self, name: str) -> tuple[bool, str]:
        """
        Validate collection name format.

        Returns:
            tuple: (is_valid: bool, error_message: str)
        """
        if not name:
            return False, "Collection name cannot be empty"

        if len(name) > 63:
            return False, "Collection name must be 63 characters or less"

        # ChromaDB allows alphanumeric, hyphens, underscores
        if not all(c.isalnum() or c in ['-', '_'] for c in name):
            return False, "Collection name can only contain alphanumeric characters, hyphens, and underscores"

        return True, ""

    async def collection_exists(self, name: str) -> bool:
        """Check if a collection exists"""
        try:
            await asyncio.to_thread(self.client.get_collection, name)
            return True
        except Exception:
            return False

    async def validate_collection_for_route(self, collection_names: list) -> tuple[bool, list]:
        """
        Validate that all collections in a list exist.

        Returns:
            tuple: (all_exist: bool, list_of_missing_collections: list)
        """
        missing_collections = []

        for collection_name in collection_names:
            exists = await self.collection_exists(collection_name)
            if not exists:
                missing_collections.append(collection_name)

        return len(missing_collections) == 0, missing_collections

