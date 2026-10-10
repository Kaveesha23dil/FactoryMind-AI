"""Local knowledge-base repository with deterministic passage retrieval.

The corpus is tiny, so keyword / hybrid retrieval is sufficient and avoids
unnecessary vector infrastructure. Every retrieved passage is returned with a
stable document id and section id so citations can be validated against the
corpus and never invented.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWLEDGE_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "documents.json"

_TOKEN_RE = re.compile(r"[a-z0-9]+")

#: Common words ignored during retrieval scoring.
_STOPWORDS = {
    "the", "and", "for", "are", "was", "with", "that", "this", "from", "not",
    "but", "has", "have", "its", "can", "may", "any", "all", "per", "into",
    "than", "then", "when", "while", "which", "there", "these", "those", "over",
}


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN_RE.findall(text.lower())
        if len(token) >= 3 and token not in _STOPWORDS
    ]


@dataclass(frozen=True)
class Passage:
    document_id: str
    document_title: str
    section_id: str
    heading: str
    text: str
    source: dict = field(default_factory=dict)
    keywords: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "document_title": self.document_title,
            "section_id": self.section_id,
            "heading": self.heading,
            "text": self.text,
            "source": self.source,
        }


class KnowledgeRepository:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or KNOWLEDGE_PATH)
        self.corpus_meta: dict = {}
        self._passages: list[Passage] = []
        self._by_id: dict[tuple[str, str], Passage] = {}
        self._load()

    def _load(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.corpus_meta = raw.get("corpus", {})
        passages: list[Passage] = []
        for document in raw.get("documents", []):
            doc_id = document["doc_id"]
            for section in document.get("sections", []):
                passage = Passage(
                    document_id=doc_id,
                    document_title=document["title"],
                    section_id=section["section_id"],
                    heading=section["heading"],
                    text=section["text"],
                    source=document.get("source", {}),
                    keywords=tuple(section.get("keywords", [])),
                )
                passages.append(passage)
                self._by_id[(doc_id, passage.section_id)] = passage
        self._passages = passages
        logger.info("Loaded knowledge base: %d passages", len(passages))

    @property
    def passages(self) -> list[Passage]:
        return list(self._passages)

    def get_passage(self, document_id: str, section_id: str) -> Passage | None:
        return self._by_id.get((document_id, section_id))

    def _score(self, passage: Passage, query_tokens: list[str]) -> float:
        if not query_tokens:
            return 0.0
        keyword_tokens = set(_tokenize(" ".join(passage.keywords)))
        heading_tokens = set(_tokenize(passage.heading))
        body_tokens = _tokenize(passage.text)
        body_counts: dict[str, int] = {}
        for token in body_tokens:
            body_counts[token] = body_counts.get(token, 0) + 1

        score = 0.0
        for token in query_tokens:
            if token in keyword_tokens:
                score += 3.0
            if token in heading_tokens:
                score += 2.0
            if token in body_counts:
                score += 1.0
        return score

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[Passage]:
        """Return the highest-scoring passages for a free-text query.

        Falls back to the first ``top_k`` passages when no query token matches,
        so the Knowledge Agent always receives a non-empty, cited context.
        """
        query_tokens = _tokenize(query)
        scored = [(self._score(passage, query_tokens), passage) for passage in self._passages]
        ranked = [item for item in sorted(scored, key=lambda x: x[0], reverse=True)]
        hits = [passage for score, passage in ranked if score > min_score][:top_k]
        if not hits:
            hits = self._passages[:top_k]
        return hits

    def catalog(self) -> list[dict]:
        return [
            {
                "document_id": passage.document_id,
                "document_title": passage.document_title,
                "section_id": passage.section_id,
                "heading": passage.heading,
            }
            for passage in self._passages
        ]


@lru_cache(maxsize=1)
def get_knowledge_repository() -> KnowledgeRepository:
    return KnowledgeRepository()
