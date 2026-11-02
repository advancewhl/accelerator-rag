"""Release-manifest gate: incomplete candidates may be honest; live may not lie."""

import json
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "validate_release_manifest.py"


def run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        check=False,
        capture_output=True,
        text=True,
    )


def manifest(**overrides):
    data = {
        "schema_version": 2,
        "release_id": "kb-2.0.0-rc.1",
        "build_id": "kb2-20261102-abcdef12",
        "status": "candidate-incomplete",
        "created_at": "2026-11-02",
        "registry": "data/documents/v2/registry-v2.json",
        "code": {"git_commit": "0b62844", "runtime_image": "not-built"},
        "corpus": {
            "revision_count": 210,
            "total_chunks": 4174,
            "eligible_chunks": 4174,
            "allow_missing_source": False,
            "parse_status_counts": {
                "parsed": 210,
                "failed": 0,
                "missing_source": 0,
                "pending_ocr": 0,
            },
        },
        "contracts": {"schema_version": 2},
        "indexes": [],
        "answer": {
            "generation_model": "not-selected",
            "generation_max_tokens": 4096,
            "max_evidence_tokens": 6000,
        },
        "verification": {},
        "operations": {"rollback_target": "unknown", "rollback_verified": False},
    }
    data.update(overrides)
    return data


def write(tmp_path: Path, payload) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_incomplete_candidate_passes_with_warnings(tmp_path):
    result = run(write(tmp_path, manifest()))

    assert result.returncode == 0
    assert "候选未包含索引" in result.stdout
    assert "errors" not in result.stdout or '"errors": 0' in result.stdout


def test_live_manifest_requires_two_indexes_and_rollback(tmp_path):
    payload = manifest(
        status="live",
        indexes=[{"dense_index_contract_id": "x", "parent_count": 1, "point_count": 1}],
        verification={"report": "x"},
        operations={"rollback_target": "kb-1.0.0", "rollback_verified": False},
    )
    result = run(write(tmp_path, payload))

    assert result.returncode == 1
    assert "两路索引" in result.stdout
    assert "回滚演练" in result.stdout


def test_complete_manifest_passes(tmp_path):
    payload = manifest(
        status="accepted",
        indexes=[
            {
                "model_name": "intfloat/multilingual-e5-base",
                "collection": "e5",
                "index_path": "/workspace/e5",
                "dense_index_contract_id": "e5",
                "parent_count": 10,
                "point_count": 12,
            },
            {
                "model_name": "Qwen/Qwen3-Embedding-0.6B",
                "collection": "qwen",
                "index_path": "/workspace/qwen",
                "dense_index_contract_id": "qwen",
                "parent_count": 10,
                "point_count": 12,
            },
        ],
        verification={
            "engineering_report": "reports/knowledge-base-v2/K5.md",
            "semantic_review_owner": "reviewer",
            "performance_baseline": "reports/perf.json",
            "rollback_drill": "reports/rollback.json",
        },
        operations={"rollback_target": "kb-1.0.0", "rollback_verified": True},
    )
    result = run(write(tmp_path, payload))

    assert result.returncode == 0
    assert '"status": "accepted"' in result.stdout


def test_token_counts_are_not_mistaken_for_credentials(tmp_path):
    payload = manifest(answer={"generation_max_tokens": 4096, "max_evidence_tokens": 6000})
    result = run(write(tmp_path, payload))

    assert result.returncode == 0
    assert "疑似凭据" not in result.stdout


def test_complete_manifest_rejects_placeholders_and_empty_corpus(tmp_path):
    payload = manifest(
        status="accepted",
        created_at="<YYYY-MM-DD>",
        code={"git_commit": "<git-commit>"},
        corpus={
            "revision_count": 0,
            "total_chunks": 0,
            "eligible_chunks": 0,
            "allow_missing_source": True,
        },
        indexes=[
            {
                "model_name": "a",
                "collection": "a",
                "index_path": "a",
                "dense_index_contract_id": "a",
                "parent_count": 1,
                "point_count": 1,
            },
            {
                "model_name": "b",
                "collection": "b",
                "index_path": "b",
                "dense_index_contract_id": "b",
                "parent_count": 1,
                "point_count": 1,
            },
        ],
        verification={
            "engineering_report": "<report>",
            "semantic_review_owner": "<owner>",
            "performance_baseline": "<perf>",
            "rollback_drill": "<rollback>",
        },
        operations={
            "rollback_target": "<previous-complete-release>",
            "rollback_verified": True,
        },
    )
    result = run(write(tmp_path, payload))

    assert result.returncode == 1
    assert "占位符" in result.stdout
    assert "corpus.revision_count 必须大于 0" in result.stdout
    assert "allow_missing_source" in result.stdout


def test_credentials_are_rejected(tmp_path):
    payload = manifest(code={"git_commit": "x", "api_key": "not-a-real-key"})
    result = run(write(tmp_path, payload))

    assert result.returncode == 1
    assert "疑似凭据" in result.stdout
