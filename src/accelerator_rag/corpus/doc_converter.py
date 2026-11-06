"""Legacy ``.doc`` conversion through a fixed LibreOffice invocation.

The original file is never overwritten.  Conversion runs headless with a
throw-away user profile so one build cannot mutate another user's LibreOffice
state.  Failures are explicit (tool missing, sandbox/permission denial, timeout,
non-zero exit, missing output); nothing pretends a conversion succeeded.

``parse_doc`` converts into a temporary directory and reuses
``parse_docx``.  The returned ``ParsedDocument`` keeps the original ``.doc``
identity (``source_path`` / ``source_format``) and records the tool and version
in ``conversion_profile``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import time

from accelerator_rag.corpus.docx_parser import parse_docx
from accelerator_rag.corpus.parsed_document import ParsedDocument


class DocConversionError(RuntimeError):
    """A ``.doc`` file could not be converted, with the concrete reason."""


@dataclass(frozen=True)
class ConversionResult:
    docx_path: Path
    tool: str
    profile: str
    seconds: float


def _safe_source_path(path: Path, source_path: str | None) -> str:
    if source_path is not None:
        return source_path
    parts = path.parts
    for index in range(1, len(parts)):
        if parts[index - 1] == "data" and parts[index] == "l0_raw":
            return PurePosixPath(*parts[index - 1 :]).as_posix()
    return f"data/l0_raw/{path.name}"


def _tool_version(tool: str) -> str:
    try:
        completed = subprocess.run(
            [tool, "--headless", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    output = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode != 0 or not output:
        return "unknown"
    return output.splitlines()[0].strip()


def convert_doc_to_docx(
    path: str | Path,
    output_dir: str | Path,
    *,
    timeout: int = 180,
) -> ConversionResult:
    """Convert one ``.doc`` file to ``.docx`` with LibreOffice headless."""

    doc_path = Path(path)
    if not doc_path.exists():
        raise FileNotFoundError(f"DOC file does not exist: {doc_path}")
    if doc_path.suffix.lower() != ".doc":
        raise ValueError(f"Expected a DOC file: {doc_path}")
    return _convert(doc_path, output_dir, "docx", timeout=timeout)


def convert_xls_to_xlsx(
    path: str | Path,
    output_dir: str | Path,
    *,
    timeout: int = 180,
) -> ConversionResult:
    """Convert one legacy ``.xls`` workbook to ``.xlsx`` (values and merges)."""

    xls_path = Path(path)
    if not xls_path.exists():
        raise FileNotFoundError(f"XLS file does not exist: {xls_path}")
    if xls_path.suffix.lower() != ".xls":
        raise ValueError(f"Expected an XLS file: {xls_path}")
    return _convert(xls_path, output_dir, "xlsx", timeout=timeout)


def _convert(
    doc_path: Path,
    output_dir: str | Path,
    target_ext: str,
    *,
    timeout: int,
) -> ConversionResult:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    tool = shutil.which("soffice")
    if tool is None:
        raise DocConversionError(
            "LibreOffice soffice was not found on PATH; install LibreOffice "
            "and make sure the soffice executable is available"
        )

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    target = output_path / f"{doc_path.stem}.{target_ext}"
    if target.exists():
        # A stale file from an earlier build must not be mistaken for success.
        target.unlink()

    version = _tool_version(tool)
    profile_text = (
        f"soffice --headless --convert-to {target_ext}; version={version}"
    )

    profile_dir = Path(tempfile.mkdtemp(prefix="accelerator-rag-lo-profile-"))
    command = [
        tool,
        "--headless",
        "--norestore",
        f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
        "--convert-to",
        target_ext,
        "--outdir",
        str(output_path),
        str(doc_path),
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise DocConversionError(
            f"LibreOffice conversion timed out after {timeout}s for "
            f"{doc_path.name}"
        ) from exc
    except PermissionError as exc:
        raise DocConversionError(
            "Permission denied while starting soffice; a sandbox may block "
            f"LibreOffice from running: {exc}"
        ) from exc
    except OSError as exc:
        raise DocConversionError(
            f"Could not start soffice; a sandbox may block LibreOffice: {exc}"
        ) from exc
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)

    seconds = time.monotonic() - started
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise DocConversionError(
            "LibreOffice conversion failed with exit code "
            f"{completed.returncode} for {doc_path.name}: {detail[:500]}"
        )
    if not target.exists():
        detail = (completed.stderr or completed.stdout or "").strip()
        raise DocConversionError(
            f"LibreOffice reported success but produced no output file for "
            f"{doc_path.name}; stderr={detail[:500]}"
        )
    if target.stat().st_size == 0:
        raise DocConversionError(
            f"LibreOffice produced an empty output file for {doc_path.name}"
        )

    return ConversionResult(
        docx_path=target,
        tool=tool,
        profile=profile_text,
        seconds=seconds,
    )


def parse_doc(
    path: str | Path,
    *,
    revision_id: str,
    asset_id: str | None = None,
    title: str | None = None,
    parser_profile: str = "doc-converted-docx-v1",
    source_path: str | None = None,
    timeout: int = 180,
    output_dir: str | Path | None = None,
    media_dir: str | Path | None = None,
    media_prefix: str = "",
    media_max_bytes: int = 256 * 1024 * 1024,
    media_min_bytes: int = 4096,
) -> ParsedDocument:
    """Convert a ``.doc`` file and parse the resulting DOCX as the original."""

    doc_path = Path(path)
    if not doc_path.exists():
        raise FileNotFoundError(f"DOC file does not exist: {doc_path}")
    if doc_path.suffix.lower() != ".doc":
        raise ValueError(f"Expected a DOC file: {doc_path}")

    resolved_source = _safe_source_path(doc_path, source_path)
    resolved_title = title or doc_path.stem

    def finish(conversion: ConversionResult) -> ParsedDocument:
        document = _parse_converted_docx(
            conversion,
            revision_id=revision_id,
            asset_id=asset_id,
            title=resolved_title,
            parser_profile=parser_profile,
            source_path=resolved_source,
            media_dir=media_dir,
            media_prefix=media_prefix,
            media_max_bytes=media_max_bytes,
            media_min_bytes=media_min_bytes,
        )
        return replace(
            document,
            conversion_profile=conversion.profile,
            metadata=document.metadata
            + (
                ("conversion_tool", conversion.tool),
                ("conversion_seconds", f"{conversion.seconds:.3f}"),
            ),
        )

    if output_dir is None:
        with tempfile.TemporaryDirectory(
            prefix="accelerator-rag-doc-"
        ) as temporary:
            return finish(
                convert_doc_to_docx(doc_path, temporary, timeout=timeout)
            )
    return finish(convert_doc_to_docx(doc_path, output_dir, timeout=timeout))


def _parse_converted_docx(
    conversion: ConversionResult,
    *,
    revision_id: str,
    asset_id: str | None,
    title: str,
    parser_profile: str,
    source_path: str,
    media_dir: str | Path | None = None,
    media_prefix: str = "",
    media_max_bytes: int = 256 * 1024 * 1024,
    media_min_bytes: int = 4096,
) -> ParsedDocument:
    return parse_docx(
        conversion.docx_path,
        revision_id=revision_id,
        asset_id=asset_id,
        title=title,
        parser_profile=parser_profile,
        source_path=source_path,
        source_format="doc",
        media_dir=media_dir,
        media_prefix=media_prefix,
        media_max_bytes=media_max_bytes,
        media_min_bytes=media_min_bytes,
    )


def parse_xls(
    path: str | Path,
    *,
    revision_id: str,
    asset_id: str | None = None,
    title: str | None = None,
    parser_profile: str = "xls-converted-xlsx-v1",
    source_path: str | None = None,
    timeout: int = 180,
    output_dir: str | Path | None = None,
) -> ParsedDocument:
    """Convert a ``.xls`` workbook and parse it as the original spreadsheet."""

    from accelerator_rag.corpus.structured_parser import parse_xlsx

    xls_path = Path(path)
    if not xls_path.exists():
        raise FileNotFoundError(f"XLS file does not exist: {xls_path}")
    if xls_path.suffix.lower() != ".xls":
        raise ValueError(f"Expected an XLS file: {xls_path}")
    resolved_source = _safe_source_path(xls_path, source_path)

    def finish(conversion: ConversionResult) -> ParsedDocument:
        document = parse_xlsx(
            conversion.docx_path,
            revision_id=revision_id,
            asset_id=asset_id,
            title=title or xls_path.stem,
            parser_profile=parser_profile,
            source_path=resolved_source,
            source_format="xls",
        )
        return replace(
            document,
            conversion_profile=conversion.profile,
            metadata=document.metadata
            + (
                ("conversion_tool", conversion.tool),
                ("conversion_seconds", f"{conversion.seconds:.3f}"),
            ),
        )

    if output_dir is None:
        with tempfile.TemporaryDirectory(prefix="accelerator-rag-xls-") as tmp:
            return finish(convert_xls_to_xlsx(xls_path, tmp, timeout=timeout))
    return finish(convert_xls_to_xlsx(xls_path, output_dir, timeout=timeout))
