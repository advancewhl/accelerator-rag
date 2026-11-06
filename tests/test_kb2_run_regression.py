"""Tests for the standalone KB2 regression runner."""

import json
from pathlib import Path
import stat
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "kb2_run_regression.py"


def _citation(document_id="doc-a", chunk_id="doc-a:chunk-1", **overrides):
    citation = {
        "number": 1,
        "source_id": "S1",
        "document_id": document_id,
        "document_version": "v1",
        "locator_kind": "page",
        "page_start": 3,
        "page_end": 3,
        "chunk_id": chunk_id,
        "quote": "quoted text",
        "document_url": f"/v1/rag/documents/{document_id}",
    }
    citation.update(overrides)
    return citation


def _payload(status="answered", citations=None, requirements=None):
    if citations is None:
        citations = [_citation()]
    if requirements is None:
        requirements = [
            {
                "id": "R1",
                "text": "question",
                "supported": True,
                "span_ids": ["S1.1"],
                "coverage": "complete",
                "reason": "",
                "missing": "",
            }
        ]
    return {
        "status": status,
        "answer": "test answer [1]",
        "requirements": requirements,
        "citations": citations,
        "latency": {"total_seconds": 0.01},
        "request_id": "test-request",
    }


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send(self, status, body, content_type="application/json"):
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
        with self.server.lock:
            self.server.requests.append({"path": self.path, "payload": payload})
        query = payload.get("query", "")
        if "timeout" in query:
            time.sleep(1.0)
            self._send(200, json.dumps(_payload()).encode("utf-8"))
        elif "http-500" in query:
            body = json.dumps({"detail": {"code": "TEST_HTTP_FAIL"}})
            self._send(500, body.encode("utf-8"))
        elif "bad-json" in query:
            self._send(200, b"not-json", content_type="text/plain")
        elif "redirect" in query:
            try:
                self.send_response(302)
                self.send_header("Location", "/moved")
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif "forbidden" in query:
            citation = {
                "number": 1,
                "source_id": "S1",
                "document_id": "doc-secret",
                "chunk_id": "doc-secret:chunk-1",
                "quote": "secret quote",
            }
            body = json.dumps(_payload(citations=[citation]))
            self._send(200, body.encode("utf-8"))
        elif "empty" in query:
            requirements = [
                {
                    "id": "R1",
                    "text": "question",
                    "supported": False,
                    "span_ids": [],
                    "coverage": "none",
                    "reason": "",
                    "missing": "no evidence",
                }
            ]
            body = json.dumps(
                _payload(
                    status="insufficient",
                    citations=[],
                    requirements=requirements,
                )
            )
            self._send(200, body.encode("utf-8"))
        else:
            self._send(200, json.dumps(_payload()).encode("utf-8"))


@pytest.fixture
def rag_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads = True
    server.requests = []
    server.lock = threading.Lock()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _write_questions(path, items, schema="test-v1"):
    path.write_text(
        json.dumps({"schema_version": schema, "items": items}, ensure_ascii=False),
        encoding="utf-8",
    )


def _item(
    item_id,
    query,
    *,
    category="alpha",
    expected_status="answered",
    document_id="doc-a",
    chunk_id=None,
):
    return {
        "id": item_id,
        "category": category,
        "query": query,
        "expected_status": expected_status,
        "gold_answer": f"gold for {item_id}",
        "must_cover": [f"fact {item_id}"],
        "evidence_groups": [
            {
                "alternatives": [
                    {
                        "document_id": document_id,
                        "document_version": "v1",
                        "locator_kind": "page",
                        "page": 3,
                        "chunk_ids": [chunk_id or f"{document_id}:chunk-1"],
                        "excerpt": f"excerpt {item_id}",
                    }
                ]
            }
        ],
    }


def _run(server, questions, tmp_path, *extra, timeout="5", output_name="report"):
    output = tmp_path / "out" / f"{output_name}.json"
    markdown = tmp_path / "out" / f"{output_name}.md"
    command = [
        sys.executable,
        str(SCRIPT),
        "--base-url",
        f"http://127.0.0.1:{server.server_address[1]}",
        "--questions",
        str(questions),
        "--output",
        str(output),
        "--markdown",
        str(markdown),
        "--timeout",
        timeout,
        *extra,
    ]
    process = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return process, output, markdown


def _by_id(report):
    return {case["id"]: case for case in report["cases"]}


