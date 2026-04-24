import re
import logging
from dataclasses import dataclass
from typing import List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


@dataclass
class ReshapedQuery:
    original_query: str
    routing_query: str
    retrieval_query: str
    expanded_concepts: List[str]
    query_type: str
    route_hint: Optional[str]


def _normalize_query(query: str) -> str:
    """Normalize query by stripping whitespace and standardizing spacing"""
    return " ".join(query.strip().split())


def _normalize_for_analysis(query: str) -> str:
    """Normalize query to lowercase for pattern matching"""
    return _normalize_query(query).lower()


def _is_short_query(query: str) -> bool:
    """Detect if query is very short (1-2 words)"""
    words = _normalize_for_analysis(query).split()
    return len(words) <= 2


def _is_fragment_query(query: str) -> bool:
    """
    Detect fragment queries like:
    - "week3 slides", "wk3 materials"
    - "benchmark1", "benchmark 1"
    - "lab2", "lab 2"
    - "assignment5", "project3"
    """
    normalized = _normalize_for_analysis(query)
    fragment_patterns = [
        r'wk\s*(\d+)',
        r'week\s*(\d+)',
        r'lab\s*(\d+)',
        r'benchmark\s*(\d+)',
        r'assignment\s*(\d+)',
        r'project\s*(\d+)',
        r'module\s*(\d+)',
        r'chapter\s*(\d+)',
    ]
    return any(re.search(pattern, normalized) for pattern in fragment_patterns)


def _is_well_formed_question(query: str) -> bool:
    """
    Detect if query is already a well-formed question.
    These should not be transformed further.
    """
    normalized = _normalize_for_analysis(query)
    
    # Contains question words at the start
    question_starters = {'where', 'what', 'how', 'why', 'when', 'who', 'which', 'is', 'are', 'can', 'could', 'would', 'should', 'do', 'does'}
    
    first_word = normalized.split()[0] if normalized.split() else ''
    
    # If it starts with question words and has reasonable length, it's probably well-formed
    if first_word in question_starters and len(normalized.split()) >= 3:
        return True
    
    return False


def _is_concept_only_query(query: str) -> bool:
    """
    Detect concept-only queries (e.g., 'sgd', 'backpropagation', 'adam').
    These are typically 1-3 words without question structure.
    """
    normalized = _normalize_for_analysis(query)
    words = normalized.split()
    
    if len(words) > 3:
        return False
    
    # Check if it contains question words
    question_words = {'how', 'what', 'where', 'why', 'when', 'can', 'could', 'would', 
                      'should', 'do', 'does', 'is', 'are', 'am', 'been', 'being'}
    
    return not any(word in question_words for word in words)


def _extract_fragment_context(query: str) -> tuple:
    """
    Extract fragment information (type and number) from query.
    Returns: (fragment_type, number) or (None, None) if not a fragment
    """
    normalized = _normalize_for_analysis(query)
    
    patterns = [
        (r'wk\s*(\d+)', 'week'),
        (r'week\s*(\d+)', 'week'),
        (r'lab\s*(\d+)', 'lab'),
        (r'benchmark\s*(\d+)', 'benchmark'),
        (r'assignment\s*(\d+)', 'assignment'),
        (r'project\s*(\d+)', 'project'),
        (r'module\s*(\d+)', 'module'),
        (r'chapter\s*(\d+)', 'chapter'),
    ]
    
    for pattern, ftype in patterns:
        match = re.search(pattern, normalized)
        if match:
            return (ftype, match.group(1))
    
    return (None, None)


