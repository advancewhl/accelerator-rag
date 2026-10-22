"""Small, data-backed report review input; no retrieval or model execution."""

from copy import deepcopy
import json
from pathlib import Path

from accelerator_rag.evaluation.retrieval import ranking_sha256


def measurement_rankings(report):
    return {
        "BM25": ranking_sha256(report["bm25"]["cases"]),
        **{
            name: ranking_sha256(row["evaluation"]["cases"])
            for name, row in report["models"].items()
        },
    }


def apply_manual_review(measurement, review):
    if measurement_rankings(measurement) != review["measurement_rankings_sha256"]:
        raise ValueError("manual review belongs to different measurement rankings")
    result = deepcopy(measurement)
    for key in ("manual_evidence_checks", "analysis_notes", "recommendation"):
        result[key] = review[key]
    result["validation_markdown"] = review.get("validation_markdown", "")
    return result


def load_manual_review(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