def test_collects_outcomes_citations_and_markdown(rag_server, tmp_path):
    questions = tmp_path / "main.json"
    _write_questions(
        questions,
        [
            _item("ok-1", "plain ok", category="alpha"),
            _item(
                "forbidden-1",
                "forbidden document",
                category="alpha",
            ),
            _item("http-500", "http-500 request", category="beta"),
            _item("bad-json", "bad-json request", category="beta"),
            _item(
                "empty-1",
                "empty citations",
                category="alpha",
                expected_status="insufficient",
            ),
            _item("redirect-1", "redirect request", category="beta"),
        ],
    )

    process, output, markdown = _run(
        rag_server,
        questions,
        tmp_path,
        "--concurrency",
        "2",
        "--limit",
        "0",
        "--forbidden-document-id",
        "doc-secret",
    )

    assert process.returncode == 1, process.stderr
    assert output.exists() and markdown.exists()
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert stat.S_IMODE(markdown.stat().st_mode) == 0o600
    report = json.loads(output.read_text(encoding="utf-8"))

    assert report["schema_version"] == "kb2-regression-v1"
    assert report["run_status"] == "failed"
    assert report["human_semantic_review"] == "未做人工语义评分"
    assert report["security"]["follow_redirects"] is False
    assert report["security"]["request_body_fields"] == ["query", "scope(optional)"]
    assert [case["id"] for case in report["cases"]] == [
        "ok-1",
        "forbidden-1",
        "http-500",
        "bad-json",
        "empty-1",
        "redirect-1",
    ]

    totals = report["totals"]
    assert totals["total"] == 6
    assert totals["success"] == 3
    assert totals["http_errors"] == 2
    assert totals["timeouts"] == 0
    assert totals["contract_errors"] == 1
    assert totals["transport_errors"] == 0
    assert totals["failures"] == 3
    assert report["status_distribution"] == {
        "answered": 2,
        "partial": 0,
        "insufficient": 1,
    }
    assert report["http_status_distribution"] == {"200": 4, "302": 1, "500": 1}

    latency = report["latency_seconds"]
    assert latency["count"] == 6
    assert latency["average"] > 0
    assert latency["p50"] is not None
    assert latency["p95"] >= latency["p50"]
    assert latency["max"] >= latency["p95"]

    cases = _by_id(report)
    ok = cases["ok-1"]
    assert ok["outcome"] == "success"
    assert ok["http_status"] == 200
    assert ok["response_status"] == "answered"
    assert ok["citation_count"] == 1
    assert ok["citations"][0]["document_id"] == "doc-a"
    assert ok["citations"][0]["chunk_id"] == "doc-a:chunk-1"
    assert ok["citations"][0]["locator"]["kind"] == "page"
    assert ok["citations"][0]["locator"]["page_start"] == 3
    assert ok["requirements_supported"] == 1
    assert ok["requirements_total"] == 1

    forbidden = cases["forbidden-1"]
    assert forbidden["outcome"] == "success"
    assert forbidden["forbidden_document_ids"] == ["doc-secret"]
    assert forbidden["citations_missing_locator"] == 1
    assert forbidden["citations_missing_document_id"] == 0

    http_error = cases["http-500"]
    assert http_error["http_status"] == 500
    assert http_error["outcome"] == "http_error"
    assert http_error["error"]["service_code"] == "TEST_HTTP_FAIL"

    contract_error = cases["bad-json"]
    assert contract_error["http_status"] == 200
    assert contract_error["outcome"] == "contract_error"
    assert contract_error["contract_errors"]

    empty = cases["empty-1"]
    assert empty["outcome"] == "success"
    assert empty["citation_empty"] is True
    assert empty["citation_count"] == 0
    assert empty["requirements_supported"] == 0

    redirect = cases["redirect-1"]
    assert redirect["http_status"] == 302
    assert redirect["outcome"] == "http_error"
    assert redirect["error"]["redirect_not_followed"] is True

    checks = report["citation_checks"]
    assert checks["total_citations"] == 2
    assert checks["cases_with_empty_citations"] == 1
    assert checks["empty_citation_case_ids"] == ["empty-1"]
    assert checks["citations_missing_locator"] == 1
    assert checks["missing_locator_case_ids"] == ["forbidden-1"]
    assert len(checks["forbidden_document_id_hits"]) == 1
    assert checks["forbidden_document_id_hits"][0]["document_id"] == "doc-secret"

    assert report["by_category"]["alpha"]["total"] == 3
    assert report["by_category"]["beta"]["total"] == 3
    assert report["by_dataset"]["main"]["total"] == 6
    assert report["by_dataset_category"]["main"]["alpha"]["total"] == 3
    assert report["expected_status"]["comparable_cases"] == 3
    assert report["expected_status"]["matches"] == 3
    assert report["reference_citation_overlap"]["cases_with_expected_evidence"] == 6
    assert report["reference_citation_overlap"]["cases_citing_expected_document"] == 1
    assert report["reference_citation_overlap"]["cases_citing_expected_chunk"] == 1

    assert len(rag_server.requests) == 6
    assert all(set(request["payload"]) == {"query"} for request in rag_server.requests)
    assert all(
        "gold for" not in json.dumps(request["payload"])
        for request in rag_server.requests
    )

    markdown_text = markdown.read_text(encoding="utf-8")
    assert "未做人工语义评分" in markdown_text
    assert "不声称语义正确率" in markdown_text
    assert "逐题结果" in markdown_text
    assert "P95" in markdown_text
    assert "| 总题数 | 6 |" in markdown_text
    assert "doc-secret" in markdown_text


