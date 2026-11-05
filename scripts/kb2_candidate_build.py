#!/usr/bin/env python3
"""Stage a Schema v2 candidate build without embedding or publishing.

Stages are explicit so a failed parse does not silently proceed to a release:

    validate -> parse -> chunks -> report -> manifest

This script never writes a Qdrant index, never starts a service, never touches a
release directory and never embeds credentials.  Index construction remains a
GPU-host step; the manifest is marked ``candidate-incomplete`` until then.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.corpus.chunking import (  # noqa: E402
    chunk_markdown,
    chunk_pdf,
)
from accelerator_rag.corpus.chunking_v2 import (  # noqa: E402
    chunk_parsed_document,
    chunking_v2_statistics,
)
from accelerator_rag.corpus.eligibility import (  # noqa: E402
    eligibility_audit,
    is_indexable_chunk,
)
from accelerator_rag.corpus.table_records import (  # noqa: E402
    build_table_records,
)
from accelerator_rag.corpus.markdown_parser import parse_markdown  # noqa: E402
from accelerator_rag.corpus.media import enrich_image_ocr  # noqa: E402
from accelerator_rag.corpus.parsed_document import (  # noqa: E402
    ParsedDocument,
    from_markdown_parsed,
    from_parsed_pdf,
)
from accelerator_rag.corpus.pdf_parser import parse_pdf  # noqa: E402
from accelerator_rag.corpus.schema_v2 import (  # noqa: E402
    Disposition,
    RegistryV2,
    RevisionRecord,
    load_registry_v2,
    to_document_record,
)


DEFAULT_REGISTRY = ROOT / "data/documents/v2/registry-v2.json"
DEFAULT_BUILD_ROOT = ROOT / "data/knowledge-builds"
# Below this size the text is a heading, TOC entry, caption or boilerplate, not
# usable evidence.  All chunks stay in the build for audit; only this list feeds
# the index stage.
MIN_INDEXABLE_CHARS = 20
DEFAULT_IMAGE_OCR_MAX = 20
_BUILD_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--build-root", type=Path, default=DEFAULT_BUILD_ROOT)
    parser.add_argument("--build-id", default="")
    parser.add_argument(
        "--stage",
        choices=("validate", "parse", "chunks", "report", "manifest", "all"),
        default="all",
    )
    parser.add_argument(
        "--allow-missing-source",
        action="store_true",
        help="record missing sources instead of failing; never use for a frozen candidate",
    )
    parser.add_argument("--max-revisions", type=int, default=0)
    parser.add_argument("--batch-id", default="")
    parser.add_argument("--revision-id", action="append", default=[])
    parser.add_argument(
        "--image-ocr-max",
        type=int,
        default=DEFAULT_IMAGE_OCR_MAX,
        help="maximum key images OCR'd per revision; 0 disables image OCR",
    )
    parser.add_argument(
        "--media-max-bytes",
        type=int,
        default=256 * 1024 * 1024,
        help="maximum image bytes materialized per revision",
    )
    parser.add_argument(
        "--media-min-bytes",
        type=int,
        default=4096,
        help="images smaller than this are not materialized",
    )
    parser.add_argument(
        "--include-restricted",
        action="store_true",
        help="include access_scope=restricted revisions (separate restricted build only)",
    )
    return parser.parse_args()


def git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def selected_revisions(
    registry: RegistryV2,
    limit: int,
    *,
    batch_id: str = "",
    revision_ids: list[str] | None = None,
    include_restricted: bool = False,
) -> list[RevisionRecord]:
    revisions = [
        revision
        for revision in registry.revisions
        if revision.disposition
        in {Disposition.TEXT_INDEX.value, Disposition.STRUCTURED_INDEX.value}
        and (
            include_restricted or revision.access_scope != "restricted"
        )
    ]
    if batch_id:
        revisions = [
            revision for revision in revisions if revision.batch_id == batch_id
        ]
    if revision_ids:
        wanted = set(revision_ids)
        revisions = [
            revision for revision in revisions if revision.revision_id in wanted
        ]
        missing = wanted - {revision.revision_id for revision in revisions}
        if missing:
            raise SystemExit(f"unknown revision IDs: {sorted(missing)}")
    return revisions[:limit] if limit else revisions


def parse_legacy(revision: RevisionRecord) -> ParsedDocument:
    path = ROOT / revision.source_path
    if revision.source_format == "pdf":
        parsed = parse_pdf(path, source_path=revision.source_path)
        return from_parsed_pdf(
            parsed,
            revision_id=revision.revision_id,
            asset_id=revision.original_asset_id,
            title=revision.title,
        )
    if revision.source_format == "md":
        parsed = parse_markdown(path, source_path=revision.source_path)
        return from_markdown_parsed(
            parsed,
            revision_id=revision.revision_id,
            asset_id=revision.original_asset_id,
            title=revision.title,
        )
    raise ValueError(f"legacy parser does not support {revision.source_format}")


def _block_order_key(block):
    """Page first, then the actual top coordinate, then a stable tie-break."""

    locator = block.position.locator_dict
    top = 0.0
    bbox = locator.get("ocr_bbox") or locator.get("bbox") or ""
    if bbox:
        try:
            top = float(bbox.split(",")[1])
        except (ValueError, IndexError):
            top = 0.0
    return (
        block.position.start,
        top,
        block.position.label,
        block.block_id,
    )


def _add_ocr_pages(
    revision: RevisionRecord, document: ParsedDocument
) -> ParsedDocument:
    """OCR pages that have no text layer; keep existing text-layer blocks."""

    if revision.source_format != "pdf":
        return document
    from accelerator_rag.corpus.ocr import ocr_pdf_pages, plan_pdf_ocr

    path = ROOT / revision.source_path
    plans = plan_pdf_ocr(path)
    if revision.ocr_profile:
        pages = [
            plan.page_number
            for plan in plans
            if plan.recommended or plan.mixed_candidate
        ]
    else:
        # A text-layer PDF may still need OCR for a large raster table region;
        # this enhancement is independent of the whole-document OCR profile.
        pages = [
            plan.page_number for plan in plans if plan.mixed_candidate
        ]
    if not pages:
        return document
    ocr_document = ocr_pdf_pages(
        path,
        revision_id=revision.revision_id,
        asset_id=revision.original_asset_id,
        source_path=revision.source_path,
        title=revision.title,
        pages=pages,
        languages=("chi_sim", "eng"),
        dpi=250,
        workers=8,
    )
    blocks = tuple(
        sorted(
            document.blocks + ocr_document.blocks,
            key=_block_order_key,
        )
    )
    return replace(
        document,
        blocks=blocks,
        warnings=document.warnings + ocr_document.warnings,
        metadata=document.metadata + ocr_document.metadata,
        ocr_profile=ocr_document.ocr_profile,
    )


def parse_revision_document(
    revision: RevisionRecord,
    *,
    media_dir: Path | None = None,
    media_prefix: str = "",
    image_ocr_max: int = DEFAULT_IMAGE_OCR_MAX,
    media_max_bytes: int = 256 * 1024 * 1024,
    media_min_bytes: int = 4096,
) -> ParsedDocument:
    if revision.batch_id == "legacy-baseline":
        document = parse_legacy(revision)
    else:
        from accelerator_rag.corpus.ingestion_v2 import parse_revision

        document = parse_revision(
            revision,
            ROOT,
            media_dir=media_dir,
            media_prefix=media_prefix,
            media_max_bytes=media_max_bytes,
            media_min_bytes=media_min_bytes,
        )
    document = _add_ocr_pages(revision, document)
    return enrich_image_ocr(
        document,
        media_root=media_dir,
        max_images=image_ocr_max,
        min_bytes=media_min_bytes,
        document_kind=revision.document_kind,
    )


def legacy_chunks(revision: RevisionRecord):
    path = ROOT / revision.source_path
    record = to_document_record(revision)
    if revision.source_format == "pdf":
        parsed = parse_pdf(path, source_path=revision.source_path)
        return chunk_pdf(parsed, record, revision=revision)
    if revision.source_format == "md":
        parsed = parse_markdown(path, source_path=revision.source_path)
        return chunk_markdown(parsed, record, revision=revision)
    raise ValueError(f"legacy chunker does not support {revision.source_format}")


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def stage_validate(registry: RegistryV2, revisions, allow_missing: bool) -> dict:
    missing = [
        revision.source_path
        for revision in revisions
        if not (ROOT / revision.source_path).is_file()
    ]
    if missing and not allow_missing:
        raise SystemExit(
            "missing source documents; use --allow-missing-source only for local "
            "contract checks, never for a frozen candidate:\n  "
            + "\n  ".join(missing[:20])
        )
    restricted_excluded = sum(
        revision.access_scope == "restricted"
        and revision.disposition
        in {Disposition.TEXT_INDEX.value, Disposition.STRUCTURED_INDEX.value}
        for revision in registry.revisions
    ) - sum(revision.access_scope == "restricted" for revision in revisions)
    return {
        "stage": "validate",
        "registry": str(registry.release_target),
        "registry_revision_count": len(registry.revisions),
        "selected_revisions": len(revisions),
        "restricted_excluded_from_selection": restricted_excluded,
        "missing_sources": missing,
        "allow_missing_source": allow_missing,
    }


def stage_parse(
    build_dir: Path,
    revisions,
    allow_missing: bool,
    *,
    image_ocr_max: int = DEFAULT_IMAGE_OCR_MAX,
    media_max_bytes: int = 256 * 1024 * 1024,
    media_min_bytes: int = 4096,
) -> dict:
    parsed_dir = build_dir / "parsed"
    records = []
    media_entries = []
    for revision in revisions:
        source = ROOT / revision.source_path
        if not source.is_file():
            records.append(
                {
                    "revision_id": revision.revision_id,
                    "status": "missing_source",
                    "source_path": revision.source_path,
                }
            )
            continue
        try:
            media_dir = build_dir / "media" / revision.revision_id
            if media_dir.is_dir():
                # A rebuild must not count stale images from an earlier pass.
                shutil.rmtree(media_dir)
            document = parse_revision_document(
                revision,
                media_dir=media_dir,
                media_prefix=f"media/{revision.revision_id}",
                image_ocr_max=image_ocr_max,
                media_max_bytes=media_max_bytes,
                media_min_bytes=media_min_bytes,
            )
            write_json(parsed_dir / f"{revision.revision_id}.json", document.to_dict())
            media_files = (
                sorted(media_dir.glob("*")) if media_dir.is_dir() else []
            )
            media_bytes = sum(path.stat().st_size for path in media_files)
            media_inventory = [
                {
                    "path": f"media/{revision.revision_id}/{path.name}",
                    "bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
                for path in media_files
            ]
            status = "parsed"
            if not document.blocks and revision.ocr_profile:
                # A scanned revision is parsed into an explicit empty asset; OCR
                # is a separate, still-pending stage, not a parser failure.
                status = "pending_ocr"
            records.append(
                {
                    "revision_id": revision.revision_id,
                    "status": status,
                    "source_path": revision.source_path,
                    "source_format": revision.source_format,
                    "block_count": len(document.blocks),
                    "position_kinds": list(document.position_kinds),
                    "warnings": list(document.warnings),
                    "parser_profile": document.parser_profile,
                    "media_files": len(media_files),
                    "media_bytes": media_bytes,
                    "media_inventory": media_inventory,
                }
            )
            media_entries.extend(media_inventory)
        except Exception as exc:
            records.append(
                {
                    "revision_id": revision.revision_id,
                    "status": "failed",
                    "source_path": revision.source_path,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:1000],
                }
            )
            if not allow_missing:
                raise
    write_json(build_dir / "parse-report.json", {"records": records})
    write_json(build_dir / "media-manifest.json", {"media": media_entries})
    return {
        "stage": "parse",
        "parsed": sum(item["status"] == "parsed" for item in records),
        "pending_ocr": sum(item["status"] == "pending_ocr" for item in records),
        "missing": sum(item["status"] == "missing_source" for item in records),
        "failed": sum(item["status"] == "failed" for item in records),
        "records": len(records),
        "media_files": sum(item.get("media_files", 0) for item in records),
        "media_bytes": sum(item.get("media_bytes", 0) for item in records),
    }


def stage_chunks(build_dir: Path, revisions, allow_missing: bool) -> dict:
    parsed_dir = build_dir / "parsed"
    chunks_dir = build_dir / "chunks"
    records_dir = build_dir / "records"
    # A stage run owns this build's chunk/record files; stale files from an
    # earlier subset must not leak into the quality report or a manifest.
    chunks_dir.mkdir(parents=True, exist_ok=True)
    records_dir.mkdir(parents=True, exist_ok=True)
    for stale in chunks_dir.glob("*.json"):
        stale.unlink()
    for stale in records_dir.glob("*.json"):
        stale.unlink()
    records = []
    all_ids: set[str] = set()
    for revision in revisions:
        source = ROOT / revision.source_path
        if not source.is_file():
            records.append(
                {
                    "revision_id": revision.revision_id,
                    "status": "missing_source",
                }
            )
            continue
        try:
            document = None
            if revision.batch_id == "legacy-baseline":
                chunks = legacy_chunks(revision)
            else:
                parsed_path = parsed_dir / f"{revision.revision_id}.json"
                if not parsed_path.is_file():
                    raise FileNotFoundError(
                        f"parsed document not found: {parsed_path}"
                    )
                document = ParsedDocument.from_dict(
                    json.loads(parsed_path.read_text(encoding="utf-8"))
                )
                if not document.blocks and revision.ocr_profile:
                    records.append(
                        {
                            "revision_id": revision.revision_id,
                            "status": "pending_ocr",
                            "warnings": list(document.warnings),
                        }
                    )
                    continue
                chunks = chunk_parsed_document(document, revision)
            table_records = (
                build_table_records(document, chunks)
                if document is not None
                else ()
            )
            if table_records:
                write_json(
                    records_dir / f"{revision.revision_id}.json",
                    {"records": [item.to_dict() for item in table_records]},
                )
            duplicate = len(all_ids & {chunk.chunk_id for chunk in chunks})
            if duplicate:
                raise ValueError(f"duplicate chunk IDs across corpus: {duplicate}")
            all_ids.update(chunk.chunk_id for chunk in chunks)
            eligible, eligibility = eligibility_audit(chunks)
            indexable = [
                chunk
                for chunk in eligible
                if is_indexable_chunk(chunk, MIN_INDEXABLE_CHARS)
                and chunk.access_scope != "restricted"
            ]
            short_retained = [
                chunk
                for chunk in indexable
                if len(chunk.text.strip()) < MIN_INDEXABLE_CHARS
            ]
            write_json(
                chunks_dir / f"{revision.revision_id}.json",
                {
                    "revision_id": revision.revision_id,
                    "document_id": revision.revision_id,
                    "chunks": [asdict(chunk) for chunk in chunks],
                    "eligible_chunk_ids": [
                        chunk.chunk_id for chunk in eligible
                    ],
                    "indexable_chunk_ids": [
                        chunk.chunk_id for chunk in indexable
                    ],
                    "eligibility": eligibility,
                    "short_chunks_filtered": len(eligible) - len(indexable),
                    "short_chunks_retained": len(short_retained),
                    "min_indexable_chars": MIN_INDEXABLE_CHARS,
                },
            )
            records.append(
                {
                    "revision_id": revision.revision_id,
                    "status": "chunked",
                    "chunk_count": len(chunks),
                    "eligible_chunk_count": len(eligible),
                    "indexable_chunk_count": len(indexable),
                    "short_chunks_filtered": len(eligible) - len(indexable),
                    "short_chunks_retained": len(short_retained),
                    "table_record_count": len(table_records),
                    "ineligible_chunk_count": len(chunks) - len(eligible),
                    "ineligible_by_reason": eligibility["ineligible_by_reason"],
                    "char_count": sum(len(chunk.text) for chunk in chunks),
                    "statistics": (
                        chunking_v2_statistics(chunks)
                        if revision.batch_id != "legacy-baseline"
                        else {
                            "algorithm": "legacy-v1",
                            "chunk_count": len(chunks),
                            "total_chars": sum(len(chunk.text) for chunk in chunks),
                        }
                    ),
                }
            )
        except Exception as exc:
            records.append(
                {
                    "revision_id": revision.revision_id,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:1000],
                }
            )
            if not allow_missing:
                raise
    write_json(build_dir / "chunk-report.json", {"records": records})
    return {
        "stage": "chunks",
        "chunked": sum(item["status"] == "chunked" for item in records),
        "pending_ocr": sum(item["status"] == "pending_ocr" for item in records),
        "missing": sum(item["status"] == "missing_source" for item in records),
        "failed": sum(item["status"] == "failed" for item in records),
        "total_chunks": sum(item.get("chunk_count", 0) for item in records),
        "eligible_chunks": sum(
            item.get("eligible_chunk_count", 0) for item in records
        ),
        "indexable_chunks": sum(
            item.get("indexable_chunk_count", 0) for item in records
        ),
        "short_chunks_filtered": sum(
            item.get("short_chunks_filtered", 0) for item in records
        ),
        "short_chunks_retained": sum(
            item.get("short_chunks_retained", 0) for item in records
        ),
        "table_records": sum(
            item.get("table_record_count", 0) for item in records
        ),
        "ineligible_chunks": sum(
            item.get("ineligible_chunk_count", 0) for item in records
        ),
        "unique_chunk_ids": len(all_ids),
    }


def stage_report(build_dir: Path, revisions) -> dict:
    selected_ids = {revision.revision_id for revision in revisions}
    chunk_files = sorted(
        path
        for path in (build_dir / "chunks").glob("*.json")
        if path.stem in selected_ids
    )
    records_dir = build_dir / "records"
    record_files = (
        sorted(records_dir.glob("*.json")) if records_dir.is_dir() else []
    )
    table_record_count = sum(
        len(json.loads(path.read_text(encoding="utf-8")).get("records", ()))
        for path in record_files
    )
    chunk_counts = {}
    total_chunks = total_chars = 0
    total_eligible = total_ineligible = total_indexable = short_filtered = 0
    short_retained = indexable_under_20 = 0
    ineligible_reasons: dict[str, int] = {}
    duplicate_ids = set()
    seen = set()
    empty_chunks = 0
    under_20 = under_50 = 0
    for path in chunk_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        chunks = payload["chunks"]
        chunk_counts[payload["revision_id"]] = len(chunks)
        eligible_ids = set(payload.get("eligible_chunk_ids", []))
        indexable_ids = set(payload.get("indexable_chunk_ids", []))
        total_eligible += len(eligible_ids)
        total_indexable += len(indexable_ids)
        short_filtered += len(eligible_ids) - len(indexable_ids)
        short_retained += payload.get("short_chunks_retained", 0)
        indexable_under_20 += sum(
            1
            for chunk in chunks
            if chunk["chunk_id"] in indexable_ids
            and len(chunk["text"]) < MIN_INDEXABLE_CHARS
        )
        total_ineligible += len(chunks) - len(eligible_ids)
        for reason, count in payload.get("eligibility", {}).get(
            "ineligible_by_reason", {}
        ).items():
            ineligible_reasons[reason] = ineligible_reasons.get(reason, 0) + count
        for chunk in chunks:
            total_chunks += 1
            total_chars += len(chunk["text"])
            if not chunk["text"].strip():
                empty_chunks += 1
            if len(chunk["text"]) < 20:
                under_20 += 1
            if len(chunk["text"]) < 50:
                under_50 += 1
            if chunk["chunk_id"] in seen:
                duplicate_ids.add(chunk["chunk_id"])
            seen.add(chunk["chunk_id"])
    report = {
        "stage": "report",
        "chunk_files": len(chunk_files),
        "total_chunks": total_chunks,
        "eligible_chunks": total_eligible,
        "indexable_chunks": total_indexable,
        "short_chunks_filtered": short_filtered,
        "short_chunks_retained": short_retained,
        "indexable_under_20_chars": indexable_under_20,
        "record_files": len(record_files),
        "table_record_count": table_record_count,
        "ineligible_chunks": total_ineligible,
        "ineligible_by_reason": dict(sorted(ineligible_reasons.items())),
        "total_chars": total_chars,
        "duplicate_chunk_ids": sorted(duplicate_ids)[:20],
        "empty_chunks": empty_chunks,
        "chunks_under_20_chars": under_20,
        "chunks_under_50_chars": under_50,
        "chunks_by_revision": chunk_counts,
        "revisions_without_chunks": [
            revision.revision_id
            for revision in revisions
            if revision.revision_id not in chunk_counts
        ],
    }
    write_json(build_dir / "quality-report.json", report)
    return {"stage": "report", **{k: report[k] for k in (
        "chunk_files",
        "total_chunks",
        "eligible_chunks",
        "indexable_chunks",
        "short_chunks_filtered",
        "ineligible_chunks",
        "total_chars",
        "empty_chunks",
        "chunks_under_20_chars",
        "chunks_under_50_chars",
    )}}


def stage_manifest(
    build_dir: Path,
    registry_path: Path,
    build_id: str,
    registry: RegistryV2,
    revisions,
    *,
    allow_missing_source: bool,
) -> dict:
    quality_path = build_dir / "quality-report.json"
    quality = (
        json.loads(quality_path.read_text(encoding="utf-8"))
        if quality_path.is_file()
        else {}
    )
    parse_path = build_dir / "parse-report.json"
    selected_ids = {revision.revision_id for revision in revisions}
    parse_records = (
        [
            record
            for record in json.loads(
                parse_path.read_text(encoding="utf-8")
            ).get("records", [])
            if record.get("revision_id") in selected_ids
        ]
        if parse_path.is_file()
        else []
    )
    parse_counts: dict[str, int] = {}
    for record in parse_records:
        status = record.get("status", "unknown")
        parse_counts[status] = parse_counts.get(status, 0) + 1
    manifest = {
        "schema_version": 2,
        "release_id": "kb-2.0.0-rc.1",
        "build_id": build_id,
        "status": "candidate-incomplete",
        "created_at": date.today().isoformat(),
        "previous_release": "unknown",
        "registry": str(registry_path.relative_to(ROOT)),
        "registry_sha256": file_sha256(registry_path),
        "source_root": "unknown-local-worktree",
        "build_dir": str(build_dir),
        "release_dir": "not-created",
        "code": {
            "git_commit": git_commit(),
            "runtime_image": "not-built",
            "dependencies": "pyproject.toml",
        },
        "corpus": {
            "revision_count": len(revisions),
            "registry_revision_count": len(registry.revisions),
            "family_count": len(
                {revision.family_id for revision in revisions}
            ),
            "text_index_count": sum(
                revision.disposition == "text_index" for revision in revisions
            ),
            "allow_missing_source": allow_missing_source,
            "chunked_revisions": quality.get("chunk_files", 0),
            "total_chunks": quality.get("total_chunks", 0),
            "eligible_chunks": quality.get("eligible_chunks", 0),
            "indexable_chunks": quality.get("indexable_chunks", 0),
            "short_chunks_filtered": quality.get("short_chunks_filtered", 0),
            "short_chunks_retained": quality.get("short_chunks_retained", 0),
            "ineligible_chunks": quality.get("ineligible_chunks", 0),
            "table_record_count": quality.get("table_record_count", 0),
            "media_file_count": sum(
                record.get("media_files", 0) for record in parse_records
            ),
            "media_bytes": sum(
                record.get("media_bytes", 0) for record in parse_records
            ),
            "media_manifest": "media-manifest.json",
            "media_manifest_sha256": (
                file_sha256(build_dir / "media-manifest.json")
                if (build_dir / "media-manifest.json").is_file()
                else ""
            ),
            "parse_status_counts": dict(sorted(parse_counts.items())),
        },
        "contracts": {
            "schema_version": 2,
            "chunking_algorithm": (
                "kb2-chunks-v2 (Office/structured); "
                "legacy PDF/Markdown keeps v1 IDs"
            ),
            "scope_policy": "retrieval.scope.RetrievalScope",
        },
        "indexes": [],
        "answer": {
            "generation_model": "not-selected",
            "reranker_model": "not-selected",
            "prompt_version": "not-frozen",
            "generation_max_tokens": 4096,
            "max_retrieval_rounds": 2,
            "max_parents": 5,
            "max_evidence_tokens": 6000,
            "default_usage_statuses": ["current", "reference"],
        },
        "incomplete_reasons": [
            "index construction requires the GPU release environment",
            "OCR content (when present) still requires manual review",
            "release directory and rollback target are not created",
            f"parse status counts: {json.dumps(parse_counts, ensure_ascii=False)}",
            f"selected_revisions={len(revisions)}",
            f"allow_missing_source={allow_missing_source}",
        ],
        "verification": {},
        "operations": {
            "rollback_target": "unknown",
            "rollback_verified": False,
        },
    }
    write_json(build_dir / "release-manifest.draft.json", manifest)
    return {"stage": "manifest", "status": manifest["status"], "build_id": build_id}


def main() -> int:
    args = parse_args()
    registry_path = args.registry.resolve()
    registry = load_registry_v2(registry_path)
    build_id = args.build_id or f"kb2-{date.today():%Y%m%d}-{git_commit()[:8]}"
    if not _BUILD_ID.fullmatch(build_id):
        raise SystemExit("build-id must be a lowercase slug")
    if not 0 <= args.image_ocr_max <= 200:
        raise SystemExit("--image-ocr-max must be between 0 and 200")
    if args.media_max_bytes < 0 or args.media_min_bytes < 0:
        raise SystemExit("media byte limits must be nonnegative")
    build_dir = args.build_root.resolve() / build_id
    revisions = selected_revisions(
        registry,
        args.max_revisions,
        batch_id=args.batch_id,
        revision_ids=args.revision_id,
        include_restricted=args.include_restricted,
    )
    if not revisions:
        raise SystemExit(
            "no revisions selected; check --batch-id/--revision-id and whether "
            "all matches are access_scope=restricted"
        )
    stages = (
        ("validate", "parse", "chunks", "report", "manifest")
        if args.stage == "all"
        else (args.stage,)
    )
    results = []
    for stage in stages:
        if stage == "validate":
            results.append(
                stage_validate(
                    registry, revisions, args.allow_missing_source
                )
            )
        elif stage == "parse":
            results.append(
                stage_parse(
                    build_dir,
                    revisions,
                    args.allow_missing_source,
                    image_ocr_max=args.image_ocr_max,
                    media_max_bytes=args.media_max_bytes,
                    media_min_bytes=args.media_min_bytes,
                )
            )
        elif stage == "chunks":
            results.append(
                stage_chunks(build_dir, revisions, args.allow_missing_source)
            )
        elif stage == "report":
            results.append(stage_report(build_dir, revisions))
        elif stage == "manifest":
            results.append(
                stage_manifest(
                    build_dir,
                    registry_path,
                    build_id,
                    registry,
                    revisions,
                    allow_missing_source=args.allow_missing_source,
                )
            )
    print(
        json.dumps(
            {
                "build_id": build_id,
                "build_dir": str(build_dir),
                "stages": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
