from dataclasses import dataclass
from typing import List


@dataclass
class ReshapedQuery:
    original_query: str
    routing_query: str
    retrieval_query: str
    expanded_concepts: List[str]


def _normalize_query(query: str) -> str:
    return " ".join(query.strip().split())


def _expand_common_academic_terms(query: str) -> List[str]:
    q = query.lower()
    concepts = []

    concept_map = {
        "sgd": [
            "stochastic gradient descent",
            "gradient descent",
            "optimization",
            "machine learning training",
            "loss function",
        ],
        "backprop": [
            "backpropagation",
            "neural networks",
            "gradient calculation",
            "training algorithm",
        ],
        "slides": [
            "lecture slides",
            "course materials",
            "presentation",
            "notes",
        ],
        "wk": [
            "week",
            "lecture",
            "course schedule",
        ],
        "week": [
            "lecture",
            "course schedule",
            "course materials",
        ],
        "benchmark": [
            "benchmark assignment",
            "project milestone",
            "progress report",
            "grading requirement",
        ],
        "lab": [
            "lab assignment",
            "project task",
            "implementation",
            "course requirement",
        ],
        "progress": [
            "project progress",
            "milestone status",
            "completed tasks",
            "remaining tasks",
        ],
    }

    for key, values in concept_map.items():
        if key in q:
            concepts.extend(values)

    seen = set()
    unique_concepts = []
    for item in concepts:
        if item not in seen:
            seen.add(item)
            unique_concepts.append(item)

    return unique_concepts


def reshape_query(query: str) -> ReshapedQuery:
    """
    Query Understanding Layer.

    Keeps the original query, while generating:
    - routing_query: clearer student-intent query for semantic routing
    - retrieval_query: expanded query for embedding/vector search
    """
    original_query = _normalize_query(query)
    concepts = _expand_common_academic_terms(original_query)

    if len(original_query.split()) <= 3:
        routing_query = f"What does the student want to know about: {original_query}?"
    else:
        routing_query = original_query

    if concepts:
        retrieval_query = original_query + " " + " ".join(concepts)
    else:
        retrieval_query = original_query

    return ReshapedQuery(
        original_query=original_query,
        routing_query=routing_query,
        retrieval_query=retrieval_query,
        expanded_concepts=concepts,
    )