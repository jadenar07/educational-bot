# crudChroma.py
import chromadb, uuid, os, urllib.parse, asyncio
import numpy as np 

from utlis.config import DB_PATH
from databases.chroma.modelsChroma import generate_embedding
from services.getPdfs import read_hyperlinks, match_filenames_to_urls
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader

class CRUD():
    def __init__(self):
        self.client = chromadb.PersistentClient(path = DB_PATH)
    
    # TODO: as noted, i removed async from most things so that I did not have to call awaiy because it was causing error after error
    def save_to_db(self, data):
        collections_embeddings_dict = {}

        for item in data:
            collection_name, document, embedding = item['collection_name'], item['document'], item['embedding']

            # Change collection_name to type str since it was an int, but has to
            # be a str in order to be used as a collection name
            collection_name = str(collection_name)

            # Note that collection_name is equivalent to channel_id
            collection = self.client.get_or_create_collection(collection_name)
            
            collection.upsert(
                ids=[str(document.metadata['id'])],
                documents=[document.page_content],
                embeddings=[embedding],
                metadatas=[document.metadata])

            embedding_array = np.asarray(embedding, dtype=np.float32)
            if collection_name not in collections_embeddings_dict:
                collections_embeddings_dict[collection_name] = []

            collections_embeddings_dict[collection_name].append(embedding_array)

            print(f"'{document.page_content}' is added to the collection {collection_name}")

        for collection_name, embs in collections_embeddings_dict.items():
            # shape [total_new_embeddings, emb_dim] (row, col)
            batch = np.vstack(embs) 
            self._update_centroid_after_batch, collection_name, batch

    def _update_centroid_after_batch(self, collection_name: str, new_doc_embs: np.ndarray):
        if new_doc_embs.size == 0:
            return
        new_doc_mean = new_doc_embs.mean(axis=0)
        prev_centroid, prev_total_docs = self._get_centroid_row(collection_name)
        new_total_docs = new_doc_embs.shape[0]
        if prev_centroid is None or prev_total_docs == 0:
            new_centroid = new_doc_mean
            using_new_total_docs = new_total_docs
        else:
            new_centroid = (prev_total_docs *
                            prev_centroid +
                            new_total_docs *
                            new_doc_mean) / (prev_total_docs +
                                           new_total_docs)
            
            using_new_total_docs = prev_total_docs + new_total_docs

        print("my creating centroid for", collection_name)
        collection = self.client.get_or_create_collection, collection_name
        collection.upsert(
            ids=[collection_name],
            embeddings=[new_centroid.astype(float).tolist()],
            metadatas=[{"doc_count": int(using_new_total_docs)}],
            documents=[f"centroid for {collection_name}"],
        )

    def _get_centroid_row(self, collection_name: str):
        try:
            centroid_row = self._centroid_collection.get(ids=[collection_name])
            if not centroid_row["ids"]:
                return None, 0
            
            centroid_vector = np.array(centroid_row["embeddings"][0], dtype=np.float32)
            total_documents_in_centroid = int(centroid_row["metadatas"][0].get("doc_count", 0))
            return centroid_vector, total_documents_in_centroid
        
        except Exception:
            return None, 0

    async def get_data_by_similarity(self, collection_name, query_embedding, top_k=10):
        try:
            # Generate the embedding for the query
            print(f"Retrieving documents for the collection: {collection_name}")

            # Get the collection
            collection = self.client.get_collection(collection_name)
            print(f"Collection retrieved: {collection}")

            # Query the collection
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )

            return results

        except Exception as e:
            print(f"Error with retrieving relevant history: {e}")
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
            print(f"Error with retrieving data by id: {e}")
            return []
    
    async def save_pdfs(self, file_path, collection_name):
        print(f"Saving PDFs from {file_path} to collection {collection_name}")
        # Get the files
        try:
            loader = DirectoryLoader(file_path, glob = "*.pdf", show_progress = True)
            docs = loader.load()

        except Exception as e:
            print(f"crudChroma.py: Error with loading PDFs: {e}")
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


