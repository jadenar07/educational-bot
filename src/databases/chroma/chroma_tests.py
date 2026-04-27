import pytest
import uuid
import numpy as np
from databases.chroma.crudChroma import CRUD


@pytest.mark.asyncio
async def test_chroma_crud_basic():
    crud = CRUD()
    collection_name = f"test_collection_{uuid.uuid4()}"
    
    try:
        # Dummy document and embedding
        dummy_doc = type("Doc", (), {})()
        dummy_doc.page_content = "Hello world"
        dummy_doc.metadata = {"id": str(uuid.uuid4()), "source": "test_source"}
        dummy_embedding = np.random.rand(384).tolist()  # Chroma expects list of floats

        # Save to DB
        data = [{
            "collection_name": collection_name,
            "document": dummy_doc,
            "embedding": dummy_embedding,
            "metadata": dummy_doc.metadata
        }]
        await crud.save_to_db(data)

        # Query by similarity
        results = await crud.get_data_by_similarity(collection_name, dummy_embedding, top_k=1)
        assert results is not None
        assert len(results["documents"][0]) > 0
        assert "Hello world" in results["documents"][0][0]

        # Query by ID
        results_by_id = await crud.get_data_by_id(collection_name, [dummy_doc.metadata["id"]])
        assert results_by_id is not None
        assert "Hello world" in results_by_id["documents"][0]
    
        # List collections includes the new one
        collections = await crud.list_collections()
        assert any(getattr(c, "name", c) == collection_name for c in collections)

        # Get all documents in collection
        all_docs = await crud.get_all_documents(collection_name)
        assert all_docs is not None
        assert "Hello world" in all_docs["documents"]

    finally:
        # Cleanup: Delete test collection
        try:
            await crud.delete_collection(collection_name)
        except Exception as e:
            print(f"Cleanup warning: {e}")


@pytest.mark.asyncio
async def test_delete_collection_removes_it():
    crud = CRUD()
    collection_name = f"test_delete_{uuid.uuid4()}"

    dummy_doc = type("Doc", (), {})()
    dummy_doc.page_content = "to be deleted"
    dummy_doc.metadata = {"id": str(uuid.uuid4()), "source": "test"}
    dummy_embedding = np.random.rand(384).tolist()
    await crud.save_to_db([{
        "collection_name": collection_name,
        "document": dummy_doc,
        "embedding": dummy_embedding,
        "metadata": dummy_doc.metadata,
    }])

    await crud.delete_collection(collection_name)

    collections = await crud.list_collections()
    assert not any(getattr(c, "name", c) == collection_name for c in collections)






