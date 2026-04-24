# Query Reshaping Update

## Overview

This update integrates a query understanding layer into the semantic routing pipeline.
Instead of routing raw user input directly, the system now reshapes each query into
different forms for routing and retrieval.

The goal is to improve performance on short, fragmented, or concept-oriented queries such as:

- `sgd`
- `week3 slides`
- `lab 2 requirements`
- `adam optimizer`

## What Was Implemented

### 1. Query Understanding Layer

In `src/services/queryReshaper.py`, each incoming query is transformed into:

- `routing_query`: a clearer version of the user intent for routing
- `retrieval_query`: an expanded version of the query for document retrieval
- `query_type`: a lightweight classification of the query
- `route_hint`: an explicit routing hint when intent is clear

The reshaper currently detects:

- well-formed questions
- fragment queries
- concept-only queries
- short queries

### 2. Routing Integration

In `src/router/semanticRouter.py`, the reshaped query is now part of the real request path:

- `routing_query` is used for semantic routing
- `retrieval_query` is used for vector retrieval
- `route_hint` can override the semantic route when the intent is reliable

This is especially useful for course-concept and course-material queries, which are now
preferentially routed to `material_info` so they can benefit from retrieval-grounded answers.

### 3. Evaluation Script

A lightweight evaluation script was added:

- `evaluate_semantic_router.py`

It compares:

- before route: original query -> route
- after route: reshaped query -> route
- before docs: original query -> retrieval
- after docs: reshaped retrieval query -> retrieval

The output is formatted as a Markdown table for easy reporting.

## Current Preliminary Result

After adding route hints, the latest preliminary routing evaluation showed:

- Queries evaluated: `10`
- Before matches expected route: `3/10`
- After matches expected route: `9/10`
- Improved cases: `6`
- Regressions: `0`

This suggests a strong improvement for short academic concept queries and fragmented
course-material queries.

## Limitations

- The current docs comparison was not completed because the local environment did not have:
  - `OPENAI_API_KEY`
  - an available Chroma database with `course_materials`
- In the local evaluation environment, `semantic_router` was unavailable, so the script
  used a TF-IDF fallback for routing evaluation
- Therefore, current results should still be described as preliminary

## How To Run

Run the evaluation script:

```powershell
py -3 evaluate_semantic_router.py
```

To enable docs comparison, make sure:

1. `OPENAI_API_KEY` is set
2. `DB_PATH` points to a valid Chroma database
3. the `course_materials` collection has been loaded

## Summary

This update moves query reshaping from a prototype idea into the real routing and retrieval flow.
It improves the system's ability to interpret underspecified student queries and route them toward
document-grounded responses.
