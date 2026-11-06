#!/usr/bin/env python3
"""Verify that every structured row record points at a parent chunk containing it.

This is a build-integrity check, not a retrieval test.  It reads only
``chunks/*.json`` and ``records/*.json`` from a candidate build directory.

For each record:

* ``chunk_id`` must name an existing chunk;
* the record's ``row_text`` must occur in that chunk's text after whitespace
  and separator normalization.

Exit code is non-zero when any record fails, so it can gate a release.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

SEPARATORS = re.compile(r"[\s|｜]+")


def norm(text: str) -> str:
    return SEPARATORS.sub("", unicodedata.normalize("NFKC", text or "")).casefold()


def load_chunks(build_dir: Path) -> dict[str, str]:
    chunks: dict[str, str] = {}
    for path in sorted((build_dir / "chunks").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for chunk in payload.get("chunks", []):
            chunk_id = chunk.get("chunk_id")
            if chunk_id:
                chunks[chunk_id] = chunk.get("text", "")
    return chunks


def row_text(record: dict) -> str:
    """Row text as it appears in the parent chunk.

    ``row_text`` also carries the synthetic ``_group`` column used for
    lookup; the chunk text renders the group in its caption instead, so the
    integrity check drops it.
    """
    cells = record.get("cells") or []
    if cells:
        return " | ".join(value for column, value in cells if column != "_group")
    text = record.get("row_text", "")
    group = record.get("_group")
    if group and text.endswith(f" | {group}"):
        text = text[: -len(group) - 3]
    return text


def verify(build_dir: Path) -> dict:
    chunks = load_chunks(build_dir)
    total = 0
    missing_chunk: list[dict] = []
    row_not_in_chunk: list[dict] = []
    for path in sorted((build_dir / "records").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for record in payload.get("records", []):
            total += 1
            chunk_id = record.get("chunk_id")
            if chunk_id not in chunks:
                missing_chunk.append(
                    {
                        "record_id": record.get("record_id"),
                        "chunk_id": chunk_id,
                    }
                )
                continue
            if norm(row_text(record)) not in norm(chunks[chunk_id]):
                row_not_in_chunk.append(
                    {
                        "record_id": record.get("record_id"),
                        "chunk_id": chunk_id,
                    }
                )
    return {
        "build_dir": str(build_dir),
        "chunk_count": len(chunks),
        "record_count": total,
        "missing_chunk": len(missing_chunk),
        "row_not_in_chunk": len(row_not_in_chunk),
        "missing_chunk_samples": missing_chunk[:5],
        "row_not_in_chunk_samples": row_not_in_chunk[:5],
        "ok": not missing_chunk and not row_not_in_chunk,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    result = verify(args.build_dir)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
