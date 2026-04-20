
import asyncio
from src.databases.chroma.crudChroma import CRUD                  
from src.router.semanticRouter import SemanticRouter  
from src.backend.modelsPydantic import QueryRequest 

async def main():
    crud = CRUD()                             # might be used by the router's handler
    router = SemanticRouter(crud)             # build routes and encoder

    # Stub the heavy LLM call so this script stays fast/offline:
    async def fake_expert(request, collection_name, prompt_name):
        # return an answer that proves which route was taken
        return {"answer": f"fake llm~ Routed to {collection_name} using prompt '{prompt_name}' for query: {request.query}"}
    router.generate_expert_response = fake_expert  # monkeypatch instance method

    # A query that should clearly match the "material_info"
    req = QueryRequest(query="Where can I find additional study materials?")

    # Directly call the handler (bypasses full process_query, which is also fine)
    resp = await router.material_info_guidance(req)
    # should show the fake answer with course_materials + prompt name
    print("router result: ", resp)            

if __name__ == "__main__":
    asyncio.run(main())                      
