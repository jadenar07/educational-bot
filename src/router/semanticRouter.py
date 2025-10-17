from semantic_router import Route
from semantic_router.routers import SemanticRouter as AurelioSemanticRouter
from semantic_router.encoders import LocalEncoder
import os, sys, logging, inspect 

# Adding path to ensure utils and backend are detected
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utlis.config import OPENAI_API_KEY
from utlis.prompts import PROMPTS
from backend.modelsPydantic import QueryRequest
from databases.chroma.modelsChroma import generate_embedding
from services.queryLangchain import fetchGptResponse
from router.utterances import UTTERANCES
from router.RouteMap import ThreadSafeMap

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class SemanticRouter:
    def __init__(self, crud):
        os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
        
        # Set up variables
        self.crud = crud
        self.encoder = LocalEncoder()
        self.routes = []
        self.route_layer = AurelioSemanticRouter(encoder=self.encoder, routes=[], auto_sync="local")
    
    #create collections endpoint is going to need to make a call to chatgpt when
    # given a description and create utterances based on it

    # has to change entirely
    def _setup_routes(self, routes: ThreadSafeMap):
        """Initialize routes and route layer"""
        router_routes = []
        for route, utterances in routes.items():
            route_obj = Route(name=route, utterances=utterances)
            router_routes.append(route_obj)
        self.route_layer.routes = router_routes
        # Ensure the index is built/synced after setting routes
        if hasattr(self.route_layer, "sync"):
            self.route_layer.sync("local")
        logging.info(f"Successfully setup routes: {self.route_layer.routes}")
        return {"status": "routes setup", "routes": [r.name for r in router_routes]}
    
    def add_route(self, name, utterances):
        logging.info(f"Before adding routes: {self.route_layer.routes}\n")
        logging.info(f"name: {name}, utterances: {utterances}")
        route_obj = Route(name=name, utterances=utterances)
        self.routes.append(route_obj)
        self.route_layer.routes = self.routes
        # Ensure the index is built/synced after adding a route
        if hasattr(self.route_layer, "sync"):
            self.route_layer.sync("local")
        logging.info(f"Successfully added routes: {self.route_layer.routes}")


    async def fallback_response(self, request=None):
        return "I'm not sure I understood that. Could you rephrase or ask something more specific?"
        
    async def generate_expert_response(self, request, collection_name, prompt_name):
        """Generates response using LLM and relevant documents"""
        query_embedding = await generate_embedding(request.query)
        collection_name = collection_name
        relevant_docs = await self.crud.get_data_by_similarity(collection_name, query_embedding, top_k=5)
        
        content = relevant_docs.get('documents')[0]
        logging.info(f"Relevant messages: {content}")

        answer = await fetchGptResponse(request.query, PROMPTS[prompt_name], relevant_docs)

        logging.info(f"Answer: {answer}")
        return {'answer': answer}

    async def process_query(self, request: QueryRequest):
        """Main entry point to process a query through the semantic router"""
        try:
            logging.info("Attempting to use route layer")
            route = self.route_layer(request.query)
            logging.info(f"Response from the route layer: {route}, original query: {request.query}")

            # Log the processed route details
            logging.info(f"Processed route: {route}")

            return route 

        except Exception as e:
            logging.error(f"Error processing query: {request.query} | Error: {e}")
            return {"error": str(e)} 

# Factory function to create router instance
def create_router(crud):
    return SemanticRouter(crud)