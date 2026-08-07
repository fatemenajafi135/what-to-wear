"""Per-source-type loaders. Each returns LangChain `Document`s with the
citation metadata (`source, url, layer, rule_id`) already stamped where the
loader can, deferring chunk-level `rule_id` to the chunkers.

Legal note: `reference_only` sources are never loaded as text — they exist
in the manifest for provenance only and their rules live in hand-distilled
card files.

Every source path resolves relative to `CORPUS_LOCAL_DIR` (constitution
Principle X: no document path lives inside the repo) — replacing the
legacy `REPO_ROOT`-relative scheme entirely. Callers pass `corpus_dir`
explicitly (from `ingest/cli.py`/`build_kb.py`, which read it from
`core.config.Settings` once) rather than each loader reading the
environment itself.
"""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.documents import Document

from ..logging_utils import get_logger

log = get_logger(__name__)

# Cap raw text pulled from long sources so a single 19th-c book / article
# doesn't flood the store.
EPUB_MAX_CHARS = 30_000
WIKI_MAX_CHARS = 18_000


def load_cards(source: dict, corpus_dir: Path) -> list[Document]:
    """Distilled/own content: one JSONL line = one atomic, pre-tagged chunk."""
    path = corpus_dir / source["path"]
    docs: list[Document] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            card = json.loads(line)
            meta = {
                "source": card.get("source", source["name"]),
                "url": card.get("url", source.get("url", "")),
                "layer": source["layer"],
                "rule_id": card["rule_id"],
                "license": source.get("license"),
            }
            for k in ("occasion", "formality", "temp_band", "season"):
                if card.get(k) is not None:
                    meta[k] = card[k]
            docs.append(Document(page_content=card["text"], metadata=meta))
    return docs


def load_wikipedia(source: dict, corpus_dir: Path) -> list[Document]:
    """Fetch (and cache) Wikipedia article text. Cached under
    `corpus_dir/kb/cache/` so rebuilds are fast and reproducible offline —
    not committed (constitution Principle X; the cache is regenerable, per
    inventory §Q1-Q3)."""
    from langchain_community.document_loaders import WikipediaLoader

    cache_dir = corpus_dir / "kb" / "cache"
    queries = [source["query"]] + list(source.get("extra_queries", []))
    docs: list[Document] = []
    cache_dir.mkdir(parents=True, exist_ok=True)
    for q in queries:
        slug = q.lower().replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")
        cache_file = cache_dir / f"wiki_{slug}.txt"
        if cache_file.exists():
            text = cache_file.read_text(encoding="utf-8")
        else:
            try:
                loaded = WikipediaLoader(query=q, load_max_docs=1, doc_content_chars_max=WIKI_MAX_CHARS).load()
                text = loaded[0].page_content if loaded else ""
                if text.strip():
                    cache_file.write_text(text, encoding="utf-8")
            except Exception as exc:  # noqa: BLE001 - offline/sandbox: skip, don't crash
                log.warning(
                    "Wikipedia fetch failed for %r (%s); skipping. Re-run with network, "
                    "or use wiki_refine.py to ingest a locally-saved page instead.",
                    q,
                    exc,
                )
                text = ""
        if text.strip():
            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": f"{source['name']} — {q}",
                        "url": source.get("url", ""),
                        "layer": source["layer"],
                        "license": source.get("license"),
                    },
                )
            )
    return docs


def load_wiki_md(source: dict, corpus_dir: Path) -> list[Document]:
    """A refined Wikipedia page (see wiki_refine.py): a local .md file,
    already cleaned of chrome (See also/References/edit links/etc). No
    live-fetch dependency — reproducible, reviewable, diffable."""
    path = corpus_dir / source["path"]
    if not path.exists():
        log.warning(
            "wiki_md source not found: %s (save the page, then run "
            "`python -m whattowear.ingest.wiki_refine <html>` to produce it)",
            path,
        )
        return []
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    if lines and lines[0].startswith("<!--"):  # drop the provenance comment line
        text = "\n".join(lines[1:]).lstrip("\n")
    return [
        Document(
            page_content=text,
            metadata={
                "source": source["name"],
                "url": source.get("url", ""),
                "layer": source["layer"],
                "license": source.get("license"),
            },
        )
    ]


def load_epub(source: dict, corpus_dir: Path) -> list[Document]:
    """Public-domain EPUB → bounded plain text (front matter skipped heuristically)."""
    import ebooklib
    from bs4 import BeautifulSoup
    from ebooklib import epub

    path = corpus_dir / source["path"]
    if not path.exists():
        log.warning("epub source not found: %s", path)
        return []
    book = epub.read_epub(str(path))
    parts: list[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        txt = soup.get_text(separator=" ", strip=True)
        if len(txt) > 200:  # skip nav/title stubs
            parts.append(txt)
    full = "\n\n".join(parts)
    # skip likely Gutenberg front matter, keep a bounded body slice
    start = full.find("CHAPTER")
    if start == -1:
        start = min(len(full), 2000)
    body = full[start : start + EPUB_MAX_CHARS]
    return [
        Document(
            page_content=body,
            metadata={
                "source": source["name"],
                "url": source.get("url", ""),
                "layer": source["layer"],
                "license": source.get("license"),
            },
        )
    ]


LOADERS = {
    "cards": load_cards,
    "wikipedia": load_wikipedia,
    "wiki_md": load_wiki_md,
    "epub": load_epub,
}


def load_source(source: dict, corpus_dir: Path) -> list[Document]:
    """Dispatch a manifest source entry to its loader. Non-ingestable /
    reference-only / want-later entries return nothing."""
    if not source.get("ingest"):
        return []
    loader = source.get("loader")
    if loader not in LOADERS:
        return []
    return LOADERS[loader](source, corpus_dir)
