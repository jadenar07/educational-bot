import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

# import asyncio, uuid
import numpy as np
from src.database.crudChroma import CRUD
import pytest
# your CRUD wrapper with centroid helpers (must be implemented)

class Doc:
    # Minimal doc double: only fields your save_to_db uses
    def __init__(self, text, id_):
        self.page_content = text
        self.metadata = {"id": id_}

@pytest.mark.asyncio
async def test_centroid_update():
    crud = CRUD()
    col =  "t_col_1234"    # unique test collection

    # Three simple vectors we'll use across two batches
    x1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    x2 = np.array([1.0, 1.0, 0.0], dtype=np.float32)
    x3 = np.array([0.0, 1.0, 1.0], dtype=np.float32)

    print(f"[BATCH 1] write 2 docs → expect centroid mean(x1,x2)")
    await crud.save_to_db([
        {"collection_name": col, "document": Doc("A", "a1"), "embedding": x1.tolist()},
        {"collection_name": col, "document": Doc("B", "b1"), "embedding": x2.tolist()},
    ])

    # Read the centroid after batch 1 (requires your CRUD to expose _get_centroid_row)
    mu1, n1 = crud._get_centroid_row(col)     # returns (centroid_vector, doc_count)
    print("[CENTROID AFTER B1]", mu1, " doc_count:", n1)

    print(f"[BATCH 2] write 1 doc → expect centroid mean(x1,x2,x3)")
    await crud.save_to_db([
        {"collection_name": col, "document": Doc("C", "c1"), "embedding": x3.tolist()},
    ])

    mu2, n2 = crud._get_centroid_row(col)
    print("[CENTROID AFTER B2]", mu2, " doc_count:", n2)

    # Cleanup: remove test collection and centroid row
    try:
        crud.client.delete_collection(col)
        print(f"[CLEANUP] deleted collection: {col}")
    except Exception as e:
        print(f"[CLEANUP] skip delete collection: {e}")

    try:
        cents = crud.client.get_or_create_collection("__centroids__")
        cents.delete(ids=[col])
        print(f"[CLEANUP] deleted centroid row for: {col}")
    except Exception as e:
        print(f"[CLEANUP] skip delete centroid row: {e}")

@pytest.mark.asyncio
async def test_crud_basics():
    crud = CRUD()
    # random collection name
    col = "t_col_1234" 

    # Handmade embeddings
    emb1 = [1.0, 0.0, 0.0]
    emb2 = [0.9, 0.1, 0.0]
    embQuery  = [1.0, 0.05, 0.0]

    # filling data with the two items
    data = [
        {"collection_name": col, "document": Doc("doc A", "a"), "embedding": emb1},
        {"collection_name": col, "document": Doc("doc B", "b"), "embedding": emb2},
    ]
    print(f"creating collection: {col}")

    # writes the data to chroma
    await crud.save_to_db(data)

    # query by similarity with the hand made data
    res = await crud.get_data_by_similarity(col, embQuery, top_k=2)
    print("query~ ids:", res.get("ids"))
    print("query~ distances:", res.get("distances"))

    # Cleanup by delete the test collection and any centroid row with same id
    try:
        crud.client.delete_collection(name=col)
        print(f"cleanup~ deleted collection: {col}")
    except Exception as e:
        print(f"cleanup~ no collection to delete: {e}")