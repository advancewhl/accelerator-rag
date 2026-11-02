"""Schema v2 parse orchestration: revisions to ``ParsedDocument`` only.

This module reads one revision's source, dispatches by ``source_format`` and
returns the format-neutral document.  It never builds an index, embeds chunks
or writes a registry; those are separate build steps with their own contracts.
"""

from __future__ import annotations

from pathlib import Path

from accelerator_rag.corpus.doc_converter import parse_doc
from accelerator_rag.corpus.docx_parser import parse_docx
from accelerator_rag.corpus.markdown_parser import parse_markdown
from accelerator_rag.corpus.parsed_document import (
    ParsedDocument,
    from_markdown_parsed,
    from_parsed_pdf,
)
from accelerator_rag.corpus.pdf_parser import parse_pdf
from accelerator_rag.corpus.pptx_parser import parse_pptx
from accelerator_rag.corpus.schema_v2 import (
    Disposition,
    RevisionRecord,
    SourceFormat,
    UsageStatus,
    source_format_for_path,
)
from accelerator_rag.corpus.structured_parser import (
    parse_csv,
    parse_ods,
    parse_xlsx,
)


_PARSEABLE_DISPOSITIONS = frozenset(
    {Disposition.TEXT_INDEX.value, Disposition.STRUCTURED_INDEX.value}
)


def _check_revision_allowed(revision: RevisionRecord) -> None:
    if revision.usage_status == UsageStatus.EXCLUDED.value:
        raise ValueError(
            f"revision {revision.revision_id} is excluded and must not be parsed"
        )
    if revision.disposition not in _PARSEABLE_DISPOSITIONS:
        raise ValueError(
            f"revision {revision.revision_id} disposition="
            f"{revision.disposition} does not allow parsing "
            "(text_index/structured_index only)"
        )


def _resolve_source(revision: RevisionRecord, project_root: str | Path) -> Path:
    root = Path(project_root).resolve()
    raw_root = (root / "data" / "l0_raw").resolve()
    local = (root / revision.source_path).resolve()
    if not local.is_relative_to(raw_root):
        raise ValueError(
            f"revision {revision.revision_id} source_path escapes data/l0_raw"
        )
    if not local.is_file():
        raise FileNotFoundError(
            f"revision {revision.revision_id} source file is missing: "
            f"{revision.source_path}"
        )
    return local


def _parse_local(
    path: Path,
    *,
    revision_id: str,
    asset_id: str | None,
    title: str | None,
    source_path: str,
    source_format: str,
    doc_output_dir: str | Path | None = None,
    timeout: int = 180,
) -> ParsedDocument:
    if source_format == SourceFormat.PDF.value:
        parsed = parse_pdf(path, source_path=source_path)
        return from_parsed_pdf(
            parsed,
            revision_id=revision_id,
            asset_id=asset_id,
            title=title,
        )
    if source_format == SourceFormat.MD.value:
        parsed = parse_markdown(path, source_path=source_path)
        return from_markdown_parsed(
            parsed,
            revision_id=revision_id,
            asset_id=asset_id,
            title=title,
        )
    if source_format == SourceFormat.DOCX.value:
        return parse_docx(
            path,
            revision_id=revision_id,
            asset_id=asset_id,
            title=title,
            source_path=source_path,
        )
    if source_format == SourceFormat.DOC.value:
        return parse_doc(
            path,
            revision_id=revision_id,
            asset_id=asset_id,
            title=title,
            source_path=source_path,
            timeout=timeout,
            output_dir=doc_output_dir,
        )
    if source_format == SourceFormat.PPTX.value:
        return parse_pptx(
            path,
            revision_id=revision_id,
            asset_id=asset_id,
            title=title,
            source_path=source_path,
        )
    if source_format == SourceFormat.XLSX.value:
        return parse_xlsx(
            path,
            revision_id=revision_id,
            asset_id=asset_id,
            title=title,
            source_path=source_path,
        )
    if source_format == SourceFormat.CSV.value:
        return parse_csv(
            path,
            revision_id=revision_id,
            asset_id=asset_id,
            title=title,
            source_path=source_path,
        )
    if source_format == SourceFormat.ODS.value:
        return parse_ods(
            path,
            revision_id=revision_id,
            asset_id=asset_id,
            title=title,
            source_path=source_path,
        )
    raise ValueError(
        f"unsupported source_format for parsing: {source_format} "
        "(pdf/md/docx/doc/pptx/xlsx/csv/ods)"
    )


def parse_revision(
    revision: RevisionRecord,
    project_root: str | Path = ".",
) -> ParsedDocument:
    """Parse one immutable revision after governance checks."""

    _check_revision_allowed(revision)
    local = _resolve_source(revision, project_root)
    return _parse_local(
        local,
        revision_id=revision.revision_id,
        asset_id=revision.original_asset_id,
        title=revision.title,
        source_path=revision.source_path,
        source_format=revision.source_format,
    )


def parse_path(
    path: str | Path,
    *,
    revision_id: str,
    asset_id: str | None = None,
    source_path: str | None = None,
    source_format: str | None = None,
    title: str | None = None,
    doc_output_dir: str | Path | None = None,
    timeout: int = 180,
) -> ParsedDocument:
    """Parse an arbitrary local path; intended for tests and dry runs."""

    local = Path(path)
    resolved_source = (
        source_path
        if source_path is not None
        else f"data/l0_raw/{local.name}"
    )
    resolved_format = source_format
    if resolved_format is None:
        detected = source_format_for_path(resolved_source)
        if detected is SourceFormat.OTHER:
            raise ValueError(
                f"cannot determine a supported source_format for {local.name}"
            )
        resolved_format = detected.value
    return _parse_local(
        local,
        revision_id=revision_id,
        asset_id=asset_id,
        title=title,
        source_path=resolved_source,
        source_format=resolved_format,
        doc_output_dir=doc_output_dir,
        timeout=timeout,
    )
