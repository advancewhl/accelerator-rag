#!/usr/bin/env python3
"""Local K1/K2 sample: Markdown revision -> ParsedDocument -> v2 chunks.

This is a contract validation, not a candidate build.  It uses only documents
that exist locally and writes a small report; it never embeds, indexes, or
touches a release.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.corpus.chunking_v2 import (  # noqa: E402
    chunk_parsed_document,
    chunking_v2_statistics,
)
from accelerator_rag.corpus.markdown_parser import parse_markdown  # noqa: E402
from accelerator_rag.corpus.parsed_document import (  # noqa: E402
    from_markdown_parsed,
)
from accelerator_rag.corpus.schema_v2 import load_registry_v2  # noqa: E402


DEFAULT_REGISTRY = ROOT / "data/documents/v2/registry-v2.json"
DEFAULT_REPORT = ROOT / "reports/knowledge-base-v2/K1-sample-markdown.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry = load_registry_v2(args.registry)
    documents = []
    all_chunk_ids: set[str] = set()
    for revision in registry.revisions:
        if revision.source_format != "md":
            continue
        path = ROOT / revision.source_path
        if not path.is_file():
            documents.append(
                {
                    "revision_id": revision.revision_id,
                    "status": "missing_source",
                    "source_path": revision.source_path,
                }
            )
            continue
        parsed = parse_markdown(path, source_path=revision.source_path)
        document = from_markdown_parsed(
            parsed,
            revision_id=revision.revision_id,
            asset_id=revision.original_asset_id,
            title=revision.title,
        )
        chunks = chunk_parsed_document(document, revision)
        all_chunk_ids.update(chunk.chunk_id for chunk in chunks)
        digest = sha256(
            "\n".join(chunk.chunk_id for chunk in chunks).encode()
        ).hexdigest()
        documents.append(
            {
                "revision_id": revision.revision_id,
                "status": "parsed",
                "source_path": revision.source_path,
                "source_format": revision.source_format,
                "usage_status": revision.usage_status,
                "document_kind": revision.document_kind,
                "position_kinds": list(document.position_kinds),
                "block_count": len(document.blocks),
                "block_types": {
                    block_type: sum(
                        block.block_type == block_type
                        for block in document.blocks
                    )
                    for block_type in sorted(
                        {block.block_type for block in document.blocks}
                    )
                },
                "chunking": chunking_v2_statistics(chunks),
                "chunk_ids_sha256": digest,
                "chunk_previews": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "position_kind": chunk.effective_position_kind,
                        "position_label": chunk.position_label,
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                        "chars": len(chunk.text),
                        "preview": chunk.text[:160],
                    }
                    for chunk in chunks[:5]
                ],
            }
        )
    report = {
        "kind": "kb2-markdown-contract-sample",
        "release_target": registry.release_target,
        "registry": str(args.registry.relative_to(ROOT)),
        "documents": documents,
        "parsed_documents": sum(item["status"] == "parsed" for item in documents),
        "total_chunks": sum(
            item.get("chunking", {}).get("chunk_count", 0) for item in documents
        ),
        "unique_chunk_ids": len(all_chunk_ids),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output.relative_to(ROOT)),
                "parsed_documents": report["parsed_documents"],
                "total_chunks": report["total_chunks"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
