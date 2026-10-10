"""Knowledge retrieval tools over the curated maintenance corpus.

Retrieved passages are treated strictly as untrusted reference data: they are
never executed as instructions. Every passage carries a document id, section
id, and exact text so citations can be validated later.
"""

from __future__ import annotations

from typing import Any

from services.api.services.knowledge_repository import (
    get_knowledge_repository,
)


def retrieve_knowledge(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Retrieve the most relevant maintenance passages for a query."""
    repo = get_knowledge_repository()
    return [passage.to_dict() for passage in repo.search(query, top_k=top_k)]


def get_passage(document_id: str, section_id: str) -> dict[str, Any] | None:
    """Fetch an exact passage by its stable ids, or ``None`` if it does not exist."""
    passage = get_knowledge_repository().get_passage(document_id, section_id)
    return passage.to_dict() if passage else None


def knowledge_catalog() -> list[dict[str, Any]]:
    """Return the full (small) catalog of available passages."""
    return get_knowledge_repository().catalog()


__all__ = ["retrieve_knowledge", "get_passage", "knowledge_catalog"]
