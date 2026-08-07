"""Ingestion CLI entry point — the only way this project's Qdrant index
gets built (constitution Principle X: "Ingestion is a CLI entry point,
never an HTTP endpoint. Idempotent by content hash.").

Usage:
    uv run python -m whattowear.ingest.cli                    # build/update the index
    uv run python -m whattowear.ingest.cli --sample-check      # cheap sanity check first
    uv run python -m whattowear.ingest.cli --force              # re-embed even if unchanged
    uv run python -m whattowear.ingest.cli --corpus-dir PATH   # override $CORPUS_LOCAL_DIR

Idempotency: a sha256 per ingestable, file-backed source is recorded in
`$CORPUS_LOCAL_DIR/.ingest_state.json` — outside the repo entirely, next
to the documents themselves, so it needs no `.gitignore` entry
(constitution Principle X: regenerable artifacts don't belong in git).
`infra/corpus.yaml` itself is never written to — see
specs/007-ai-port/data-model.md's note on why (it's a person-authored,
comment-rich file; PyYAML's dumper is not comment-preserving).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .build_kb import build_vectorstore, ingest_all, load_manifest, print_report, sample_check
from .build_kb import write_attributions as _write_attributions

_STATE_FILENAME = ".ingest_state.json"


def _state_path(corpus_dir: Path) -> Path:
    return corpus_dir / _STATE_FILENAME


def _load_state(corpus_dir: Path) -> dict[str, str]:
    path = _state_path(corpus_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(corpus_dir: Path, state: dict[str, str]) -> None:
    _state_path(corpus_dir).write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _current_hashes(corpus_dir: Path) -> dict[str, str]:
    """One sha256 per `ingest: true` source that has a local file
    (`path` field) — the `wikipedia` (live-fetch) loader has no local file
    to hash and is treated as always-needing-a-check, though nothing in
    the current manifest actually uses it."""
    hashes: dict[str, str] = {}
    for source in load_manifest():
        if not source.get("ingest") or "path" not in source:
            continue
        file_path = corpus_dir / source["path"]
        if file_path.exists():
            hashes[source["name"]] = _hash_file(file_path)
    return hashes


def _qdrant_collection_matches(url: str, api_key: str | None, collection: str, expected_count: int) -> bool:
    from qdrant_client import QdrantClient

    client = QdrantClient(url=url, api_key=api_key)
    return client.collection_exists(collection) and client.count(collection).count == expected_count


def main(
    corpus_dir: Path | None = None,
    force: bool = False,
    do_sample_check: bool = False,
    sample_n: int = 2,
    verbose: bool = False,
) -> int:
    from ..adapters.llm_gateway import get_embeddings  # noqa: F401 - fail fast if the gateway key is missing
    from ..core.config import get_settings
    from .build_kb import COLLECTION

    settings = get_settings()
    resolved_corpus_dir = corpus_dir or (Path(settings.corpus_local_dir) if settings.corpus_local_dir else None)
    if resolved_corpus_dir is None:
        raise SystemExit("CORPUS_LOCAL_DIR is required (or pass --corpus-dir). Set it in .env (see .env.example).")
    if not resolved_corpus_dir.exists():
        raise SystemExit(f"corpus directory does not exist: {resolved_corpus_dir}")

    chunks = ingest_all(resolved_corpus_dir, verbose=verbose)
    print_report(chunks)

    if do_sample_check:
        sample_check(chunks, n_per_layer=sample_n)
        return 0

    current_hashes = _current_hashes(resolved_corpus_dir)
    previous_hashes = _load_state(resolved_corpus_dir)
    unchanged = not force and current_hashes == previous_hashes

    if unchanged and settings.wtw_qdrant_url:
        if _qdrant_collection_matches(settings.wtw_qdrant_url, settings.wtw_qdrant_api_key, COLLECTION, len(chunks)):
            print(f"\nNothing changed ({len(current_hashes)} sources hashed) — skipping re-embedding.")
            return 0

    build_vectorstore(chunks, url=settings.wtw_qdrant_url, api_key=settings.wtw_qdrant_api_key)
    _save_state(resolved_corpus_dir, current_hashes)
    attributions_path = _write_attributions()
    where = f"persisted to {settings.wtw_qdrant_url}" if settings.wtw_qdrant_url else "in-memory, NOT persisted"
    print(f"\nEmbedded {len(chunks)} chunks into collection '{COLLECTION}' ({where}).")
    print(f"Wrote {attributions_path}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus-dir", type=Path, default=None, help="override $CORPUS_LOCAL_DIR")
    ap.add_argument("--force", action="store_true", help="re-embed even if content hashes are unchanged")
    ap.add_argument(
        "--sample-check",
        nargs="?",
        const=2,
        type=int,
        default=None,
        metavar="N",
        help="cheap sanity check: embed only N chunks per layer + run sample "
        "similarity searches, instead of the full corpus (default N=2)",
    )
    ap.add_argument("-v", "--verbose", action="store_true", help="log every source's chunks (rule_id + preview)")
    args = ap.parse_args()

    raise SystemExit(
        main(
            corpus_dir=args.corpus_dir,
            force=args.force,
            do_sample_check=args.sample_check is not None,
            sample_n=args.sample_check or 2,
            verbose=args.verbose,
        )
    )
