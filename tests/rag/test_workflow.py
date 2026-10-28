"""Behavioral regressions for the complete requirement-driven evidence loop."""

import json
from threading import Lock

import pytest

from accelerator_rag.domain.knowledge import KnowledgeChunk, RetrievalResult
from accelerator_rag.domain.model import AssistantResponse, ToolCall
from accelerator_rag.rag.answer import (
    AnswerContractError,
    Selection,
    Support,
    _numbers,
    _reference_key,
    generate,
    resolve,
    select_evidence,
    Requirement,
)
from accelerator_rag.rag.context import EvidenceContextBuilder
from accelerator_rag.rag.evidence import choose_subset
from accelerator_rag.rag.retrieval import RequirementRetriever
from accelerator_rag.rag.service import RagService
from accelerator_rag.rag.workflow import run_workflow


def hit(cid, text, score=0.9, *, page=1, version="2021"):
    chunk = KnowledgeChunk(
        cid,
        "design",
        "Design",
        text,
        "data/l0_raw/design.pdf",
        version,
        "en",
        "control",
        "interlock",
        page,
        page,
    )
    return RetrievalResult(1, score, chunk, "test")


class Provider:
    def __init__(self, outputs, events=None):
        self.outputs = iter(outputs)
        self.events = events if events is not None else []

    def complete(self, messages, tools, **kwargs):
        name = tools[0]["function"]["name"]
        expected, output = next(self.outputs)
        assert name == expected
        self.events.append(name)
        return AssistantResponse(
            tool_calls=(ToolCall(id="call", name=name, arguments=json.dumps(output)),)
        )


def test_subset_covers_requirements_instead_of_just_high_scores():
    context = EvidenceContextBuilder(max_sources=20).build(
        [
            hit("popular", "General controller background.", 0.99),
            hit("logic", "The controller executes safety logic.", 0.8),
            hit("link", "The converter carries interlock signals.", 0.6),
        ]
    )
    selection = Selection(
        requirements=[
            Support(id="R1", supported=True, span_ids=["S2.1"]),
            Support(id="R2", supported=True, span_ids=["S3.1"]),
        ]
    )
    selected, support, trace = choose_subset(
        context, selection, len, max_sources=2, token_budget=5000
    )
    assert set(selected.sources) == {"S2", "S3"}
    assert all(s.supported for s in support.requirements)
    assert trace["context_tokens"] <= trace["token_budget"]
    # Stable span identities are necessary for valid citations after pruning.
    assert "S3.1" in selected.spans


def test_equivalent_bundle_can_complete_requirement_within_source_budget():
    context = EvidenceContextBuilder().build(
        [
            hit("detail-a", "The source registers information."),
            hit("detail-b", "The web displays registered information."),
            hit("overview", "Information is registered and displayed on the web."),
        ]
    )
    assessment = Selection(
        requirements=[
            Support(
                id="R1",
                supported=True,
                span_ids=["S1.1", "S2.1"],
                alternatives=[["S3.1"]],
            )
        ]
    )
    selected, selection, _ = choose_subset(
        context, assessment, len, max_sources=1, token_budget=5000
    )
    assert set(selected.sources) == {"S3"}
    assert selection.requirements[0].supported
    assert selection.requirements[0].span_ids == ["S3.1"]
    assert not selection.requirements[0].alternatives


def test_field_inventory_rejects_an_incomplete_summary_bundle():
    context = EvidenceContextBuilder().build(
        [
            hit("summary", "The metadata includes address and path."),
            hit("detail", "The registered fields are address, path and control port."),
        ]
    )
    output = {
        "requirements": [
            {
                "id": "R1",
                "supported": True,
                "span_ids": ["S1.1"],
                "alternatives": [["S1.1"]],
                "items": [
                    {
                        "name": "address",
                        "source_term": "address",
                        "span_ids": ["S1.1", "S2.1"],
                    },
                    {
                        "name": "path",
                        "source_term": "path",
                        "span_ids": ["S1.1", "S2.1"],
                    },
                    {
                        "name": "control port",
                        "source_term": "control port",
                        "span_ids": ["S2.1"],
                    },
                ],
            }
        ]
    }
    assessment = select_evidence(
        Provider([("submit_evidence", output)]),
        "Which fields are registered?",
        [Requirement(id="R1", question="Which fields are registered?")],
        context,
        assessment=True,
    )
    selected, support, _ = choose_subset(
        context, assessment, len, max_sources=1, token_budget=5000
    )
    assert set(selected.sources) == {"S2"}
    assert support.requirements[0].supported
    assert len(support.requirements[0].items) == 3
    assert all(item.span_ids == ["S2.1"] for item in support.requirements[0].items)


