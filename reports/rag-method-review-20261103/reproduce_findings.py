"""Offline review probes using synthetic evidence; does not modify the service."""

from dataclasses import asdict
import json

from qdrant_client import QdrantClient, models

from accelerator_rag.corpus.parsed_document import (
    ParsedBlock, ParsedDocument, SourcePosition, TableData,
)
from accelerator_rag.corpus.table_records import build_table_records
from accelerator_rag.domain.knowledge import KnowledgeChunk, RetrievalResult
from accelerator_rag.domain.model import AssistantResponse, ToolCall
from accelerator_rag.rag.answer import (
    AnswerContractError, EvidenceConflict, Requirement, Selection, Support,
    _numbers, generate, select_evidence,
)
from accelerator_rag.rag.context import EvidenceContextBuilder
from accelerator_rag.rag.evidence import choose_subset
from accelerator_rag.retrieval.scope import RetrievalScope
from accelerator_rag.storage.qdrant_passages import build_scope_filter


def chunk(cid, text, **overrides):
    values = dict(
        chunk_id=cid, document_id="synthetic-manual", document_title="Manual",
        text=text, source_path="data/l0_raw/manual.docx", document_version="r1",
        language="en", category="control_system", topic="timing",
        page_start=1, page_end=1, usage_status="reference", access_scope="internal",
    )
    values.update(overrides)
    return KnowledgeChunk(**values)


def context(*chunks):
    return EvidenceContextBuilder().build([
        RetrievalResult(i, 0.8, c, "synthetic")
        for i, c in enumerate(chunks, 1)
    ])


class FixedProvider:
    def __init__(self, payload):
        self.payload = payload

    def complete(self, messages, tools, **kwargs):
        return AssistantResponse(tool_calls=(ToolCall(
            id="synthetic", name=tools[0]["function"]["name"],
            arguments=json.dumps(self.payload),
        ),))


def main():
    results = {}
    alias_chunk = chunk(
        "alias", "Timing instructions.", family_id="timing-manual",
        tags="series:shine-control-operation-manual-series",
    )
    scope = RetrievalScope(family_ids=frozenset({
        "shine-control-operation-manual-series",
    }))
    client = QdrantClient(":memory:")
    try:
        client.create_collection("probe", vectors_config=models.VectorParams(
            size=2, distance=models.Distance.COSINE,
        ))
        client.upsert("probe", points=[models.PointStruct(
            id=1, vector=[1.0, 0.0], payload=asdict(alias_chunk),
        )])
        results["legacy_family_alias"] = {
            "python_scope_allows": scope.allows(alias_chunk),
            "qdrant_count": client.count(
                "probe", count_filter=build_scope_filter(scope), exact=True,
            ).count,
        }

    finally:
        client.close()

    table = TableData(
        rows=(("Terminal", "Signal"), ("X01", "Signal-A"), ("X02", "Signal-B")),
        header_rows=1, row_numbers=(1, 2, 3), column_letters=("A", "B"),
    )
    block = ParsedBlock(
        block_id="synthetic-table", block_type="table", text=table.text,
        position=SourcePosition(
            kind="cell_range", start=1, end=3, label="Sheet1!A1:B3",
            locator=(("sheet", "Sheet1"),),
        ), table=table,
    )
    parsed = ParsedDocument(
        revision_id="synthetic-manual", asset_id="synthetic-asset",
        source_path="data/l0_raw/manual.docx", source_format="docx",
        title="Manual", blocks=(block,), parser_profile="synthetic",
    )
    first = chunk("first-piece", "Terminal | Signal\nX01 | Signal-A",
                  source_block_ids=block.block_id)
    last = chunk("last-piece", "Terminal | Signal\nX02 | Signal-B",
                 source_block_ids=block.block_id)
    records = build_table_records(parsed, [first, last])
    results["split_table_mapping"] = {
        "first_row_parent": records[0].chunk_id,
        "expected_first_row_parent": first.chunk_id,
        "all_parents": [r.chunk_id for r in records],
    }

    left, right = "Delay is less than 10 us.", "Delay is at least 10 ms."
    results["numeric_guard"] = {
        "source_numbers": sorted(_numbers(left)),
        "wrong_claim_numbers": sorted(_numbers(right)),
        "guard_cannot_distinguish": _numbers(left) == _numbers(right),
        "conversion_1000_ms_to_1_s_rejected_by_number_set": bool(
            _numbers("Delay is 1 s.") - _numbers("Delay is 1000 ms.")
        ),
    }

    ocr_context = context(
        chunk("ocr", "The temperature limit is 80 C.",
              extraction_method="ocr", review_status="required"),
        chunk("native", "This cabinet uses temperature monitoring."),
    )
    selection_payload = {"requirements": [{
        "id": "R1", "supported": True, "span_ids": ["S1.1", "S2.1"],
    }]}
    selection = select_evidence(
        FixedProvider(selection_payload), "What is the temperature limit?",
        [Requirement(id="R1", question="What is the temperature limit?")],
        ocr_context, assessment=True,
    )
    results["ocr_mixed_evidence_guard"] = {
        "supported_with_unverified_value_and_native_background":
            selection.requirements[0].supported,
        "note": "Synthetic model selection; demonstrates a guard gap, not model error frequency.",
    }

    conflict_context = context(
        chunk("conflict-a", "The threshold is 10 V."),
        chunk("conflict-b", "The threshold is 20 V."),
    )
    selected, selection, trace = choose_subset(
        conflict_context,
        Selection(requirements=[Support(
            id="R1", supported=True, span_ids=["S1.1"], alternatives=[["S2.1"]],
        )], conflicts=[EvidenceConflict(
            source_ids=["S1", "S2"], reason="Unresolved values under the same condition.",
        )]),
        len, token_budget=6000, query="What is the threshold?",
    )
    results["unresolved_conflict"] = {
        "selected_sources": list(selected.sources),
        "supported": selection.requirements[0].supported,
        "returned_conflicts": len(selection.conflicts),
        "conflicts_in_trace": len(trace["conflicts"]),
    }

    cross_context = context(
        chunk("number", "The response time is 10 us.", document_id="specification"),
        chunk("condition", "This specification applies to prototype A.",
              document_id="applicability"),
    )
    claim = {"claims": [{
        "requirement_ids": ["R1"], "span_ids": ["S1.1", "S2.1"],
        "text": "The response time of prototype A is 10 us.",
    }]}
    try:
        generate(
            FixedProvider(claim), "What is the response time of prototype A?",
            cross_context,
            requirements=[Requirement(
                id="R1", question="What is the response time of prototype A?",
            )],
            selection=[Support(
                id="R1", supported=True, span_ids=["S1.1", "S2.1"],
            )],
        )
    except AnswerContractError as error:
        results["cross_document_quantitative_claim"] = {
            "exception": str(error), "cause": str(error.__cause__),
            "same_revision_labels": True,
        }
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
