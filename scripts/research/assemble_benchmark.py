"""Assemble the 300-question benchmark into dev / val / sealed-test splits.

Reads one or more JSONL files (draft scenario files or the consolidated W5 file),
runs the structural validator, then writes:

  <out>/dev/questions.json
  <out>/val/questions.json
  <out>/sealed-test/questions.json      (chmod 700 dir, guard note)
  <out>/manifest.json
  <out>/stats.json

Usage:
  python3 scripts/research/assemble_benchmark.py \
      --out data/evaluation/research-benchmark-300-v1 \
      data/evaluation/research-benchmark-300-v1/w5-gold-interventions.jsonl
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_jsonl(paths):
    items = []
    for path in paths:
        with path.open(encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                if line.strip():
                    item = json.loads(line)
                    item.pop("_file", None)
                    item.pop("_line", None)
                    items.append(item)
    return items


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    parser.add_argument("--out", default=str(ROOT / "data/evaluation/research-benchmark-300-v1"))
    args = parser.parse_args()

    paths = [Path(f) for f in args.files]
    validator = ROOT / "scripts" / "research" / "validate_benchmark.py"
    proc = subprocess.run(
        [sys.executable, str(validator), "--json", *map(str, paths)],
        capture_output=True,
        text=True,
    )
    report = json.loads(proc.stdout)
    if report["errors"]:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        print("refusing to assemble: validation errors")
        return 1

    items = load_jsonl(paths)
    out = Path(args.out)
    splits = {"dev": [], "val": [], "test": []}
    for item in items:
        splits[item["split"]].append(item)

    if {k: len(v) for k, v in splits.items()} != {"dev": 100, "val": 50, "test": 150}:
        print(f"unexpected split sizes: {[ (k, len(v)) for k, v in splits.items() ]}")
        return 1

    policy = ROOT / "docs" / "research" / "benchmark-300" / "split-policy.json"
    spec = ROOT / "docs" / "research" / "benchmark-300" / "SPEC.md"

    def compat(record: dict) -> dict:
        """Add flat aliases so existing regression runners can consume the item."""
        out_record = dict(record)
        out_record["id"] = record["base_id"]
        out_record["expected_status"] = record["gold"]["status"]
        out_record["gold_answer"] = record["gold"]["answer"]
        out_record["required_facts"] = [
            f["statement"] for f in record["gold"]["required_facts"]
        ]
        out_record["forbidden_claims"] = record["gold"]["forbidden_claims"]
        return out_record

    def write_split(name: str, records: list[dict], sealed: bool) -> dict:
        target_dir = out / ("sealed-test" if name == "test" else name)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "questions.json"
        payload = {
            "schema_version": "benchmark-300-split-v1",
            "split": name,
            "count": len(records),
            "sealed": sealed,
            "items": [compat(r) for r in sorted(records, key=lambda x: x["base_id"])],
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        digest = sha256_file(target)
        if sealed:
            os.chmod(target_dir, 0o700)
            os.chmod(target, 0o600)
            (target_dir / "SEALED.md").write_text(
                "# 物理隔离说明\n\n"
                "本目录为阶段四最终评测用的 150 道测试题，阶段一即封存。\n\n"
                f"- `questions.json` 的 SHA-256：`{digest}`（与 manifest 一致）。\n"
                "- 访问策略：方法开发、出题与标注人员不得读取 `questions.json`；R1—R5 独立审核代理按 review-protocol 可在审核期读取；阶段四最终评测执行人可读取。\n"
                "- 阶段二、三的机制迭代只允许使用 `dev/` 与 `val/`。\n"
                "- 评测加载器必须在阶段四实现显式放行开关（如 `BENCHMARK_ALLOW_SEALED=1`）；阶段一不提供加载器。\n"
                "- 任何修改必须重新生成 manifest 并记录原因。\n",
                encoding="utf-8",
            )
        return {
            "path": str(target.relative_to(out)),
            "count": len(records),
            "sha256": digest,
        }

    written = {
        "dev": write_split("dev", splits["dev"], False),
        "val": write_split("val", splits["val"], False),
        "test": write_split("test", splits["test"], True),
    }

    stats = {
        "count": len(items),
        "by_split": {k: len(v) for k, v in splits.items()},
        "by_scenario": dict(collections.Counter(i["scenario"] for i in items)),
        "by_split_scenario": {
            split: dict(collections.Counter(i["scenario"] for i in recs))
            for split, recs in splits.items()
        },
        "by_task_type": dict(collections.Counter(i["task_type"] for i in items)),
        "by_verdict_class": dict(collections.Counter(i["gold"]["verdict_class"] for i in items)),
        "by_gold_status": dict(collections.Counter(i["gold"]["status"] for i in items)),
        "by_cluster": dict(collections.Counter(i["cluster_id"] for i in items)),
        "explicit_scope": dict(
            collections.Counter(
                i["split"] for i in items if i["scope"]["mode"] == "explicit_revisions"
            )
        ),
        "interventions": {
            "total": sum(len(i["interventions"]) for i in items),
            "should_change": sum(
                1 for i in items for iv in i["interventions"] if iv["pair_role"] == "should_change"
            ),
            "should_hold": sum(
                1 for i in items for iv in i["interventions"] if iv["pair_role"] == "should_hold"
            ),
            "by_operation": dict(
                collections.Counter(iv["operation"] for i in items for iv in i["interventions"])
            ),
        },
        "evidence": {
            "chunks_referenced": len(
                {ev["chunk_id"] for i in items for ev in i["gold"]["evidence_minimal"]}
            ),
            "revisions_referenced": len(
                {ev["revision_id"] for i in items for ev in i["gold"]["evidence_minimal"]}
            ),
            "families_referenced": len({f for i in items for f in i["family_ids"]}),
        },
    }

    manifest = {
        "schema_version": "benchmark-300-manifest-v1",
        "assembled_on": "2026-11-07",
        "sealed": True,
        "sealing_policy": {
            "sealed_dir": "sealed-test",
            "dir_mode": "700",
            "file_mode": "600",
            "review_access": "R1-R5 may read during review per review-protocol",
            "loader_guard": "phase-4 evaluator must implement BENCHMARK_ALLOW_SEALED",
            "source_files": "test-bearing source JSONL and w5 report are kept under sealed-test/_work with 600",
        },
        "release_id": "kb-2.0.0-rc.3",
        "corpus_digest": json.loads(
            (ROOT / "tmp" / "research-rc3" / "inventory" / "corpus-digest.json").read_text(
                encoding="utf-8"
            )
        ),
        "spec_sha256": sha256_file(spec),
        "split_policy_sha256": sha256_file(policy),
        "source_files": [
            {"path": str(p), "sha256": sha256_file(p)} for p in paths
        ],
        "splits": written,
        "stats": stats,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (out / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps({"splits": written, "stats": stats}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
