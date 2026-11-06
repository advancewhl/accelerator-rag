"""Exact row lookup injects the parent chunk before evidence selection."""

from accelerator_rag.corpus.table_records import TableRecord, TableRecordIndex
from accelerator_rag.domain.knowledge import KnowledgeChunk, RetrievalResult
from accelerator_rag.rag.retrieval import RequirementRetriever
from accelerator_rag.retrieval.scope import default_scope


def make_chunk(chunk_id="terminal:chunk", text="设备 | 端子号\nBPM01 | X09"):
    return KnowledgeChunk(
        chunk_id,
        "terminal-rev",
        "端子对应表",
        text,
        "data/l0_raw/incoming/2026-11-02-shine-control/资料/端子表.xlsx",
        "3.8",
        "zh",
        "control_system",
        "wiring",
        1,
        1,
        position_kind="cell_range",
        position_label="主控柜!A17:C19",
        content_role="table",
    )


def test_more_than_five_exact_rows_are_not_dropped():
    chunks = [make_chunk(f"terminal:row-{index}", f"row {index}") for index in range(8)]
    records = tuple(
        TableRecord(
            record_id=f"table:r{index}",
            revision_id="terminal-rev",
            table_block_id="table",
            sheet="主控柜",
            row_number=index,
            headers=("端子",),
            cells=(("A", f"X{index}"),),
            row_text=f"X{index}",
            chunk_id=chunk.chunk_id,
        )
        for index, chunk in enumerate(chunks[:7])
    )

    class Dense:
        def search_with_trace(self, query, *, top_k, scope=None):
            return [], [], {"rerank_seconds": 0}

    class Lexical:
        def search(self, query, *, top_k, scope=None):
            return []

    class Reranker:
        def score(self, query, texts):
            return [0.0] * len(texts)

    retriever = RequirementRetriever(
        Dense(),
        chunks,
        Reranker(),
        structured_index=TableRecordIndex(records),
    )
    retriever.lexical = Lexical()
    _hits, trace = retriever.retrieve(
        "X0 X1 X2 X3 X4 X5 X6", ["X0 X1 X2 X3 X4 X5 X6"], scope=default_scope()
    )
    chosen = {item["chunk_id"] for item in trace["chosen"]}

    assert {chunk.chunk_id for chunk in chunks[:7]} <= chosen


def test_exact_row_is_injected_even_when_reranker_prefers_other_text():
    exact = make_chunk()
    other = make_chunk("terminal:other", "unrelated table text")
    records = (
        TableRecord(
            record_id="table:r18",
            revision_id="terminal-rev",
            table_block_id="table",
            sheet="主控柜",
            row_number=18,
            headers=("设备", "端子号"),
            cells=(("A", "BPM01"), ("B", "X09")),
            row_text="BPM01 | X09",
            chunk_id=exact.chunk_id,
        ),
    )
    index = TableRecordIndex(records)

    class Dense:
        def search_with_trace(self, query, *, top_k, scope=None):
            return [], [], {"rerank_seconds": 0}

    class Lexical:
        def search(self, query, *, top_k, scope=None):
            return []

    class Reranker:
        def score(self, query, texts):
            return [0.0 if text.startswith("unrelated") else 0.1 for text in texts]

    retriever = RequirementRetriever(
        Dense(), [exact, other], Reranker(), structured_index=index
    )
    retriever.lexical = Lexical()
    hits, trace = retriever.retrieve("X09", ["X09"], scope=default_scope())

    ordered = [hit.chunk.chunk_id for hit in hits]
    assert ordered[0] == exact.chunk_id
    assert exact.chunk_id in ordered
    assert trace["structured_exact"] == [exact.chunk_id]
    assert any(
        origin["channel"] == "structured-exact"
        for origin in trace["ranked"][0]["origins"]
    )


def test_all_exact_rows_survive_competing_non_exact_candidates():
    exact_chunks = [make_chunk(f"terminal:exact-{i}", f"exact {i}") for i in range(7)]
    other_chunks = [make_chunk(f"terminal:other-{i}", f"other {i}") for i in range(20)]
    records = tuple(
        TableRecord(
            record_id=f"table:r{i}",
            revision_id="terminal-rev",
            table_block_id="table",
            sheet="主控柜",
            row_number=i,
            headers=("端子",),
            cells=(("A", f"X{i}"),),
            row_text=f"X{i}",
            chunk_id=chunk.chunk_id,
        )
        for i, chunk in enumerate(exact_chunks)
    )

    class Dense:
        def search_with_trace(self, query, *, top_k, scope=None):
            return [
                RetrievalResult(rank, 1.0, chunk, "fake")
                for rank, chunk in enumerate(other_chunks[:10], 1)
            ], [], {"rerank_seconds": 0}

    class Lexical:
        def search(self, query, *, top_k, scope=None):
            return []

    class Reranker:
        def score(self, query, texts):
            return [0.0 if text.startswith("exact") else 1.0 for text in texts]

    retriever = RequirementRetriever(
        Dense(),
        exact_chunks + other_chunks,
        Reranker(),
        structured_index=TableRecordIndex(records),
    )
    retriever.lexical = Lexical()
    _hits, trace = retriever.retrieve(
        "X0 X1 X2 X3 X4 X5 X6", ["X0 X1 X2 X3 X4 X5 X6"], scope=default_scope()
    )
    chosen = {item["chunk_id"] for item in trace["chosen"]}

    assert {chunk.chunk_id for chunk in exact_chunks} <= chosen
    assert len(trace["chosen"]) <= 20