def test_field_inventory_cannot_invent_a_source_term():
    context = EvidenceContextBuilder().build(
        [hit("detail", "The registered fields are address and path.")]
    )
    output = {
        "requirements": [
            {
                "id": "R1",
                "supported": True,
                "span_ids": ["S1.1"],
                "items": [
                    {
                        "name": "serial number",
                        "source_term": "serial number",
                        "span_ids": ["S1.1"],
                    },
                ],
            }
        ]
    }
    with pytest.raises(AnswerContractError):
        select_evidence(
            Provider([("submit_evidence", output)] * 2),
            "Which fields?",
            [Requirement(id="R1", question="Which fields?")],
            context,
        )


def test_quantitative_alternative_cannot_change_document_version_scope():
    context = EvidenceContextBuilder().build(
        [
            hit("current", "The documented maximum energy is 20 GeV.", version="2024"),
            hit("old", "Energy 8 GeV.", version="2017"),
        ]
    )
    output = {
        "requirements": [
            {
                "id": "R1",
                "supported": True,
                "span_ids": ["S1.1"],
                "alternatives": [["S2.1"]],
            }
        ]
    }
    assessment = select_evidence(
        Provider([("submit_evidence", output)]),
        "Maximum energy?",
        [Requirement(id="R1", question="Maximum energy?")],
        context,
        assessment=True,
    )
    assert not assessment.requirements[0].alternatives
    selected, _, _ = choose_subset(
        context, assessment, len, max_sources=1, token_budget=5000
    )
    assert set(selected.sources) == {"S1"}


@pytest.mark.parametrize(
    "query,old_version,new_version,expected_count",
    [
        ("请对照不同年份文档的最大能量，保留各自口径。", "2007", "2010", 2),
        ("Compare energy across document versions.", "2007", "2010", 2),
        ("What is the maximum energy?", "2007", "2010", 1),
        ("比较不同版本的最大能量。", "2010", "2010", 1),
        ("比较不同版本的最大能量。", "unknown", "2010", 1),
    ],
)
def test_version_comparison_preserves_scoped_disagreement(
    query, old_version, new_version, expected_count
):
    context = EvidenceContextBuilder().build(
        [
            hit("old", "Maximum energy 20 GeV.", version=old_version),
            hit("new", "Maximum energy 17.5 GeV.", version=new_version),
        ]
    )
    assessment = Selection.model_validate(
        {
            "requirements": [
                {"id": "R1", "supported": True, "span_ids": ["S1.1", "S2.1"]}
            ],
            "conflicts": [
                {"source_ids": ["S1", "S2"], "reason": "Different energy values."}
            ],
        }
    )
    selected, support, trace = choose_subset(
        context, assessment, len, token_budget=5000, query=query
    )
    assert len(selected.sources) == expected_count
    assert support.requirements[0].supported == (expected_count == 2)
    assert bool(trace["scope_differences"]) == (expected_count == 2)
    assert bool(trace["conflicts"]) == (expected_count == 1)


def test_subset_excludes_conflicting_sources_and_respects_budget():
    context = EvidenceContextBuilder().build(
        [hit("old", "Setpoint is 3 bar."), hit("new", "Setpoint is 5 bar.")]
    )
    assessment = Selection.model_validate(
        {
            "requirements": [
                {"id": "R1", "supported": True, "span_ids": ["S1.1"]},
                {"id": "R2", "supported": True, "span_ids": ["S2.1"]},
            ],
            "conflicts": [
                {
                    "source_ids": ["S1", "S2"],
                    "reason": "Different setpoints for the same operating scope.",
                }
            ],
        }
    )
    selected, support, _ = choose_subset(context, assessment, len, token_budget=5000)
    assert len(selected.sources) == 1
    assert sum(s.supported for s in support.requirements) == 1
    selected, support, trace = choose_subset(context, assessment, len, token_budget=100)
    assert not selected.sources and not any(s.supported for s in support.requirements)
    assert trace["context_tokens"] <= 100


