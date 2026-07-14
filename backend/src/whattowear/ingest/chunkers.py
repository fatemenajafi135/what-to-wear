"""Chunking strategies.

A **pluggable registry** (`CHUNKERS`), not a single splitter — different files
and layers legitimately need different strategies, and shouldn't be forced
through the same one. Selected per source via the manifest's `chunker:` field
(currently only `atomic`/`section` are wired into any real source; the rest
are built for the next round of experiments, per notebook 02's baseline vs.
advanced story — none of them are activated by the current manifest).

- **atomic** — one style rule / concept per chunk. Used for authored cards
  (dress codes, trend cards, distilled rules). The doc is already one rule, so
  its `rule_id` is preserved verbatim. This is what makes metadata-filtering
  precise and gives clean, stable citations. *(active: L1/L3/L4 card sources)*

- **section** — fixed character-size splitting for long articles / PD prose.
  Avoids whole-article "mush" retrieval. Each chunk gets a synthesized, stable
  `rule_id` derived from the source so citations still resolve. Its separators
  target old MediaWiki wikitext headers (`== H ==`), NOT the ATX markdown
  (`# H`) that wiki_refine.py now produces — for real markdown sources,
  `markdown_header` below is the structurally-correct fit; `section` still
  works (falls through to `\\n\\n` paragraph splitting) but is header-blind.
  *(active: all current long-form sources, incl. the refined Wikipedia .md files)*

- **markdown_header** — splits on ATX header hierarchy first (keeping the
  header path, e.g. "Color mixing > Primary colors", as metadata), then caps
  oversized sections by character count. The structural match for
  wiki_refine.py output. Free, offline. *(not yet wired to any source)*

- **token** — same recursive splitting as `section`, but sized by tiktoken
  token count instead of raw characters — chunk size tracks what the
  embedding/chat model actually consumes, not a char-count proxy for it. Free,
  offline. *(not yet wired to any source)*

- **semantic** — embedding-based breakpoint chunking (splits where consecutive
  sentences' embedding similarity drops sharply) via LangChain's
  `SemanticChunker`. COSTS an embedding call per sentence — opt-in only. This
  is the AIE10 course's flagged "Advanced Build: implement a semantic chunking
  strategy." *(implemented, intentionally never executed this session — do not
  call chunk_semantic() without deliberately opting into the cost)*

Rationale for atomic vs section (graded, see notebook 01): atomic rules are the
retrieval + citation unit; section chunks keep long sources usable without
dominating similarity. We deliberately accept the resulting chunk-size
heterogeneity and measure its effect (Task-6 second lever).
"""

from __future__ import annotations

import os
import re

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

# Section splitter tuned for articles/prose; heterogeneity vs atomic cards is
# intentional and measured in the eval harness. chunk_size is env-configurable so
# the Task-6 "change one variable" experiment (notebook 02) can sweep it.
SECTION_CHUNK_SIZE = int(os.environ.get("WTW_CHUNK_SIZE", "900"))
SECTION_CHUNK_OVERLAP = int(os.environ.get("WTW_CHUNK_OVERLAP", "120"))
_SECTION_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=SECTION_CHUNK_SIZE,
    chunk_overlap=SECTION_CHUNK_OVERLAP,
    add_start_index=True,
    separators=["\n== ", "\n=== ", "\n\n", "\n", ". ", " "],
)

_MD_HEADERS_TO_SPLIT_ON = [("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4")]
_MD_HEADER_KEYS = [h[1] for h in _MD_HEADERS_TO_SPLIT_ON]


def _slug(text: str, maxlen: int = 24) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:maxlen] or "src"


def chunk_atomic(docs: list[Document]) -> list[Document]:
    """Cards are already atomic; keep as-is (rule_id already present)."""
    out = []
    for d in docs:
        if "rule_id" not in d.metadata:
            d.metadata["rule_id"] = _slug(d.page_content[:24])
        d.metadata["granularity"] = "atomic"
        out.append(d)
    return out


def chunk_section(docs: list[Document]) -> list[Document]:
    """Split long docs into fixed character-size chunks, stamping a stable rule_id."""
    out: list[Document] = []
    for d in docs:
        layer = d.metadata.get("layer", "Lx")
        prefix = f"{layer}-{_slug(d.metadata.get('source', 'src'))}"
        pieces = _SECTION_SPLITTER.split_documents([d])
        for i, piece in enumerate(pieces):
            piece.metadata = dict(d.metadata)  # inherit source/url/layer/license
            piece.metadata["rule_id"] = f"{prefix}-sec-{i:03d}"
            piece.metadata["granularity"] = "section"
            out.append(piece)
    return out


