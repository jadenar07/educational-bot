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
from fastapi import HTTPException


# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
ROLE_ROUTES = {
    "student":["course_materials", "mental_support"],
    "professor":["course_materials","teaching_support"]
}

PROFILE_ROUTES_MAP={
    "course_materials":["material_info_rt"],
    "teaching_support":["progress_report","problem_solve_rt"],
    "mental_support":["mental_support_rt"]
}

class SemanticRouter:
    def __init__(self, crud):
        os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
        
        # Set up variables
        self.crud = crud
        self.encoder = LocalEncoder()
        # self._setup_routes()

        # Define all possible route responses
        self.route_responses = {
            "material_info_rt": self.material_info_guidance,
            "progress_report": self.progress_report_guidance,
            "problem_solve_rt": self.problem_solve_guidance,
            "mental_support_rt": self.mental_support_guidance,
        }

        self.route_layer_cache = {} # Cache for route layers per role
        self.response_map_cache = {} # Cache for response maps per role

        logging.info("Initializing and caching routers...") # Build and cache routers
        for role in ROLE_ROUTES.keys(): 
            self._setup_routes(role)
        logging.info("All routers built and cached.")

    # Set up routes based on role     
    def _setup_routes(self, role: str):
        self.progress_report_rt = Route(
            name="progress_report",
            utterances=UTTERANCES["progress_report"],
        )

        self.problem_solve_rt = Route(
            name="problem_solve_rt",
            utterances=UTTERANCES["problem_solve"],
        )

        self.material_info_rt = Route(
            name="material_info_rt",
            utterances=UTTERANCES["material_info"],
        )

        self.mental_support_rt = Route(
            name="mental_support_rt",
            utterances=UTTERANCES["mental_support"],
        )
        profiles= ROLE_ROUTES.get(role,[]) # Get profiles for the role
        # If no profiles found, raise exception
        if not profiles:
            raise HTTPException(status_code = 403, detail=f"No profiles found for role '{role}'")
        
        # Determine allowed routes based on profiles
        allowed_route_names=set()
        for p in profiles:
            allowed_route_names.update(PROFILE_ROUTES_MAP.get(p,[]))

        # Build allowed routes list
        allowed_routes=[]
        for route_name in allowed_route_names:
            route_object=getattr(self, route_name, None)
            if route_object:
                allowed_routes.append(route_object)

        # Build the route layer 
        route_layer=AurelioSemanticRouter( 
            encoder=self.encoder,
            routes=allowed_routes,
            auto_sync="local"
        )
        # Filter route responses based on allowed routes
        filtered_responses = { 
            name: func for name, func in self.route_responses.items() 
            if name in allowed_route_names 
        }
        self.route_layer_cache[role] = route_layer
        self.response_map_cache[role] = filtered_responses
        
        logging.info(f"Routes cached for role '{role}': {list(filtered_responses.keys())}")

       
    # Response functions
    async def progress_report_guidance(self, request=None):
        return "Tracking your submitted labs and reviewing feedback will help ensure steady progress."

    async def problem_solve_guidance(self, request=None):
        return "Start by breaking the problem into smaller parts and focus on the key concepts."

    async def material_info_guidance(self, request):
        return await self.generate_expert_response(request, collection_name="course_materials", prompt_name="course_instructor")

    async def mental_support_guidance(self, request=None):
        return "If you are feeling overwhelmed, NYU provides free counseling services to help students manage stress."

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

    async def process_query(self, request: QueryRequest, role: str = None):
        """Main entry point to process a query through the semantic router"""
        try:
            if role is None:
                # Try to infer role from the request object, if available
                role = getattr(request, "role", None) or getattr(request, "user_role", None)
            # If we still don't have a role, return a clear error instead of failing later
            if role is None:
                logging.warning("process_query called without a role and no role could be inferred from the request.")
                raise HTTPException(status_code=400, detail="Role is required to process the query.")
            # Get the cached route layer and response map for the role
            route_layer = self.route_layer_cache.get(role)
            route_responses = self.response_map_cache.get(role)
            # Check if the role is valid and has a router
            if not route_layer or not route_responses:
                logging.warning(f"No router configured for role '{role}'.")
                raise HTTPException(status_code=403, detail=f"Role '{role}' does not have any configured routes.")
            
            route = route_layer(request.query)

            logging.info(f"Processed route: {route}")

            if hasattr(route, 'name') and route.name:
                response_function = self.route_responses.get(route.name, self.fallback_response)

                # Handle async and non-async functions
                if inspect.iscoroutinefunction(response_function):
                    response = await response_function(request)
                else:
                    response = response_function(request)
            else:
                response = await self.fallback_response(request)

            # Ensure response is properly formatted
            if inspect.iscoroutine(response):
                response = await response 
                
            if isinstance(response, dict):
                return response  
            elif isinstance(response, str):
                return {"answer": response}  
            else:
                return {"answer": str(response)} 

        except Exception as e:
            logging.error(f"Error processing query: {request.query} | Error: {e}")
            return {"error": str(e)} 

# Factory function to create router instance
def create_router(crud):
    return SemanticRouter(crud)