def test_true_fact_survives_incomplete_requirement_review():
    context = EvidenceContextBuilder().build(
        [hit("converter", "The module converts electrical and optical signals.")]
    )
    requirement = [{"id": "R1", "question": "What protection does the module perform?"}]
    claim = {
        "claims": [
            {
                "requirement_ids": ["R1"],
                "span_ids": ["S1.1"],
                "text": "The module converts electrical and optical signals.",
            }
        ]
    }
    review = {
        "claims": [{"index": 0, "entailed": True}],
        "requirements": [
            {
                "id": "R1",
                "entailed_and_complete": False,
                "reason": "The action list is unavailable.",
                "missing": "Specific trip conditions.",
            }
        ],
    }
    outputs = [
        ("submit_requirements", {"requirements": requirement}),
        (
            "submit_evidence",
            {"requirements": [{"id": "R1", "supported": True, "span_ids": ["S1.1"]}]},
        ),
        ("submit_claims", claim),
        ("submit_grounding_review", review),
        ("submit_claims", claim),
        ("submit_grounding_review", review),
    ]
    result = resolve(
        generate(
            Provider(outputs), "What protection does the module perform?", context
        ),
        context,
    )
    assert result["status"] == "partial"
    assert "converts electrical and optical" in result["answer"]
    assert "Specific trip conditions" in result["answer"]
    assert result["requirements"][0]["coverage"] == "partial"
    assert result["citations"][0]["quote"]


def test_invalid_numeric_sentence_does_not_discard_valid_facts():
    context = EvidenceContextBuilder().build(
        [hit("design", "The mode is CW. The energy is 8 GeV.")]
    )
    req = [
        Requirement(id="R1", question="Mode?"),
        Requirement(id="R2", question="Energy?"),
    ]
    support = [
        Support(id="R1", supported=True, span_ids=["S1.1"]),
        Support(id="R2", supported=True, span_ids=["S1.2"]),
    ]
    claims = {
        "claims": [
            {
                "requirement_ids": ["R1"],
                "span_ids": ["S1.1"],
                "text": "The mode is CW.",
            },
            {
                "requirement_ids": ["R2"],
                "span_ids": ["S1.2"],
                "text": "The energy is 9 GeV.",
            },
        ]
    }
    review = {
        "claims": [{"index": 0, "entailed": True}],
        "requirements": [
            {"id": "R1", "entailed_and_complete": True},
            {
                "id": "R2",
                "entailed_and_complete": False,
                "missing": "No verified energy was stated.",
            },
        ],
    }
    audit = {}
    result = generate(
        Provider([("submit_claims", claims), ("submit_grounding_review", review)] * 2),
        "Mode and energy?",
        context,
        requirements=req,
        selection=support,
        audit=audit,
    )
    assert (
        result.status == "partial"
        and "CW" in result.answer
        and "9 GeV" not in result.answer
    )
    assert not result.requirements[1]["supported"]
    assert audit["discarded_validation"]


