"""Small regression checks for the code-owned coverage and source boundary."""

import json
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from accelerator_rag.domain.model import AssistantResponse, ToolCall
from accelerator_rag.rag.answer import AnswerContractError, generate, resolve
from accelerator_rag.rag.context import EvidenceContext
from accelerator_rag.rag.api import create_app


class Provider:
    def __init__(self, outputs):
        self.outputs = iter(outputs)

    def complete(self, messages, tools, **kwargs):
        assert sum(m.role == "system" for m in messages) == 1
        assert "$ref" not in json.dumps(tools)
        return AssistantResponse(
            tool_calls=(
                ToolCall(
                    id="call",
                    name=tools[0]["function"]["name"],
                    arguments=json.dumps(next(self.outputs)),
                ),
            )
        )


def context():
    chunk = SimpleNamespace(
        text="The mode is CW. Energy is 8 GeV.",
        document_title="Design",
        document_version="2017",
        document_id="design",
        page_start=1,
        page_end=1,
        chunk_id="chunk",
    )
    hit = SimpleNamespace(chunk=chunk, rank=1, score=0.9)
    return EvidenceContext(
        {"S1": hit},
        "[]",
        {"S1.1": ("S1", "The mode is CW."), "S1.2": ("S1", "Energy is 8 GeV.")},
    )


@pytest.mark.parametrize(
    "supported,status",
    [
        ([True, True], "answered"),
        ([True, False], "partial"),
        ([False, False], "insufficient"),
    ],
)
def test_coverage_owns_status(supported, status):
    req = [
        {"id": "R1", "question": "What mode?"},
        {"id": "R2", "question": "What energy?"},
    ]
    selection = [
        {"id": f"R{i}", "supported": v, "span_ids": [f"S1.{i}"] if v else []}
        for i, v in enumerate(supported, 1)
    ]
    outputs = [{"requirements": req}, {"requirements": selection}]
    if any(supported):
        outputs += [
            {
                "claims": [
                    {
                        "requirement_ids": [f"R{i}"],
                        "span_ids": [f"S1.{i}"],
                        "text": "CW mode." if i == 1 else "8 GeV.",
                    }
                    for i, v in enumerate(supported, 1)
                    if v
                ]
            },
            {
                "claims": [
                    {"index": i, "entailed": True} for i in range(sum(supported))
                ],
                "requirements": [
                    {"id": f"R{i}", "entailed_and_complete": True}
                    for i, v in enumerate(supported, 1)
                    if v
                ],
            },
        ]
    answer = resolve(
        generate(Provider(outputs), "What mode and energy?", context()), context()
    )
    assert answer["status"] == status
    assert [r["supported"] for r in answer["requirements"]] == supported
    assert all("source_path" not in c for c in answer["citations"])
    if status == "partial":
        assert "What energy?" in answer["answer"]


def test_semantically_rejected_claim_is_withheld():
    outputs = [
        {"requirements": [{"id": "R1", "question": "What mode?"}]},
        {"requirements": [{"id": "R1", "supported": True, "span_ids": ["S1.1"]}]},
        {
            "claims": [
                {
                    "requirement_ids": ["R1"],
                    "span_ids": ["S1.1"],
                    "text": "Pulsed mode.",
                }
            ]
        },
        {
            "claims": [{"index": 0, "entailed": False}],
            "requirements": [{"id": "R1", "entailed_and_complete": False}],
        },
    ]
    outputs += outputs[2:]
    result = generate(Provider(outputs), "What mode?", context())
    assert result.status == "insufficient" and "Pulsed" not in result.answer


def test_unknown_spans_fail_closed():
    bad = {"requirements": [{"id": "R1", "supported": True, "span_ids": ["S99.1"]}]}
    with pytest.raises(AnswerContractError):
        generate(
            Provider([{"requirements": [{"id": "R1", "question": "Mode?"}]}, bad, bad]),
            "Mode?",
            context(),
        )


def test_pdf_endpoint_accepts_only_registry_ids(tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with TestClient(create_app(SimpleNamespace(documents={"design": pdf}))) as client:
        assert (
            client.get("/v1/rag/documents/design").headers["content-type"]
            == "application/pdf"
        )
        assert client.get("/v1/rag/documents/unknown").status_code == 404
        assert client.get("/v1/rag/documents/%2Fetc%2Fpasswd").status_code == 404


def test_synthesis_cannot_invent_even_arithmetic_numbers():
    req = {"requirements": [{"id": "R1", "question": "What energy?"}]}
    evidence = {"requirements": [{"id": "R1", "supported": True, "span_ids": ["S1.2"]}]}
    bad = {
        "claims": [
            {
                "requirement_ids": ["R1"],
                "span_ids": ["S1.2"],
                "text": "The energy is 9 GeV.",
            }
        ]
    }
    with pytest.raises(AnswerContractError):
        generate(Provider([req, evidence, bad, bad]), "What energy?", context())


@pytest.mark.parametrize(
    "query",
    [
        "What firmware build is currently installed on SHINE?",
        "What is the current refrigerator outlet pressure?",
        "当前 SHINE 固件版本是什么？",
    ],
)
def test_live_operational_facts_are_guarded_without_an_explicit_date(query):
    from accelerator_rag.rag.answer import _temporal_gap

    assert _temporal_gap(query, context())


def test_redundant_function_array_wrapper_is_unambiguous():
    from accelerator_rag.providers.structured import (
        inline_schema,
        normalize_tool_arguments,
    )
    from accelerator_rag.rag.answer import Synthesis

    schema = inline_schema(Synthesis.model_json_schema())
    claim = {"requirement_ids": ["R1"], "span_ids": ["S1.1"], "text": "CW mode."}
    nested = {"claims": [{"claims": [claim]}]}
    assert (
        Synthesis.model_validate(normalize_tool_arguments(nested, schema))
        .claims[0]
        .text
        == "CW mode."
    )
    nested["claims"][0]["extra"] = True
    with pytest.raises(ValueError):
        Synthesis.model_validate(normalize_tool_arguments(nested, schema))
