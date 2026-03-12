"""
In-process adapters for the internal graph retrieval engines.

These adapters bypass the legacy HTTP transport layer while reusing the existing
graph and LightRAG service handlers for behavior parity.
"""

from __future__ import annotations

from typing import Any
import os
import sys
from pathlib import Path


_SERVICES_DIR = Path(__file__).resolve().parent
_SRC_DIR = _SERVICES_DIR.parent
_INTEGRATIONS_DIR = _SRC_DIR / "integrations"

for candidate in (str(_SERVICES_DIR), str(_SRC_DIR), str(_INTEGRATIONS_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)


def _unpack_flask_result(result: Any) -> tuple[int, Any]:
    response = result
    status_code = 200

    if isinstance(result, tuple):
        response = result[0]
        if len(result) >= 2 and isinstance(result[1], int):
            status_code = result[1]
        elif hasattr(response, "status_code"):
            status_code = int(response.status_code)
    elif hasattr(response, "status_code"):
        status_code = int(response.status_code)

    if hasattr(response, "get_json"):
        try:
            payload = response.get_json(silent=True)
        except TypeError:
            payload = response.get_json()
    else:
        payload = response

    return status_code, payload


def query_networkx_graph(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    from src.services import graph_query_service

    if not graph_query_service.graph_loaded:
        graph_query_service.initialize_graph(os.getenv("GRAPH_PATH"))

    with graph_query_service.app.test_request_context(
        "/query", method="POST", json=payload
    ):
        status_code, response_payload = _unpack_flask_result(
            graph_query_service.query_graph()
        )
    return status_code, response_payload if isinstance(response_payload, dict) else {"response": response_payload}


def graph_health() -> tuple[int, dict[str, Any]]:
    from src.services import graph_query_service

    if not graph_query_service.graph_loaded:
        graph_query_service.initialize_graph(os.getenv("GRAPH_PATH"))

    with graph_query_service.app.test_request_context("/health", method="GET"):
        status_code, response_payload = _unpack_flask_result(graph_query_service.health())
    return status_code, response_payload if isinstance(response_payload, dict) else {}


def graph_stats() -> tuple[int, dict[str, Any]]:
    from src.services import graph_query_service

    if not graph_query_service.graph_loaded:
        graph_query_service.initialize_graph(os.getenv("GRAPH_PATH"))

    with graph_query_service.app.test_request_context("/stats", method="GET"):
        status_code, response_payload = _unpack_flask_result(graph_query_service.get_stats())
    return status_code, response_payload if isinstance(response_payload, dict) else {}


def find_graph_path(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    from src.services import graph_query_service

    if not graph_query_service.graph_loaded:
        graph_query_service.initialize_graph(os.getenv("GRAPH_PATH"))

    with graph_query_service.app.test_request_context(
        "/path", method="POST", json=payload
    ):
        status_code, response_payload = _unpack_flask_result(graph_query_service.find_path())
    return status_code, response_payload if isinstance(response_payload, dict) else {}


def search_graph_entities(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    from src.services import graph_query_service

    if not graph_query_service.graph_loaded:
        graph_query_service.initialize_graph(os.getenv("GRAPH_PATH"))

    with graph_query_service.app.test_request_context(
        "/search_entities", method="POST", json=payload
    ):
        status_code, response_payload = _unpack_flask_result(graph_query_service.search_entities())
    return status_code, response_payload if isinstance(response_payload, dict) else {}


def query_lightrag(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    from src.integrations import lightrag_service

    with lightrag_service.app.test_request_context(
        "/query", method="POST", json=payload
    ):
        status_code, response_payload = _unpack_flask_result(
            lightrag_service.query_graph()
        )
    return status_code, response_payload if isinstance(response_payload, dict) else {"answer": str(response_payload or "")}


def lightrag_health() -> tuple[int, dict[str, Any]]:
    from src.integrations import lightrag_service

    with lightrag_service.app.test_request_context("/health", method="GET"):
        status_code, response_payload = _unpack_flask_result(lightrag_service.health())
    return status_code, response_payload if isinstance(response_payload, dict) else {}


def lightrag_stats() -> tuple[int, dict[str, Any]]:
    from src.integrations import lightrag_service

    with lightrag_service.app.test_request_context("/stats", method="GET"):
        status_code, response_payload = _unpack_flask_result(lightrag_service.stats())
    return status_code, response_payload if isinstance(response_payload, dict) else {}