def test_missing_relation_triggers_targeted_recall_before_generation():
    events = []
    first = hit("logic", "The controller executes safety logic.")
    second = hit("link", "The converter carries the controller interlock signals.", 0.8)

    class Retriever:
        queries = []

        def retrieve(self, query, queries, *, anchors):
            events.append("retrieve")
            self.queries.append(queries)
            return ([first] if len(self.queries) == 1 else [first, second]), {
                "rerank_seconds": 0
            }

    outputs = [
        (
            "submit_requirements",
            {
                "requirements": [
                    {
                        "id": "R1",
                        "question": "How are the modules connected?",
                        "search_query": "controller converter interlock connection",
                    }
                ]
            },
        ),
        (
            "submit_evidence",
            {
                "requirements": [
                    {
                        "id": "R1",
                        "supported": False,
                        "span_ids": ["S1.1"],
                        "missing": "The signal connection.",
                    }
                ]
            },
        ),
        (
            "submit_supplementary_queries",
            {
                "queries": [
                    {
                        "requirement_id": "R1",
                        "text": "controller converter interlock signal connection",
                    }
                ]
            },
        ),
        (
            "submit_evidence",
            {
                "requirements": [
                    {"id": "R1", "supported": True, "span_ids": ["S1.1", "S2.1"]}
                ]
            },
        ),
        (
            "submit_claims",
            {
                "claims": [
                    {
                        "requirement_ids": ["R1"],
                        "span_ids": ["S1.1", "S2.1"],
                        "text": "The controller executes safety logic; the converter carries its interlock signals.",
                    }
                ]
            },
        ),
        (
            "submit_grounding_review",
            {
                "claims": [{"index": 0, "entailed": True}],
                "requirements": [{"id": "R1", "entailed_and_complete": True}],
            },
        ),
    ]
    retriever = Retriever()
    result, trace = run_workflow(
        Provider(outputs, events),
        retriever,
        "How do these cooperate?",
        Lock(),
        len,
        token_budget=5000,
    )
    assert result["status"] == "answered"
    assert events[:2] == ["submit_requirements", "retrieve"]
    assert (
        events.index("submit_claims")
        > [i for i, event in enumerate(events) if event == "retrieve"][-1]
    )
    assert retriever.queries[1] == ["controller converter interlock signal connection"]
    assert len(trace["rounds"]) == 2


def test_final_review_can_complete_an_evidence_backed_premise_correction():
    context = EvidenceContextBuilder().build(
        [hit("converter", "The module converts electrical and optical signals.")]
    )
    provider = Provider(
        [
            (
                "submit_claims",
                {
                    "claims": [
                        {
                            "requirement_ids": ["R1"],
                            "span_ids": ["S1.1"],
                            "text": "The documented role is electrical and optical conversion.",
                        }
                    ]
                },
            ),
            (
                "submit_grounding_review",
                {
                    "claims": [{"index": 0, "entailed": True}],
                    "requirements": [
                        {
                            "id": "R1",
                            "entailed_and_complete": True,
                            "reason": "The answer corrects the unsupported premise and explains the documented role.",
                        }
                    ],
                },
            ),
        ]
    )
    result = generate(
        provider,
        "What protection does it execute?",
        context,
        requirements=[
            Requirement(id="R1", question="What protection does it execute?")
        ],
        selection=[
            Support(
                id="R1",
                supported=False,
                span_ids=["S1.1"],
                missing="Independent protection logic.",
            )
        ],
    )
    assert result.status == "answered"
    assert result.requirements[0]["supported"] is True
    assert result.requirements[0]["missing"] == ""


def test_absence_of_explicit_wiring_cannot_be_upgraded_to_complete():
    context = EvidenceContextBuilder().build(
        [hit("converter", "The module has one fiber port.")]
    )
    claims = {
        "claims": [
            {
                "requirement_ids": ["R1"],
                "span_ids": ["S1.1"],
                "text": "The evidence gives one fiber port but no per-port wiring table.",
            }
        ]
    }
    review = {
        "claims": [{"index": 0, "entailed": True}],
        "requirements": [{"id": "R1", "entailed_and_complete": True}],
    }
    result = generate(
        Provider([("submit_claims", claims), ("submit_grounding_review", review)]),
        "Give every port wiring entry.",
        context,
        requirements=[Requirement(id="R1", question="Give every port wiring entry.")],
        selection=[
            Support(
                id="R1",
                supported=False,
                span_ids=["S1.1"],
                missing="Port-to-signal wiring assignments.",
            )
        ],
    )
    assert result.status == "partial"
    assert not result.requirements[0]["supported"]
    assert "Port-to-signal wiring assignments" in result.answer


