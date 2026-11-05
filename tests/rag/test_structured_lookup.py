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
