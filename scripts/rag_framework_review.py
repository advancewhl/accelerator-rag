"""Independently audit saved HTTP responses, real quotes and frozen targets."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re

import pymupdf

from accelerator_rag.evaluation.retrieval import normalize_evidence
from accelerator_rag.rag.answer import _requires_exact_evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default="reports/rag-framework-20261028")
    args = parser.parse_args()
    root = Path(args.directory)
    raw = json.loads((root / "http-results.json").read_text())
    with gzip.open(root / "request-traces.json.gz", "rt") as stream:
        traces = {t["request_id"]: t for t in json.load(stream)}
    benchmark = Path("data/evaluation/retrieval_baseline.json")
    labels = {q["id"]: q for q in json.loads(benchmark.read_text())["queries"]}
    registry = {
        d["doc_id"]: d
        for d in json.loads(Path("data/documents/registry.json").read_text())
    }
    invalid, coverage = [], []
    page_counts = {}
    positive = negative = supplemented = citation_count = scope_differences = 0
    for row in raw["cases"]:
        data = row.get("response", {})
        if row.get("http_status") != 200 or "request_id" not in data:
            invalid.append([row["id"], "HTTP/request identity"])
            continue
        trace = traces[data["request_id"]]
        chosen = trace["rounds"][trace["selected_round"] - 1]
        initial_support = {
            r["id"]: r
            for r in chosen.get("selected_support", {}).get("requirements", [])
        }
        for requirement in data["requirements"]:
            initial = initial_support.get(requirement["id"])
            if (
                requirement["supported"]
                and initial
                and not initial["supported"]
                and _requires_exact_evidence(requirement["text"])
            ):
                invalid.append(
                    [row["id"], "unsupported exact value/list marked complete"]
                )
        parents = {h["chunk"]["chunk_id"]: h["chunk"] for h in chosen["results"]}
        if trace["query"] != row["query"] or trace["response"] != data:
            invalid.append([row["id"], "response/trace mismatch"])
        for round_row in trace["rounds"]:
            subset = round_row["subset"]
            selected = set(subset["selected_sources"])
            candidates = {c["source_id"]: c for c in round_row["candidates"]}
            for difference in subset.get("scope_differences", []):
                scope_differences += 1
                versions = {
                    candidates[sid]["document_version"]
                    for sid in difference["source_ids"]
                }
                if len(versions) != 2 or "unknown" in versions:
                    invalid.append([row["id"], "invalid comparative version scopes"])
            if (
                subset["context_tokens"] > subset["token_budget"]
                or len(selected) > subset["max_sources"]
            ):
                invalid.append([row["id"], "evidence budget"])
            if any(set(c["source_ids"]) <= selected for c in subset["conflicts"]):
                invalid.append([row["id"], "conflicting sources retained"])
        supplemented += any("supplementary_queries" in r for r in trace["rounds"])
        if len(trace["rounds"]) > 2:
            invalid.append([row["id"], "retrieval iteration budget"])
        refs = set(map(int, re.findall(r"\[(\d+)\]", data["answer"])))
        if refs != {c["number"] for c in data["citations"]}:
            invalid.append([row["id"], "citation identity"])
        for citation in data["citations"]:
            citation_count += 1
            parent = parents.get(citation["chunk_id"])
            if parent is None:
                invalid.append([row["id"], "citation outside selected subset"])
                continue
            if any(
                citation[k] != parent[k]
                for k in (
                    "document_id",
                    "document_title",
                    "document_version",
                    "page_start",
                    "page_end",
                )
            ):
                invalid.append([row["id"], "source metadata"])
            for quote in citation["quote"].split("\n\n"):
                if normalize_evidence(quote) not in normalize_evidence(parent["text"]):
                    invalid.append([row["id"], "quote outside canonical source"])
            docid = citation["document_id"]
            if docid not in page_counts:
                with pymupdf.open(registry[docid]["source_path"]) as pdf:
                    page_counts[docid] = len(pdf)
            if (
                not 1
                <= citation["page_start"]
                <= citation["page_end"]
                <= page_counts[docid]
            ):
                invalid.append([row["id"], "physical PDF page"])
        if row["id"] not in labels:
            continue
        query = labels[row["id"]]
        if query["query"] != row["query"]:
            invalid.append([row["id"], "frozen query changed"])
        if not query["answerable"]:
            negative += data["status"] == "insufficient" and not data["citations"]
            continue
        positive += data["status"] == "answered"

        def matches(text, metadata, target):
            return (
                metadata["document_id"] == target["document_id"]
                and metadata["page_start"] <= target["page"] <= metadata["page_end"]
                and normalize_evidence(target["excerpt"]) in normalize_evidence(text)
            )

        quote_groups, parent_groups = [], []
        for i, group in enumerate(query["evidence_groups"], 1):
            if any(
                matches(c["quote"], c, target)
                for c in data["citations"]
                for target in group["alternatives"]
            ):
                quote_groups.append(i)
            if any(
                matches(p["text"], p, target)
                for p in parents.values()
                for target in group["alternatives"]
            ):
                parent_groups.append(i)
        coverage.append(
            {
                "id": row["id"],
                "groups": len(query["evidence_groups"]),
                "judgment_mode": query["judgment_mode"],
                "quoted_groups": quote_groups,
                "selected_parent_groups": parent_groups,
            }
        )

    def complete(row, key):
        return (
            bool(row[key])
            if row["judgment_mode"] == "any"
            else len(row[key]) == row["groups"]
        )

    result = {
        "source_benchmark_sha256": hashlib.sha256(benchmark.read_bytes()).hexdigest(),
        "requests": len(raw["cases"]),
        "positive_answered": positive,
        "negative_correctly_refused": negative,
        "citation_count": citation_count,
        "cited_documents": len(page_counts),
        "supplemented_requests": supplemented,
        "version_scope_differences": scope_differences,
        "quoted_frozen_target_complete": sum(
            complete(r, "quoted_groups") for r in coverage
        ),
        "selected_parent_frozen_target_complete": sum(
            complete(r, "selected_parent_groups") for r in coverage
        ),
        "invalid": invalid,
        "frozen_target_coverage": coverage,
        "interpretation": "Target containment is a diagnostic; it is independent of self-reported supported flags and does not alone prove semantic accuracy.",
    }
    (root / "independent-review.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "frozen_target_coverage"},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