def test_relation_reuses_joint_verified_facts_with_explicit_binding():
    context = EvidenceContextBuilder().build(
        [
            hit(
                "joint",
                "The controller executes safety logic. The converter carries its signals.",
            )
        ]
    )
    claims = {
        "claims": [
            {
                "requirement_ids": ["R1"],
                "span_ids": ["S1.1"],
                "text": "The controller executes safety logic.",
            },
            {
                "requirement_ids": ["R2"],
                "span_ids": ["S1.1", "S1.2"],
                "text": "The controller executes the logic and the converter carries its signals.",
            },
        ]
    }
    review = {
        "claims": [{"index": 0, "entailed": True}, {"index": 1, "entailed": True}],
        "requirements": [
            {"id": "R1", "entailed_and_complete": True},
            {"id": "R2", "entailed_and_complete": True},
        ],
    }
    result = generate(
        Provider([("submit_claims", claims), ("submit_grounding_review", review)]),
        "Roles and cooperation?",
        context,
        requirements=[
            Requirement(id="R1", question="Controller role?"),
            Requirement(id="R2", question="How do they cooperate?"),
        ],
        selection=[
            Support(id="R1", supported=True, span_ids=["S1.1"]),
            Support(id="R2", supported=True, span_ids=["S1.2"]),
        ],
    )
    assert result.status == "answered"
    assert "S1.1" in result.requirements[1]["span_ids"]


def test_joint_evidence_does_not_allow_unverified_context_spans():
    context = EvidenceContextBuilder().build(
        [hit("joint", "The mode is CW. The energy is 8 GeV.")]
    )
    wrong = {
        "claims": [
            {
                "requirement_ids": ["R1"],
                "span_ids": ["S1.2"],
                "text": "The energy is 8 GeV.",
            }
        ]
    }
    with pytest.raises(AnswerContractError):
        generate(
            Provider([("submit_claims", wrong)] * 2),
            "Mode?",
            context,
            requirements=[Requirement(id="R1", question="Mode?")],
            selection=[Support(id="R1", supported=True, span_ids=["S1.1"])],
        )


def test_missing_evidence_exhausts_budget_and_refuses_without_invention():
    class Retriever:
        calls = 0

        def retrieve(self, query, queries, *, anchors):
            self.calls += 1
            return [hit("unrelated", "Database monitoring.")], {"rerank_seconds": 0}

    no_evidence = {
        "requirements": [
            {
                "id": "R1",
                "supported": False,
                "span_ids": [],
                "missing": "No trip thresholds.",
            }
        ]
    }
    outputs = [
        (
            "submit_requirements",
            {
                "requirements": [
                    {"id": "R1", "question": "What are the trip thresholds?"}
                ]
            },
        ),
        ("submit_evidence", no_evidence),
        (
            "submit_supplementary_queries",
            {"queries": [{"requirement_id": "R1", "text": "trip thresholds"}]},
        ),
        ("submit_evidence", no_evidence),
    ]
    retriever = Retriever()
    result, trace = run_workflow(
        Provider(outputs), retriever, "Trip thresholds?", Lock(), len
    )
    assert result["status"] == "insufficient" and not result["citations"]
    assert retriever.calls == 2 and len(trace["rounds"]) == 2


def test_hybrid_retrieval_expands_same_page_without_crossing_versions():
    main = hit("main", "The controller and converter work together.")
    neighbor = hit("neighbor", "Local contacts connect to the controller.")
    other_version = hit("old", "Obsolete connection.", version="2017")

    class Dense:
        def search_with_trace(self, query, *, top_k):
            return [main], [], {"rerank_seconds": 0}

    class Reranker:
        def score(self, query, texts):
            return [0.9] * len(texts)

    retriever = RequirementRetriever(
        Dense(), [h.chunk for h in [main, neighbor, other_version]], Reranker()
    )
    # Isolate neighbor expansion from lexical ranking in this test.
    retriever.lexical = type("Empty", (), {"search": lambda *a, **k: []})()
    results, _ = retriever.retrieve("controller connection", ["controller connection"])
    assert {h.chunk.chunk_id for h in results} == {"main", "neighbor"}


