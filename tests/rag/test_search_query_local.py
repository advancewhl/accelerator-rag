"""Chinese/local subqueries and dense candidate retention (F10)."""

import json
from threading import Lock

import pytest
from pydantic import ValidationError

from accelerator_rag.domain.knowledge import KnowledgeChunk, RetrievalResult
from accelerator_rag.domain.model import AssistantResponse, ToolCall
from accelerator_rag.rag.answer import Requirement, extract_requirements
from accelerator_rag.rag.retrieval import RequirementRetriever
from accelerator_rag.rag.workflow import _retrieval_queries, run_workflow


class Provider:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.messages = []

    def complete(self, messages, tools, **kwargs):
        name = tools[0]["function"]["name"]
        expected, output = next(self.outputs)
        assert name == expected
        self.messages.append(messages)
        return AssistantResponse(
            tool_calls=(ToolCall(id="call", name=name, arguments=json.dumps(output)),)
        )


class RecordingRetriever:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def retrieve(self, query, queries, *, anchors):
        self.calls.append(list(queries))
        return self.hits, {"rerank_seconds": 0}


def chunk(chunk_id, text):
    return KnowledgeChunk(
        chunk_id,
        chunk_id.split(":")[0],
        "Design",
        text,
        "data/l0_raw/design.pdf",
        "2024",
        "en",
        "control",
        "interlock",
        1,
        1,
    )


def test_requirement_accepts_optional_local_query_and_validates_length():
    requirement = Requirement(
        id="R1",
        question="联锁响应时间是多少？",
        search_query="interlock response time",
        search_query_local="SR:BPM01:X 的联锁响应时间是多少？",
    )
    assert requirement.search_query_local == "SR:BPM01:X 的联锁响应时间是多少？"
    assert Requirement(id="R1", question="Q").search_query_local == ""
    assert (
        Requirement(id="R1", question="Q", search_query_local="x" * 1500)
        .search_query_local
        == "x" * 1500
    )
    with pytest.raises(ValidationError):
        Requirement(id="R1", question="Q", search_query_local="x" * 1501)
    with pytest.raises(ValidationError):
        Requirement(id="R1", question="Q", search_query_local=7)


def test_requirement_extraction_prompts_for_verbatim_local_identifiers():
    output = {
        "requirements": [
            {
                "id": "R1",
                "question": "SR:BPM01:X 的联锁响应时间是多少？",
                "search_query": "SR:BPM01:X interlock response time",
                "search_query_local": "SR:BPM01:X 的联锁响应时间是多少？",
            }
        ]
    }
    provider = Provider([("submit_requirements", output)])
    requirements = extract_requirements(
        provider, "SR:BPM01:X 的联锁响应时间是多少？"
    )

    assert requirements[0].search_query_local == "SR:BPM01:X 的联锁响应时间是多少？"
    assert requirements[0].search_query == "SR:BPM01:X interlock response time"
    system_prompt = provider.messages[0][0].content
    assert "search_query_local" in system_prompt
    assert "逐字保留" in system_prompt


def test_workflow_sends_original_english_and_local_queries_deduped():
    outputs = [
        (
            "submit_requirements",
            {
                "requirements": [
                    {
                        "id": "R1",
                        "question": "联锁响应时间是多少？",
                        "search_query": "interlock response time",
                        # Same as the original question: must be deduplicated.
                        "search_query_local": "联锁响应时间是多少？",
                    },
                    {
                        "id": "R2",
                        "question": "哪些端子接线？",
                        "search_query": "terminal wiring",
                        "search_query_local": "端子接线",
                    },
                ]
            },
        ),
        (
            "submit_evidence",
            {
                "requirements": [
                    {"id": "R1", "supported": False, "span_ids": []},
                    {"id": "R2", "supported": False, "span_ids": []},
                ]
            },
        ),
    ]
    retriever = RecordingRetriever([])
    result, _trace = run_workflow(
        Provider(outputs),
        retriever,
        "联锁响应时间是多少？",
        Lock(),
        len,
        max_rounds=1,
    )

    assert result["status"] == "insufficient"
    assert retriever.calls == [
        [
            "联锁响应时间是多少？",
            "interlock response time",
            "terminal wiring",
            "端子接线",
        ]
    ]