def test_neighbour_context_survives_a_full_scored_candidate_pool():
    """Neighbours score 0; a plain top-48 cut used to drop all of them."""

    from accelerator_rag.domain.knowledge import KnowledgeChunk

    def para(cid, ordinal, text):
        return KnowledgeChunk(
            cid, "manual", "Manual", text, "data/l0_raw/manual.docx", "1",
            "zh", "control_system", "timing", 1, 1,
            position_kind="paragraph", document_ordinal=ordinal,
        )

    anchor = para("manual:anchor", 50, "anchor step")
    neighbour = para("manual:next", 51, "next step")
    others = [para(f"other:{i}", 0, f"other {i}") for i in range(60)]
    others = [
        KnowledgeChunk(**{**chunk.__dict__, "document_id": f"other-{i}"})
        for i, chunk in enumerate(others)
    ]

    class Dense:
        def search_with_trace(self, query, *, top_k, scope=None):
            pool = [anchor] + others
            return [
                RetrievalResult(rank, 1.0, chunk, "fake")
                for rank, chunk in enumerate(pool[:10], 1)
            ], [], {"rerank_seconds": 0}

    class Lexical:
        def search(self, query, *, top_k, scope=None):
            return []

    class Reranker:
        def score(self, query, texts):
            return [1.0] * len(texts)

    retriever = RequirementRetriever(Dense(), [anchor, neighbour, *others], Reranker())
    retriever.lexical = Lexical()
    queries = [f"q{i}" for i in range(8)]

    class ManyDense(Dense):
        def search_with_trace(self, query, *, top_k, scope=None):
            index = int(query[1:])
            pool = [anchor] + others[index * 7 : index * 7 + 9]
            return [
                RetrievalResult(rank, 1.0, chunk, "fake")
                for rank, chunk in enumerate(pool, 1)
            ], [], {"rerank_seconds": 0}

    retriever.dense = ManyDense()
    _hits, trace = retriever.retrieve("q", queries, scope=default_scope())
    ranked = {item["chunk_id"] for item in trace["ranked"]}
    assert trace["candidate_count"] > 48
    assert "manual:next" in ranked


def test_lookup_api_returns_ranked_hits_with_headers_and_row_link():
    from fastapi.testclient import TestClient

    from accelerator_rag.rag.api import create_app

    records = (
        TableRecord(
            record_id="sw:b:r5",
            revision_id="switch-rev",
            table_block_id="sw:b",
            sheet="L3",
            row_number=5,
            headers=("设备", "端口", "系统", "网络分配", "分组"),
            cells=(
                ("A", "L3-CN01柜（DEVSW001）"),
                ("B", "9-16"),
                ("C", "固态功率源"),
                ("D", "VLAN10"),
                ("_group", "L3-CN01柜（DEVSW001）"),
            ),
            row_text="L3-CN01柜（DEVSW001） | 9-16 | 固态功率源 | VLAN10",
            chunk_id="sw:c1",
        ),
        TableRecord(
            record_id="sw:b:r6",
            revision_id="switch-rev",
            table_block_id="sw:b",
            sheet="L3",
            row_number=6,
            headers=("设备", "端口", "系统", "网络分配", "分组"),
            cells=(
                ("A", "L3-CN01柜（DEVSW001）"),
                ("B", "17-20"),
                ("C", "电源"),
                ("D", "VLAN20"),
                ("_group", "L3-CN01柜（DEVSW001）"),
            ),
            row_text="L3-CN01柜（DEVSW001） | 17-20 | 电源 | VLAN20",
            chunk_id="sw:c1",
        ),
    )

    class Service:
        release_id = "kb-test"
        table_records = TableRecordIndex(records)

        def answer(self, query, scope=None):
            raise AssertionError("not used")

    with TestClient(create_app(Service())) as client:
        response = client.get(
            "/v1/rag/structured/lookup",
            params={"q": "L3-CN01柜 DEVSW001 第12口是哪个VLAN"},
        )
        empty = client.get("/v1/rag/structured/lookup", params={"q": "  "})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 1
    top = body["hits"][0]
    assert top["row_number"] == 5 and top["near_best"]
    assert {"header": "网络分配", "column": "D", "value": "VLAN10"} in top["fields"]
    assert top["view_url"].endswith("block_id=sw%3Ab&row=5")
    assert "端口12" in top["matched"]
    assert body["records"][0]["record_id"] == "sw:b:r5"
    assert empty.status_code == 422
