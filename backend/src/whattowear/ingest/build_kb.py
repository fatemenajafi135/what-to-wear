"""Manifest-driven knowledge-base build.

Reads `data/kb/manifest.yaml`, loads + chunks every ingestable source into one
metadata-tagged list of chunks, and (given a gateway key) embeds them into an
in-memory Qdrant collection with a `layer` field for filtering.

Run as a script to build, validate metadata, print per-layer counts, and write
ATTRIBUTIONS.md. Use `--sample-check` to cheaply validate embeddings on a
handful of chunks before committing to `--embed` on the full corpus.
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from dotenv import load_dotenv
from langchain_core.documents import Document

from ..logging_utils import configure_logging, get_logger
from .chunkers import chunk_docs
from .loaders import REPO_ROOT, load_source

# QDRANT_URL/QDRANT_API_KEY below read os.environ at import time — this module
# must not rely on some other module (e.g. config.py) having already called
# load_dotenv() first, or these silently fall back to their hardcoded
# defaults whenever build_kb/kb is imported before anything that imports
# config.py (a real bug: caught when a fresh script importing only
# whattowear.kb picked up the wrong Qdrant URL despite .env being correct).
load_dotenv()

MANIFEST_PATH = REPO_ROOT / "data" / "kb" / "manifest.yaml"
COLLECTION = "whattowear_kb"
REQUIRED_META = ("source", "url", "layer", "rule_id")

# Qdrant server URL — persists the embedded corpus across process runs AND
# supports genuine concurrent access from multiple processes/notebook kernels
# at once (each `uv run python -c "..."` / notebook kernel is a separate
# process; without a shared store, every get_kb() call would re-embed all 391
# chunks from scratch). Local on-disk mode was tried first but only supports
# one process at a time — it kept producing "already locked" errors across
# ordinary multi-notebook usage, so a real server replaces it. Two ways to run
# one, either works, just point WTW_QDRANT_URL (+ WTW_QDRANT_API_KEY) at it:
#   - local Docker (kept around, not currently running):
#     docker run -d --name whattowear-qdrant -p 6333:6333 -p 6334:6334 \
#       -v ./artifacts/qdrant_server_storage:/qdrant/storage qdrant/qdrant
#     -> WTW_QDRANT_URL=http://localhost:6333, no api key
#   - Qdrant Cloud free tier (cloud.qdrant.io): create a cluster, copy its URL
#     + API key into .env as WTW_QDRANT_URL / WTW_QDRANT_API_KEY
# Set WTW_QDRANT_URL="" to force in-memory (e.g. tests/CI that want a
# guaranteed-fresh store).
QDRANT_URL: str | None = os.environ.get("WTW_QDRANT_URL", "http://localhost:6333") or None
QDRANT_API_KEY: str | None = os.environ.get("WTW_QDRANT_API_KEY") or None

log = get_logger(__name__)


def _preview(text: str, n: int = 70) -> str:
    return text[:n].replace("\n", " ").strip()


def load_manifest(path: Path = MANIFEST_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)["sources"]


def ingest_all(manifest_path: Path = MANIFEST_PATH, verbose: bool = False) -> list[Document]:
    """Load + chunk every `ingest: true` source. No embeddings — offline-safe.

    With verbose=True, logs each source as it's processed and every chunk it
    produced (rule_id + preview) — inspect before paying to embed anything.
    """
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
        docs = load_source(source)
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
):
    """Embed chunks into a Qdrant collection (needs a gateway key — this is the
    costly step; see `sample_check` to validate cheaply first).

    url=None -> in-memory (gone when the process exits, the old default).
    Pass a server URL (local Docker or Qdrant Cloud) to persist instead — see
    `kb.py`'s QDRANT_URL, which is what `get_kb()` actually uses."""
    from langchain_qdrant import QdrantVectorStore

    from ..config import get_embeddings

    log.info(
        "embedding %d chunk(s) into collection '%s' (%s)...",
        len(chunks),
        collection,
        f"persisting to {url}" if url else "in-memory",
    )
    location_kwargs = {"url": url, "api_key": api_key} if url else {"location": ":memory:"}
    # force_recreate: a rebuild must REPLACE the collection, not add to it.
    # Without this, from_documents upserts new points alongside whatever's
    # already there, so a persisted collection accumulates across runs (a real
    # bug: it bloated to 3314 points for a 391-chunk corpus). The point count
    # then never matches len(chunks), so get_kb() re-embeds on every process
    # start — slow, and it intermittently times out against Qdrant Cloud.
    # Recreating means a rebuild always lands at exactly len(chunks), so the
    # freshness check passes afterward and startups just reconnect.
    # A longer client timeout + smaller upsert batches, so a slow/cold Qdrant
    # Cloud response can't abort the (re)build mid-way and leave a partial
    # collection (seen in practice: the default timeout aborted after the
    # first 64-point batch). Both tunable via env for a persistently slow host.
    vs = QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
        collection_name=collection,
        force_recreate=True,
        timeout=int(os.environ.get("WTW_QDRANT_TIMEOUT", "120")),
        batch_size=int(os.environ.get("WTW_QDRANT_BATCH_SIZE", "32")),
        **location_kwargs,
    )
    if url:
        # Server mode (local Docker or Qdrant Cloud) requires an explicit payload
        # index to filter on a field — in-memory/local-path mode doesn't enforce
        # this, which is why this was only caught after switching to a real
        # server. hybrid.py's L3 retrieval filters on metadata.layer; without
        # this index that filtered similarity_search raises a 400 Bad Request
        # ("Index required but not found for metadata.layer"). A compound
        # filter needs an index per field used in it — hybrid.py's new L1
        # semantic branch (Feature 007 Task A) filters on layer AND
        # granularity together, so granularity needs its own index too.
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
    layer, deterministic by rule_id) into a throwaway collection, then run a
    couple of sample similarity searches so you can eyeball whether the setup
    (embedding model, metadata, chunk content) looks right — BEFORE paying to
    embed the full corpus with --embed.
    """
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
        "sample-check complete. If results look right, run `--embed` for the full corpus (%d chunks).",
        len(chunks),
    )


def write_attributions(path: Path | None = None) -> Path:
    """CC-BY-SA share-alike: list every attributable source (handoff §4)."""
    path = path or (REPO_ROOT / "ATTRIBUTIONS.md")
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


def _print_report(chunks: list[Document]) -> None:
    by_layer = Counter(c.metadata["layer"] for c in chunks)
    by_source = Counter(c.metadata["source"] for c in chunks)
    print(f"\nTotal chunks: {len(chunks)}")
    print("Per layer:", dict(sorted(by_layer.items())))
    print("Per source:")
    for src, n in by_source.most_common():
        print(f"  {n:3d}  {src}")
    # guard: no copyrighted book text stored. Reference-only BOOK sources
    # (loader: reference_only) must contribute zero chunks. Note: distilled L1
    # cards may *cite* a book as provenance (url reference-only://…) — that is our
    # own text and is allowed; we key the guard on the book source names instead.
    ref_only_names = {s["name"] for s in load_manifest() if s.get("loader") == "reference_only"}
    leaked = [c for c in chunks if c.metadata.get("source") in ref_only_names]
    assert not leaked, f"reference-only book text leaked into the store: {leaked[:1]}"
    print("\nOK: metadata complete, rule_ids unique, no reference-only book text stored.")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--embed", action="store_true", help="embed the FULL corpus into Qdrant (needs gateway key, real cost)"
    )
    ap.add_argument(
        "--sample-check",
        nargs="?",
        const=2,
        type=int,
        metavar="N",
        default=None,
        help="cheap sanity check: embed only N chunks per layer + run sample "
        "similarity searches before committing to --embed (default N=2)",
    )
    ap.add_argument(
        "-v", "--verbose", action="store_true", help="log every source's chunks (rule_id + content preview)"
    )
    args = ap.parse_args()

    chunks = ingest_all(verbose=args.verbose)
    _print_report(chunks)
    attr = write_attributions()
    print(f"Wrote {attr}")

    if args.sample_check is not None:
        sample_check(chunks, n_per_layer=args.sample_check)
    if args.embed:
        build_vectorstore(chunks, url=QDRANT_URL, api_key=QDRANT_API_KEY)
        where = f"persisted to {QDRANT_URL}" if QDRANT_URL else "in-memory, NOT persisted"
        print(f"Embedded {len(chunks)} chunks into collection '{COLLECTION}' ({where}).")
