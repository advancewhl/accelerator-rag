import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "day8_corpus_inventory.py"


def write_registry(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "doc_id": "demo-epics",
                    "title": "EPICS Demo",
                    "source_path": "data/raw/demo.pdf",
                    "category": "control_system",
                    "topic": "epics",
                    "document_type": "pdf",
                    "language": "en",
                    "version": "unknown",
                    "status": "active",
                }
            ]
        ),
        encoding="utf-8",
    )


def run_inventory(tmp_path: Path, registry_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--project-root",
            str(tmp_path),
            "--registry",
            str(registry_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_inventory_script_succeeds_for_matching_file(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw"
    raw_root.mkdir(parents=True)
    (raw_root / "demo.pdf").write_bytes(b"pdf")
    registry_path = tmp_path / "registry.json"
    write_registry(registry_path)

    result = run_inventory(tmp_path, registry_path)

    assert result.returncode == 0
    assert "Registered documents" in result.stdout
    assert "validation: OK" in result.stdout


def test_inventory_script_fails_for_unregistered_file(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw"
    raw_root.mkdir(parents=True)
    (raw_root / "demo.pdf").write_bytes(b"pdf")
    (raw_root / "extra.pdf").write_bytes(b"pdf")
    registry_path = tmp_path / "registry.json"
    write_registry(registry_path)

    result = run_inventory(tmp_path, registry_path)

    assert result.returncode == 1
    assert "unregistered_files" in result.stdout
    assert "validation: FAILED" in result.stdout
