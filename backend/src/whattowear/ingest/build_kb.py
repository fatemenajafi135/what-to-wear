"""Manifest-driven knowledge-base build.

Reads `infra/corpus.yaml` (constitution Principle X — the tracked
reproducibility contract; the documents it describes never are), loads +
chunks every ingestable source into one metadata-tagged list of chunks,
and (given a gateway key) embeds them into a Qdrant collection with a
`layer` field for filtering.

This module holds the reusable build logic only — `ingest/cli.py` is the
actual CLI entry point (constitution: "Ingestion is a CLI entry point,
never an HTTP endpoint"); `kb.py`'s `get_kb()` also calls into this module
to build/reconnect to the process-wide KnowledgeBase singleton.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import yaml
from langchain_core.documents import Document

from ..logging_utils import configure_logging, get_logger
from ..ports import VectorStore
from .chunkers import chunk_docs
from .loaders import load_source

# infra/corpus.yaml is 4 levels up from this file (ingest -> whattowear -> src -> backend -> repo root)
MANIFEST_PATH = Path(__file__).resolve().parents[4] / "infra" / "corpus.yaml"
COLLECTION = "whattowear_kb"
REQUIRED_META = ("source", "url", "layer", "rule_id")

log = get_logger(__name__)


def _preview(text: str, n: int = 70) -> str:
    return text[:n].replace("\n", " ").strip()


def load_manifest(path: Path = MANIFEST_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)["sources"]


def ingest_all(corpus_dir: Path, manifest_path: Path = MANIFEST_PATH, verbose: bool = False) -> list[Document]:
    """Load + chunk every `ingest: true` source. No embeddings — offline-safe.

    With verbose=True, logs each source as it's processed and every chunk
    it produced (rule_id + preview) — inspect before paying to embed
    anything."""
    configure_logging(verbose)
    chunks: list[Document] = []
    for source in load_manifest(manifest_path):
        if not source.get("ingest"):
            log.debug("skip (not ingestable, status=%s): %s", source.get("status"), source["name"])
            continue
        log.info(
            "source: %-52s layer=%-3s loader=%-9s status=%s",
            source["name"],
            source.get("layer"),
            source.get("loader"),
            source.get("status"),
        )
        docs = load_source(source, corpus_dir)
        if not docs:
            log.warning("  -> 0 docs loaded (fetch failed or skipped)")
            continue
        src_chunks = chunk_docs(docs, source.get("chunker", "section"), **source.get("chunker_options", {}))
        log.info("  -> %d chunk(s) [%s]", len(src_chunks), source.get("chunker", "section"))
        for c in src_chunks:
            log.debug(
                "     chunk %-28s (%4d chars): %s",
                c.metadata["rule_id"],
                len(c.page_content),
                _preview(c.page_content),
            )
        chunks.extend(src_chunks)
    _validate(chunks)
    return chunks


def _validate(chunks: list[Document]) -> None:
    seen_ids: set[str] = set()
    for c in chunks:
        for key in REQUIRED_META:
            if not c.metadata.get(key):
                raise ValueError(f"chunk missing required metadata '{key}': {c.metadata}")
        rid = c.metadata["rule_id"]
        if rid in seen_ids:
            raise ValueError(f"duplicate rule_id: {rid}")
        seen_ids.add(rid)


def build_vectorstore(
    chunks: list[Document],
    collection: str = COLLECTION,
    url: str | None = None,
    api_key: str | None = None,
) -> VectorStore:
    """Embed chunks into a Qdrant collection (needs a gateway key — this is
    the costly step; see `sample_check` to validate cheaply first).

    url=None -> in-memory (gone when the process exits).
    Pass a server URL (the local Docker container, `infra/docker-compose.yml`)
    to persist instead — see `kb.py`'s `get_kb()`, which is what actually
    uses this in production."""
    from langchain_qdrant import QdrantVectorStore

    from ..adapters.llm_gateway import get_embeddings
    from ..core.config import get_settings

    settings = get_settings()
    log.info(
        "embedding %d chunk(s) into collection '%s' (%s)...",
        len(chunks),
        collection,
        f"persisting to {url}" if url else "in-memory",
    )
    location_kwargs = {"url": url, "api_key": api_key} if url else {"location": ":memory:"}
    # force_recreate: a rebuild must REPLACE the collection, not add to it.
    # Without this, from_documents upserts new points alongside whatever's
    # already there, so a persisted collection accumulates across runs. The
    # point count then never matches len(chunks), so get_kb() re-embeds on
    # every process start. Recreating means a rebuild always lands at
    # exactly len(chunks), so the freshness check passes afterward and
    # startups just reconnect. A longer client timeout + smaller upsert
    # batches, so a slow/cold Qdrant response can't abort the (re)build
    # mid-way and leave a partial collection — both tunable via Settings
    # for a persistently slow host.
    vs = QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
        collection_name=collection,
        force_recreate=True,
        timeout=settings.wtw_qdrant_timeout,
        batch_size=settings.wtw_qdrant_batch_size,
        **location_kwargs,
    )
    if url:
        # Server mode requires an explicit payload index to filter on a
        # field — in-memory/local-path mode doesn't enforce this.
        # hybrid.py's L3 retrieval filters on metadata.layer; without this
        # index that filtered similarity_search raises a 400 Bad Request
        # ("Index required but not found for metadata.layer"). A compound
        # filter needs an index per field used in it — the L1 semantic
        # branch filters on layer AND granularity together, so granularity
        # needs its own index too.
        from qdrant_client import models

        vs.client.create_payload_index(
            collection_name=collection,
            field_name="metadata.layer",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        vs.client.create_payload_index(
            collection_name=collection,
            field_name="metadata.granularity",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
    return vs


def sample_check(chunks: list[Document], n_per_layer: int = 2, probes: list[str] | None = None) -> None:
    """Cheap sanity check: embed only a HANDFUL of chunks (n_per_layer per
    layer, deterministic by rule_id) into a throwaway collection, then run
    a couple of sample similarity searches so you can eyeball whether the
    setup (embedding model, metadata, chunk content) looks right — BEFORE
    paying to embed the full corpus."""
    by_layer: dict[str, list[Document]] = defaultdict(list)
    for c in sorted(chunks, key=lambda d: d.metadata["rule_id"]):
        by_layer[c.metadata["layer"]].append(c)
    sample = [c for layer_chunks in by_layer.values() for c in layer_chunks[:n_per_layer]]

    log.info(
        "sample-check: embedding %d/%d chunks (%d per layer, deterministic) — NOT the full corpus",
        len(sample),
        len(chunks),
        n_per_layer,
    )
    for c in sample:
        log.info("  sample chunk: %-28s [%s] %s", c.metadata["rule_id"], c.metadata["layer"], _preview(c.page_content))

    vs = build_vectorstore(sample, collection="whattowear_sample_check")
    log.info("sample-check: embedded OK. Running sanity similarity searches...")

    probes = probes or ["formal wedding attire", "cold weather outerwear", "current fashion trend"]
    for q in probes:
        hits = vs.similarity_search(q, k=2)
        log.info("  query: %r", q)
        for h in hits:
            log.info("    -> %-28s [%s] %s", h.metadata["rule_id"], h.metadata["layer"], _preview(h.page_content))

    log.info(
        "sample-check complete. If results look right, run the full ingestion CLI (%d chunks).",
        len(chunks),
    )


def write_attributions(path: Path | None = None) -> Path:
    """CC-BY-SA share-alike: list every attributable source."""
    path = path or (MANIFEST_PATH.parents[1] / "backend" / "ATTRIBUTIONS.md")
    lines = [
        "# Attributions",
        "",
        "Sources ingested into the What to Wear knowledge base, by license.",
        "CC-BY-SA sources require attribution + share-alike.",
        "",
    ]
    by_license: dict[str, list[dict]] = {}
    for s in load_manifest():
        if not s.get("ingest"):
            continue
        by_license.setdefault(s.get("license", "unknown"), []).append(s)
    for lic in sorted(by_license):
        lines.append(f"## {lic}")
        for s in by_license[lic]:
            url = s.get("url", "")
            lines.append(f"- **{s['name']}** ({s['layer']}) — {url}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def print_report(chunks: list[Document]) -> None:
    by_layer = Counter(c.metadata["layer"] for c in chunks)
    by_source = Counter(c.metadata["source"] for c in chunks)
    print(f"\nTotal chunks: {len(chunks)}")
    print("Per layer:", dict(sorted(by_layer.items())))
    print("Per source:")
    for src, n in by_source.most_common():
        print(f"  {n:3d}  {src}")
    # guard: no copyrighted book text stored. Reference-only BOOK sources
    # (loader: reference_only) must contribute zero chunks. Distilled L1
    # cards may *cite* a book as provenance (url reference-only://…) — that
    # is our own text and is allowed; the guard keys on the book source
    # names instead.
    ref_only_names = {s["name"] for s in load_manifest() if s.get("loader") == "reference_only"}
    leaked = [c for c in chunks if c.metadata.get("source") in ref_only_names]
    assert not leaked, f"reference-only book text leaked into the store: {leaked[:1]}"
    print("\nOK: metadata complete, rule_ids unique, no reference-only book text stored.")
