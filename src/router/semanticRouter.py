from semantic_router import Route
from semantic_router.routers import SemanticRouter as AurelioSemanticRouter
from semantic_router.encoders import LocalEncoder
import os, sys, logging, inspect 
from types import SimpleNamespace

# Adding path to ensure utils and backend are detected
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utlis.config import OPENAI_API_KEY
from utlis.prompts import PROMPTS
from backend.modelsPydantic import QueryRequest
from databases.chroma.modelsChroma import generate_embedding
from services.queryLangchain import fetchGptResponse
from services.queryReshaper import reshape_query
from router.utterances import UTTERANCES

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class SemanticRouter:
    def __init__(self, crud):
        os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
        
        # Set up variables
        self.crud = crud
        self.encoder = LocalEncoder()
        self._setup_routes()
        
    def _setup_routes(self):
        """Initialize routes and route layer"""
        # Route definitions and their utterances
        self.progress_report_rt = Route(
            name="progress_report",
            utterances=UTTERANCES["progress_report"],
        )

        self.problem_solve_rt = Route(
            name="problem_solve",
            utterances=UTTERANCES["problem_solve"],
        )

        self.material_info_rt = Route(
            name="material_info",
            utterances=UTTERANCES["material_info"],
        )

        self.mental_support_rt = Route(
            name="mental_support",
            utterances=UTTERANCES["mental_support"],
        )

        # Define Route Layer
        self.route_layer = AurelioSemanticRouter(encoder=self.encoder, routes=[
            self.progress_report_rt,
            self.problem_solve_rt,
            self.material_info_rt,
            self.mental_support_rt,
        ], auto_sync="local")

        
        # Setup response mapping
        self.route_responses = {
            "progress_report": self.progress_report_guidance,
            "problem_solve": self.problem_solve_guidance,
            "material_info": self.material_info_guidance,
            "mental_support": self.mental_support_guidance,
            "fallback": self.fallback_response,
        }
    
    # Response functions
    async def progress_report_guidance(self, request=None):
        return "Tracking your submitted labs and reviewing feedback will help ensure steady progress."

    async def problem_solve_guidance(self, request=None):
        return "Start by breaking the problem into smaller parts and focus on the key concepts."

    async def material_info_guidance(self, request, reshaped=None):
        return await self.generate_expert_response(request, collection_name="course_materials", prompt_name="course_instructor", reshaped=reshaped)

    async def mental_support_guidance(self, request=None):
        return "If you are feeling overwhelmed, NYU provides free counseling services to help students manage stress."

    async def fallback_response(self, request=None):
        return "I'm not sure I understood that. Could you rephrase or ask something more specific?"

    def _apply_route_hint(self, route, reshaped):
        """
        Prefer explicit hints from the query understanding layer when available.
        This keeps concept explanations and course artifact lookups on the
        material_info path, which has retrieval + LLM grounding.
        """
        if reshaped and reshaped.route_hint:
            current_name = getattr(route, "name", None)
            if current_name != reshaped.route_hint:
                logging.info(
                    f"Overriding route '{current_name}' with hint '{reshaped.route_hint}'"
                )
            return SimpleNamespace(name=reshaped.route_hint)
        return route
        
    async def generate_expert_response(self, request, collection_name, prompt_name, reshaped=None):
        """
        Generates response using LLM and relevant documents.
        
        Uses reshaped.retrieval_query for embedding if available, 
        otherwise falls back to original query.
        """
        # Use retrieval query if reshaped is available, otherwise use original query
        embedding_query = reshaped.retrieval_query if reshaped else request.query
        
        query_embedding = await generate_embedding(embedding_query)
        relevant_docs = await self.crud.get_data_by_similarity(collection_name, query_embedding, top_k=5)
        
        content = relevant_docs.get('documents')[0]
        logging.info(f"Relevant messages: {content}")
        
        # Build context that includes both original and reshaped queries
        if reshaped:
            logging.info(f"Query Understanding Layer:")
            logging.info(f"  Original: {reshaped.original_query}")
            logging.info(f"  Routing: {reshaped.routing_query}")
            logging.info(f"  Retrieval: {reshaped.retrieval_query}")
            query_for_llm = request.query  # Use original query for LLM
        else:
            query_for_llm = request.query

        answer = await fetchGptResponse(query_for_llm, PROMPTS[prompt_name], relevant_docs)

        logging.info(f"Answer: {answer}")
        return {'answer': answer}

    async def process_query(self, request: QueryRequest):
        """
        Main entry point to process a query through the semantic router.
        
        Uses the Query Understanding Layer to transform raw queries before routing.
        """
        try:
            # ---- QUERY UNDERSTANDING LAYER ----
            # Transform raw user query into routing and retrieval variants
            reshaped = reshape_query(request.query)
            logging.info(f"Query Understanding Layer - Original: '{reshaped.original_query}'")
            logging.info(f"Query Understanding Layer - Routing: '{reshaped.routing_query}'")
            logging.info(f"Query Understanding Layer - Retrieval: '{reshaped.retrieval_query}'")
            
            # ---- SEMANTIC ROUTING ----
            # Use routing_query for better semantic understanding
            route = self.route_layer(reshaped.routing_query)
            route = self._apply_route_hint(route, reshaped)

            # Log the processed route details
            logging.info(f"Processed route: {route}")

            if hasattr(route, 'name') and route.name:
                response_function = self.route_responses.get(route.name, self.fallback_response)

                # Handle async and non-async functions
                if inspect.iscoroutinefunction(response_function):
                    # Pass reshaped query to functions that need it (like material_info_guidance)
                    if route.name == "material_info":
                        response = await response_function(request, reshaped=reshaped)
                    else:
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
