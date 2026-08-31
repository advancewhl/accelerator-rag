from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pymupdf

from accelerator_rag.corpus.pdf_parser import parse_pdf
from accelerator_rag.corpus.registry import DocumentRecord, load_registry


def _build_artifact(
    record: DocumentRecord,
    project_root: Path,
) -> dict[str, Any]:
    source_path = project_root / record.source_path
    parsed = parse_pdf(source_path)

    return {
        "schema_version": 1,
        "document": asdict(record),
        "parser": {
            "name": "pymupdf",
            "version": pymupdf.__version__,
        },
        "pdf": parsed.to_dict(),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = path.with_suffix(path.suffix + ".tmp")

    temporary_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary_path.replace(path)


def _warning_counts(
    artifact: dict[str, Any],
) -> Counter[str]:
    counts: Counter[str] = Counter()

    for page in artifact["pdf"]["pages"]:
        counts.update(page["warnings"])

    return counts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse registered PDF documents for Day 9.",
    )

    parser.add_argument(
        "--registry",
        default="data/documents/registry.json",
        help="Registry JSON path relative to project root.",
    )

    parser.add_argument(
        "--output-dir",
        default="data/parsed/pdf",
        help="Parsed JSON output directory relative to project root.",
    )

    parser.add_argument(
        "--doc-id",
        action="append",
        default=[],
        help="Only parse selected doc_id. May be supplied multiple times.",
    )

    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    project_root = Path(__file__).resolve().parents[1]

    registry_path = project_root / args.registry
    output_dir = project_root / args.output_dir

    records = load_registry(registry_path)

    pdf_records = [
        record
        for record in records
        if record.document_type == "pdf"
    ]

    if args.doc_id:
        selected_ids = set(args.doc_id)

        pdf_records = [
            record
            for record in pdf_records
            if record.doc_id in selected_ids
        ]

        found_ids = {record.doc_id for record in pdf_records}
        missing_ids = selected_ids - found_ids

        if missing_ids:
            raise ValueError(
                "registry 中不存在这些 PDF doc_id: "
                + ", ".join(sorted(missing_ids))
            )

    total_pages = 0
    total_chars = 0
    total_blocks = 0
    total_images = 0
    total_warning_counts: Counter[str] = Counter()

    failures: list[tuple[str, str]] = []

    print(f"registered PDFs: {len(pdf_records)}")
    print()

    for index, record in enumerate(pdf_records, start=1):
        print(
            f"[{index}/{len(pdf_records)}] "
            f"{record.doc_id}"
        )

        try:
            artifact = _build_artifact(
                record=record,
                project_root=project_root,
            )

            output_path = (
                output_dir / f"{record.doc_id}.json"
            )

            _write_json(output_path, artifact)

            pages = artifact["pdf"]["pages"]

            page_count = artifact["pdf"]["page_count"]
            char_count = sum(page["char_count"] for page in pages)
            block_count = sum(len(page["blocks"]) for page in pages)
            image_count = sum(page["image_count"] for page in pages)

            warning_counts = _warning_counts(artifact)

            total_pages += page_count
            total_chars += char_count
            total_blocks += block_count
            total_images += image_count
            total_warning_counts.update(warning_counts)

            print(
                "  OK "
                f"pages={page_count} "
                f"chars={char_count} "
                f"blocks={block_count} "
                f"images={image_count} "
                f"warnings={dict(warning_counts)}"
            )

        except Exception as exc:
            failures.append(
                (record.doc_id, str(exc))
            )

            print(
                f"  FAILED {type(exc).__name__}: {exc}"
            )

    print()
    print("===== summary =====")
    print("success:", len(pdf_records) - len(failures))
    print("failed:", len(failures))
    print("pages:", total_pages)
    print("chars:", total_chars)
    print("blocks:", total_blocks)
    print("images:", total_images)
    print("page warnings:", dict(total_warning_counts))

    if failures:
        print()
        print("===== failures =====")

        for doc_id, message in failures:
            print(f"{doc_id}: {message}")

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())