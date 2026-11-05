"""Image materialization and selective image OCR.

Pictures are evidence anchors first.  OCR is opt-in, bounded, and only applies
to images whose caption or surrounding heading indicates operations, parameters
or flow diagrams.  OCR text always remains review-required.
"""

from __future__ import annotations

from dataclasses import replace
import re
from pathlib import Path
import subprocess

from accelerator_rag.corpus.ocr import detect_ocr_tool, ocr_image_file
from accelerator_rag.corpus.parsed_document import (
    ParsedBlock,
    ParsedDocument,
    make_block_id,
)
from accelerator_rag.domain.position import BlockType

_KEY_IMAGE = re.compile(
    r"操作|界面|参数|指标|流程|步骤|接线|端子|配置|设置|曲线|框图|"
    r"截图|示意图|流程图|拓扑|screenshot|parameter|workflow|wiring|"
    r"terminal|configuration",
    re.IGNORECASE,
)


def image_blocks(parsed: ParsedDocument) -> list[ParsedBlock]:
    return [
        block
        for block in parsed.blocks
        if block.block_type == BlockType.IMAGE.value
    ]


_OPERATIONAL_KINDS = frozenset(
    {
        "operation_manual",
        "installation_maintenance",
        "interface_specification",
        "test_plan",
        "test_report",
        "acceptance_report",
    }
)


def select_key_images(
    parsed: ParsedDocument,
    *,
    max_images: int = 20,
    min_bytes: int = 8 * 1024,
    document_kind: str = "",
) -> list[ParsedBlock]:
    """Return at most ``max_images`` candidate pictures, deterministically."""

    selected = []
    heading = ""
    last_slide = None
    for block in parsed.blocks:
        if block.position.kind == "slide":
            if last_slide is not None and block.position.start != last_slide:
                heading = ""
            last_slide = block.position.start
        if block.block_type == BlockType.HEADING.value and block.text.strip():
            heading = block.text.strip()
        if block.block_type != BlockType.IMAGE.value:
            continue
        metadata = dict(block.metadata)
        status = metadata.get("media_status", "")
        if status not in {"", "materialized", "duplicate"}:
            continue
        if not metadata.get("media_path"):
            continue
        size = int(metadata.get("media_bytes", "0") or 0)
        if size and size < min_bytes:
            continue
        context = " ".join(
            part
            for part in (
                heading,
                block.caption,
                metadata.get("image_caption", ""),
                metadata.get("media_path", ""),
            )
            if part
        )
        if document_kind not in _OPERATIONAL_KINDS and not _KEY_IMAGE.search(
            context
        ):
            continue
        selected.append(block)
    if document_kind in _OPERATIONAL_KINDS:
        # Operation screenshots are usually the largest images in the manual.
        selected.sort(
            key=lambda block: (
                -int(dict(block.metadata).get("media_bytes", "0") or 0),
                block.block_id,
            )
        )
    else:
        selected.sort(key=lambda block: block.block_id)
    return selected[:max_images]


def enrich_image_ocr(
    parsed: ParsedDocument,
    *,
    media_root: str | Path | None,
    max_images: int = 20,
    min_bytes: int = 8 * 1024,
    languages: tuple[str, ...] = ("chi_sim", "eng"),
    psm: int = 6,
    timeout: int = 60,
    document_kind: str = "",
) -> ParsedDocument:
    """Append review-required OCR text after selected IMAGE blocks."""

    if media_root is None or max_images <= 0:
        return parsed
    root = Path(media_root)
    selected = {
        block.block_id
        for block in select_key_images(
            parsed,
            max_images=max_images,
            min_bytes=min_bytes,
            document_kind=document_kind,
        )
    }
    if not selected:
        return parsed
    tool = detect_ocr_tool()
    if not tool.available:
        return replace(
            parsed,
            warnings=parsed.warnings + ("image_ocr_unavailable",),
        )
    missing = sorted(set(languages) - set(tool.languages))
    if missing:
        return replace(
            parsed,
            warnings=parsed.warnings
            + ("image_ocr_languages_missing:" + ",".join(missing),),
        )
    added: dict[str, ParsedBlock] = {}
    warnings = list(parsed.warnings)
    for block in parsed.blocks:
        if block.block_id not in selected:
            continue
        metadata = dict(block.metadata)
        media_path = metadata.get("media_path", "")
        path = root / Path(media_path).name if media_path else None
        if path is None or not path.is_file():
            warnings.append(f"image_ocr_missing_file:{block.block_id}")
            continue
        try:
            text = ocr_image_file(
                path,
                languages=languages,
                psm=psm,
                timeout=timeout,
            )
        except (
            OSError,
            RuntimeError,
            ValueError,
            subprocess.SubprocessError,
        ) as exc:
            warnings.append(
                f"image_ocr_failed:{block.block_id}:{type(exc).__name__}"
            )
            continue
        text = text.strip()
        if not text:
            continue
        created = ParsedBlock(
            block_id=make_block_id(
                parsed.revision_id,
                parsed.asset_id,
                len(parsed.blocks) + len(added),
                BlockType.PARAGRAPH.value,
                block.position,
                text,
            ),
            block_type=BlockType.PARAGRAPH.value,
            text=text,
            position=block.position,
            metadata=(
                ("ocr", "tesseract-image"),
                ("source", "image_ocr"),
                ("manual_review_required", "true"),
                ("media_block_id", block.block_id),
                ("image_caption", block.caption),
                ("ocr_languages", "+".join(languages)),
            ),
        )
        added[block.block_id] = created
    if not added:
        return replace(parsed, warnings=tuple(warnings))
    blocks = []
    for block in parsed.blocks:
        blocks.append(block)
        if block.block_id in added:
            blocks.append(added[block.block_id])
    return replace(
        parsed,
        blocks=tuple(blocks),
        warnings=tuple(warnings) + (f"image_ocr_count:{len(added)}",),
        metadata=parsed.metadata
        + (("image_ocr_count", str(len(added))),),
    )
