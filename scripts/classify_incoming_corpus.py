#!/usr/bin/env python3
"""Classify an incoming SHINE control-system batch into ingestion decisions.

Consumes the inventory JSON produced by analyze_incoming_corpus.py and writes a
CSV plus per-bucket statistics.  Path rules are explicit so the decision for
every file can be reviewed and changed in one place.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# (regex, bucket, priority, handling, note)
RULES: list[tuple[str, str, str, str, str]] = [
    # --- containers / junk -------------------------------------------------
    (r"^.*/~\$", "junk", "exclude", "exclude", "Office 临时锁文件"),
    (r"\.(zip|rar)$", "container", "exclude", "exclude", "嵌套压缩包，内容与已解压目录重复/待单独处理"),
    (r"\.(jpg|jpeg|png)$", "image", "exclude", "exclude", "扫描签字页，无正文"),
    (r"^3 样机验收/米清茹补充材料/代码/", "supplement", "P3", "exclude", "IP 表/日志/脚本，属配置快照而非知识文档"),
    (r"^3 样机验收/米清茹补充材料/", "core_design", "P1", "convert", "IOC 设计规范、GitLab 使用说明、数据库设计"),
    (r"^3 样机验收/陈广花补充材料/", "supplement", "P3", "exclude", "图纸/端子表/归档包，结构化表格，暂不入文本索引"),
    # --- standards ---------------------------------------------------------
    (r"^SHINE-OP-TL-002 2024 总控相关标准和规范\.pdf$", "standard", "P0", "ingest", "5 份单项规范的合并版"),
    (r"^总控相关标准和规范/", "standard", "P1", "ingest", "单项规范；与合并版重复，建议只留一份"),
    (r"^序号24-SHINE-OP-TL-018- 设备命名规则", "standard", "P2", "ocr", "扫描件，需 OCR；命名规则类"),
    (r"^附件-SHINE-OP-TL-004-2022-SHINE项目技术代号规则", "standard", "P2", "ocr", "扫描件，需 OCR；命名规则类"),
    (r"^SHINE控制信号命名规则-签发版\.pdf$", "standard", "P1", "ingest", "命名规则正文"),
    (r"^SHINE-AC编号\.docx$", "standard", "P1", "convert", "系统代号表"),
    (r"^机柜命名规则\.pptx$", "standard", "P1", "convert", "机柜命名规则"),
    (r"^20230613加速器总体设备命名规则专题会纪要\.pdf$", "standard", "P2", "ingest", "会议纪要，过程性"),
    # --- core design, newest ----------------------------------------------
    (r"^1、硬X射线自由电子激光装置优化设计报告-加速器分册V6", "core_design", "P0", "convert", "2024 优化设计报告，最新主线设计"),
    (r"^六、加速器控制20240422\.docx$", "core_design", "P0", "convert", "2024 工程设计报告·加速器控制章"),
    (r"^硬X射线自由电子激光装置网络安全设计报告\.docx$", "core_design", "P0", "convert", "2026-11 最新，网络安全"),
    (r"^归档文档（20251119）/", "core_design", "P0", "convert", "2025 硬线归档：IOC/定时/电源/激光/安全"),
    (r"^归档文档（202410）/", "core_design", "P1", "convert", "2024 归档：控制网络/联锁/真空/EPICS 部署"),
    # --- earlier design generations ---------------------------------------
    (r"^1 硬线工程/", "core_design", "P1", "convert", "2018-2019 初步设计报告（历史版）"),
    (r"^归档文档（20221117）/", "core_design", "P1", "convert", "2022 技术设计报告（历史版）"),
    # --- manuals -----------------------------------------------------------
    (r"^操作手册/第二版/", "manual", "P2", "convert", "第二版操作手册，可能被第三版取代"),
    (r"^操作手册/第三版（202411）/", "manual", "P1", "convert", "第三版操作手册（最新）"),
    (r"^操作手册/", "manual", "P1", "convert", "第一版操作手册"),
    (r"^归档文档（202310）/", "manual", "P2", "convert", "2023 归档：界面操作说明/监控设计"),
    # --- prototypes --------------------------------------------------------
    (r"^2 重大专项/", "prototype", "P2", "convert", "样机设计与评审，过程性材料"),
    (r"^3 样机验收/", "prototype", "P2", "convert", "样机测试/验收，过程性材料"),
    # --- project-level docs ------------------------------------------------
    (r"^OPI及IOC控制器网络配置", "core_design", "P1", "convert", "IOC 网络配置规范"),
    (r"^SHINE注入器段IOC管理规范文档", "core_design", "P1", "convert", "IOC 管理规范"),
    (r"^加速器工艺安装技术规范（PDF）\.pdf$", "standard", "P2", "ocr", "扫描件，需 OCR"),
]

DEFAULT = ("other", "P2", "review", "未匹配规则，人工判断")

TYPE_HANDLING = {
    "pdf": {"ingest": "ingest", "ocr": "ocr", "convert": "ingest", "exclude": "exclude", "review": "ingest"},
    "docx": {"ingest": "convert", "ocr": "ocr", "convert": "convert", "exclude": "exclude", "review": "convert"},
    "doc": {"ingest": "convert", "ocr": "ocr", "convert": "convert", "exclude": "exclude", "review": "convert"},
    "pptx": {"ingest": "convert", "ocr": "ocr", "convert": "convert", "exclude": "exclude", "review": "convert"},
    "xlsx": {"ingest": "exclude", "ocr": "ocr", "convert": "exclude", "exclude": "exclude", "review": "exclude"},
    "legacy": {"ingest": "convert", "ocr": "ocr", "convert": "convert", "exclude": "exclude", "review": "convert"},
    "other": {"ingest": "exclude", "ocr": "ocr", "convert": "exclude", "exclude": "exclude", "review": "exclude"},
}


def classify(rec: dict) -> tuple[str, str, str, str]:
    path = rec["path"]
    for pattern, bucket, priority, handling, note in RULES:
        if re.search(pattern, path):
            kind = rec.get("kind", "other")
            handling = TYPE_HANDLING.get(kind, TYPE_HANDLING["other"]).get(handling, handling)
            # scanned PDFs cannot be ingested as text
            if kind == "pdf" and rec.get("pages_without_text") == rec.get("pages") and handling == "ingest":
                handling, note = "ocr", note + "；整本扫描件，需 OCR"
            return bucket, priority, handling, note
    kind = rec.get("kind", "other")
    handling = TYPE_HANDLING.get(kind, TYPE_HANDLING["other"])["review"]
    return DEFAULT[0], DEFAULT[1], handling, DEFAULT[3]


def main() -> int:
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    records = json.loads(src.read_text(encoding="utf-8"))

    rows = []
    for rec in records:
        bucket, priority, handling, note = classify(rec)
        rows.append(
            {
                "path": rec["path"],
                "ext": rec["ext"],
                "kind": rec.get("kind", ""),
                "bytes": rec["bytes"],
                "chars": rec.get("chars", 0),
                "approx_tokens": rec.get("approx_tokens", 0),
                "pages": rec.get("pages", ""),
                "pages_without_text": rec.get("pages_without_text", ""),
                "bucket": bucket,
                "priority": priority,
                "handling": handling,
                "note": note,
            }
        )

    rows.sort(key=lambda r: (r["bucket"], r["priority"], r["path"]))
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print("bucket x handling")
    table = defaultdict(Counter)
    for r in rows:
        table[r["bucket"]][r["handling"]] += 1
    for bucket in sorted(table):
        print(f"  {bucket:<14} {dict(table[bucket])}")

    print("\npriority x chars")
    chars = defaultdict(int)
    files = Counter()
    for r in rows:
        chars[r["priority"]] += r["chars"]
        files[r["priority"]] += 1
    for p in sorted(chars):
        print(f"  {p:<8} files={files[p]:>3} chars={chars[p]:>10,} tokens≈{chars[p]*0.62:>10,.0f}")

    print("\nhandling totals")
    print("  " + str(dict(Counter(r["handling"] for r in rows))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
