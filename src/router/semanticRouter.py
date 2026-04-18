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
        # Delay heavy initialization (models, encoders, index) until first use
        self.encoder = None
        self.routes = []
        self.route_layer = None

    def _init_route_layer(self):
        """Lazily initialize the underlying AurelioSemanticRouter to avoid heavy work at import/construct time."""
        if self.route_layer is None:
            # create encoder only when needed
            if self.encoder is None:
                self.encoder = LocalEncoder()
            self.route_layer = AurelioSemanticRouter(encoder=self.encoder, routes=list(self.routes), auto_sync="local")
            # ensure index is synced after creation
            if hasattr(self.route_layer, "sync"):
                try:
                    self.route_layer.sync("local")
                except Exception as e:
                    logging.error(f'Semantic Router Layer Startup Error: {e}')
    
    #create collections endpoint is going to need to make a call to chatgpt when
    # given a description and create utterances based on it

    # has to change entirely
    def _setup_routes(self, routes: ThreadSafeMap):
        """Initialize routes and route layer"""
        router_routes = []
        for route, utterances in routes.items():
            route_obj = Route(name=route, utterances=utterances)
            router_routes.append(route_obj)
        # keep internal `self.routes` in sync with the route layer so
        # later calls to `add_route` append rather than overwrite.
        self.routes = router_routes
        # ensure the route layer exists before updating
        self._init_route_layer()
        self.route_layer.routes = list(self.routes)
        logging.info(f"Successfully setup routes: {self.route_layer.routes}")
        return {"status": "routes setup", "routes": [r.name for r in router_routes]}
    
    def add_route(self, name, utterances):
        # route_layer may be None; log current known route names
        current_routes = getattr(self.route_layer, 'routes', self.routes)
        logging.info(f"Before adding routes: {current_routes}\n")
        logging.info(f"name: {name}, utterances: {utterances}")
        route_obj = Route(name=name, utterances=utterances)
        self.routes.append(route_obj)
        # ensure router is initialized then update
        self._init_route_layer()
        self.route_layer.routes = self.routes
        if hasattr(self.route_layer, "sync"):
            try:
                self.route_layer.sync("local")
            except Exception as e:
                logging.error(f'Add Route Error: {e}')
        logging.info(f"Successfully added routes: {self.route_layer.routes}")


    async def fallback_response(self, request=None):
        return "I'm not sure I understood that. Could you rephrase or ask something more specific?"
        
    async def generate_expert_response(self, request, collection_name, prompt_name):
        """Generates response using LLM and relevant documents"""
        query_embedding = await generate_embedding(request.query)
        collection_name = collection_name
        relevant_docs = await self.crud.get_data_by_similarity(collection_name, query_embedding, top_k=5)

        # Extract the list of documents (Chroma returns list-of-lists)
        docs = relevant_docs.get('documents', [])
        content = docs[0] if isinstance(docs, list) and len(docs) > 0 else []
        logging.info(f"Relevant messages: {content}")

        # Pass only a compact dict to the LLM to avoid sending excessive data
        answer = await fetchGptResponse(request.query, PROMPTS[prompt_name], {"relevant_documents": content})

        logging.info(f"Answer: {answer}")
        return {'answer': answer}

    async def process_query(self, request: QueryRequest):
        """Main entry point to process a query through the semantic router"""
        try:
            logging.info("Attempting to use route layer")
            # ensure route layer is ready (lazy init)
            self._init_route_layer()
            route = self.route_layer(request.query)
            logging.info(f"Raw route result type: {type(route)}; repr: {repr(route)}")

            # Normalize route to an object with a `name` attribute expected by the caller
            if hasattr(route, "name"):
                normalized = route
            elif isinstance(route, str):
                # router returned the matched route name as a string
                class _R: pass
                r = _R()
                r.name = route
                normalized = r
            elif isinstance(route, dict) and "name" in route:
                class _R: pass
                r = _R()
                r.name = route.get("name")
                normalized = r
            else:
                # fallback: coerce to string as the route name
                class _R: pass
                r = _R()
                r.name = str(route)
                normalized = r
            logging.info(f"Response from the route layer: {route}, original query: {request.query}")

            logging.info(f"Processed route: {normalized}")

            return normalized

        except Exception as e:
            logging.error(f"Error processing query: {request.query} | Error: {e}")
            return {"error": str(e)} 

# Factory function to create router instance
def create_router(crud):
    return SemanticRouter(crud)