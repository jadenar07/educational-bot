from database.crudChroma import CRUD

crud = CRUD()
client = crud.client

collections = client.list_collections()
print("\n📄 Documents in Each Collection:")
for col in collections:
    collection = client.get_collection(col.name)
    results = collection.get()
    print(f"\n🗂 Collection: {col.name}")
    print(f"   Total documents: {len(results.get('ids', []))}")

    for i, (doc_id, doc) in enumerate(zip(results.get("ids", []), results.get("documents", []))):
        snippet = (doc[:80] + "...") if len(doc) > 80 else doc
        print(f"     {i+1}. ID={doc_id}, Content: {snippet}")