def _expand_common_academic_terms(query: str) -> List[str]:
    """Expand common academic terms with related concepts"""
    q = _normalize_for_analysis(query)
    concepts = []

    concept_map = {
        # Optimization concepts
        "sgd": [
            "stochastic gradient descent",
            "gradient descent",
            "optimization",
            "machine learning training",
            "loss function",
            "convergence",
        ],
        "gradient descent": [
            "optimization",
            "gradient",
            "learning rate",
            "convergence",
            "loss function",
        ],
        "adam": [
            "adam optimizer",
            "adaptive learning rate",
            "momentum",
            "optimization algorithm",
            "convergence",
        ],
        "backprop": [
            "backpropagation",
            "neural networks",
            "gradient calculation",
            "training algorithm",
            "chain rule",
            "derivatives",
        ],
        
        # Neural networks
        "neural network": [
            "neural networks",
            "deep learning",
            "layers",
            "activation functions",
            "weights",
            "training",
        ],
        "cnn": [
            "convolutional neural networks",
            "image classification",
            "convolution",
            "pooling",
            "feature extraction",
        ],
        "rnn": [
            "recurrent neural networks",
            "sequence modeling",
            "lstm",
            "temporal dependencies",
            "gates",
        ],
        "transformer": [
            "transformer architecture",
            "attention mechanism",
            "self-attention",
            "nlp",
            "bert",
        ],
        
        # Course materials
        "slides": [
            "lecture slides",
            "course materials",
            "presentation",
            "lecture notes",
            "handouts",
        ],
        "wk": [
            "week",
            "lecture",
            "course schedule",
            "materials",
        ],
        "week": [
            "lecture",
            "course schedule",
            "course materials",
            "readings",
            "assignments",
        ],
        "benchmark": [
            "benchmark assignment",
            "project milestone",
            "progress report",
            "grading criteria",
            "requirements",
        ],
        "lab": [
            "lab assignment",
            "project task",
            "implementation",
            "course requirement",
            "hands-on",
        ],
        "progress": [
            "progress tracking",
            "milestone status",
            "completed tasks",
            "pending work",
            "feedback",
        ],
        "materials": [
            "course materials",
            "lecture notes",
            "readings",
            "resources",
            "references",
        ],
        "resources": [
            "course resources",
            "learning materials",
            "references",
            "study guides",
            "documentation",
        ],
    }

    for key, values in concept_map.items():
        if key in q:
            concepts.extend(values)

    # Remove duplicates while preserving order
    seen = set()
    unique_concepts = []
    for item in concepts:
        if item not in seen:
            seen.add(item)
            unique_concepts.append(item)

    return unique_concepts


def _infer_route_hint(query: str, query_type: str, fragment_type: Optional[str] = None) -> Optional[str]:
    """
    Provide a strong routing hint when we can infer intent reliably.

    We prefer material_info for concept explanations and course artifact lookups
    because that path retrieves course documents and generates grounded answers.
    """
    normalized = _normalize_for_analysis(query)

    if "progress report" in normalized:
        return "progress_report"

    academic_concepts = {
        "sgd",
        "gradient descent",
        "backprop",
        "backpropagation",
        "adam",
        "optimizer",
        "neural network",
        "cnn",
        "rnn",
        "transformer",
        "bert",
        "loss function",
        "optimization",
    }
    material_terms = {
        "slides",
        "materials",
        "resources",
        "notes",
        "lecture",
        "readings",
        "textbook",
        "requirement",
        "requirements",
        "assignment",
        "lab",
        "project",
        "module",
        "chapter",
        "benchmark",
        "grading criteria",
    }

    if fragment_type in {"week", "lab", "assignment", "project", "module", "chapter", "benchmark"}:
        return "material_info"

    if query_type == "concept" and any(term in normalized for term in academic_concepts):
        return "material_info"

    if any(term in normalized for term in material_terms):
        return "material_info"

    return None


def _generate_routing_query_for_fragment(fragment_type: str, number: str, original: str) -> str:
    """Generate routing query for fragment queries"""
    routing_queries = {
        'week': f"Where can I find week {number} lecture slides and course materials?",
        'lab': f"What are the requirements and resources for lab {number}?",
        'benchmark': f"What is benchmark {number} and what are the grading criteria?",
        'assignment': f"Where can I find assignment {number} details and requirements?",
        'project': f"What are the requirements for project {number}?",
        'module': f"What topics and materials are covered in module {number}?",
        'chapter': f"What are the key concepts in chapter {number}?",
    }
    
    return routing_queries.get(fragment_type, f"Can you provide information about {original}?")