def test_query_cap_keeps_local_identifiers_verbatim():
    local_queries = [
        "SR:BPM01:X 的联锁状态",
        "X09 的联锁状态",
        "SR:BPM01:X 与 X09 的联锁",
        "SR:BPM01:X 端子 X09 接线",
        "SR:BPM01:X 版本号 V2.1",
        "X09 响应时间 SR:BPM01:X",
    ]
    requirements = [
        {
            "id": f"R{i}",
            "question": f"Question {i}?",
            "search_query": f"english probe {i}",
            "search_query_local": text,
        }
        for i, text in enumerate(local_queries, 1)
    ]
    outputs = [
        ("submit_requirements", {"requirements": requirements}),
        (
            "submit_evidence",
            {
                "requirements": [
                    {"id": f"R{i}", "supported": False, "span_ids": []}
                    for i in range(1, 7)
                ]
            },
        ),
    ]
    retriever = RecordingRetriever([])
    query = "SR:BPM01:X 和 X09 的联锁状态？"
    run_workflow(
        Provider(outputs), retriever, query, Lock(), len, max_rounds=1
    )

    sent = retriever.calls[0]
    # 1 original + 6 English + 6 local would exceed the cap.  Every local probe
    # survives with its identifiers verbatim; only one English probe fits.
    assert sent == [query, "english probe 1", *local_queries]
    assert len(sent) == 8
    assert "SR:BPM01:X" in sent[0] and "X09" in sent[0]
    assert all(
        "SR:BPM01:X" in text or "X09" in text for text in sent[2:]
    )


def test_dense_ranks_six_to_ten_enter_requirement_fusion():
    hits = [
        RetrievalResult(
            rank, 1.0 / rank, chunk(f"doc{i:02d}:p", f"passage {i}"), "fake"
        )
        for i, rank in enumerate(range(1, 11), 1)
    ]

    class Dense:
        def __init__(self):
            self.top_k = None

        def search_with_trace(self, query, *, top_k, scope=None):
            self.top_k = top_k
            traces = [
                {
                    "parent_chunk_id": hit.chunk.chunk_id,
                    "passage_id": f"passage-{hit.rank}",
                    "passage_excerpt": hit.chunk.text,
                }
                for hit in hits
            ]
            return hits, traces, {"rerank_seconds": 0}

    class Lexical:
        def __init__(self):
            self.top_k = None

        def search(self, query, *, top_k, scope=None):
            self.top_k = top_k
            return []

    class Reranker:
        def score(self, query, texts):
            return [1.0] * len(texts)

    dense, lexical = Dense(), Lexical()
    retriever = RequirementRetriever(
        dense, [hit.chunk for hit in hits], Reranker()
    )
    retriever.lexical = lexical
    results, trace = retriever.retrieve("interlock", ["interlock"])

    assert dense.top_k == 10
    assert lexical.top_k == 5
    assert len(results) == 10
    assert "doc06:p" in {hit.chunk.chunk_id for hit in results}
    assert trace["searches"][0]["dense_trace"] == [
        {
            "parent_chunk_id": hit.chunk.chunk_id,
            "passage_id": f"passage-{hit.rank}",
            "passage_excerpt": hit.chunk.text,
        }
        for hit in hits
    ]


def test_query_cap_keeps_every_local_probe_and_original_question():
    requirements = [
        Requirement(
            id=f"R{index}",
            question=f"第{index}个问题",
            search_query=f"english probe {index}",
            search_query_local=f"本地标识符 {index} SR:BPM01:X",
        )
        for index in range(1, 7)
    ]
    queries = _retrieval_queries("原始问题", requirements)

    assert len(queries) == 8
    assert queries[0] == "原始问题"
    assert all(
        requirement.search_query_local in queries
        for requirement in requirements
    )
    assert sum(query.startswith("english probe") for query in queries) == 1


def test_every_requirement_gets_a_probe_even_with_mixed_local_coverage():
    requirements = [
        Requirement(
            id=f"R{index}",
            question=f"第{index}个问题",
            search_query=f"english {index}",
            search_query_local=f"本地 {index}" if index <= 2 else "",
        )
        for index in range(1, 7)
    ]
    queries = _retrieval_queries("原始问题", requirements)

    assert len(queries) <= 8
    for index in (1, 2):
        assert f"本地 {index}" in queries
    for index in range(3, 7):
        assert f"english {index}" in queries


def test_blank_local_query_is_ignored_instead_of_failing_retrieval():
    requirements = [
        Requirement(
            id="R1",
            question="联锁响应时间？",
            search_query="interlock response",
            search_query_local="   ",
        )
    ]
    queries = _retrieval_queries("联锁响应时间？", requirements)

    assert queries == ["联锁响应时间？", "interlock response"]
    assert all(query.strip() for query in queries)


def test_blank_search_query_falls_back_to_the_question_per_requirement():
    requirements = [
        Requirement(id="R1", question="第一个问题", search_query="   ", search_query_local=""),
        Requirement(id="R2", question="第二个问题", search_query="", search_query_local=""),
    ]
    queries = _retrieval_queries("原始问题", requirements)

    assert "第一个问题" in queries
    assert "第二个问题" in queries
