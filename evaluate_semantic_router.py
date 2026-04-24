#!/usr/bin/env python3
"""
Lightweight evaluation script for the semantic router + query reshaper.

What it compares for each test query:
1. Before route: original query -> semantic router
2. After route: reshaped routing query -> semantic router
3. Before docs: original query -> embedding retrieval (optional)
4. After docs: reshaped retrieval query -> embedding retrieval (optional)

This is intended for quick, human-reviewed evaluation so we can say:
"preliminary evaluation shows improvement"
when the after-case produces better routes or more relevant documents.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from typing import List
from types import SimpleNamespace

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from semantic_router import Route
    from semantic_router.encoders import LocalEncoder
    from semantic_router.routers import SemanticRouter as AurelioSemanticRouter

    HAS_SEMANTIC_ROUTER = True
except ImportError:
    Route = None
    LocalEncoder = None
    AurelioSemanticRouter = None
    HAS_SEMANTIC_ROUTER = False

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from router.utterances import UTTERANCES
from services.queryReshaper import reshape_query


DEFAULT_COLLECTION = "course_materials"
DEFAULT_DB_PATH = os.getenv("DB_PATH", "./local_chromadb")
DEFAULT_TOP_K = 3


@dataclass(frozen=True)
class EvalCase:
    query: str
    expected_route: str
    note: str


@dataclass
class EvalResult:
    query: str
    expected_route: str
    note: str
    query_type: str
    route_hint: str | None
    routing_query: str
    retrieval_query: str
    before_route: str
    after_route: str
    before_sources: List[str]
    after_sources: List[str]


TEST_CASES: List[EvalCase] = [
    EvalCase("sgd", "material_info", "Short concept query"),
    EvalCase("week3 slides", "material_info", "Fragment query for course materials"),
    EvalCase("benchmark1", "material_info", "Benchmark details or grading lookup"),
    EvalCase("backpropagation", "material_info", "Academic concept"),
    EvalCase("lab 2 requirements", "material_info", "Assignment requirement lookup"),
    EvalCase("adam optimizer", "material_info", "Optimizer concept"),
    EvalCase("Where can I find week 3 materials?", "material_info", "Already well-formed material question"),
    EvalCase("what?", "fallback_manual", "Ambiguous query, likely needs manual judgment"),
    EvalCase("progress report", "progress_report", "Progress-related short query"),
    EvalCase("I feel overwhelmed with coursework", "mental_support", "Student support intent"),
]


class FallbackRouteLayer:
    """
    Lightweight fallback when semantic-router is not installed.

    It scores a query against route utterances with TF-IDF cosine similarity
    and returns an object with a .name attribute, mirroring the semantic-router API.
    """

    def __init__(self, utterances_by_route):
        self.route_order = list(utterances_by_route.keys())
        self.examples: List[str] = []
        self.example_routes: List[str] = []

        for route_name, utterances in utterances_by_route.items():
            for utterance in utterances:
                self.examples.append(utterance)
                self.example_routes.append(route_name)

        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.example_matrix = self.vectorizer.fit_transform(self.examples)

    def __call__(self, query: str):
        query_matrix = self.vectorizer.transform([query])
        scores = cosine_similarity(query_matrix, self.example_matrix)[0]

        best_by_route = {route_name: 0.0 for route_name in self.route_order}
        for route_name, score in zip(self.example_routes, scores):
            if score > best_by_route[route_name]:
                best_by_route[route_name] = float(score)

        best_route = max(best_by_route, key=best_by_route.get)
        return SimpleNamespace(name=best_route, scores=best_by_route)


def build_route_layer():
    if HAS_SEMANTIC_ROUTER:
        encoder = LocalEncoder()
        routes = [
            Route(name="progress_report", utterances=UTTERANCES["progress_report"]),
            Route(name="problem_solve", utterances=UTTERANCES["problem_solve"]),
            Route(name="material_info", utterances=UTTERANCES["material_info"]),
            Route(name="mental_support", utterances=UTTERANCES["mental_support"]),
        ]
        return AurelioSemanticRouter(encoder=encoder, routes=routes, auto_sync="local")

    return FallbackRouteLayer(
        {
            "progress_report": UTTERANCES["progress_report"],
            "problem_solve": UTTERANCES["problem_solve"],
            "material_info": UTTERANCES["material_info"],
            "mental_support": UTTERANCES["mental_support"],
        }
    )


def safe_route_name(route_result) -> str:
    return getattr(route_result, "name", "fallback") or "fallback"


def resolve_after_route_name(route_layer, reshaped) -> str:
    route_result = route_layer(reshaped.routing_query)
    if reshaped.route_hint:
        return reshaped.route_hint
    return safe_route_name(route_result)


def get_route_label_status(expected_route: str, actual_route: str) -> str:
    if expected_route == "fallback_manual":
        return "manual"
    if actual_route == expected_route:
        return "match"
    return "mismatch"


def retrieval_is_available(db_path: str, collection_name: str) -> bool:
    if not os.getenv("OPENAI_API_KEY"):
        return False
    if not os.path.exists(db_path):
        return False

    try:
        import chromadb

        client = chromadb.PersistentClient(path=db_path)
        client.get_collection(collection_name)
        return True
    except Exception:
        return False


def fetch_top_sources(
    query: str,
    db_path: str,
    collection_name: str,
    top_k: int,
) -> List[str]:
    import chromadb
    from langchain_openai import OpenAIEmbeddings

    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_collection(collection_name)
    embedding_model = OpenAIEmbeddings(model="text-embedding-ada-002")
    query_embedding = embedding_model.embed_query(query)
    results = collection.query(query_embeddings=[query_embedding], n_results=top_k)

    metadatas = results.get("metadatas") or [[]]
    documents = results.get("documents") or [[]]

    formatted = []
    for metadata, document in zip(metadatas[0], documents[0]):
        source = (metadata or {}).get("source", "unknown source")
        preview = " ".join(str(document).split())[:120]
        formatted.append(f"{source} | {preview}")
    return formatted


async def evaluate_queries(
    top_k: int,
    db_path: str,
    collection_name: str,
) -> List[EvalResult]:
    route_layer = build_route_layer()
    can_retrieve = retrieval_is_available(db_path, collection_name)
    results: List[EvalResult] = []

    for case in TEST_CASES:
        reshaped = reshape_query(case.query)
        before_route = safe_route_name(route_layer(case.query))
        after_route = resolve_after_route_name(route_layer, reshaped)

        before_sources: List[str] = []
        after_sources: List[str] = []
        if can_retrieve:
            before_sources = await asyncio.to_thread(
                fetch_top_sources,
                case.query,
                db_path,
                collection_name,
                top_k,
            )
            after_sources = await asyncio.to_thread(
                fetch_top_sources,
                reshaped.retrieval_query,
                db_path,
                collection_name,
                top_k,
            )

        results.append(
            EvalResult(
                query=case.query,
                expected_route=case.expected_route,
                note=case.note,
                query_type=reshaped.query_type,
                route_hint=reshaped.route_hint,
                routing_query=reshaped.routing_query,
                retrieval_query=reshaped.retrieval_query,
                before_route=before_route,
                after_route=after_route,
                before_sources=before_sources,
                after_sources=after_sources,
            )
        )

    return results


def print_summary(results: List[EvalResult], retrieval_enabled: bool) -> None:
    route_before_matches = 0
    route_after_matches = 0
    route_improved = 0
    route_regressed = 0

    def md(text: str) -> str:
        return str(text).replace("|", "\\|").replace("\n", " ").strip()

    def docs_cell(items: List[str]) -> str:
        if not items:
            return "skipped"
        shortened = []
        for item in items:
            shortened.append(md(item[:140]))
        return "<br>".join(shortened)

    for index, result in enumerate(results, start=1):
        before_status = get_route_label_status(result.expected_route, result.before_route)
        after_status = get_route_label_status(result.expected_route, result.after_route)

        if before_status == "match":
            route_before_matches += 1
        if after_status == "match":
            route_after_matches += 1
        if before_status != "match" and after_status == "match":
            route_improved += 1
        if before_status == "match" and after_status != "match":
            route_regressed += 1

    print("# Semantic Router Preliminary Evaluation")
    print()
    print("## Summary")
    print()
    print("| Metric | Value |")
    print("| --- | ---: |")
    print(f"| Queries evaluated | {len(results)} |")
    print(f"| Before matches expected route | {route_before_matches} |")
    print(f"| After matches expected route | {route_after_matches} |")
    print(f"| Improved after reshape | {route_improved} |")
    print(f"| Regressed after reshape | {route_regressed} |")
    print(f"| Docs comparison enabled | {'yes' if retrieval_enabled else 'no'} |")
    print(f"| Semantic router package available | {'yes' if HAS_SEMANTIC_ROUTER else 'no (TF-IDF fallback used)'} |")
    print()
    print("## Per-Query Results")
    print()
    print("| # | Query | Expected Route | Before Route | After Route | Route Hint | Query Type | Routing Query | Retrieval Query | Before Docs | After Docs | Notes |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")

    for index, result in enumerate(results, start=1):
        before_status = get_route_label_status(result.expected_route, result.before_route)
        after_status = get_route_label_status(result.expected_route, result.after_route)

        before_route_cell = f"{md(result.before_route)} ({before_status})"
        after_route_cell = f"{md(result.after_route)} ({after_status})"
        before_docs_cell = docs_cell(result.before_sources) if retrieval_enabled else "skipped"
        after_docs_cell = docs_cell(result.after_sources) if retrieval_enabled else "skipped"

        print(
            f"| {index} | {md(result.query)} | {md(result.expected_route)} | "
            f"{before_route_cell} | {after_route_cell} | {md(result.route_hint or 'none')} | "
            f"{md(result.query_type)} | {md(result.routing_query)} | "
            f"{md(result.retrieval_query)} | {before_docs_cell} | {after_docs_cell} | {md(result.note)} |"
        )

    print()
    if retrieval_enabled:
        print("Preliminary readout: if the `After Route` column matches intent more often and `After Docs` looks more relevant by inspection,")
        print('it is reasonable to report that "preliminary evaluation shows improvement."')
    else:
        print("Docs comparison was skipped because `OPENAI_API_KEY`, the Chroma DB, or the target collection was unavailable.")
    if not HAS_SEMANTIC_ROUTER:
        print("Routing used a TF-IDF fallback because `semantic_router` is not installed in this environment.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate semantic router before/after query reshaping.")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="Number of retrieved docs to show.")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Path to local Chroma DB.")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION, help="Chroma collection to query.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    retrieval_enabled = retrieval_is_available(args.db_path, args.collection)
    results = await evaluate_queries(
        top_k=args.top_k,
        db_path=args.db_path,
        collection_name=args.collection,
    )
    print_summary(results=results, retrieval_enabled=retrieval_enabled)


if __name__ == "__main__":
    asyncio.run(main())