def test_cross_version_quantities_must_keep_separate_claims():
    context = EvidenceContextBuilder().build(
        [
            hit("old", "The maximum energy is 3 GeV.", version="2017"),
            hit("new", "The maximum energy is 5 GeV.", version="2021"),
        ]
    )
    req = [
        Requirement(id="R1", question="Compare the maximum energy in the two versions.")
    ]
    support = [Support(id="R1", supported=True, span_ids=["S1.1", "S2.1"])]
    mixed = {
        "claims": [
            {
                "requirement_ids": ["R1"],
                "span_ids": ["S1.1", "S2.1"],
                "text": "The maxima are 3 GeV and 5 GeV.",
            }
        ]
    }
    with pytest.raises(AnswerContractError):
        generate(
            Provider([("submit_claims", mixed)] * 2),
            "Compare versions?",
            context,
            requirements=req,
            selection=support,
        )
    separate = {
        "claims": [
            {
                "requirement_ids": ["R1"],
                "span_ids": ["S1.1"],
                "text": "The 2017 maximum is 3 GeV.",
            },
            {
                "requirement_ids": ["R1"],
                "span_ids": ["S2.1"],
                "text": "The 2021 maximum is 5 GeV.",
            },
        ]
    }
    review = {
        "claims": [{"index": 0, "entailed": True}, {"index": 1, "entailed": True}],
        "requirements": [{"id": "R1", "entailed_and_complete": True}],
    }
    result = generate(
        Provider([("submit_claims", separate), ("submit_grounding_review", review)]),
        "Compare versions?",
        context,
        requirements=req,
        selection=support,
    )
    assert result.status == "answered"
    assert "2017" in result.answer and "2021" in result.answer


def test_invalid_conflict_identity_is_rejected():
    context = EvidenceContextBuilder().build([hit("a", "Safety logic.")])
    output = {
        "requirements": [{"id": "R1", "supported": True, "span_ids": ["S1.1"]}],
        "conflicts": [{"source_ids": ["S1", "S99"], "reason": "Invalid source."}],
    }
    with pytest.raises(AnswerContractError):
        select_evidence(
            Provider([("submit_evidence", output)] * 2),
            "Safety?",
            [Requirement(id="R1", question="Safety?")],
            context,
        )


def test_zero_padded_version_dates_do_not_discard_supported_claims():
    context = EvidenceContextBuilder().build(
        [hit("energy", "Normal operation energy is 17.5 GeV.", version="2007-07")]
    )
    req = [Requirement(id="R1", question="常规运行能量是多少？")]
    output = {
        "claims": [
            {
                "requirement_ids": ["R1"],
                "span_ids": ["S1.1"],
                "text": "2007 年 7 月版本的常规运行能量为 17.5 GeV。",
            }
        ]
    }
    review = {
        "claims": [{"index": 0, "entailed": True}],
        "requirements": [{"id": "R1", "entailed_and_complete": True}],
    }
    result = generate(
        Provider([("submit_claims", output), ("submit_grounding_review", review)]),
        "常规运行能量是多少？",
        context,
        requirements=req,
        selection=[Support(id="R1", supported=True, span_ids=["S1.1"])],
    )
    assert result.status == "answered"
    assert _numbers("2007-07 17.50") == _numbers("2007 年 7 月 17.5")
    assert not _numbers("17.6") <= _numbers("17.50")


def test_numeral_translation_keeps_values_but_rejects_new_numbers():
    assert {"1", "16"} <= _numbers("one fiber port and sixteen electric ports")
    assert {"1", "16"} <= _numbers("一个光纤口和十六个电口")
    assert "17" not in _numbers("one fiber port and sixteen electric ports")
    assert _numbers("数十毫秒") == _numbers("several tens millisecond")
    assert "30" not in _numbers("several tens millisecond")
    assert "2" not in _numbers("相关量化信息只有两项：")
    assert _reference_key("Table 1") == _reference_key("表1")
    assert _reference_key("Fig 3.1") == _reference_key("图 3.1")


def test_request_traces_are_private_and_bounded(tmp_path):
    service = RagService(None, None, trace_dir=tmp_path)
    for i in range(103):
        service._save_trace(f"{i:032x}", {"request_id": f"{i:032x}"})
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 100
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in files)
