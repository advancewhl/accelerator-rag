"""Full canonical evidence plus request-local span IDs for exact answer selection."""

from dataclasses import dataclass, field
import json
import re

from accelerator_rag.domain.knowledge import RetrievalResult


@dataclass(frozen=True)
class EvidenceContext:
    sources: dict[str, RetrievalResult]
    model_content: str
    spans: dict[str, tuple[str, str]] = field(default_factory=dict)

    def subset(self, source_ids):
        """Keep request-local identities stable across selection and generation."""
        selected = set(source_ids)
        if not selected <= self.sources.keys():
            raise ValueError("unknown evidence source")
        records = [
            r for r in json.loads(self.model_content) if r["source_id"] in selected
        ]
        return EvidenceContext(
            {sid: hit for sid, hit in self.sources.items() if sid in selected},
            json.dumps(records, ensure_ascii=False),
            {sid: value for sid, value in self.spans.items() if value[0] in selected},
        )


class EvidenceContextBuilder:
    def __init__(self, max_sources=5):
        if type(max_sources) is not int or not 1 <= max_sources <= 24:
            raise ValueError("invalid evidence source limit")
        self.max_sources = max_sources

    def build(self, results: list[RetrievalResult]) -> EvidenceContext:
        if len(results) > self.max_sources:
            raise ValueError("too many canonical evidence parents")
        if len({r.chunk.chunk_id for r in results}) != len(results):
            raise ValueError("duplicate canonical parents")
        sources = {f"S{i}": hit for i, hit in enumerate(results, 1)}
        spans, records = {}, []
        for sid, hit in sources.items():
            segments = []
            # These are presentation spans only: no corpus/index/chunk changes.
            flat = re.sub(r"\s+", " ", hit.chunk.text).strip()
            sentences = [
                t.strip()
                for t in re.split(
                    r"(?<=[。！？])\s*|(?<=[.!?])\s+(?=[A-Z\u4e00-\u9fff])", flat
                )
                if t.strip()
            ]
            for index, text in enumerate(sentences):
                # Keep antecedents for quotations beginning with a referring
                # expression; this avoids detached 'Then/It/information' claims.
                referring = re.match(
                    r"(?:It\b|They\b|This\b|These\b|Those\b|Then\b|The information\b|The linked\b|With (?:one |a )pair of (?:this|such)\b|Response is\b|该|其|这些|此|其中|此外)",
                    text,
                    re.IGNORECASE,
                )
                if index and referring:
                    text = segments[index - 1]["text"] + " " + text
                span_id = f"{sid}.{len(segments) + 1}"
                spans[span_id] = (sid, text)
                segments.append({"span_id": span_id, "text": text})
            records.append(
                {
                    "source_id": sid,
                    "document_title": hit.chunk.document_title,
                    "document_version": hit.chunk.document_version,
                    "page_start": hit.chunk.page_start,
                    "page_end": hit.chunk.page_end,
                    "text": hit.chunk.text,
                    "answer_spans": segments,
                }
            )
        # Full KnowledgeChunk.text always remains in context, independently of
        # the selectable spans. Internal paths and evaluation labels are absent.
        return EvidenceContext(sources, json.dumps(records, ensure_ascii=False), spans)