def chunk_markdown_header(docs: list[Document], max_chars: int = 900, overlap: int = 120) -> list[Document]:
    """Header-hierarchy-aware splitting for real ATX markdown (e.g. wiki_refine.py
    output): split on `#`/`##`/`###`/`####` first, keeping the header path as
    metadata (`section_path`), then cap any still-oversized section by character
    count so no single chunk balloons. Free, offline — no embedding calls."""
    header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=_MD_HEADERS_TO_SPLIT_ON, strip_headers=False)
    size_splitter = RecursiveCharacterTextSplitter(chunk_size=max_chars, chunk_overlap=overlap, add_start_index=True)

    out: list[Document] = []
    for d in docs:
        layer = d.metadata.get("layer", "Lx")
        prefix = f"{layer}-{_slug(d.metadata.get('source', 'src'))}"
        header_sections = header_splitter.split_text(d.page_content)
        idx = 0
        for section in header_sections:
            pieces = (
                size_splitter.split_documents([section])
                if len(section.page_content) > max_chars
                else [section]
            )
            for piece in pieces:
                meta = dict(d.metadata)  # source/url/layer/license from the parent doc
                meta["rule_id"] = f"{prefix}-md-{idx:03d}"
                meta["granularity"] = "section"
                header_path = " > ".join(
                    str(piece.metadata[k]) for k in _MD_HEADER_KEYS if piece.metadata.get(k)
                )
                if header_path:
                    meta["section_path"] = header_path
                out.append(Document(page_content=piece.page_content, metadata=meta))
                idx += 1
    return out


def chunk_token(docs: list[Document], max_tokens: int = 250, overlap_tokens: int = 40) -> list[Document]:
    """Recursive splitting sized by tiktoken token count (cl100k_base) instead
    of raw characters — tracks what the embedding/chat model actually consumes
    rather than a char-count proxy for it. Free, offline (tiktoken runs locally,
    no API call)."""
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base", chunk_size=max_tokens, chunk_overlap=overlap_tokens,
    )
    out: list[Document] = []
    for d in docs:
        layer = d.metadata.get("layer", "Lx")
        prefix = f"{layer}-{_slug(d.metadata.get('source', 'src'))}"
        pieces = splitter.split_documents([d])
        for i, piece in enumerate(pieces):
            piece.metadata = dict(d.metadata)
            piece.metadata["rule_id"] = f"{prefix}-tok-{i:03d}"
            piece.metadata["granularity"] = "section"
            out.append(piece)
    return out


def chunk_semantic(docs: list[Document], breakpoint_type: str = "percentile") -> list[Document]:
    """Embedding-based semantic chunking: splits where consecutive sentences'
    embedding similarity drops sharply, instead of a fixed size. COSTS one
    embedding call per sentence via the gateway — this is opt-in, experiment-only
    code. Nothing in the manifest uses it; do not call this without deliberately
    choosing to pay for it."""
    from langchain_experimental.text_splitter import SemanticChunker

    from ..config import get_embeddings  # lazy: no gateway key required unless called

    splitter = SemanticChunker(get_embeddings(), breakpoint_threshold_type=breakpoint_type)
    out: list[Document] = []
    for d in docs:
        layer = d.metadata.get("layer", "Lx")
        prefix = f"{layer}-{_slug(d.metadata.get('source', 'src'))}"
        pieces = splitter.split_documents([d])
        for i, piece in enumerate(pieces):
            piece.metadata = dict(d.metadata)
            piece.metadata["rule_id"] = f"{prefix}-sem-{i:03d}"
            piece.metadata["granularity"] = "section"
            out.append(piece)
    return out


CHUNKERS = {
    "atomic": chunk_atomic,
    "section": chunk_section,
    "markdown_header": chunk_markdown_header,
    "token": chunk_token,
    "semantic": chunk_semantic,
}


def chunk_docs(docs: list[Document], strategy: str, **kwargs) -> list[Document]:
    fn = CHUNKERS.get(strategy, chunk_section)
    return fn(docs, **kwargs) if kwargs else fn(docs)
