"""Regression coverage for stale gold and label isolation in the 50-item runner."""

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from accelerator_rag.evaluation.validity import (
    Evidence,
    EvidenceGroup,
    Pilot,
    PilotItem,
    evidence_coverage,
    validate_pilot,
)


def item_for(chunk):
    return PilotItem(
        id="P50-001",
        category="conditions",
        query="Does this source support this claim?",
        expected_status="answered",
        gold_answer="gold stays local",
        must_cover=["gold stays local"],
        forbidden_claims=["inventing evidence"],
        evidence_groups=[
            EvidenceGroup(
                alternatives=[
                    Evidence(
                        document_id=chunk.document_id,
                        document_version=chunk.document_version,
                        locator_kind="page",
                        page=chunk.page_start,
                        excerpt=chunk.text,
                        chunk_ids=[chunk.chunk_id],
                    )
                ]
            )
        ],
        cluster=chunk.document_id,
        overlaps_legacy=None,
        human_review="pending",
    )


def pilot_for(item):
    return Pilot(
        schema_version="validity-pilot-v2",
        dataset_revision="test",
        purpose="development_only",
        independent_test_allowed=False,
        items=[item.model_copy(update={"id": f"P50-{i:03d}"}) for i in range(50)],
    )


@pytest.mark.parametrize(
    "change,error",
    [
        ({"excerpt": "not in source"}, "excerpt absent"),
        ({"document_version": "old"}, "stale document version"),
        ({"locator_kind": "section"}, "wrong locator kind"),
        ({"chunk_ids": ["old-chunk"]}, "stale or unsearchable"),
    ],
)
def test_stale_evidence_cannot_pass_on_file_existence(chunk, record, change, error):
    item = item_for(chunk)
    documents = [
        SimpleNamespace(
            record=record,
            parsed=SimpleNamespace(
                pages=[SimpleNamespace(page_number=chunk.page_start, text=chunk.text)]
            ),
        )
    ]
    validate_pilot(pilot_for(item), documents, [chunk])
    item.evidence_groups[0].alternatives[0] = (
        item.evidence_groups[0].alternatives[0].model_copy(update=change)
    )
    with pytest.raises(ValueError, match=error):
        validate_pilot(pilot_for(item), documents, [chunk])


def test_same_page_without_excerpt_does_not_cover_group(chunk):
    item = item_for(chunk)
    other = replace(chunk, chunk_id="other", text="unrelated but same physical page")
    assert evidence_coverage(item, [other]) == [False]
    assert evidence_coverage(item, [chunk]) == [True]


def test_http_sends_only_question_and_requires_source_versions(chunk):
    path = Path(__file__).resolve().parents[2] / "scripts/run_validity_pilot.py"
    spec = importlib.util.spec_from_file_location("pilot_runner", path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    pilot = pilot_for(item_for(chunk))
    sent = []
    ready = True

    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "documents": [
                        {
                            "document_id": chunk.document_id,
                            "versions": [chunk.document_version if ready else "stale"],
                            "original_available": True,
                        }
                    ]
                },
            )
        payload = json.loads(request.content)
        sent.append(payload)
        assert payload == {"query": pilot.items[0].query}
        return httpx.Response(200, json={"status": "answered", "answer": "response"})

    with httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(handler)
    ) as client:
        rows = runner.run_http(client, pilot, lambda rows, catalog: None)
        assert len(rows) == len(sent) == 50
        ready = False
        with pytest.raises(ValueError, match="candidate corpus not ready"):
            runner.run_http(client, pilot, lambda rows, catalog: None)
        assert len(sent) == 50