def _generate_routing_query_for_concept(query: str) -> str:
    """Generate routing query for concept-only queries"""
    normalized = _normalize_for_analysis(query)
    
    # Map common concepts to routing questions
    concept_to_question = {
        'sgd': 'Explain stochastic gradient descent in the context of machine learning and optimization.',
        'gradient descent': 'Explain gradient descent optimization algorithm and how it works.',
        'backprop': 'Explain backpropagation algorithm in neural networks.',
        'backpropagation': 'Explain backpropagation algorithm in neural networks.',
        'adam': 'Explain the Adam optimizer and how it differs from standard gradient descent.',
        'neural network': 'Explain neural networks, their structure, and how they learn.',
        'cnn': 'Explain convolutional neural networks and their applications.',
        'rnn': 'Explain recurrent neural networks and sequence modeling.',
        'transformer': 'Explain transformer architecture and attention mechanisms.',
        'bert': 'Explain BERT and transformer-based language models.',
        'loss function': 'Explain loss functions and how they guide model training.',
        'optimization': 'Explain optimization techniques in machine learning.',
    }
    
    if normalized in concept_to_question:
        return concept_to_question[normalized]
    
    # Check for partial matches
    for concept_key, question in concept_to_question.items():
        if concept_key in normalized or normalized in concept_key:
            return question
    
    # Default
    return f"Can you explain {normalized} in the context of this course?"


def reshape_query(query: str) -> ReshapedQuery:
    """
    Query Understanding Layer that transforms raw user query into structured representations.

    Priority order for detection:
    1. Well-formed questions (no transformation)
    2. Fragment queries (week3, lab2, etc)
    3. Concept-only queries (sgd, backpropagation)
    4. Short queries (1-2 words)
    5. Default (use as-is)

    Returns:
        ReshapedQuery with original, routing, and retrieval queries
    """
    original_query = _normalize_query(query)
    concepts = _expand_common_academic_terms(original_query)
    query_type = "default"
    route_hint = None
    frag_type = None

    # ---- ROUTING QUERY GENERATION ----
    # Priority: Well-formed > Fragment > Concept > Short > Default
    
    if _is_well_formed_question(query):
        # Already a good question, use as-is
        routing_query = original_query
        query_type = "well_formed"
        logging.info(f"Well-formed question detected: '{routing_query}'")
    
    elif _is_fragment_query(query):
        frag_type, frag_num = _extract_fragment_context(query)
        routing_query = _generate_routing_query_for_fragment(frag_type, frag_num, original_query)
        query_type = "fragment"
        logging.info(f"Fragment query detected: '{original_query}' -> '{routing_query}'")
    
    elif _is_concept_only_query(query):
        routing_query = _generate_routing_query_for_concept(original_query)
        query_type = "concept"
        logging.info(f"Concept-only query detected: '{original_query}' -> '{routing_query}'")
    
    elif _is_short_query(query):
        routing_query = f"What does the student want to know about {original_query}?"
        query_type = "short"
        logging.info(f"Short query detected: '{original_query}' -> '{routing_query}'")
    
    else:
        # Fallback - use original
        routing_query = original_query
        logging.info(f"Using original query as-is: '{routing_query}'")

    # ---- RETRIEVAL QUERY GENERATION ----
    # Combine original with expanded concepts for better vector search
    if concepts:
        retrieval_query = original_query + " " + " ".join(concepts)
        logging.info(f"Expanded retrieval query with {len(concepts)} concepts")
    else:
        retrieval_query = original_query

    route_hint = _infer_route_hint(original_query, query_type, frag_type)
    if route_hint:
        logging.info(f"Route hint inferred: '{route_hint}' for query '{original_query}'")

    return ReshapedQuery(
        original_query=original_query,
        routing_query=routing_query,
        retrieval_query=retrieval_query,
        expanded_concepts=concepts,
        query_type=query_type,
        route_hint=route_hint,
    )