def test_forbidden_document_id_fails_acceptance(rag_server, tmp_path):
    questions = tmp_path / "forbidden.json"
    _write_questions(questions, [_item("forbidden-1", "forbidden document")])

    process, output, markdown = _run(
        rag_server,
        questions,
        tmp_path,
        "--forbidden-document-id",
        "doc-secret",
    )

    assert process.returncode == 1, process.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["totals"]["success"] == 1
    assert report["totals"]["failures"] == 0
    assert report["acceptance"] == {
        "passed": False,
        "request_failures": 0,
        "forbidden_document_id_hits": 1,
    }
    assert report["run_status"] == "failed"
    assert report["exit_code"] == 1
    assert "**FAIL**" in markdown.read_text(encoding="utf-8")


def test_limit_and_legacy_question_fields(rag_server, tmp_path):
    questions = tmp_path / "legacy.json"
    _write_questions(
        questions,
        [
            {
                "id": "S1-X-001",
                "category": "task1_parameter_condition",
                "question": "legacy question one",
                "expected_status": "answerable",
                "gold_answer": "legacy gold answer",
                "must_cover": [{"id": "M1", "fact": "fact one", "type": "text"}],
                "evidence": [
                    {
                        "id": "E1",
                        "document_id": "doc-a",
                        "page": 3,
                        "excerpt": "legacy excerpt",
                    }
                ],
            },
            {
                "id": "S1-X-002",
                "category": "task1_parameter_condition",
                "question": "legacy question two",
                "expected_status": "partial",
                "gold_answer": "legacy gold answer two",
            },
        ],
        schema="prab-seed-questions-v1",
    )

    process, output, markdown = _run(rag_server, questions, tmp_path, "--limit", "1")

    assert process.returncode == 0, process.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["totals"]["total"] == 1
    assert report["datasets"][0]["item_count"] == 2
    assert report["datasets"][0]["selected_count"] == 1
    case = report["cases"][0]
    assert case["id"] == "S1-X-001"
    assert case["question"] == "legacy question one"
    assert case["expected"]["status"] == "answerable"
    assert case["expected"]["status_normalized"] == "answered"
    assert case["expected"]["must_cover"] == ["fact one"]
    assert case["expected"]["evidence"]["document_ids"] == ["doc-a"]
    assert len(rag_server.requests) == 1
    assert set(rag_server.requests[0]["payload"]) == {"query"}

    qid_questions = tmp_path / "qid.json"
    _write_questions(
        qid_questions,
        [
            {
                "qid": "What is the qid-based question?",
                "category": "qid_category",
                "expected_status": "answered",
            }
        ],
        schema="qid-v1",
    )
    process, output, _ = _run(
        rag_server,
        qid_questions,
        tmp_path,
        output_name="qid-report",
    )
    assert process.returncode == 0, process.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    case = report["cases"][0]
    assert case["id"] == "Q000"
    assert case["question"] == "What is the qid-based question?"


def test_timeout_does_not_abort_batch(rag_server, tmp_path):
    questions = tmp_path / "timeout.json"
    _write_questions(
        questions,
        [
            _item("slow-1", "please timeout now"),
            _item("fast-1", "plain ok"),
        ],
    )

    process, output, markdown = _run(
        rag_server, questions, tmp_path, "--timeout", "0.3"
    )

    assert process.returncode == 1, process.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["totals"]["total"] == 2
    assert report["totals"]["timeouts"] == 1
    assert report["totals"]["success"] == 1
    cases = _by_id(report)
    slow = cases["slow-1"]
    assert slow["timed_out"] is True
    assert slow["outcome"] == "timeout"
    assert slow["http_status"] is None
    assert slow["elapsed_seconds"] >= 0.25
    assert cases["fast-1"]["outcome"] == "success"
    assert len(rag_server.requests) == 2
    assert "超时" in markdown.read_text(encoding="utf-8")


def test_rejects_credentials_in_base_url(tmp_path):
    questions = tmp_path / "questions.json"
    _write_questions(questions, [_item("one", "plain ok")])
    output = tmp_path / "report.json"
    process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--base-url",
            "http://user:secret@127.0.0.1:1",
            "--questions",
            str(questions),
            "--output",
            str(output),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert process.returncode == 2
    assert "credentials" in process.stderr
    assert "secret" not in process.stderr
    assert not output.exists()
