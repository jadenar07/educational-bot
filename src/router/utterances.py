import sys, os, logging, ast
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import asyncio
from src.router.RouteMap import ThreadSafeMap
from src.services.queryLangchain import fetchGptResponse
import json

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

LLM_ROLE = """
You are an expert utterance generator for an academic support system. Your job is to create realistic student user utterances that belong to a specific intent category so they can be used for semantic routing.

When I give you a collection name and a category description, you must generate 20–30 natural language utterances that fit that category.

Critical requirements:

You must output a Python-style list assigned to a variable.

The variable name must match the collection name exactly as provided (same spelling, casing, and formatting). Do NOT modify it into snake_case or ALL_CAPS unless that’s exactly what I provided.

The utterances must be diverse (avoid duplicates and shallow rewordings).

The utterances must be semantically aligned with the category description so a semantic router can correctly route them.

Use realistic university/college student phrasing, including a mix of:

direct questions

informal questions

statements asking for help

short and long phrasing variations

Keep the output only to the Python variable assignment and list (no explanations, no headings, no extra text).

Input I will provide:
Collection name: <collection_name>
Category description: <category_description>

Your output must look exactly like this format:
<collection_name> = [
"Utterance 1...",
"Utterance 2...",
...
]

"""


UTTERANCES = ThreadSafeMap()

# Load persisted utterances from file on startup
_utterances_path = os.path.join(os.path.dirname(__file__), 'utterances.json')
if os.path.exists(_utterances_path):
    try:
        with open(_utterances_path, 'r', encoding='utf-8') as f:
            persisted = json.load(f)

        # Populate the ThreadSafeMap
        for name, utterances in persisted.items():
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(UTTERANCES.set(name, utterances))
            else:
                loop.run_until_complete(UTTERANCES.set(name, utterances))
        logging.info("Loaded persisted utterances from utterances.json")
    except Exception as e:
        logging.error(f"Failed to load persisted utterances: {e}")

async def create_utterances(query):
    try:
        response = await fetchGptResponse(query=query, role=LLM_ROLE)
        name, utterances_str = response.split('=', 1)
        name = name.strip()
        utterances_str = utterances_str.strip()
        # Parse the utterances string into a Python list
        utterances = ast.literal_eval(utterances_str)
        if not isinstance(utterances, list):
            raise ValueError("Utterances is not a list after parsing.")

        logging.info(f"Succesfuly generated utterances for {name}: {utterances}")
        await UTTERANCES.set(name, utterances)
        # Persist all utterances to file after update
        try:
            # Gather all utterances in the map
            all_utterances = await UTTERANCES.snapshot()
            with open(os.path.join(os.path.dirname(__file__), 'utterances.json'), 'w', encoding='utf-8') as f:
                json.dump(all_utterances, f, ensure_ascii=False, indent=2)
            logging.info("Persisted utterances to utterances.json")
        except Exception as file_err:
            logging.error(f"Failed to persist utterances: {file_err}")
        logging.info(f"Updated utterances: {UTTERANCES}")
    except Exception as e:
        raise Exception(f"Error creating utterances: {e}")


# Tests
# ex = """
# name: mentalSupportUtterances, description: Student expressions related to academic stress, burnout, lack of motivation, and requests for emotional or mental health support.
# """
# if __name__ == "__main__":
#     # result = asyncio.run(create_utterances(ex))
#     print(str(UTTERANCES))
