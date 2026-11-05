"""Normalized-content readers for Office and structured sources.

The service prefers the parsed snapshot produced by the same build as the
indexes.  When a release does not ship a snapshot, the original file is parsed
on demand with the same parser profile and the response says so explicitly.
Nothing here re-embeds, re-chunks or writes an index.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from importlib import import_module
import json
from pathlib import Path
from threading import Lock
from time import monotonic

from accelerator_rag.corpus.chunking_v2 import (
    block_evidence_profile,
    section_path_map,
)
from accelerator_rag.corpus.parsed_document import ParsedDocument


class ReaderUnavailable(ValueError):
    """This document has no normalized reader, or its snapshot is unreadable."""


@dataclass(frozen=True)
class ReaderRecord:
    document_id: str
    path: Path
    source_path: str
    title: str


_RENDERABLE_MEDIA = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
)
# Parsed snapshots are the production path, so the optional Office parser
# packages must never be imported just to serve a release that ships one.
_FACTORY_IMPORTS = {
    ".docx": ("accelerator_rag.corpus.docx_parser", "parse_docx"),
    ".pptx": ("accelerator_rag.corpus.pptx_parser", "parse_pptx"),
    ".xlsx": ("accelerator_rag.corpus.structured_parser", "parse_xlsx"),
    ".csv": ("accelerator_rag.corpus.structured_parser", "parse_csv"),
}


def _parse_factory(suffix: str):
    module_name, attribute = _FACTORY_IMPORTS[suffix]
    module = import_module(module_name)
    return getattr(module, attribute)


def _payload(
    parsed: ParsedDocument,
    *,
    document_id: str,
    source: str,
    original_path: Path,
) -> dict:
    paths = section_path_map(parsed.blocks)
    blocks = []
    for ordinal, block in enumerate(parsed.blocks):
        profile = block_evidence_profile(block, parsed)
        metadata = dict(block.metadata)
        record = {
            "ordinal": ordinal,
            "block_id": block.block_id,
            "block_type": block.block_type,
            "text": block.text,
            "heading_level": block.heading_level,
            "caption": block.caption,
            "position": block.position.to_dict(),
            "table": block.table.to_dict() if block.table is not None else None,
            "section_path": paths.get(block.block_id, ""),
            "content_role": profile["content_role"],
            "extraction_method": profile["extraction_method"],
            "review_status": profile["review_status"],
            "formula_status": profile["formula_status"],
            "metadata": metadata,
        }
        media_path = metadata.get("media_path", "")
        if media_path:
            record["media_url"] = (
                f"/v1/rag/documents/{document_id}/media/"
                f"{Path(media_path).name}"
            )
        blocks.append(record)
    return {
        "document_id": document_id,
        "revision_id": parsed.revision_id,
        "asset_id": parsed.asset_id,
        "document_format": parsed.source_format,
        "document_title": parsed.title,
        "source": source,
        "parser_profile": parsed.parser_profile,
        "conversion_profile": parsed.conversion_profile,
        "ocr_profile": parsed.ocr_profile,
        "warnings": list(parsed.warnings),
        "block_count": len(blocks),
        "blocks": blocks,
        "original_available": original_path.is_file(),
    }


class DocumentReader:
    """Bounded, thread-safe cache around snapshot/on-demand parsing."""

    def __init__(
        self,
        *,
        snapshot_dir: str | Path | None = None,
        max_entries=8,
        max_on_demand_bytes=64 * 1024 * 1024,
    ):
        if type(max_entries) is not int or not 1 <= max_entries <= 32:
            raise ValueError("invalid reader cache size")
        if type(max_on_demand_bytes) is not int or max_on_demand_bytes < 1:
            raise ValueError("invalid on-demand parse limit")
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else None
        self.max_entries = max_entries
        self.max_on_demand_bytes = max_on_demand_bytes
        self._cache: OrderedDict[tuple, dict] = OrderedDict()
        self._lock = Lock()

    def _snapshot(self, document_id: str) -> tuple[ParsedDocument, float] | None:
        if self.snapshot_dir is None:
            return None
        path = self.snapshot_dir / "parsed" / f"{document_id}.json"
        if not path.is_file():
            return None
        try:
            parsed = ParsedDocument.from_dict(
                json.loads(path.read_text(encoding="utf-8"))
            )
            return parsed, path.stat().st_mtime
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _parse_on_demand(self, record: ReaderRecord, *, timeout: int) -> ParsedDocument:
        suffix = record.path.suffix.lower()
        common = {
            "revision_id": record.document_id,
            "title": record.title,
            "source_path": record.source_path,
        }
        if suffix != ".doc" and suffix not in _FACTORY_IMPORTS:
            raise ReaderUnavailable(f"no normalized reader for {suffix or 'unknown'}")
        try:
            if suffix == ".doc":
                from accelerator_rag.corpus.doc_converter import parse_doc

                return parse_doc(record.path, timeout=timeout, **common)
            return _parse_factory(suffix)(record.path, **common)
        except Exception as exc:
            # PackageNotFoundError/BadZipFile and similar parser exceptions
            # must become a 503, never a 500 for one damaged document.
            raise ReaderUnavailable(
                f"{type(exc).__name__}: {exc}"
            ) from exc

    def _filter_media(self, payload: dict) -> None:
        root = (
            Path(self.snapshot_dir).resolve()
            if self.snapshot_dir is not None
            else None
        )
        for block in payload.get("blocks", ()):
            metadata = block.get("metadata") or {}
            media_path = metadata.get("media_path", "")
            if not media_path or root is None:
                block.pop("media_url", None)
                continue
            path = (root / media_path).resolve()
            if (
                not path.is_relative_to(root / "media")
                or path.suffix.lower() not in _RENDERABLE_MEDIA
                or not path.is_file()
            ):
                block.pop("media_url", None)

    def read(self, record: ReaderRecord, *, timeout: int = 60) -> dict:
        suffix = record.path.suffix.lower()
        if suffix in {".pdf", ".md", ".markdown"}:
            raise ReaderUnavailable("native reader handles this format")
        if not record.path.is_file():
            raise ReaderUnavailable("original file is missing")
        snapshot = self._snapshot(record.document_id)
        stat = record.path.stat()
        if snapshot is None and stat.st_size > self.max_on_demand_bytes:
            raise ReaderUnavailable(
                "document exceeds the on-demand parse limit; "
                "publish a parsed snapshot for this revision"
            )
        key = (
            record.document_id,
            str(record.path),
            stat.st_mtime_ns,
            stat.st_size,
            snapshot[1] if snapshot else None,
        )
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return cached
        if snapshot is not None:
            parsed, _mtime = snapshot
            payload = _payload(
                parsed,
                document_id=record.document_id,
                source="snapshot",
                original_path=record.path,
            )
        else:
            started = monotonic()
            parsed = self._parse_on_demand(record, timeout=timeout)
            payload = _payload(
                parsed,
                document_id=record.document_id,
                source=("on_demand_conversion" if suffix == ".doc" else "on_demand"),
                original_path=record.path,
            )
            payload["parse_seconds"] = round(monotonic() - started, 3)
            payload["snapshot_missing"] = True
        self._filter_media(payload)
        with self._lock:
            self._cache[key] = payload
            self._cache.move_to_end(key)
            while len(self._cache) > self.max_entries:
                self._cache.popitem(last=False)
        return payload
