"""DOC conversion: explicit failures and identity-preserving parse_doc."""

from pathlib import Path
import shutil
import subprocess

from docx import Document
import pytest

from accelerator_rag.corpus import doc_converter
from accelerator_rag.corpus.doc_converter import (
    ConversionResult,
    DocConversionError,
    convert_doc_to_docx,
    parse_doc,
)


def _dummy_doc(tmp_path: Path) -> Path:
    path = tmp_path / "manual.doc"
    path.write_bytes(b"legacy-doc-placeholder")
    return path


def _version_run(command, *, stdout="LibreOffice 7.3.7.2 30(Build:2)\n"):
    return subprocess.CompletedProcess(
        command, 0, stdout=stdout, stderr=""
    )


def test_missing_soffice_reports_tool_missing(tmp_path, monkeypatch):
    doc = _dummy_doc(tmp_path)
    monkeypatch.setattr(doc_converter.shutil, "which", lambda name: None)

    with pytest.raises(DocConversionError, match="not found"):
        convert_doc_to_docx(doc, tmp_path / "out")


def test_input_validation(tmp_path):
    with pytest.raises(FileNotFoundError):
        convert_doc_to_docx(tmp_path / "missing.doc", tmp_path / "out")

    wrong_suffix = tmp_path / "wrong.docx"
    wrong_suffix.write_bytes(b"x")
    with pytest.raises(ValueError, match="DOC"):
        convert_doc_to_docx(wrong_suffix, tmp_path / "out")


def test_timeout_is_reported(tmp_path, monkeypatch):
    doc = _dummy_doc(tmp_path)
    monkeypatch.setattr(
        doc_converter.shutil, "which", lambda name: "/usr/bin/soffice"
    )

    def fake_run(command, **kwargs):
        if "--version" in command:
            return _version_run(command)
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(doc_converter.subprocess, "run", fake_run)

    with pytest.raises(DocConversionError, match="timed out"):
        convert_doc_to_docx(doc, tmp_path / "out", timeout=5)


def test_nonzero_exit_is_reported(tmp_path, monkeypatch):
    doc = _dummy_doc(tmp_path)
    monkeypatch.setattr(
        doc_converter.shutil, "which", lambda name: "/usr/bin/soffice"
    )

    def fake_run(command, **kwargs):
        if "--version" in command:
            return _version_run(command)
        return subprocess.CompletedProcess(
            command, 1, stdout="", stderr="sandbox denied"
        )

    monkeypatch.setattr(doc_converter.subprocess, "run", fake_run)

    with pytest.raises(DocConversionError, match="exit code 1"):
        convert_doc_to_docx(doc, tmp_path / "out")


def test_missing_output_file_is_reported(tmp_path, monkeypatch):
    doc = _dummy_doc(tmp_path)
    monkeypatch.setattr(
        doc_converter.shutil, "which", lambda name: "/usr/bin/soffice"
    )

    def fake_run(command, **kwargs):
        if "--version" in command:
            return _version_run(command)
        return subprocess.CompletedProcess(
            command, 0, stdout="convert", stderr=""
        )

    monkeypatch.setattr(doc_converter.subprocess, "run", fake_run)

    with pytest.raises(DocConversionError, match="no output file"):
        convert_doc_to_docx(doc, tmp_path / "out")


def test_success_records_command_and_version(tmp_path, monkeypatch):
    doc = _dummy_doc(tmp_path)
    monkeypatch.setattr(
        doc_converter.shutil, "which", lambda name: "/usr/bin/soffice"
    )
    commands = []

    def fake_run(command, **kwargs):
        commands.append(list(command))
        if "--version" in command:
            return _version_run(command)
        output_dir = Path(command[command.index("--outdir") + 1])
        source = Path(command[-1])
        (output_dir / f"{source.stem}.docx").write_bytes(b"PK fake docx")
        return subprocess.CompletedProcess(
            command, 0, stdout="convert", stderr=""
        )

    monkeypatch.setattr(doc_converter.subprocess, "run", fake_run)

    result = convert_doc_to_docx(doc, tmp_path / "out")

    assert isinstance(result, ConversionResult)
    assert result.docx_path == tmp_path / "out" / "manual.docx"
    assert result.docx_path.exists()
    assert result.tool == "/usr/bin/soffice"
    assert "7.3.7.2" in result.profile
    assert "soffice --headless --convert-to docx" in result.profile
    assert "UserInstallation" not in result.profile
    assert "file://" not in result.profile
    assert result.seconds >= 0

    conversion_command = next(
        command for command in commands if "--convert-to" in command
    )
    assert "--headless" in conversion_command
    assert "docx" in conversion_command
    assert any(
        argument.startswith("-env:UserInstallation=file://")
        for argument in conversion_command
    )


