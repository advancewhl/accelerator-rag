"""Run real framework regression; labels stay in this client, outside RAG inputs."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from time import perf_counter

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18003")
    parser.add_argument(
        "--questions", default="data/evaluation/retrieval_baseline.json"
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--trace-dir")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.workers <= 2:
        raise ValueError("use one or two bounded HTTP workers")
    if httpx.URL(args.base_url).host not in {"localhost", "127.0.0.1", "10.101.9.190"}:
        raise ValueError("only the existing group RAG service is authorized")
    path = Path(args.questions)
    cases = [
        {"id": q["id"], "query": q["query"], "answerable": q["answerable"]}
        for q in json.loads(path.read_text())["queries"]
    ]
    cases += [
        {
            "id": "cryo-original",
            "query": "shine低温系统中，主plc和cpld分别负责什么保护？，两者如何配合",
        },
        {
            "id": "cryo-paraphrase",
            "query": "SHINE 低温联锁里的主 PLC 和 CPLD 是怎样分工与协同的？",
        },
        {
            "id": "cryo-missing-details",
            "query": "SHINE 低温 CPLD 每个端口的接线表和所有保护阈值是什么？",
        },
        {
            "id": "xfel-version-scopes",
            "query": "请对照不同年份文档说明 European XFEL 的常规运行能量与最大能量，保留各自口径。",
        },
    ]
    report = {
        "execution": "real production HTTP",
        "benchmark_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "cases": [],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    def run_case(case):
        with httpx.Client(
            base_url=args.base_url, trust_env=False, timeout=180
        ) as client:
            row = dict(case)
            started = perf_counter()
            try:
                response = client.post("/v1/rag/answer", json={"query": case["query"]})
                row.update(http_status=response.status_code, response=response.json())
                data = row["response"]
                if response.status_code == 200:
                    row["status_consistent"] = (
                        all(r["supported"] for r in data["requirements"])
                        if data["status"] == "answered"
                        else bool(data["citations"])
                        if data["status"] == "partial"
                        else not data["citations"]
                    )
                    if args.trace_dir:
                        trace = json.loads(
                            (
                                Path(args.trace_dir) / (data["request_id"] + ".json")
                            ).read_text()
                        )
                        row["trace_summary"] = {
                            "rounds": len(trace["rounds"]),
                            "selected_round": trace["selected_round"],
                            "calls": len(trace["calls"]),
                            "budgets_respected": all(
                                r["subset"]["context_tokens"]
                                <= r["subset"]["token_budget"]
                                and len(r["subset"]["selected_sources"])
                                <= r["subset"]["max_sources"]
                                for r in trace["rounds"]
                            ),
                            "supplemented": any(
                                "supplementary_queries" in r for r in trace["rounds"]
                            ),
                        }
            except Exception as exc:
                row["error"] = {"type": type(exc).__name__, "message": str(exc)}
            row["wall_seconds"] = perf_counter() - started
            return row

    report["workers"] = args.workers
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for row in executor.map(run_case, cases):
            report["cases"].append(row)
            report["summary"] = {
                "statuses": dict(
                    Counter(
                        r.get("response", {}).get("status", "error")
                        for r in report["cases"]
                    )
                ),
                "http_errors": sum(
                    r.get("http_status") != 200 for r in report["cases"]
                ),
                "client_errors": sum("error" in r for r in report["cases"]),
            }
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            print(
                len(report["cases"]),
                row["id"],
                row.get("http_status"),
                row.get("response", {}).get("status", row.get("error")),
                round(row["wall_seconds"], 2),
                flush=True,
            )


if __name__ == "__main__":
    main()
