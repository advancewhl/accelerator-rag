import json

import pytest

from conftest import ROOT

from accelerator_rag.evidence_pack.index import load_index
from accelerator_rag.evidence_pack.pipeline import run_question

FACTS = ROOT / "data" / "facts" / "facts.jsonl"
QUESTIONS = ROOT / "data" / "evaluation" / "research-benchmark-300-v1"


def _corpus_available():
    return FACTS.exists() and (QUESTIONS / "dev" / "questions.json").exists()


@pytest.mark.corpus
def test_pipeline_is_byte_stable_and_uses_pack():
    if not _corpus_available():
        pytest.skip("phase-2 facts or dev questions are absent")
    index = load_index(splits=("dev",), facts_path=FACTS)
    item = next(
        question
        for question in json.loads(
            (QUESTIONS / "dev" / "questions.json").read_text(encoding="utf-8")
        )["items"]
        if question["base_id"] == "S1-DEV-001"
    )
    first = run_question(index, item, command="pytest")
    second = run_question(index, item, command="pytest")
    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second, ensure_ascii=False, sort_keys=True
    )
    assert first["route"] == "exact_record"
    assert first["verification"]["status"] == "answered"
    assert first["pack"]["tokens"] <= first["pack"]["budget"]
    assert first["pack"]["selection"]["passes"] == 2
    assert first["recompute"]["report_sha256"]


@pytest.mark.corpus
def test_pipeline_accepts_greedy_only_pass_count():
    if not _corpus_available():
        pytest.skip("phase-2 facts or dev questions are absent")
    index = load_index(splits=("dev",), facts_path=FACTS)
    item = next(
        question
        for question in json.loads(
            (QUESTIONS / "dev" / "questions.json").read_text(encoding="utf-8")
        )["items"]
        if question["base_id"] == "S1-DEV-001"
    )
    report = run_question(index, item, command="pytest", max_passes=0)
    assert report["pack"]["selection"]["passes"] == 0
    assert report["pack"]["tokens"] <= report["pack"]["budget"]


@pytest.mark.corpus
def test_pipeline_refuses_sealed_split():
    index = load_index(splits=("dev",), facts_path=FACTS)
    with pytest.raises(ValueError):
        run_question(
            index,
            {
                "base_id": "X",
                "split": "test",
                "query": "x",
                "family_ids": [],
                "gold": {"verdict_class": "deterministic"},
            },
        )


@pytest.mark.corpus
def test_runner_replay_with_limit():
    if not _corpus_available():
        pytest.skip("phase-2 facts or dev questions are absent")
    import importlib.util

    path = ROOT / "scripts" / "research" / "run_evidence_pack.py"
    spec = importlib.util.spec_from_file_location("run_evidence_pack", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run_split(
        "dev",
        facts_path=FACTS,
        reranker="none",
        learned=None,
        archiver_path=None,
        limit=1,
    )
    assert result["schema_version"] == module.RUN_SCHEMA
    assert result["reports"][0]["evaluation"]["budget_ok"] is True
    assert result["summary"]["gold_chunk_recall_pack"] is not None
