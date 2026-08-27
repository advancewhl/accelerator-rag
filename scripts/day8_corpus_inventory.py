from __future__ import annotations

import argparse
from pathlib import Path

from accelerator_rag.corpus.registry import (
    CorpusInventory,
    DocumentRecord,
    build_inventory,
    load_registry,
    validate_inventory,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = PROJECT_ROOT / "data" / "documents" / "registry.json"


def format_bytes(byte_count: int) -> str:
    value = float(byte_count)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def print_counts(label: str, counts: dict[str, int]) -> None:
    values = ", ".join(f"{name}={count}" for name, count in counts.items())
    print(f"{label}: {values or '-'}")


def print_inventory(inventory: CorpusInventory) -> None:
    print("Corpus inventory")
    print(f"registered_documents: {inventory.registered_count}")
    print(f"raw_files: {inventory.raw_file_count}")
    print(f"registered_size: {format_bytes(inventory.registered_size_bytes)}")
    print_counts("categories", inventory.by_category)
    print_counts("topics", inventory.by_topic)
    print_counts("document_types", inventory.by_document_type)
    print_counts("languages", inventory.by_language)
    print_counts("statuses", inventory.by_status)

    if inventory.missing_files:
        print("missing_files:")
        for path in inventory.missing_files:
            print(f"  - {path}")
    if inventory.unregistered_files:
        print("unregistered_files:")
        for path in inventory.unregistered_files:
            print(f"  - {path}")


def print_records(records: list[DocumentRecord]) -> None:
    print("Registered documents")
    for index, record in enumerate(records, start=1):
        print(
            f"{index:02d}. {record.source_path} | "
            f"{record.category}/{record.topic} | "
            f"{record.language} | {record.version} | {record.status}"
        )
    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the corpus registry and print inventory statistics."
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help="Path to registry.json",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Project root containing data/raw",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = load_registry(args.registry)
    inventory = build_inventory(records, args.project_root)
    print_records(records)
    print_inventory(inventory)

    try:
        validate_inventory(inventory)
    except ValueError as exc:
        print(f"validation: FAILED ({exc})")
        return 1

    print("validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
