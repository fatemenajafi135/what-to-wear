"""Shared retrieval types."""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.documents import Document


@dataclass
class RetrievalResult:
    """Per-layer retrieved chunks + a flat view. Every chunk carries its
    {source, url, layer, rule_id} metadata for downstream citation."""

    l1: list[Document] = field(default_factory=list)  # Combine (harmony rules)
    l3: list[Document] = field(default_factory=list)  # Elevate (trends)
    l4: list[Document] = field(default_factory=list)  # Filter (dress code + weather)
    strategy: str = "hybrid"

    def all(self) -> list[Document]:
        return [*self.l4, *self.l1, *self.l3]

    def rule_ids(self) -> list[str]:
        return [d.metadata["rule_id"] for d in self.all()]
