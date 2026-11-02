"""Snapshot repo-authored Markdown docs into the frozen raw corpus.

`data/l0_raw/` is the immutable source root for every indexed document (PDF and
now Markdown). The Waveform/RAG documents are authored under `docs/`, so this
script copies them into `data/l0_raw/<sub>/<file>` and records both hashes in
`data/documents/registry-md.snapshot.json`. Nothing else writes to l0_raw.

Usage:
    python scripts/snapshot_markdown_docs.py            # copy changed files
    python scripts/snapshot_markdown_docs.py --check    # fail on drift
"""

import argparse
import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/documents/registry-md.json"
MANIFEST = ROOT / "data/documents/registry-md.snapshot.json"
RAW_PREFIX = "data/l0_raw/"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def authored_path(record) -> Path:
    """docs/<sub>/<file> mirrors data/l0_raw/<sub>/<file>; no hidden mapping."""
    relative = record["source_path"]
    if not relative.startswith(RAW_PREFIX):
        raise ValueError(f"source_path must start with {RAW_PREFIX}: {relative}")
    return ROOT / "docs" / relative[len(RAW_PREFIX) :]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    records = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows, problems = [], []
    for record in records:
        source = authored_path(record)
        target = ROOT / record["source_path"]
        if not source.is_file():
            problems.append(f"missing authored source: {source.relative_to(ROOT)}")
            continue
        source_sha = digest(source)
        target_sha = digest(target) if target.is_file() else None
        action = "copy"
        if target_sha == source_sha:
            action = "up-to-date"
        elif target_sha is not None:
            action = "update"
        if args.check and action != "up-to-date":
            problems.append(
                f"stale snapshot: {record['doc_id']} ({action}); "
                "run without --check"
            )
        if not args.check and action != "up-to-date":
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_bytes(source.read_bytes())
            temporary.replace(target)
        rows.append(
            {
                "doc_id": record["doc_id"],
                "authored_path": str(source.relative_to(ROOT)),
                "raw_path": record["source_path"],
                "authored_sha256": source_sha,
                "raw_sha256": source_sha if action != "up-to-date" else target_sha,
                "action": action,
            }
        )

    if not args.check:
        MANIFEST.write_text(
            json.dumps(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "raw_root": RAW_PREFIX,
                    "documents": rows,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    for row in rows:
        print(f"{row['action']:>12}  {row['doc_id']:<40} {row['authored_sha256'][:12]}")
    for problem in problems:
        print(f"ERROR {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