def _make_real_legacy_doc(workdir: Path) -> tuple[Path | None, str]:
    """Best-effort probe; returns (None, reason) when soffice cannot convert."""

    tool = shutil.which("soffice")
    if tool is None:
        return None, "soffice was not found on PATH"
    seed = workdir / "seed.docx"
    document = Document()
    document.add_heading("真实转换标题", level=1)
    document.add_paragraph("真实转换正文。")
    document.save(seed)
    profile = workdir / "lo-profile"
    command = [
        tool,
        "--headless",
        "--norestore",
        f"-env:UserInstallation={profile.resolve().as_uri()}",
        "--convert-to",
        "doc",
        "--outdir",
        str(workdir),
        str(seed),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, "soffice conversion timed out after 60s"
    except OSError as exc:
        return None, f"could not start soffice: {exc}"
    target = workdir / "seed.doc"
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        return None, f"soffice exited {completed.returncode}: {detail[:300]}"
    if not target.exists():
        return None, "soffice reported success but produced no .doc output"
    return target, ""


@pytest.fixture(scope="module")
def real_legacy_doc(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("soffice-probe")
    target, reason = _make_real_legacy_doc(workdir)
    if target is None:
        pytest.skip(f"soffice conversion is unavailable here: {reason}")
    return target


def test_real_soffice_conversion_round_trip(real_legacy_doc):
    parsed = parse_doc(
        real_legacy_doc,
        revision_id="doc-real-r1",
        source_path="data/l0_raw/tests/seed.doc",
        timeout=120,
    )

    assert parsed.source_format == "doc"
    assert parsed.source_path == "data/l0_raw/tests/seed.doc"
    assert parsed.conversion_profile.startswith("soffice --headless")
    assert any(
        block.block_type == "heading" and "转换标题" in block.text
        for block in parsed.blocks
    )
    assert any(
        block.block_type == "paragraph" and "转换正文" in block.text
        for block in parsed.blocks
    )


def test_parse_doc_keeps_original_doc_identity(tmp_path, monkeypatch):
    source_docx = tmp_path / "source.docx"
    document = Document()
    document.add_heading("转换后标题", level=1)
    document.add_paragraph("转换后正文。")
    document.save(source_docx)

    doc_path = _dummy_doc(tmp_path)
    original_bytes = doc_path.read_bytes()

    def fake_convert(path, output_dir, *, timeout=180):
        target = Path(output_dir) / f"{Path(path).stem}.docx"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_docx, target)
        return ConversionResult(
            docx_path=target,
            tool="/fake/soffice",
            profile="soffice --headless --convert-to docx; version=fake-1.0",
            seconds=0.25,
        )

    monkeypatch.setattr(
        doc_converter, "convert_doc_to_docx", fake_convert
    )

    parsed = parse_doc(
        doc_path,
        revision_id="doc-sample-r1",
        source_path="data/l0_raw/tests/manual.doc",
        title="转换手册",
    )

    assert parsed.source_path == "data/l0_raw/tests/manual.doc"
    assert parsed.source_format == "doc"
    assert parsed.title == "转换手册"
    assert "fake-1.0" in parsed.conversion_profile
    assert dict(parsed.metadata)["conversion_tool"] == "/fake/soffice"
    assert parsed.blocks[0].block_type == "heading"
    assert parsed.blocks[0].text == "转换后标题"
    assert doc_path.read_bytes() == original_bytes

    kept_dir = tmp_path / "converted"
    parse_doc(
        doc_path,
        revision_id="doc-sample-r1",
        source_path="data/l0_raw/tests/manual.doc",
        output_dir=kept_dir,
    )
    assert (kept_dir / "manual.docx").exists()
