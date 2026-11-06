"""Run the historical 50-question RAG regression against a live HTTP service.

This runner is deliberately standalone: it uses only the Python standard
library and never imports project code or credentials.  Only ``{"query": ...}``
is sent to the service; labels, gold answers and evidence stay in this client.

It is an engineering regression harness.  It does not score semantic answer
correctness.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import threading
import time
from urllib import error, parse, request


SCHEMA_VERSION = "kb2-regression-v1"
STATUS_VALUES = ("answered", "partial", "insufficient")
STATUS_ALIASES = {
    "answered": "answered",
    "answerable": "answered",
    "partial": "partial",
    "insufficient": "insufficient",
    "no_answer": "insufficient",
    "unanswerable": "insufficient",
}
QUESTION_KEYS = ("query", "question", "prompt", "question_text", "text")
ID_KEYS = ("id", "question_id", "case_id")
EXPECTED_STATUS_KEYS = ("expected_status", "expected", "gold_status")
GOLD_KEYS = ("gold_answer", "reference_answer", "expected_answer")
DEFAULT_QUESTIONS = (
    Path(__file__).resolve().parents[1] / "data/evaluation/validity-pilot-v2.json"
)
URL_PATTERN = re.compile(r"https?://[^\s'\"<>]+")
REDACT_PATTERN = re.compile(
    r"(?i)\b(authorization|api[_-]?key|token|password|secret)\b\s*[:=]\s*\S+"
)
ABS_PATH_PATTERN = re.compile(
    r"/(?:opt|home|srv|var|etc|tmp|root|mnt|proc)(?:/[^\s'\"<>]+)+"
)
SAFE_CODE_PATTERN = re.compile(r"[A-Za-z0-9_.:-]{1,200}")


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _first_str(mapping, keys):
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str):
            value = value.strip()
            if value:
                return value
    return None


def _string_list(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    result = []
    for entry in value:
        if isinstance(entry, str) and entry.strip():
            result.append(entry.strip())
    return result


def _looks_like_question(value):
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    if " " in text or "\t" in text or "\n" in text:
        return True
    if "?" in text or "？" in text:
        return True
    return any("一" <= char <= "鿿" for char in text)


def _pick_question(item):
    for key in QUESTION_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    qid = item.get("qid")
    if _looks_like_question(qid):
        return qid.strip()
    return None


def _pick_id(item, index):
    for key in ID_KEYS:
        value = item.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            text = str(value).strip()
            if text:
                return text
    qid = item.get("qid")
    if isinstance(qid, (str, int)) and not isinstance(qid, bool):
        text = str(qid).strip()
        if text and not _looks_like_question(text):
            return text
    return f"Q{index:03d}"


def _normalize_expected_status(value):
    if not isinstance(value, str):
        return None
    return STATUS_ALIASES.get(value.strip().lower())


def _normalize_must_cover(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    result = []
    for entry in value:
        if isinstance(entry, str):
            text = entry.strip()
        elif isinstance(entry, dict):
            text = _first_str(
                entry, ("fact", "text", "description", "requirement", "question")
            )
        else:
            text = None
        if text:
            result.append(text)
    return result


def _normalize_evidence_entry(entry):
    if not isinstance(entry, dict):
        return None
    page = entry.get("page")
    if page is None:
        page = entry.get("page_start")
    section = entry.get("section")
    if section is None:
        section = entry.get("section_id")
    if section is None:
        section = entry.get("anchor")
    locator_kind = _first_str(entry, ("locator_kind",))
    if locator_kind is None:
        if page is not None:
            locator_kind = "page"
        elif section is not None:
            locator_kind = "section"
    excerpt = entry.get("excerpt")
    return {
        "id": _first_str(entry, ("id", "evidence_id")),
        "document_id": _first_str(entry, ("document_id", "doc_id")),
        "document_version": _first_str(entry, ("document_version", "version")),
        "locator_kind": locator_kind,
        "page": page,
        "section": section,
        "chunk_ids": _string_list(entry.get("chunk_ids")),
        "locator": _first_str(entry, ("locator", "location")),
        "excerpt": excerpt if isinstance(excerpt, str) else None,
    }


def _evidence_payload(source, entries, groups=None, items=None):
    entries = [entry for entry in entries if entry]
    document_ids = sorted(
        {entry["document_id"] for entry in entries if entry["document_id"]}
    )
    chunk_ids = sorted(
        {chunk_id for entry in entries for chunk_id in entry["chunk_ids"]}
    )
    return {
        "source": source,
        "group_count": len(groups) if groups is not None else None,
        "alternative_count": len(entries),
        "groups": groups,
        "items": items,
        "document_ids": document_ids,
        "chunk_ids": chunk_ids,
    }


def _extract_evidence(item):
    groups = item.get("evidence_groups")
    if isinstance(groups, list):
        normalized_groups = []
        for group in groups:
            if isinstance(group, dict):
                alternatives = group.get("alternatives")
            else:
                alternatives = group
            if isinstance(alternatives, dict):
                alternatives = [alternatives]
            if not isinstance(alternatives, list):
                alternatives = []
            normalized_groups.append(
                [
                    entry
                    for entry in (
                        _normalize_evidence_entry(candidate)
                        for candidate in alternatives
                    )
                    if entry
                ]
            )
        entries = [entry for group in normalized_groups for entry in group]
        return _evidence_payload("evidence_groups", entries, groups=normalized_groups)
    evidence = item.get("evidence")
    if isinstance(evidence, list):
        entries = [
            entry
            for entry in (
                _normalize_evidence_entry(candidate) for candidate in evidence
            )
            if entry
        ]
        return _evidence_payload("evidence", entries, items=entries)
    if isinstance(evidence, dict):
        entries = [entry for entry in [_normalize_evidence_entry(evidence)] if entry]
        return _evidence_payload("evidence", entries, items=entries)
    return None


def _normalize_item(raw, index):
    if not isinstance(raw, dict):
        raise ValueError(f"question {index} is not an object")
    question = _pick_question(raw)
    if not question:
        raise ValueError(f"question {index} has no question/query field")
    qid = _pick_id(raw, index)
    category = (
        _first_str(raw, ("category", "group", "topic", "cluster", "type"))
        or "uncategorized"
    )
    expected_raw = _first_str(raw, EXPECTED_STATUS_KEYS)
    expected_norm = _normalize_expected_status(expected_raw)
    if expected_norm is None and isinstance(raw.get("answerable"), bool):
        expected_norm = "answered" if raw["answerable"] else "insufficient"
        expected_raw = expected_norm
    must_cover_value = raw.get("must_cover")
    if must_cover_value is None:
        must_cover_value = raw.get("required_facts")
    forbidden_value = raw.get("forbidden_claims")
    if forbidden_value is None:
        forbidden_value = raw.get("forbidden")
    gold_answer = _first_str(raw, GOLD_KEYS)
    must_cover = _normalize_must_cover(must_cover_value)
    forbidden_claims = _normalize_must_cover(forbidden_value)
    evidence = _extract_evidence(raw)
    expected = None
    if any((expected_raw, gold_answer, must_cover, forbidden_claims)) or (
        evidence is not None
    ):
        expected = {
            "status": expected_raw,
            "status_normalized": expected_norm,
            "gold_answer": gold_answer,
            "must_cover": must_cover,
            "forbidden_claims": forbidden_claims,
            "evidence": evidence,
        }
    scope = raw.get("scope")
    return {
        "id": qid,
        "category": category,
        "question": question,
        "expected": expected,
        # Optional retrieval scope chosen by the benchmark author. It carries
        # only document identity (never labels or answers) and lets a question
        # about a historical/pending revision run with that revision visible.
        "scope": scope if isinstance(scope, dict) else None,
    }


def _looks_like_question_item(item):
    return _pick_question(item) is not None


def _question_items(document):
    if isinstance(document, list):
        return document
    if isinstance(document, dict):
        for key in ("items", "queries", "cases", "questions"):
            value = document.get(key)
            if isinstance(value, list):
                return value
        if _looks_like_question_item(document):
            return [document]
        for value in document.values():
            if isinstance(value, list) and value:
                if all(isinstance(entry, dict) for entry in value):
                    if any(_looks_like_question_item(entry) for entry in value[:5]):
                        return value
    raise ValueError("question file has no item list")


def _unique_label(base, used):
    label = base or "questions"
    counter = 2
    while label in used:
        label = f"{base}#{counter}"
        counter += 1
    used.add(label)
    return label


def load_datasets(paths):
    datasets = []
    items = []
    used_labels = set()
    for path in paths:
        try:
            raw_bytes = path.read_bytes()
        except OSError as exc:
            raise ValueError(f"cannot read question file {path}: {exc}") from exc
        try:
            document = json.loads(raw_bytes)
        except json.JSONDecodeError as exc:
            raise ValueError(f"question file {path} is not valid JSON: {exc}") from exc
        raw_items = _question_items(document)
        label = _unique_label(path.stem, used_labels)
        metadata = {
            "label": label,
            "path": str(path),
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "schema_version": (
                document.get("schema_version") if isinstance(document, dict) else None
            ),
            "dataset_revision": (
                document.get("dataset_revision") if isinstance(document, dict) else None
            ),
            "purpose": (
                document.get("purpose") if isinstance(document, dict) else None
            ),
            "item_count": len(raw_items),
            "selected_count": 0,
        }
        seen = set()
        for index, raw in enumerate(raw_items):
            item = _normalize_item(raw, index)
            if item["id"] in seen:
                raise ValueError(f"duplicate question id {item['id']} in {path}")
            seen.add(item["id"])
            item["dataset"] = label
            item["dataset_index"] = index
            items.append(item)
        datasets.append(metadata)
    return datasets, items


def normalize_base_url(raw):
    parts = parse.urlsplit((raw or "").strip())
    if parts.scheme not in {"http", "https"}:
        raise ValueError("--base-url must use http or https")
    if not parts.hostname:
        raise ValueError("--base-url must include a host")
    if parts.username is not None or parts.password is not None:
        raise ValueError("--base-url must not include credentials")
    if parts.query or parts.fragment:
        raise ValueError("--base-url must not include a query or fragment")
    path = parts.path.rstrip("/")
    return parse.urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def answer_endpoint(base_url):
    return base_url.rstrip("/") + "/v1/rag/answer"


class _NoRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _build_opener():
    # ProxyHandler({}) ignores proxy environment variables for determinism.
    return request.build_opener(request.ProxyHandler({}), _NoRedirectHandler())


def _sanitize_message(value, base_url=None):
    text = str(value)
    if base_url:
        text = text.replace(base_url, "<base_url>")
    text = URL_PATTERN.sub("<url>", text)
    text = REDACT_PATTERN.sub(lambda match: match.group(1) + "=<redacted>", text)
    text = ABS_PATH_PATTERN.sub("<path>", text)
    text = " ".join(text.split())
    return text[:500]


def _safe_service_code(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    if SAFE_CODE_PATTERN.fullmatch(value):
        return value
    return _sanitize_message(value)[:200]


def _service_error_code(body):
    if not body:
        return None
    try:
        data = json.loads(body)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    detail = data.get("detail")
    if isinstance(detail, dict):
        code = _safe_service_code(detail.get("code"))
        if code:
            return code
    for key in ("code", "error_code"):
        code = _safe_service_code(data.get(key))
        if code:
            return code
    nested_error = data.get("error")
    if isinstance(nested_error, dict):
        code = _safe_service_code(nested_error.get("code"))
        if code:
            return code
    return None


def _is_timeout(exc):
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    reason = getattr(exc, "reason", None)
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return True
    return "timed out" in str(reason or exc).lower()


def _citation_locator(citation):
    kind = _first_str(citation, ("locator_kind",))
    page_start = citation.get("page_start")
    page_end = citation.get("page_end")
    position_label = _first_str(citation, ("position_label",))
    section = citation.get("section")
    if section is None:
        section = citation.get("section_index")
    if not kind:
        if page_start is not None:
            kind = "page"
        elif position_label or section is not None:
            kind = "section"
    present = False
    if kind in {"page", "pdf_page"}:
        present = page_start is not None
    elif kind in {"section", "heading", "markdown_section"}:
        present = bool(position_label) or section is not None or page_start is not None
    elif kind:
        present = bool(position_label) or section is not None or page_start is not None
    return {
        "kind": kind,
        "page_start": page_start,
        "page_end": page_end,
        "position_label": position_label,
        "section": section,
        "present": present,
    }


def _reference_overlap(item, citations):
    expected = (item.get("expected") or {}).get("evidence") or {}
    expected_documents = set(expected.get("document_ids") or [])
    expected_chunks = set(expected.get("chunk_ids") or [])
    cited_documents = {
        citation.get("document_id")
        for citation in citations
        if citation.get("document_id")
    }
    cited_chunks = {
        citation.get("chunk_id") for citation in citations if citation.get("chunk_id")
    }
    return {
        "expected_document_count": len(expected_documents),
        "expected_chunk_count": len(expected_chunks),
        "cited_expected_document_ids": sorted(expected_documents & cited_documents),
        "cited_expected_chunk_ids": sorted(expected_chunks & cited_chunks),
        "any_cited_expected_document": bool(expected_documents & cited_documents),
        "any_cited_expected_chunk": bool(expected_chunks & cited_chunks),
    }


def _new_case(item):
    return {
        "index": item["index"],
        "id": item["id"],
        "dataset": item["dataset"],
        "category": item["category"],
        "question": item["question"],
        "expected": item.get("expected"),
        "scope": item.get("scope"),
        "http_status": None,
        "response_status": None,
        "answer": None,
        "citation_count": None,
        "citations": [],
        "requirements_total": None,
        "requirements_supported": None,
        "requirements": [],
        "outcome": None,
        "success": False,
        "timed_out": False,
        "elapsed_seconds": None,
        "contract_errors": [],
        "error": None,
        "citations_missing_locator": 0,
        "citations_missing_document_id": 0,
        "citations_missing_chunk_id": 0,
        "citation_empty": None,
        "forbidden_document_ids": [],
        "reference_overlap": _reference_overlap(item, []),
        "response": None,
        "response_body_bytes": None,
    }


def _finalize_error(
    case,
    started,
    outcome,
    error_type,
    message,
    base_url,
    timeout,
    *,
    http_status=None,
    body=b"",
    redirect_not_followed=False,
):
    case["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    case["http_status"] = http_status
    case["outcome"] = outcome
    case["success"] = False
    case["timed_out"] = outcome == "timeout"
    case["response_body_bytes"] = len(body)
    case["error"] = {
        "type": error_type,
        "http_status": http_status,
        "service_code": _service_error_code(body),
        "message": _sanitize_message(message, base_url),
        "redirect_not_followed": redirect_not_followed,
    }
    if outcome == "timeout":
        case["error"]["timeout_seconds"] = timeout
    return case


def _analyze_citations(case, citations, item, forbidden_ids, errors):
    case["citation_count"] = len(citations)
    case["citation_empty"] = len(citations) == 0
    summaries = []
    for index, citation in enumerate(citations):
        if not isinstance(citation, dict):
            errors.append(f"citations[{index}] is not an object")
            continue
        document_id = citation.get("document_id")
        if isinstance(document_id, str) and document_id.strip():
            document_id = document_id.strip()
        else:
            document_id = None
            case["citations_missing_document_id"] += 1
        chunk_id = citation.get("chunk_id")
        if isinstance(chunk_id, str) and chunk_id.strip():
            chunk_id = chunk_id.strip()
        else:
            chunk_id = None
            case["citations_missing_chunk_id"] += 1
        locator = _citation_locator(citation)
        if not locator["present"]:
            case["citations_missing_locator"] += 1
        if document_id and document_id in forbidden_ids:
            case["forbidden_document_ids"].append(document_id)
        summaries.append(
            {
                "number": citation.get("number"),
                "source_id": citation.get("source_id"),
                "document_id": document_id,
                "document_version": citation.get("document_version"),
                "locator": locator,
                "chunk_id": chunk_id,
            }
        )
    case["citations"] = summaries
    case["forbidden_document_ids"] = sorted(set(case["forbidden_document_ids"]))
    case["reference_overlap"] = _reference_overlap(item, summaries)


def _analyze_requirements(case, requirements, errors):
    case["requirements_total"] = len(requirements)
    supported_count = 0
    summaries = []
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            errors.append(f"requirements[{index}] is not an object")
            continue
        supported = requirement.get("supported")
        if not isinstance(supported, bool):
            errors.append(f"requirements[{index}].supported is not a boolean")
            supported = None
        elif supported:
            supported_count += 1
        summaries.append(
            {
                "id": requirement.get("id"),
                "supported": supported,
                "coverage": requirement.get("coverage"),
            }
        )
    case["requirements_supported"] = supported_count
    case["requirements"] = summaries


def _analyze_response(case, data, item, forbidden_ids):
    errors = case["contract_errors"]
    if not isinstance(data, dict):
        errors.append("response body is not a JSON object")
        return
    status = data.get("status")
    if isinstance(status, str) and status in STATUS_VALUES:
        case["response_status"] = status
    else:
        errors.append(
            "response.status missing or not one of answered/partial/insufficient"
        )
    answer = data.get("answer")
    if isinstance(answer, str):
        case["answer"] = answer
    else:
        errors.append("response.answer missing or not a string")
    citations = data.get("citations")
    if isinstance(citations, list):
        _analyze_citations(case, citations, item, forbidden_ids, errors)
    else:
        errors.append("response.citations missing or not a list")
    requirements = data.get("requirements")
    if isinstance(requirements, list):
        _analyze_requirements(case, requirements, errors)
    else:
        errors.append("response.requirements missing or not a list")


def _run_case(item, endpoint, base_url, timeout, forbidden_ids):
    case = _new_case(item)
    body = {"query": item["question"]}
    if item.get("scope"):
        body["scope"] = item["scope"]
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "kb2-regression/1.0",
        },
    )
    started = time.perf_counter()
    body = b""
    try:
        with _build_opener().open(http_request, timeout=timeout) as response:
            http_status = response.status
            body = response.read()
    except error.HTTPError as exc:
        try:
            body = exc.read()
        except OSError:
            body = b""
        return _finalize_error(
            case,
            started,
            "http_error",
            type(exc).__name__,
            f"HTTP {exc.code}: {exc.msg}",
            base_url,
            timeout,
            http_status=exc.code,
            body=body,
            redirect_not_followed=300 <= exc.code < 400,
        )
    except (TimeoutError, socket.timeout) as exc:
        return _finalize_error(
            case,
            started,
            "timeout",
            type(exc).__name__,
            f"request timed out after {timeout:g}s",
            base_url,
            timeout,
        )
    except error.URLError as exc:
        if _is_timeout(exc):
            return _finalize_error(
                case,
                started,
                "timeout",
                type(exc).__name__,
                f"request timed out after {timeout:g}s",
                base_url,
                timeout,
            )
        return _finalize_error(
            case,
            started,
            "transport_error",
            type(exc).__name__,
            f"{exc.reason}",
            base_url,
            timeout,
        )
    except Exception as exc:
        if _is_timeout(exc):
            return _finalize_error(
                case,
                started,
                "timeout",
                type(exc).__name__,
                f"request timed out after {timeout:g}s",
                base_url,
                timeout,
            )
        return _finalize_error(
            case,
            started,
            "transport_error",
            type(exc).__name__,
            str(exc),
            base_url,
            timeout,
        )

    case["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    case["http_status"] = http_status
    case["response_body_bytes"] = len(body)
    if http_status != 200:
        return _finalize_error(
            case,
            started,
            "http_error",
            "HTTPError",
            f"HTTP {http_status}",
            base_url,
            timeout,
            http_status=http_status,
            body=body,
            redirect_not_followed=300 <= http_status < 400,
        )
    try:
        data = json.loads(body)
    except (TypeError, ValueError) as exc:
        case["outcome"] = "contract_error"
        case["contract_errors"].append(
            f"response body is not valid JSON: {_sanitize_message(exc, base_url)}"
        )
        case["error"] = {
            "type": "ContractError",
            "http_status": 200,
            "service_code": None,
            "message": "response body is not valid JSON",
            "redirect_not_followed": False,
        }
        return case
    case["response"] = data
    _analyze_response(case, data, item, forbidden_ids)
    if case["contract_errors"]:
        case["outcome"] = "contract_error"
        case["error"] = {
            "type": "ContractError",
            "http_status": 200,
            "service_code": None,
            "message": _sanitize_message(
                "; ".join(case["contract_errors"][:3]), base_url
            ),
            "redirect_not_followed": False,
        }
    else:
        case["outcome"] = "success"
        case["success"] = True
    return case


def _unexpected_case(item, exc, base_url):
    case = _new_case(item)
    case["elapsed_seconds"] = 0.0
    case["outcome"] = "transport_error"
    case["error"] = {
        "type": type(exc).__name__,
        "http_status": None,
        "service_code": None,
        "message": _sanitize_message(exc, base_url),
        "redirect_not_followed": False,
    }
    return case


def _percentile(sorted_values, pct):
    if not sorted_values:
        return None
    rank = (pct * len(sorted_values) + 99) // 100
    rank = max(1, min(rank, len(sorted_values)))
    return sorted_values[rank - 1]


def _latency_stats(values):
    cleaned = sorted(
        float(value)
        for value in values
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    )
    if not cleaned:
        return {
            "count": 0,
            "total": None,
            "average": None,
            "p50": None,
            "p95": None,
            "min": None,
            "max": None,
            "percentile_method": "nearest-rank",
        }
    total = sum(cleaned)
    return {
        "count": len(cleaned),
        "total": round(total, 6),
        "average": round(total / len(cleaned), 6),
        "p50": round(_percentile(cleaned, 50), 6),
        "p95": round(_percentile(cleaned, 95), 6),
        "min": round(cleaned[0], 6),
        "max": round(cleaned[-1], 6),
        "percentile_method": "nearest-rank",
    }


def _status_distribution(cases):
    counts = Counter(
        case.get("response_status")
        for case in cases
        if case.get("response_status") in STATUS_VALUES
    )
    return {status: counts.get(status, 0) for status in STATUS_VALUES}


def _summarize_cases(cases):
    success = [case for case in cases if case.get("outcome") == "success"]
    outcomes = Counter(case.get("outcome") or "pending" for case in cases)
    return {
        "total": len(cases),
        "success": len(success),
        "failures": len(cases) - len(success),
        "http_errors": outcomes.get("http_error", 0),
        "timeouts": outcomes.get("timeout", 0),
        "contract_errors": outcomes.get("contract_error", 0),
        "transport_errors": outcomes.get("transport_error", 0),
        "outcome_distribution": dict(sorted(outcomes.items())),
        "status_distribution": _status_distribution(cases),
        "latency_seconds": _latency_stats(
            [case.get("elapsed_seconds") for case in cases]
        ),
        "latency_seconds_successful": _latency_stats(
            [case.get("elapsed_seconds") for case in success]
        ),
        "citation_count": sum(case.get("citation_count") or 0 for case in cases),
        "cases_with_empty_citations": sum(
            1 for case in cases if case.get("citation_empty") is True
        ),
        "citations_missing_locator": sum(
            case.get("citations_missing_locator") or 0 for case in cases
        ),
        "citations_missing_document_id": sum(
            case.get("citations_missing_document_id") or 0 for case in cases
        ),
        "citations_missing_chunk_id": sum(
            case.get("citations_missing_chunk_id") or 0 for case in cases
        ),
        "cases_with_forbidden_document_id": sum(
            1 for case in cases if case.get("forbidden_document_ids")
        ),
    }


def _expected_summary(cases):
    distribution = Counter()
    matches = 0
    comparable = 0
    for case in cases:
        expected = case.get("expected") or {}
        expected_status = expected.get("status_normalized")
        distribution[expected_status or "unavailable"] += 1
        actual_status = case.get("response_status")
        if expected_status in STATUS_VALUES and actual_status in STATUS_VALUES:
            comparable += 1
            if expected_status == actual_status:
                matches += 1
    return {
        "expected_status_distribution": dict(sorted(distribution.items())),
        "comparable_cases": comparable,
        "matches": matches,
        "note": "interface diagnostic only; not semantic accuracy",
    }


def _reference_summary(cases):
    with_evidence = [
        case
        for case in cases
        if (case.get("reference_overlap") or {}).get("expected_document_count")
        or (case.get("reference_overlap") or {}).get("expected_chunk_count")
    ]
    return {
        "cases_with_expected_evidence": len(with_evidence),
        "cases_citing_expected_document": sum(
            1
            for case in with_evidence
            if case["reference_overlap"]["any_cited_expected_document"]
        ),
        "cases_citing_expected_chunk": sum(
            1
            for case in with_evidence
            if case["reference_overlap"]["any_cited_expected_chunk"]
        ),
        "note": (
            "document/chunk ID overlap only; not evidence coverage or semantic "
            "correctness"
        ),
    }


def _forbidden_hits(cases, forbidden_ids):
    hits = []
    for case in cases:
        for citation in case.get("citations") or []:
            document_id = citation.get("document_id")
            if document_id and document_id in forbidden_ids:
                hits.append(
                    {
                        "case_id": case["id"],
                        "dataset": case["dataset"],
                        "citation_number": citation.get("number"),
                        "document_id": document_id,
                    }
                )
    return hits


def _case_ids(cases, predicate):
    return [case["id"] for case in cases if predicate(case)]


def build_report(cases, datasets, metadata, *, final):
    ordered = sorted(cases, key=lambda case: case.get("index", 0))
    totals = _summarize_cases(ordered)
    forbidden_ids = set(metadata["forbidden_ids"])
    forbidden_hits = _forbidden_hits(ordered, forbidden_ids)
    acceptance_passed = totals["failures"] == 0 and not forbidden_hits
    report = {
        "schema_version": SCHEMA_VERSION,
        "tool": "scripts/kb2_run_regression.py",
        "generated_at": _utc_now(),
        "started_at": metadata["started_at"],
        "finished_at": _utc_now() if final else None,
        "duration_seconds": (
            round(time.perf_counter() - metadata["started_monotonic"], 6)
            if final
            else None
        ),
        "run_status": (
            ("passed" if acceptance_passed else "failed") if final else "running"
        ),
        "exit_code": (0 if acceptance_passed else 1) if final else None,
        "acceptance": {
            "passed": acceptance_passed if final else None,
            "request_failures": totals["failures"],
            "forbidden_document_id_hits": len(forbidden_hits),
        },
        "base_url": metadata["base_url"],
        "endpoint": metadata["endpoint"],
        "timeout_seconds": metadata["timeout"],
        "concurrency": metadata["concurrency"],
        "limit": metadata["limit"],
        "question_paths": metadata["question_paths"],
        "datasets": datasets,
        "forbidden_document_ids": sorted(forbidden_ids),
        "evaluation_scope": (
            "engineering regression only; HTTP, contract, latency and citation "
            "statistics are not semantic accuracy; 未做人工语义评分"
        ),
        "human_semantic_review": "未做人工语义评分",
        "security": {
            "follow_redirects": False,
            "proxy_environment_disabled": True,
            "credentials_in_base_url": False,
            "labels_sent_to_service": False,
            "request_body_fields": ["query", "scope(optional)"],
            "output_file_mode": "0600",
        },
        "totals": totals,
        "status_distribution": totals["status_distribution"],
        "http_status_distribution": dict(
            sorted(
                Counter(
                    str(case["http_status"])
                    for case in ordered
                    if isinstance(case.get("http_status"), int)
                ).items()
            )
        ),
        "latency_seconds": totals["latency_seconds"],
        "latency_seconds_successful": totals["latency_seconds_successful"],
        "citation_checks": {
            "total_citations": totals["citation_count"],
            "cases_with_empty_citations": totals["cases_with_empty_citations"],
            "empty_citation_case_ids": _case_ids(
                ordered, lambda case: case.get("citation_empty") is True
            ),
            "citations_missing_locator": totals["citations_missing_locator"],
            "missing_locator_case_ids": _case_ids(
                ordered, lambda case: (case.get("citations_missing_locator") or 0) > 0
            ),
            "citations_missing_document_id": totals["citations_missing_document_id"],
            "citations_missing_chunk_id": totals["citations_missing_chunk_id"],
            "forbidden_document_ids": sorted(forbidden_ids),
            "forbidden_document_id_hits": forbidden_hits,
        },
        "expected_status": _expected_summary(ordered),
        "reference_citation_overlap": _reference_summary(ordered),
        "by_dataset": {
            dataset["label"]: _summarize_cases(
                [case for case in ordered if case.get("dataset") == dataset["label"]]
            )
            for dataset in datasets
        },
        "by_category": {
            category: _summarize_cases(
                [case for case in ordered if case.get("category") == category]
            )
            for category in sorted({case.get("category") for case in ordered})
        },
        "by_dataset_category": {
            dataset["label"]: {
                category: _summarize_cases(
                    [
                        case
                        for case in ordered
                        if case.get("dataset") == dataset["label"]
                        and case.get("category") == category
                    ]
                )
                for category in sorted(
                    {
                        case.get("category")
                        for case in ordered
                        if case.get("dataset") == dataset["label"]
                    }
                )
            }
            for dataset in datasets
        },
        "cases": ordered,
    }
    return report


def _format_seconds(value):
    if value is None:
        return "-"
    return f"{value:.3f}"


def _format_percent(count, total):
    if not total:
        return "-"
    return f"{count / total * 100:.1f}%"


def _md(value):
    if value is None:
        return "-"
    text = str(value).replace("\\", "\\\\").replace("|", "\\|")
    text = " ".join(text.split())
    return text[:160]


def _case_result_label(case):
    outcome = case.get("outcome") or "pending"
    if outcome == "success":
        return "success"
    error = case.get("error") or {}
    if outcome == "http_error":
        label = f"http_error {case.get('http_status')}"
        if error.get("service_code"):
            label += f" ({error['service_code']})"
        if error.get("redirect_not_followed"):
            label += " [redirect not followed]"
        return label
    if outcome == "timeout":
        return "timeout"
    if outcome == "contract_error":
        message = (case.get("contract_errors") or ["contract violation"])[0]
        return f"contract_error: {message}"
    return f"{outcome}: {error.get('message') or '-'}"


def render_markdown(report):
    lines = []
    totals = report["totals"]
    latency = report["latency_seconds"]
    successful_latency = report["latency_seconds_successful"]
    status = report["run_status"]
    conclusion = {"passed": "PASS", "failed": "FAIL"}.get(status, "RUNNING")

    lines.extend(
        [
            "# KB2 RAG 回归报告",
            "",
            f"- 生成时间（UTC）：{report['generated_at']}",
            f"- 目标服务：`{report['base_url']}`",
            f"- API：`{report['endpoint']}`",
        ]
    )
    for dataset in report["datasets"]:
        schema = dataset.get("schema_version") or "-"
        lines.append(
            f"- 题集 `{dataset['label']}`：`{dataset['path']}`"
            f"（schema `{schema}`，{dataset['selected_count']}/"
            f"{dataset['item_count']} 题）"
        )
    lines.extend(
        [
            f"- 运行参数：timeout={report['timeout_seconds']:g}s，"
            f"concurrency={report['concurrency']}，limit={report['limit']}",
            f"- 结论：**{conclusion}**",
            f"- 验收判定：请求失败 {report['acceptance']['request_failures']}，"
            f"受限 document_id 命中 "
            f"{report['acceptance']['forbidden_document_id_hits']}",
            "",
            "> 本报告只做工程回归统计（HTTP、响应契约、延迟、引用定位和受限文档检查），"
            "未做人工语义评分，不声称语义正确率。",
            "",
            "## 1. 汇总",
            "",
            "| 指标 | 数值 |",
            "| --- | ---: |",
            f"| 总题数 | {totals['total']} |",
            f"| 成功 | {totals['success']} |",
            f"| 请求失败 | {totals['failures']} |",
            f"| HTTP 错误 | {totals['http_errors']} |",
            f"| 超时 | {totals['timeouts']} |",
            f"| 契约错误 | {totals['contract_errors']} |",
            f"| 传输错误 | {totals['transport_errors']} |",
            f"| 平均延迟 | {_format_seconds(latency['average'])} s |",
            f"| P50 延迟 | {_format_seconds(latency['p50'])} s |",
            f"| P95 延迟 | {_format_seconds(latency['p95'])} s |",
            f"| 引用为空题数 | {totals['cases_with_empty_citations']} |",
            f"| 定位缺失引用数 | {totals['citations_missing_locator']} |",
            f"| 受限 document_id 命中 | "
            f"{len(report['citation_checks']['forbidden_document_id_hits'])} |",
            "",
            "## 2. 响应状态分布",
            "",
            "| status | 数量 | 占比 |",
            "| --- | ---: | ---: |",
        ]
    )
    for status_value in STATUS_VALUES:
        count = report["status_distribution"].get(status_value, 0)
        lines.append(
            f"| {status_value} | {count} | {_format_percent(count, totals['total'])} |"
        )
    expected = report["expected_status"]
    lines.extend(
        [
            "",
            "期望状态分布（仅供接口诊断，不是语义评分）："
            + json.dumps(expected["expected_status_distribution"], ensure_ascii=False),
            "",
            "## 3. 延迟",
            "",
            "| 范围 | n | 平均(s) | P50(s) | P95(s) | 最大(s) |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for label, values in (
        ("全部请求", latency),
        ("成功请求", successful_latency),
    ):
        lines.append(
            f"| {label} | {values['count']} | "
            f"{_format_seconds(values['average'])} | "
            f"{_format_seconds(values['p50'])} | "
            f"{_format_seconds(values['p95'])} | "
            f"{_format_seconds(values['max'])} |"
        )
    checks = report["citation_checks"]
    lines.extend(
        [
            "",
            "## 4. 引用检查",
            "",
            "| 检查 | 数量 |",
            "| --- | ---: |",
            f"| 总引用数 | {checks['total_citations']} |",
            f"| 引用为空的题 | {checks['cases_with_empty_citations']} |",
            f"| 缺少定位的引用 | {checks['citations_missing_locator']} |",
            f"| 缺少 document_id 的引用 | {checks['citations_missing_document_id']} |",
            f"| 缺少 chunk_id 的引用 | {checks['citations_missing_chunk_id']} |",
            f"| 受限 document_id 命中 | {len(checks['forbidden_document_id_hits'])} |",
        ]
    )
    if checks["forbidden_document_id_hits"]:
        lines.extend(["", "受限 document_id 命中清单：", ""])
        for hit in checks["forbidden_document_id_hits"]:
            lines.append(
                f"- `{hit['case_id']}` citation {hit['citation_number']}: "
                f"`{hit['document_id']}`"
            )
    if checks["empty_citation_case_ids"]:
        lines.extend(
            [
                "",
                "引用为空的题："
                + ", ".join(
                    f"`{case_id}`" for case_id in checks["empty_citation_case_ids"]
                ),
            ]
        )
    if checks["missing_locator_case_ids"]:
        lines.extend(
            [
                "",
                "存在定位缺失引用的题："
                + ", ".join(
                    f"`{case_id}`" for case_id in checks["missing_locator_case_ids"]
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## 5. 按题集",
            "",
            "| 题集 | 题数 | 成功 | HTTP 错误 | 超时 | 契约错误 | "
            "answered | partial | insufficient | P50(s) | P95(s) |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: "
            "| ---: | ---: |",
        ]
    )
    for dataset in report["datasets"]:
        values = report["by_dataset"].get(dataset["label"], {})
        statuses = values.get("status_distribution", {})
        latency_values = values.get("latency_seconds", {})
        lines.append(
            f"| {_md(dataset['label'])} | {values.get('total', 0)} | "
            f"{values.get('success', 0)} | {values.get('http_errors', 0)} | "
            f"{values.get('timeouts', 0)} | "
            f"{values.get('contract_errors', 0)} | "
            f"{statuses.get('answered', 0)} | {statuses.get('partial', 0)} | "
            f"{statuses.get('insufficient', 0)} | "
            f"{_format_seconds(latency_values.get('p50'))} | "
            f"{_format_seconds(latency_values.get('p95'))} |"
        )

    lines.extend(
        [
            "",
            "## 6. 按类别",
            "",
            "| 类别 | 题数 | 成功 | HTTP 错误 | 超时 | 契约错误 | "
            "answered | partial | insufficient | P50(s) | P95(s) |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: "
            "| ---: | ---: |",
        ]
    )
    for category, values in report["by_category"].items():
        statuses = values.get("status_distribution", {})
        latency_values = values.get("latency_seconds", {})
        lines.append(
            f"| {_md(category)} | {values.get('total', 0)} | "
            f"{values.get('success', 0)} | {values.get('http_errors', 0)} | "
            f"{values.get('timeouts', 0)} | "
            f"{values.get('contract_errors', 0)} | "
            f"{statuses.get('answered', 0)} | {statuses.get('partial', 0)} | "
            f"{statuses.get('insufficient', 0)} | "
            f"{_format_seconds(latency_values.get('p50'))} | "
            f"{_format_seconds(latency_values.get('p95'))} |"
        )

    lines.extend(
        [
            "",
            "## 7. 逐题结果",
            "",
            "| # | 题集 | ID | 类别 | expected | HTTP | 耗时(s) | status | "
            "引用 | requirements | 结果 |",
            "| ---: | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |",
        ]
    )
    for case in report["cases"]:
        expected_status = (case.get("expected") or {}).get("status_normalized")
        requirements = "-"
        if case.get("requirements_total") is not None:
            requirements = (
                f"{case.get('requirements_supported', 0)}/{case['requirements_total']}"
            )
        lines.append(
            f"| {case['index'] + 1} | {_md(case['dataset'])} | "
            f"{_md(case['id'])} | {_md(case['category'])} | "
            f"{_md(expected_status)} | {_md(case.get('http_status'))} | "
            f"{_format_seconds(case.get('elapsed_seconds'))} | "
            f"{_md(case.get('response_status'))} | "
            f"{_md(case.get('citation_count'))} | {requirements} | "
            f"{_md(_case_result_label(case))} |"
        )

    lines.extend(
        [
            "",
            "## 8. 说明",
            "",
            '- 请求体为 `{"query": ..., "scope": ...}`（scope 可选，只含文档身份）；题集标签、期望答案、must_cover '
            "和证据均未发送给服务。",
            "- 默认不跟随重定向，禁用环境代理，不发送任何凭据。",
            "- JSON 和 Markdown 输出文件权限为 `0600`。",
            "- 状态分布和 HTTP/契约统计只说明接口行为，不是回答正确率。",
            "- 未做人工语义评分；需要人工按题集 gold_answer 与引用原文复核。",
            "",
        ]
    )
    return "\n".join(lines)


def _atomic_write_private(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        os.fchmod(fd, 0o600)
        handle = os.fdopen(fd, "w", encoding="utf-8", newline="\n")
        fd = None
        try:
            with handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            if fd is not None:
                os.close(fd)
        os.replace(temporary_name, path)
        os.chmod(path, 0o600)
    except BaseException:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


class RunState:
    def __init__(self, output, markdown, datasets, metadata):
        self.output = Path(output)
        self.markdown = Path(markdown)
        self.datasets = datasets
        self.metadata = metadata
        self.cases = []
        self._lock = threading.Lock()

    def add(self, case):
        with self._lock:
            self.cases.append(case)
            self._persist_locked(final=False)

    def set_cases(self, cases):
        with self._lock:
            self.cases = list(cases)

    def persist(self, final):
        with self._lock:
            return self._persist_locked(final=final)

    def _persist_locked(self, *, final):
        report = build_report(self.cases, self.datasets, self.metadata, final=final)
        payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        _atomic_write_private(self.output, payload)
        _atomic_write_private(self.markdown, render_markdown(report))
        return report


def run_cases(
    items, endpoint, base_url, timeout, concurrency, forbidden_ids, on_complete
):
    results = [None] * len(items)
    lock = threading.Lock()
    cursor = {"next": 0}

    def execute(index):
        item = items[index]
        try:
            case = _run_case(item, endpoint, base_url, timeout, forbidden_ids)
        except Exception as exc:  # never lose the rest of the batch
            case = _unexpected_case(item, exc, base_url)
        with lock:
            results[index] = case
        on_complete(case)

    def worker():
        while True:
            with lock:
                index = cursor["next"]
                if index >= len(items):
                    return
                cursor["next"] = index + 1
            execute(index)

    if concurrency == 1:
        for index in range(len(items)):
            execute(index)
        return results
    threads = [
        threading.Thread(target=worker, name=f"kb2-worker-{index}", daemon=True)
        for index in range(min(concurrency, len(items)))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        required=True,
        help="RAG service base URL (http/https; credentials are rejected)",
    )
    parser.add_argument(
        "--questions",
        action="append",
        metavar="PATH",
        help="question JSON; repeat for multiple sets (default: validity-pilot-v2)",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--markdown",
        type=Path,
        help="Markdown summary path (default: --output with .md suffix)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="socket timeout for each request in seconds (default: 180)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="parallel request workers, 1-16 (default: 1)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="maximum questions to run after loading; 0 = all (default: 0)",
    )
    parser.add_argument(
        "--forbidden-document-id",
        action="append",
        default=[],
        metavar="ID",
        help="restricted document_id expected never to appear in citations",
    )
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")
    if not 1 <= args.concurrency <= 16:
        parser.error("--concurrency must be between 1 and 16")
    if args.limit < 0:
        parser.error("--limit must be >= 0")
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        base_url = normalize_base_url(args.base_url)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    question_paths = [
        Path(path) for path in (args.questions or [str(DEFAULT_QUESTIONS)])
    ]
    try:
        datasets, items = load_datasets(question_paths)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(
            f"error: cannot load questions: {_sanitize_message(exc)}",
            file=sys.stderr,
        )
        return 2
    if args.limit:
        items = items[: args.limit]
    if not items:
        print("error: no questions selected", file=sys.stderr)
        return 2
    for index, item in enumerate(items):
        item["index"] = index
    selected = Counter(item["dataset"] for item in items)
    for dataset in datasets:
        dataset["selected_count"] = selected.get(dataset["label"], 0)

    endpoint = answer_endpoint(base_url)
    markdown = args.markdown or args.output.with_suffix(".md")
    metadata = {
        "started_at": _utc_now(),
        "started_monotonic": time.perf_counter(),
        "base_url": base_url,
        "endpoint": endpoint,
        "timeout": args.timeout,
        "concurrency": args.concurrency,
        "limit": args.limit,
        "question_paths": [str(path) for path in question_paths],
        "forbidden_ids": sorted(set(args.forbidden_document_id)),
    }
    state = RunState(args.output, markdown, datasets, metadata)
    try:
        state.persist(final=False)
    except OSError as exc:
        print(f"error: cannot write output: {exc}", file=sys.stderr)
        return 2

    try:
        results = run_cases(
            items,
            endpoint,
            base_url,
            args.timeout,
            args.concurrency,
            metadata["forbidden_ids"],
            state.add,
        )
    except KeyboardInterrupt:
        state.persist(final=False)
        print("interrupted", file=sys.stderr)
        return 130

    completed = []
    for index, item in enumerate(items):
        case = results[index]
        if case is None:
            case = _unexpected_case(
                item, RuntimeError("worker did not return a result"), base_url
            )
        completed.append(case)
    state.set_cases(completed)
    try:
        report = state.persist(final=True)
    except OSError as exc:
        print(f"error: cannot write final output: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "run_status": report["run_status"],
                "output": str(args.output),
                "markdown": str(markdown),
                "totals": {
                    key: report["totals"][key]
                    for key in (
                        "total",
                        "success",
                        "http_errors",
                        "timeouts",
                        "contract_errors",
                        "transport_errors",
                        "failures",
                    )
                },
                "status_distribution": report["status_distribution"],
                "latency_seconds": report["latency_seconds"],
                "acceptance": report["acceptance"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["run_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
