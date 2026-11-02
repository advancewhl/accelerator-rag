#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate K1/K4 governance candidate JSON for kb-2.0.0.

This script is standalone and intentionally does not import ``accelerator_rag``.
It reads the 2026-11-02 batch decision CSV, the batch analysis markdown, the
inventory JSON (for cover/head snippets) and the legacy registry, then writes:

  data/documents/v2/dispositions.draft.json
  data/documents/v2/family-candidates.draft.json
  data/documents/v2/conflict-candidates.draft.json

The output is a *draft candidate* set: it records evidence and open questions,
not approved current revisions. It does not read the raw documents' full text,
does not OCR, does not convert Office files, and does not access the network.

Usage:
  /home/whloong/miniconda3/envs/accelerator-rag/bin/python -I \
      scripts/build_v2_governance.py

  # Run from outside the repository with an explicit root:
  python -I /tmp/build_v2_governance.py --root /path/to/repo
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

BATCH_ID = "2026-11-02-shine-control"
GENERATED_ON = "2026-11-02"
SOURCE_PREFIX = "data/l0_raw/incoming/2026-11-02-shine-control/资料/"

CSV_REL = "reports/incoming-2026-11-02/document-decisions.csv"
ANALYSIS_REL = "reports/incoming-2026-11-02/ANALYSIS.md"
INVENTORY_REL = "reports/incoming-2026-11-02/inventory.clean.json"
REGISTRY_REL = "data/documents/registry.json"
PLAN_REL = "docs/roadmap/knowledge-base-v2-plan.md"

SCHEMA_VERSION = 2
EXPECTED_ROWS = 218

SOURCE_FORMATS = {
    "pdf", "md", "docx", "doc", "pptx", "xlsx", "csv", "ods",
    "txt", "image", "archive", "code", "other",
}
DOCUMENT_KINDS = {
    "overall_design", "subsystem_design", "standard_specification",
    "interface_specification", "operation_manual", "installation_maintenance",
    "test_plan", "test_report", "acceptance_report", "development_summary",
    "review_opinion", "meeting_record", "paper", "configuration_snapshot",
    "structured_list", "drawing", "unknown",
}
PRIORITIES = {"P0", "P1", "P2", "P3", "exclude"}
DISPOSITIONS = {
    "text_index", "structured_index", "attachment_only",
    "catalog_only", "deferred", "excluded",
}
PLANNED_ACTIONS = {
    "ingest", "convert", "ocr", "structured", "attachment",
    "catalog", "exclude", "defer",
}

EXT_TO_FORMAT = {
    ".pdf": "pdf",
    ".md": "md",
    ".docx": "docx",
    ".doc": "doc",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".csv": "csv",
    ".ods": "ods",
    ".txt": "txt",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".zip": "archive",
    ".rar": "archive",
    ".7z": "archive",
    ".py": "code",
    ".sh": "code",
    ".acf": "code",
    ".log": "code",
    # Schema v2 maps unknown/absent suffixes to "other"; do the same so the
    # draft can be merged into registry-v2.json without a format mismatch.
    "": "other",
}

HANDLING_TO_DISPOSITION = {
    "ingest": ("text_index", "ingest"),
    "convert": ("text_index", "convert"),
    "ocr": ("text_index", "ocr"),
}


# ---------------------------------------------------------------------------
# Per-file document_kind
# ---------------------------------------------------------------------------

EXPLICIT_KIND = {
    "3 样机验收/陈广花补充材料/一号测试厅归档文档.rar": "unknown",
    "归档文档（202310）/2023控制系统硬线项目归档文件(1).zip": "unknown",
    "1、硬X射线自由电子激光装置优化设计报告-加速器分册V6（返回通读版本）.docx": "overall_design",
    "六、加速器控制20240422.docx": "overall_design",
    "1 硬线工程/24. 控制需求工作联系单.pdf": "unknown",
    "1 硬线工程/25. 联锁系统硬件信号接口规格.pdf": "standard_specification",
    "1 硬线工程/26. 设备控制及通讯接口标准.pdf": "standard_specification",
    "归档文档（20251119）/2025硬线归档/王睿归档报告（1）.pdf": "unknown",
    "归档文档（20251119）/2025硬线归档/王睿归档报告（2）.pdf": "unknown",
    "归档文档（202310）/硬线归档报告封面.docx": "unknown",
    "3 样机验收/陈广花补充材料/水平测试平台2控制柜电路图V2.pdf": "drawing",
    "3 样机验收/陈广花补充材料/端子对应表最终版3.8现场改造.xlsx": "structured_list",
    "3 样机验收/陈广花补充材料/补充材料清单.xlsx": "structured_list",
    "3 样机验收/米清茹补充材料/Git及GitLab的使用说明.docx": "operation_manual",
    "3 样机验收/米清茹补充材料/IOC设计规范-v1.2.docx": "standard_specification",
    "3 样机验收/米清茹补充材料/网页访问mysql数据库设计.docx": "subsystem_design",
    "归档文档（20251119）/2025硬线归档/基于LabVIEW与EPICS的方波信号频率应用.docx": "subsystem_design",
    "SHINE-AC编号.docx": "structured_list",
}


def classify_document_kind(path: str) -> str:
    """Return a candidate business type from the filename and directory."""
    if path in EXPLICIT_KIND:
        return EXPLICIT_KIND[path]

    name = path

    # Office lock files are not documents, regardless of the directory name.
    if "~$" in name:
        return "unknown"

    if path.startswith("操作手册/"):
        return "operation_manual"

    # 2023 nested archive: the embedded files use the same naming as the
    # extracted tree, so the 归档文档（202310） rules below apply.
    if path.startswith("3 样机验收/米清茹补充材料/代码/"):
        return "configuration_snapshot"

    if path.startswith("3 样机验收/"):
        if "测试大纲" in name:
            return "test_plan"
        if "自测报告" in name or "测试报告" in name:
            return "test_report"
        if "研制总结" in name:
            return "development_summary"
        if "验收评审报告" in name:
            return "review_opinion"
        if "验收书" in name or "验收申请书" in name:
            return "acceptance_report"
        if "设计评审报告" in name:
            return "review_opinion"
        if "设计报告" in name:
            return "subsystem_design"
        if "移交清单" in name:
            return "structured_list"

    if path.startswith("2 重大专项/"):
        if "会议手册" in name or "例会纪要" in name:
            return "meeting_record"
        if "评审报告" in name or "专家意见反馈表" in name:
            return "review_opinion"
        if "设计报告" in name:
            return "subsystem_design"
        if "网络需求" in name:
            return "interface_specification"
        if "地址分配" in name:
            return "configuration_snapshot"
        if "方案确认" in name:
            return "review_opinion"

    if path.startswith("归档文档（202310）/"):
        if "操作说明" in name or "操作手册" in name:
            return "operation_manual"
        if "验收测试报告" in name:
            return "test_report"
        if "设计报告" in name:
            return "subsystem_design"
        if "移交清单" in name:
            return "structured_list"
        if "封面" in name:
            return "unknown"

    if path.startswith("归档文档（20221117）/"):
        if "评审申请书" in name or "评审意见" in name:
            return "review_opinion"
        if "安装配置报告" in name:
            return "installation_maintenance"
        if "技术设计报告" in name or "设计报告" in name or "远程控制" in name:
            return "subsystem_design"
        if "移交清单" in name:
            return "structured_list"

    if path.startswith("归档文档（202410）/"):
        if "操作手册" in name or "操作说明" in name:
            return "operation_manual"
        if "安装步骤" in name or "配置方法" in name:
            return "installation_maintenance"
        if "数据交互" in name:
            return "interface_specification"
        if "测试技术报告" in name or "测试情况总结" in name:
            return "test_report"
        if "设计报告" in name:
            return "subsystem_design"
        if "总结报告" in name:
            return "development_summary"
        if "移交清单" in name:
            return "structured_list"
        if (
            "Archiver" in name
            or "Accelerator Control System" in name
            or "电源分配单元" in name
        ):
            return "subsystem_design"

    if path.startswith("归档文档（20251119）/"):
        if (
            "IOC 模板建立" in name
            or "IOC应用开发" in name
            or "IOC设备安装维护" in name
        ):
            return "installation_maintenance"
        if "OPI环境安装" in name:
            return "installation_maintenance"
        if "EPICS-SNMP模块配置" in name:
            return "installation_maintenance"
        if "研制总结" in name:
            return "development_summary"
        if "设计报告" in name:
            return "subsystem_design"
        if "安全管理" in name:
            return "subsystem_design"
        if "移交清单" in name:
            return "structured_list"

    if path.startswith("1 硬线工程/"):
        if "评审报告" in name:
            return "review_opinion"
        if "工作联系单" in name:
            return "unknown"
        return "subsystem_design"

    if path.startswith("总控相关标准和规范/"):
        return "standard_specification"

    if "网络安全设计报告" in name:
        return "subsystem_design"
    if "SHINE-OP-TL-002" in name:
        return "standard_specification"
    if "SHINE控制信号命名规则" in name:
        return "standard_specification"
    if "OPI及IOC控制器网络配置" in name:
        return "configuration_snapshot"
    if "IOC管理规范" in name:
        return "standard_specification"
    if "机柜命名规则" in name:
        return "standard_specification"
    if "专题会纪要" in name:
        return "meeting_record"
    if "加速器工艺安装技术规范" in name:
        return "standard_specification"
    if name.startswith("序号24-SHINE-OP-TL-018") or name.startswith("附件-SHINE-OP-TL-004"):
        return "standard_specification"

    if name.endswith(".jpg"):
        return "structured_list"
    return "unknown"


# ---------------------------------------------------------------------------
# Re-routing of the 27 handling=exclude rows
# ---------------------------------------------------------------------------

EXCLUDE_DISPOSITIONS = {
    "3 样机验收/陈广花补充材料/一号测试厅归档文档.rar": ("catalog_only", "catalog"),
    "归档文档（202310）/2023控制系统硬线项目归档文件(1).zip": ("catalog_only", "catalog"),
    "归档文档（20221117）/归档清单（20221117签字版）.jpg": ("attachment_only", "attachment"),
    "归档文档（202410）/硬线项目归档文件移交清单（签字版）.jpg": ("attachment_only", "attachment"),
    "归档文档（20251119）/2025硬线归档/移交清单-签字版.jpg": ("attachment_only", "attachment"),
    "3 样机验收/~$率图像采集样机研制总结报告.docx": ("excluded", "exclude"),
    "操作手册/~$INE激光界面操作手册.doc": ("excluded", "exclude"),
    "3 样机验收/米清茹补充材料/代码/README.txt": ("catalog_only", "catalog"),
    "3 样机验收/米清茹补充材料/代码/S99logServer": ("catalog_only", "catalog"),
    "3 样机验收/米清茹补充材料/代码/acsTest.acf": ("catalog_only", "catalog"),
    "3 样机验收/米清茹补充材料/代码/caput.log": ("deferred", "defer"),
    "3 样机验收/米清茹补充材料/代码/caputLog-202004141600": ("deferred", "defer"),
    "3 样机验收/米清茹补充材料/代码/caputlog-offset": ("deferred", "defer"),
    "3 样机验收/米清茹补充材料/代码/genIPList.py": ("catalog_only", "catalog"),
    "3 样机验收/米清茹补充材料/代码/hla-ip.csv": ("catalog_only", "catalog"),
    "3 样机验收/米清茹补充材料/代码/hla-ip.ods": ("catalog_only", "catalog"),
    "3 样机验收/米清茹补充材料/代码/importIPFile.py": ("catalog_only", "catalog"),
    "3 样机验收/米清茹补充材料/代码/ps-ip.csv": ("catalog_only", "catalog"),
    "3 样机验收/米清茹补充材料/代码/shine-proto-ip.csv": ("catalog_only", "catalog"),
    "3 样机验收/米清茹补充材料/代码/temIPList": ("catalog_only", "catalog"),
    "3 样机验收/米清茹补充材料/代码/tmpIPAlive": ("catalog_only", "catalog"),
    "3 样机验收/米清茹补充材料/代码/tmpIPList": ("catalog_only", "catalog"),
    "3 样机验收/米清茹补充材料/代码/updateCaputlogDb.py": ("catalog_only", "catalog"),
    "3 样机验收/米清茹补充材料/代码/updateCaputlogDb.sh": ("catalog_only", "catalog"),
    "3 样机验收/陈广花补充材料/水平测试平台2控制柜电路图V2.pdf": ("attachment_only", "attachment"),
    "3 样机验收/陈广花补充材料/端子对应表最终版3.8现场改造.xlsx": ("structured_index", "structured"),
    "3 样机验收/陈广花补充材料/补充材料清单.xlsx": ("structured_index", "structured"),
}


# ---------------------------------------------------------------------------
# Reasons and notes
# ---------------------------------------------------------------------------

REASON_OVERRIDES = {
    "3 样机验收/陈广花补充材料/一号测试厅归档文档.rar": (
        "嵌套 RAR 压缩包；ANALYSIS §4.2/§7 仅列目录、未解压评估。"
        "按压缩包规则转 catalog_only，登记容器与内部路径，不把压缩包当正文索引。"
    ),
    "归档文档（202310）/2023控制系统硬线项目归档文件(1).zip": (
        "嵌套 ZIP 压缩包；ANALYSIS §4.2 指出 zip 内 12 个文件与同目录已解压目录完全对应。"
        "按 catalog_only 仅登记容器，避免与已解压文件重复索引。"
    ),
    "归档文档（20221117）/归档清单（20221117签字版）.jpg": (
        "扫描签字页，无正文；按签字图片规则转 attachment_only，保留原件供归档核对。"
    ),
    "归档文档（202410）/硬线项目归档文件移交清单（签字版）.jpg": (
        "扫描签字页，无正文；按签字图片规则转 attachment_only，保留原件供归档核对。"
    ),
    "归档文档（20251119）/2025硬线归档/移交清单-签字版.jpg": (
        "扫描签字页，无正文；按签字图片规则转 attachment_only，保留原件供归档核对。"
    ),
    "3 样机验收/陈广花补充材料/水平测试平台2控制柜电路图V2.pdf": (
        "图纸类 PDF（94 页，inventory 记录有文本层但正文主要是图框文字）；"
        "首版不做电路拓扑自动理解，按计划 §3.2 转 attachment_only，保留附件阅读。"
    ),
    "3 样机验收/陈广花补充材料/端子对应表最终版3.8现场改造.xlsx": (
        "端子对应表；按计划 §7.4 建立端子/行列级结构化索引，作为首版结构化试点，"
        "不作为普通段落切块。"
    ),
    "3 样机验收/陈广花补充材料/补充材料清单.xlsx": (
        "补充材料清单；按结构化清单建立行列级索引，便于目录管理。"
        "计划 §2.2 提出进入目录管理，当前按 structured_index 候选处置，待确认。"
    ),
    "1 硬线工程/25. 联锁系统硬件信号接口规格.pdf": (
        "整本扫描件（3 页，无文本层）；ANALYSIS §3.2 指出 总控相关标准和规范/ 下已有文本版。"
        "当前按 text_index/ocr 候选登记用于等价核对；确认等价后可降为 attachment_only。"
    ),
    "1 硬线工程/26. 设备控制及通讯接口标准.pdf": (
        "整本扫描件（2 页，无文本层）；ANALYSIS §3.2 指出 总控相关标准和规范/ 下已有文本版。"
        "当前按 text_index/ocr 候选登记用于等价核对；确认等价后可降为 attachment_only。"
    ),
}

SPECIAL_NOTES = {
    "归档文档（20251119）/2025硬线归档/王睿归档报告（1）.pdf": (
        "未读全文；报告主题/业务类型 unknown；仅按 2025 归档目录登记。"
    ),
    "归档文档（20251119）/2025硬线归档/王睿归档报告（2）.pdf": (
        "未读全文；报告主题/业务类型 unknown；仅按 2025 归档目录登记。"
    ),
    "归档文档（202310）/硬线归档报告封面.docx": (
        "未读全文；仅封面页（166 字符）；业务类型 unknown。"
    ),
    "1、硬X射线自由电子激光装置优化设计报告-加速器分册V6（返回通读版本）.docx": (
        "文件名含“返回通读版本”；批准状态、生效时间、替代范围均 unknown；未读全文。"
        "inventory head 的“一、概述”称 7.2 GeV。"
    ),
    "硬X射线自由电子激光装置网络安全设计报告.docx": (
        "封面文字（inventory head）：编制史武军、吕慧慧、唐小丰；审核、审定、会签栏空白；"
        "日期“2026年11月5日”晚于批次日期 2026-11-02；未读全文，批准/生效状态 unknown。"
    ),
    "1 硬线工程/20. 常规功率源控制初步设计报告.docx": (
        "inventory head 的“概述”称“能量为8GeV”；与 V6 的 7.2 GeV 存在设计能量口径差异，"
        "见 conflict-candidates.draft.json。"
    ),
    "1 硬线工程/21. 束流分配及功率源控制初步设计报告.docx": (
        "inventory head 的“概述”称已加速至 8GeV；与 V6 的 7.2 GeV 存在设计能量口径差异，"
        "见 conflict-candidates.draft.json。"
    ),
    "1 硬线工程/25. 联锁系统硬件信号接口规格.pdf": (
        "对应文本版：总控相关标准和规范/联锁系统硬件信号接口规范.pdf；等价关系待确认。"
    ),
    "1 硬线工程/26. 设备控制及通讯接口标准.pdf": (
        "对应文本版：总控相关标准和规范/设备控制及通讯接口标准规范-xin.pdf；等价关系待确认。"
    ),
    "归档文档（202310）/2023控制系统硬线项目归档文件(1)/2023控制系统硬线项目归档文件/硬X射线自由电子激光装置项目1号井功率源控制界面操作说明.docx": (
        "ANALYSIS §4.2 列为与 操作手册/SHINE功率源控制界面操作说明.docx 完全重复（SHA-256 相同）；"
        "最终应共享原始资产，避免重复索引。"
    ),
    "归档文档（202310）/2023控制系统硬线项目归档文件(1)/2023控制系统硬线项目归档文件/硬X射线自由电子激光装置项目1号井温湿度控制界面操作说明.docx": (
        "ANALYSIS §4.2 列为与 操作手册/SHINE温湿度控制界面操作说明.docx 完全重复（SHA-256 相同）；"
        "最终应共享原始资产，避免重复索引。"
    ),
    "归档文档（202310）/2023控制系统硬线项目归档文件(1)/2023控制系统硬线项目归档文件/硬X射线自由电子激光装置项目1号井电源控制界面操作说明.docx": (
        "ANALYSIS §4.2 列为与 操作手册/SHINE电源控制界面操作说明.docx 完全重复（SHA-256 相同）；"
        "最终应共享原始资产，避免重复索引。"
    ),
    "归档文档（202310）/基于Nagios 的White Rabbit定时网络监控系统设计报告.docx": (
        "与嵌套目录同名文件标题相同、字符数不同（2580 vs 2786），疑似版本差异，未读全文，待确认。"
    ),
    "归档文档（202310）/基于SNMP的定时网络监控系统设计报告.docx": (
        "与嵌套目录同名文件标题相同、字符数不同（2938 vs 3124），疑似版本差异，未读全文，待确认。"
    ),
    "归档文档（202310）/2023控制系统硬线项目归档文件(1)/2023控制系统硬线项目归档文件/硬X射线自由电子激光装置项目定时系统控制界面操作说明.doc": (
        "2023 归档副本；与 操作手册/ 第一版/第二版定时手册的关系未逐份确认。"
    ),
    "归档文档（202310）/2023控制系统硬线项目归档文件(1)/2023控制系统硬线项目归档文件/硬X射线自由电子激光装置项目恒温机柜控制界面操作说明.doc": (
        "2023 归档副本；与 操作手册/ 第一版/第二版恒温机柜手册的关系未逐份确认。"
    ),
    "归档文档（202310）/2023控制系统硬线项目归档文件(1)/2023控制系统硬线项目归档文件/硬X射线自由电子激光装置项目联锁系统控制界面操作说明.docx": (
        "2023 归档副本；与 操作手册/ 第一版/第二版联锁手册的关系未逐份确认。"
    ),
    "归档文档（202410）/SHINE存档数据查询软件操作手册.doc": (
        "2024 归档副本；手册代次、批准状态与适用范围 unknown。"
    ),
    "归档文档（202410）/SHINE注入器联锁系统操作说明-归档2410.docx": (
        "2024 归档副本；手册代次、批准状态与适用范围 unknown。"
    ),
    "归档文档（202410）/SHINE注入段真空控制操作手册.doc": (
        "2024 归档副本；手册代次、批准状态与适用范围 unknown。"
    ),
    "归档文档（20221117）/9.评审意见-专家签字版.pdf": (
        "专家评审意见签字版扫描件（1 页，无文本层）；OCR 后作为评审证据，签字页保留附件。"
    ),
    "归档文档（202310）/2023控制系统硬线项目归档文件(1)/2023控制系统硬线项目归档文件/2023控制系统移交清单签字版-Page-1.pdf": (
        "2023 移交清单签字版单页扫描件（无文本层）；OCR 后作为归档证据。"
    ),
    "3 样机验收/快联锁样机测试报告.pdf": "17 页整本无文本层；未 OCR。",
    "3 样机验收/恒温机柜控制样机测试报告.pdf": "7 页整本无文本层；未 OCR。",
    "3 样机验收/控制系统开发环境样机测试报告.pdf": "11 页整本无文本层；未 OCR。",
    "3 样机验收/真空设备控制样机测试报告.pdf": "12 页整本无文本层；未 OCR。",
    "3 样机验收/高帧率图像采集样机测试报告.pdf": "6 页整本无文本层；未 OCR。",
    "1 硬线工程/24. 控制需求工作联系单.pdf": "47 页整本无文本层；未 OCR；业务类型待确认。",
    "加速器工艺安装技术规范（PDF）.pdf": "22 页整本无文本层；未 OCR。",
    "序号24-SHINE-OP-TL-018- 设备命名规则-R0-20190903.pdf": "14 页整本无文本层；未 OCR。",
    "附件-SHINE-OP-TL-004-2022-SHINE项目技术代号规则-20220926.pdf": "12 页整本无文本层；未 OCR。",
    "3 样机验收/~$率图像采集样机研制总结报告.docx": "162 bytes，无正文。",
    "操作手册/~$INE激光界面操作手册.doc": "162 bytes，无正文。",
    "3 样机验收/米清茹补充材料/代码/temIPList": (
        "ANALYSIS §4.2 列为与 tmpIPList 完全重复（SHA-256 相同）。"
    ),
    "3 样机验收/米清茹补充材料/代码/tmpIPList": (
        "ANALYSIS §4.2 列为与 temIPList 完全重复（SHA-256 相同）。"
    ),
    "3 样机验收/米清茹补充材料/代码/caput.log": "运行日志；采集时间、完整性与用途未确认。",
    "3 样机验收/米清茹补充材料/代码/caputLog-202004141600": "历史运行日志；采集时间、完整性与用途未确认。",
    "3 样机验收/米清茹补充材料/代码/caputlog-offset": "运行日志偏移文件；用途与完整性未确认。",
    "3 样机验收/陈广花补充材料/水平测试平台2控制柜电路图V2.pdf": (
        "94 页图纸；未做图纸语义识别；正文主要是图框文字。"
    ),
    "3 样机验收/陈广花补充材料/端子对应表最终版3.8现场改造.xlsx": (
        "端子表；列为 P3，按计划 §7.4 结构化试点；字段含义与设备/版本范围待确认。"
    ),
    "3 样机验收/陈广花补充材料/补充材料清单.xlsx": (
        "补充材料清单；计划 §2.2 提出进入目录管理，当前按结构化清单候选处置，待确认。"
    ),
}


def reason_for(row: dict, disposition: str, action: str) -> str:
    path = row["path"]
    if path in REASON_OVERRIDES:
        return REASON_OVERRIDES[path]

    if disposition == "text_index":
        if action == "ingest":
            return "CSV handling=ingest；PDF 有文本层，按现有 PDF 链路解析入库。"
        if action == "convert":
            if path.endswith(".doc"):
                return (
                    "CSV handling=convert；旧版 DOC 需在固定环境转 DOCX/PDF 后解析入库，"
                    "保留原件与转换记录。"
                )
            if path.endswith(".pptx"):
                return (
                    "CSV handling=convert；PPTX 按幻灯片提取标题、文本框、表格与备注后入库，"
                    "备注单独标识。"
                )
            return "CSV handling=convert；Office 文档需转换后解析入库，保留原件与转换记录。"
        if action == "ocr":
            return (
                "CSV handling=ocr；整本或关键页缺少文本层，需 OCR 并逐页复核数值、单位和符号后入库。"
            )

    if disposition == "structured_index":
        return "结构化表格；按计划 §7.4 建立行列级结构化索引，不作为普通段落切块。"
    if disposition == "attachment_only":
        return "按计划 §3.2/§6.1 保留原件供附件阅读与核对，不建立全文文本索引。"
    if disposition == "catalog_only":
        return "按计划 §3.2/§6.1 仅登记目录、容器或配置快照，不进入正文索引。"
    if disposition == "deferred":
        return "运行日志/过程数据，采集时间、完整性与用途未确认，暂缓处置（计划 §3.2）。"
    if disposition == "excluded":
        return "Office 临时锁文件，无正文内容，按计划 §2.2 排除。"
    raise ValueError(f"no reason for {path!r}: {disposition}/{action}")


def notes_for(row: dict, disposition: str) -> str:
    path = row["path"]
    parts: list[str] = []

    csv_note = (row.get("note") or "").strip()
    if csv_note:
        parts.append(csv_note)

    special = SPECIAL_NOTES.get(path)
    if special:
        parts.append(special)

    if disposition == "text_index":
        joined_so_far = "".join(parts)
        if row.get("handling") == "ocr" and "未 OCR" not in joined_so_far:
            parts.append("未 OCR；页数与文本层状态来自 inventory.clean.json。")
        elif row.get("handling") == "convert":
            parts.append("未做 docx/pptx→PDF 转换与版式保真检查（ANALYSIS §7）。")
        if (
            row.get("pages")
            and row.get("pages_without_text")
            and "无文本层" not in joined_so_far
        ):
            parts.append(
                f"inventory 记录 {row['pages_without_text']} 页无文本层，入库时需逐页复核并补 OCR。"
            )
        if not row.get("pages") and "未读全文" not in joined_so_far:
            parts.append("未读全文；业务类型与版本按文件名/目录/批次分析草案判断。")

    if disposition == "catalog_only" and path.startswith("3 样机验收/米清茹补充材料/代码/"):
        parts.append("IP 表/配置脚本；未执行、未读取内容，未联网；访问范围待确认。")
    if disposition == "deferred":
        parts.append("未读取日志内容；未联网；待确认是否作为版本化附件保留。")

    if path in (
        "3 样机验收/陈广花补充材料/一号测试厅归档文档.rar",
        "归档文档（202310）/2023控制系统硬线项目归档文件(1).zip",
    ):
        parts.append("压缩包未展开；最终是否展开子文件需按同一审查流程另行确认。")

    # Normalize and de-duplicate while preserving order.  Chinese notes often
    # end with a full stop; joining with "；" should not produce "。；".
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        part = part.strip().strip("；;。 ")
        if part and part not in seen:
            out.append(part)
            seen.add(part)
    return "；".join(out) if out else "候选记录；未读全文，待人工确认。"


# ---------------------------------------------------------------------------
# Version-family candidates
# ---------------------------------------------------------------------------

def m(kind: str, value: str, label: str) -> dict:
    return {"kind": kind, "value": value, "revision_label": label}


def manual_family_members(rows: list[dict]) -> list[dict]:
    members = []
    manual_prefixes = ("操作手册/", "归档文档（202310）/", "归档文档（202410）/")
    for row in rows:
        path = row["path"]
        if not path.startswith(manual_prefixes):
            continue
        if classify_document_kind(path) != "operation_manual":
            continue
        if "第三版" in path:
            label = "第三版（2024-11；目录名）"
        elif "第二版" in path:
            label = "第二版（2023-12；目录名/文件名）"
        elif path.startswith("归档文档（202310）"):
            label = "2023 归档副本（与第一版/第二版关系待确认）"
        elif path.startswith("归档文档（202410）"):
            label = "2024 归档副本（手册代次待确认）"
        else:
            label = "第一版（目录/CSV 标注；日期 unknown）"
        members.append(m("batch_path", path, label))
    return members


def build_families(rows: list[dict]) -> list[dict]:
    families = [
        {
            "family_id": "accelerator-overall-design",
            "title": "加速器总体设计（2017 初步设计 / 2024 优化设计 V6 / 控制章节）",
            "description": (
                "同一装置总体设计的不同代次与章节。仅建立候选关系；"
                "V6 是否批准、是否整篇替代 2017 版尚未确认。"
            ),
            "members": [
                m(
                    "legacy_doc_id",
                    "shine-accelerator-preliminary-design-report-2017",
                    "初步设计报告（加速器分册）2017-12-26（registry version）",
                ),
                m(
                    "batch_path",
                    "1、硬X射线自由电子激光装置优化设计报告-加速器分册V6（返回通读版本）.docx",
                    "优化设计 V6；文件名含“返回通读版本”，批准状态 unknown",
                ),
                m(
                    "batch_path",
                    "六、加速器控制20240422.docx",
                    "2024-04-22 工程设计报告·加速器控制章（文件名）",
                ),
            ],
            "relation": "version_and_scope_candidate",
            "confidence": "medium",
            "evidence": (
                "ANALYSIS §4.3 对比 2018 初步设计 8 GeV 与 V6 7.2 GeV；"
                "ANALYSIS 附录 A 将 V6 与控制章列为 P0；"
                "计划 §6.2 要求梳理“既有初步设计、优化设计 V6、控制章节之间的范围关系”。"
            ),
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-total-control-integration-design",
            "title": "总控集成系统设计（2022 技术设计 / 评审申请书 / 2024-10 设计报告）",
            "description": (
                "总控集成系统的技术设计、评审申请与 2024-10 后续设计报告。"
                "是否与 2018 初步设计构成同一文档族，需全文与版本记录确认。"
            ),
            "members": [
                m(
                    "batch_path",
                    "归档文档（20221117）/1.总控集成系统技术设计报告.docx",
                    "2022 技术设计（归档文档（20221117）批次）",
                ),
                m(
                    "batch_path",
                    "归档文档（20221117）/5.总控集成系统研制设备设计评审申请书.docx",
                    "2022 评审申请书（归档批次）",
                ),
                m(
                    "batch_path",
                    "归档文档（202410）/SHINE Accelerator Control System.docx",
                    "2024-10 总控集成系统设计报告（封面；英文正文）",
                ),
            ],
            "relation": "related_design_series",
            "confidence": "medium",
            "evidence": (
                "ANALYSIS §2 列出 2022 技术设计 15 份，包含总控集成、设备控制、上层应用软件；"
                "ANALYSIS §4.1 引用《总控集成系统技术设计报告》按五项功能分层；"
                "2024 归档的 SHINE Accelerator Control System 首段显示“总控集成系统设计报告，2024年10月”。"
            ),
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-equipment-control-design",
            "title": "设备控制系统设计（2018 初步设计 / 2022 技术设计 / 2024 数据交互）",
            "description": (
                "设备控制子系统的初步设计、技术设计与 OPI/IOC/PLC 数据交互说明。"
            ),
            "members": [
                m("batch_path", "1 硬线工程/12. 设备控制初步设计报告.docx", "初步设计（2018–2019 批次）"),
                m(
                    "batch_path",
                    "归档文档（20221117）/2.设备控制系统技术设计报告.docx",
                    "2022 技术设计（归档批次）",
                ),
                m(
                    "batch_path",
                    "归档文档（20221117）/6.设备控制研制设备设计评审申请书.docx",
                    "2022 评审申请书（归档批次）",
                ),
                m(
                    "batch_path",
                    "归档文档（202410）/SHINE OPI、IOC、PLC之间数据交互.docx",
                    "2024 归档·OPI/IOC/PLC 数据交互",
                ),
            ],
            "relation": "version_family",
            "confidence": "medium",
            "evidence": (
                "ANALYSIS §2：2018–2019 初步设计含设备控制；2022 技术设计含设备控制系统；"
                "2024 归档含 OPI、IOC、PLC 数据交互。文件名提供同名子系统证据。"
            ),
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-upper-software-design",
            "title": "上层应用软件设计（2018 初步设计 / 2022 技术设计）",
            "description": "上层软件/上层应用软件子系统的初步设计、技术设计与评审申请。",
            "members": [
                m("batch_path", "1 硬线工程/10. 上层软件初步设计报告.docx", "初步设计（2018–2019 批次）"),
                m(
                    "batch_path",
                    "归档文档（20221117）/4.上层应用软件系统技术设计报告.docx",
                    "2022 技术设计（归档批次）",
                ),
                m(
                    "batch_path",
                    "归档文档（20221117）/8.上层应用软件系统研制设备设计评审申请书.docx",
                    "2022 评审申请书（归档批次）",
                ),
            ],
            "relation": "version_family",
            "confidence": "medium",
            "evidence": (
                "ANALYSIS §2：2018–2019 初步设计含上层软件；"
                "2022 技术设计含上层应用软件系统技术设计报告与评审申请书。"
            ),
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-interlock-system-design",
            "title": "联锁系统设计（2019 初步 / 2022 技术 / 2022 运行模式 / 2024 远程下装与温度联锁）",
            "description": (
                "机器联锁/快联锁子系统的初步设计、技术设计、运行模式设计及后续专题设计。"
                "技术设计是否整篇替代初步设计、快联锁样机是否属于同一族，均待确认。"
            ),
            "members": [
                m("batch_path", "1 硬线工程/23. 联锁系统初步设计报告.docx", "初步设计 2019-10（封面）"),
                m(
                    "batch_path",
                    "归档文档（20221117）/3.联锁系统技术设计报告.docx",
                    "技术设计 2022-07（封面）",
                ),
                m(
                    "batch_path",
                    "归档文档（20221117）/11.联锁系统运行模式设计报告.pdf",
                    "2022 技术设计·运行模式（归档批次）",
                ),
                m(
                    "batch_path",
                    "归档文档（20221117）/7.联锁研制设备设计评审申请书.docx",
                    "2022 评审申请书（归档批次）",
                ),
                m(
                    "batch_path",
                    "归档文档（202410）/SHINE快联锁系统远程控制系统搭建及下装测试技术报告20241028.docx",
                    "2024-10-28 远程控制/下装测试（文件名）",
                ),
                m(
                    "batch_path",
                    "归档文档（202410）/SHINE磁铁电源及温度联锁设计报告.docx",
                    "2024 归档·磁铁电源温度联锁",
                ),
            ],
            "relation": "version_family",
            "confidence": "high",
            "evidence": (
                "ANALYSIS §2/§4.1 列出联锁初步设计、技术设计、运行模式设计、快联锁样机与远程下装测试；"
                "计划 §6.2 要求建立分系统设计初步/技术/研制总结关系。"
            ),
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-timing-system-design",
            "title": "定时系统设计（2018 初步/样机 / 2023 监控 / 2024–2025 归档）",
            "description": (
                "主定时、定时样机、定时网络监控、L1 段定时与诊断平台的历年说明。"
                "设计指标与实测口径、样机代次和各归档关系待确认。"
            ),
            "members": [
                m("batch_path", "1 硬线工程/5. 主定时系统初步设计报告.docx", "初步设计 2018-12（封面）"),
                m("batch_path", "2 重大专项/11. 定时样机设计报告.pdf", "样机设计 2018-07（封面）"),
                m("batch_path", "2 重大专项/12. 定时样机评审报告.pptx", "样机评审（日期 unknown）"),
                m(
                    "batch_path",
                    "归档文档（20251119）/2025硬线归档/硬X射线自由电子激光装置项目L1段定时系统研制总结.docx",
                    "L1 段研制总结 2025-11（封面）",
                ),
                m(
                    "batch_path",
                    "归档文档（20251119）/2025硬线归档/硬X射线自由电子激光装置项目SHINE定时系统分析诊断平台设计报告.docx",
                    "2025 归档·诊断平台设计",
                ),
                m(
                    "batch_path",
                    "归档文档（20251119）/2025硬线归档/硬X射线自由电子激光装置项目定时EPICS-SNMP模块配置以及IOC建立说明.docx",
                    "2025 归档·EPICS-SNMP/IOC 配置",
                ),
                m(
                    "batch_path",
                    "归档文档（202410）/SHINE定时系统devSnmp模块配置方法及IOC建立说明20241028.docx",
                    "2024-10-28 devSnmp/IOC 配置（文件名）",
                ),
                m(
                    "batch_path",
                    "归档文档（202410）/SHINE注入器段定时系统安装测试情况总结.docx",
                    "2024 归档·注入器段定时安装测试",
                ),
                m(
                    "batch_path",
                    "归档文档（202310）/2023控制系统硬线项目归档文件(1)/2023控制系统硬线项目归档文件/硬X射线自由电子激光装置项目基于Nagios 的White Rabbit定时网络监控系统设计报告.docx",
                    "2023 归档·Nagios/White Rabbit 监控",
                ),
                m(
                    "batch_path",
                    "归档文档（202310）/2023控制系统硬线项目归档文件(1)/2023控制系统硬线项目归档文件/硬X射线自由电子激光装置项目基于SNMP的定时网络监控系统设计报告.docx",
                    "2023 归档·SNMP 监控",
                ),
                m(
                    "batch_path",
                    "归档文档（202310）/基于Nagios 的White Rabbit定时网络监控系统设计报告.docx",
                    "2023 归档根目录·Nagios/White Rabbit 监控（与嵌套目录同名，字符数不同）",
                ),
                m(
                    "batch_path",
                    "归档文档（202310）/基于SNMP的定时网络监控系统设计报告.docx",
                    "2023 归档根目录·SNMP 监控（与嵌套目录同名，字符数不同）",
                ),
                m(
                    "batch_path",
                    "归档文档（202310）/2023控制系统硬线项目归档文件(1)/2023控制系统硬线项目归档文件/硬X射线自由电子激光装置项目定时系统节点验收测试报告.docx",
                    "2023 归档·定时节点验收测试",
                ),
            ],
            "relation": "version_and_evidence_chain",
            "confidence": "medium",
            "evidence": (
                "ANALYSIS §2 列出主定时初步设计、定时样机、2023/2024/2025 定时归档；"
                "ANALYSIS §4.1 引用定时样机设计指标并与 L1 段研制总结对照。"
            ),
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-control-network-design",
            "title": "控制网络设计（2018 初步 / 2023 网络配置 / 2024 装置网络）",
            "description": "控制网络子系统的初步设计、网络配置与后续装置控制网络设计。",
            "members": [
                m("batch_path", "1 硬线工程/4. 控制网络初步设计报告.docx", "初步设计（2018–2019 批次）"),
                m(
                    "batch_path",
                    "归档文档（202410）/SHINE装置控制网络设计报告.docx",
                    "2024 归档·装置控制网络设计",
                ),
                m(
                    "batch_path",
                    "OPI及IOC控制器网络配置（2023.0905）.docx",
                    "2023-09-05 网络配置（文件名）",
                ),
            ],
            "relation": "version_family",
            "confidence": "medium",
            "evidence": (
                "ANALYSIS §2 列出控制网络初步设计与 2024 装置控制网络设计报告；"
                "文件名显示 OPI/IOC 控制器网络配置。"
            ),
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-data-storage-and-archive",
            "title": "数据存储与存档（2018 初步 / 2023 设计 / 2024 Archiver / 2025 安全管理）",
            "description": (
                "数据存储、通道存档、查询软件与 Archiver 的历年设计，"
                "以及 2025 年设备运行数据安全管理。"
            ),
            "members": [
                m("batch_path", "1 硬线工程/7. 数据存储初步设计报告.docx", "初步设计（2018–2019 批次）"),
                m("batch_path", "1 硬线工程/8. 通道数据存档初步设计报告.docx", "初步设计（2018–2019 批次）"),
                m(
                    "batch_path",
                    "3 样机验收/米清茹补充材料/网页访问mysql数据库设计.docx",
                    "数据库设计（日期 unknown）",
                ),
                m(
                    "batch_path",
                    "归档文档（202310）/2023控制系统硬线项目归档文件(1)/2023控制系统硬线项目归档文件/硬X射线自由电子激光装置项目数据存储系统设计报告.doc",
                    "2023 归档·数据存储",
                ),
                m(
                    "batch_path",
                    "归档文档（202310）/2023控制系统硬线项目归档文件(1)/2023控制系统硬线项目归档文件/硬X射线自由电子激光装置项目数据存档系统查询软件设计报告.doc",
                    "2023 归档·存档查询软件",
                ),
                m(
                    "batch_path",
                    "归档文档（202410）/SHINE基于Django的Archiver Appliance.docx",
                    "2024 归档·Django Archiver",
                ),
                m(
                    "batch_path",
                    "归档文档（20251119）/2025硬线归档/SHINE加速器设备运行数据的安全管理.docx",
                    "2025 归档·运行数据安全管理",
                ),
            ],
            "relation": "version_family",
            "confidence": "medium",
            "evidence": (
                "ANALYSIS §2 列出数据存储/通道存档初步设计、2023 数据存储与存档查询、"
                "2024 Django Archiver、2025 运行数据安全。"
            ),
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-ioc-management",
            "title": "IOC 管理与安装维护（设计规范 / 管理规范 / 2024–2025 模板、开发、安装）",
            "description": (
                "IOC 设计规范、管理规范、Git/GitLab 使用说明，以及 2024–2025 年"
                "IOC 模板建立、应用开发、设备安装维护和 EPICS 模块安装。"
            ),
            "members": [
                m(
                    "batch_path",
                    "归档文档（20251119）/2025硬线归档/SHINE IOC 模板建立.docx",
                    "2025 归档·IOC 模板建立",
                ),
                m(
                    "batch_path",
                    "归档文档（20251119）/2025硬线归档/SHINE IOC应用开发建立说明.docx",
                    "2025 归档·IOC 应用开发",
                ),
                m(
                    "batch_path",
                    "归档文档（20251119）/2025硬线归档/SHINE IOC设备安装维护说明.docx",
                    "2025 归档·IOC 设备安装维护",
                ),
                m(
                    "batch_path",
                    "3 样机验收/米清茹补充材料/Git及GitLab的使用说明.docx",
                    "Git/GitLab 使用说明（日期 unknown）",
                ),
                m(
                    "batch_path",
                    "3 样机验收/米清茹补充材料/IOC设计规范-v1.2.docx",
                    "IOC 设计规范 v1.2（文件名）",
                ),
                m(
                    "batch_path",
                    "SHINE注入器段IOC管理规范文档（20230908）-陈广花.docx",
                    "IOC 管理规范 2023-09-08（文件名）",
                ),
                m(
                    "batch_path",
                    "归档文档（202410）/SHINE EPICS模块详细安装步骤.docx",
                    "2024 归档·EPICS 模块安装",
                ),
            ],
            "relation": "series",
            "confidence": "medium",
            "evidence": (
                "ANALYSIS §2 列出 2025 IOC 模板/开发/安装维护、米清茹 IOC 设计规范与 GitLab、"
                "2023 IOC 管理规范；计划 §6.2 要求梳理 IOC 历年说明关系。"
            ),
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-power-supply-control-design",
            "title": "电源与功率源控制（2018 初步 / 2024 PDU / 2025 热备电源）",
            "description": (
                "电源分配单元、电源控制、常规功率源、束流分配及功率源的初步设计，"
                "以及 2024 控制系统 PDU 和 2025 热备电源设计。"
            ),
            "members": [
                m("batch_path", "1 硬线工程/13. 电源分配单元初步设计报告.docx", "PDU 初步设计（2018–2019 批次）"),
                m("batch_path", "1 硬线工程/16. 电源控制系统初步设计报告.docx", "电源控制初步设计（2018–2019 批次）"),
                m("batch_path", "1 硬线工程/20. 常规功率源控制初步设计报告.docx", "常规功率源初步设计 2018-11（封面）"),
                m("batch_path", "1 硬线工程/21. 束流分配及功率源控制初步设计报告.docx", "束流分配及功率源初步设计 2018-10（封面）"),
                m(
                    "batch_path",
                    "归档文档（20251119）/2025硬线归档/基于SNMP的电源分配单元设计报告.docx",
                    "2025 归档·SNMP PDU 设计",
                ),
                m(
                    "batch_path",
                    "归档文档（202410）/SHINE控制系统电源分配单元.docx",
                    "2024 归档·控制系统 PDU",
                ),
                m(
                    "batch_path",
                    "归档文档（20251119）/2025硬线归档/SHINE 热备电源控制系统设计报告-2025.09.11.docx",
                    "2025-09-11 热备电源（文件名）",
                ),
            ],
            "relation": "version_family",
            "confidence": "medium",
            "evidence": (
                "ANALYSIS §2 列出电源分配单元/电源控制/常规功率源/束流分配初步设计、"
                "2024 PDU、2025 热备电源。"
            ),
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-vacuum-control-design",
            "title": "真空控制设计（2018 初步 / 2018 样机评审 / 2024 注入段总结）",
            "description": "真空控制子系统的初步设计、样机设计评审与注入段真空控制总结。",
            "members": [
                m("batch_path", "1 硬线工程/14. 真空控制系统初步设计报告.docx", "初步设计（2018–2019 批次）"),
                m("batch_path", "1 硬线工程/15. 真空控制样机设计评审报告.pptx", "2018–2019 真空样机设计评审"),
                m(
                    "batch_path",
                    "归档文档（202410）/SHINE直线加速器注入段真空设备控制总结报告.docx",
                    "2024 归档·注入段真空控制总结",
                ),
            ],
            "relation": "version_family",
            "confidence": "medium",
            "evidence": (
                "ANALYSIS §2 列出真空控制初步设计、真空样机评审、2024 注入段真空总结。"
            ),
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-motion-control-design",
            "title": "运动控制设计（2018 初步 / 2022 四自由度平台远程控制）",
            "description": "波荡器及段间运动控制、集成电机运动控制与四自由度平台远程控制。",
            "members": [
                m("batch_path", "1 硬线工程/17. 波荡器及段间运动控制初步设计报告.docx", "初步设计（2018–2019 批次）"),
                m("batch_path", "1 硬线工程/18. 集成电机运动控制初步设计报告.docx", "初步设计（2018–2019 批次）"),
                m(
                    "batch_path",
                    "归档文档（20221117）/10.四自由度运动平台远程控制.docx",
                    "2022 技术设计·四自由度平台远程控制",
                ),
            ],
            "relation": "version_family",
            "confidence": "medium",
            "evidence": (
                "ANALYSIS §2 列出波荡器及段间运动控制、集成电机运动控制初步设计、"
                "2022 四自由度平台远程控制。"
            ),
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-alarm-system-design",
            "title": "报警系统设计（2018 初步 / 2022 安装配置）",
            "description": "报警系统初步设计与 2022 年报警系统安装配置报告。",
            "members": [
                m("batch_path", "1 硬线工程/11. 报警系统初步设计报告.docx", "初步设计（2018–2019 批次）"),
                m(
                    "batch_path",
                    "归档文档（20221117）/13.报警系统安装配置报告.pdf",
                    "2022 技术设计·报警安装配置",
                ),
            ],
            "relation": "version_family",
            "confidence": "medium",
            "evidence": "ANALYSIS §2 列出报警系统初步设计与 2022 报警系统安装配置报告。",
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-control-standards-2024",
            "title": "总控相关标准和规范（2024 合并版 / 5 份单项 / 扫描副本）",
            "description": (
                "2024 合并版规范、5 份单项规范，以及 1 硬线工程下的两份扫描副本。"
                "合并版已由 ANALYSIS 确认完整包含单项规范正文；扫描副本的等价关系待确认。"
            ),
            "members": [
                m(
                    "batch_path",
                    "SHINE-OP-TL-002 2024 总控相关标准和规范.pdf",
                    "2024 合并版（文件名）",
                ),
                m("batch_path", "总控相关标准和规范/EPICS软件版本规范.pdf", "单项规范（日期 unknown）"),
                m("batch_path", "总控相关标准和规范/PyDM界面设计规范.pdf", "单项规范（日期 unknown）"),
                m("batch_path", "总控相关标准和规范/数据格式与存储规范.pdf", "单项规范（日期 unknown）"),
                m("batch_path", "总控相关标准和规范/联锁系统硬件信号接口规范.pdf", "单项规范（日期 unknown）"),
                m(
                    "batch_path",
                    "总控相关标准和规范/设备控制及通讯接口标准规范-xin.pdf",
                    "单项规范（日期 unknown）",
                ),
                m(
                    "batch_path",
                    "1 硬线工程/25. 联锁系统硬件信号接口规格.pdf",
                    "扫描副本（3 页；与文本版等价待确认）",
                ),
                m(
                    "batch_path",
                    "1 硬线工程/26. 设备控制及通讯接口标准.pdf",
                    "扫描副本（2 页；与文本版等价待确认）",
                ),
            ],
            "relation": "contains_and_equivalent",
            "confidence": "high",
            "evidence": (
                "ANALYSIS §4.2 确认 2024 合并版完整包含 5 份单项规范正文；"
                "ANALYSIS §3.2 指出 1 硬线工程/25、26 为扫描件且已有文本版；"
                "计划 §6.2 要求梳理合并版/单项/扫描副本关系。"
            ),
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-device-naming-rules",
            "title": "设备与控制信号命名规则（编号表 / 信号 / 机柜 / 命名 / 技术代号）",
            "description": (
                "系统代号表、控制信号命名规则、机柜命名规则、设备命名规则、"
                "技术代号规则及 2023 年专题会纪要。属于相关规范簇，不是同一文档的多个修订。"
            ),
            "members": [
                m("batch_path", "SHINE-AC编号.docx", "系统代号表（日期 unknown）"),
                m("batch_path", "SHINE控制信号命名规则-签发版.pdf", "签发版（日期 unknown）"),
                m("batch_path", "机柜命名规则.pptx", "机柜命名规则（日期 unknown）"),
                m(
                    "batch_path",
                    "20230613加速器总体设备命名规则专题会纪要.pdf",
                    "2023-06-13 专题会纪要（文件名）",
                ),
                m(
                    "batch_path",
                    "序号24-SHINE-OP-TL-018- 设备命名规则-R0-20190903.pdf",
                    "SHINE-OP-TL-018 R0（2019-09-03，文件名）",
                ),
                m(
                    "batch_path",
                    "附件-SHINE-OP-TL-004-2022-SHINE项目技术代号规则-20220926.pdf",
                    "SHINE-OP-TL-004（2022-09-26，文件名）",
                ),
            ],
            "relation": "related_normative_cluster",
            "confidence": "medium",
            "evidence": (
                "ANALYSIS §2 列出 SHINE-AC 编号、控制信号命名规则、机柜命名规则、"
                "命名规则专题会纪要、SHINE-OP-TL-018/004；文件名与标准号提供关联证据。"
            ),
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-control-operation-manual-series",
            "title": "控制系统界面操作手册（第一版 / 第二版 / 第三版 / 归档副本）",
            "description": (
                "控制系统各功能界面的操作手册合集。第一版、第二版（2023-12）、"
                "第三版（2024-11）与 2023/2024 归档副本之间的关系。"
                "统一族仅用于候选分组；具体功能是否逐一手册形成独立版本链，待确认。"
            ),
            "members": manual_family_members(rows),
            "relation": "series",
            "confidence": "medium",
            "evidence": (
                "ANALYSIS §2 列出操作手册 23 份第一/二/三版；"
                "ANALYSIS §4.2 指出 3 组操作手册与 2023 归档完全重复；"
                "目录名含第一版/第二版（20231206）/第三版（202411）。"
            ),
            "needs_confirmation": True,
        },
        {
            "family_id": "shine-prototype-fast-interlock-acceptance",
            "title": "快联锁样机测试与验收证据链",
            "description": (
                "快联锁样机的设计、评审、测试大纲、自测、测试报告、研制总结、"
                "验收申请、验收书与验收评审。"
            ),
            "members": [
                m("batch_path", "2 重大专项/8. 快联锁样机设计报告.docx", "样机设计 2018-07（封面）"),
                m("batch_path", "2 重大专项/9. 快联锁样机评审报告.pptx", "样机设计评审（日期 unknown）"),
                m("batch_path", "2 重大专项/10. 快联锁样机工艺设计评审报告.pptx", "工艺设计评审（日期 unknown）"),
                m("batch_path", "3 样机验收/快联锁样机测试大纲.docx", "测试大纲（日期 unknown）"),
                m("batch_path", "3 样机验收/快联锁样机自测报告.docx", "自测报告 2021-06-12（封面）"),
                m("batch_path", "3 样机验收/快联锁样机测试报告.pdf", "测试报告（17 页扫描件，未 OCR）"),
                m("batch_path", "3 样机验收/快联锁样机研制总结报告.docx", "研制总结 2021-06（封面）"),
                m("batch_path", "3 样机验收/快联锁样机验收申请书.docx", "验收申请书（日期 unknown）"),
                m("batch_path", "3 样机验收/快联锁样机验收书.docx", "验收书（日期 unknown）"),
                m("batch_path", "3 样机验收/快联锁样机验收评审报告.pdf", "验收评审报告 2021-06-17（封面）"),
                m("batch_path", "3 样机验收/快联锁样机验收评审报告.pptx", "验收评审报告（演示稿；日期 unknown）"),
            ],
            "relation": "evidence_chain",
            "confidence": "high",
            "evidence": (
                "ANALYSIS §2 将 3 样机验收描述为测试大纲、自测报告、测试报告、研制总结、"
                "验收书、验收评审；文件名显示快联锁同一证据链；ANALYSIS §4.1 引用快联锁设计指标。"
            ),
            "needs_confirmation": False,
        },
        {
            "family_id": "shine-prototype-constant-temperature-cabinet-acceptance",
            "title": "恒温机柜控制样机测试与验收证据链",
            "description": "恒温机柜控制样机的设计、测试大纲、自测、测试报告、研制总结与验收材料。",
            "members": [
                m("batch_path", "3 样机验收/恒温机柜控制设计报告.docx", "设计报告（日期 unknown）"),
                m("batch_path", "3 样机验收/恒温机柜控制测试大纲.docx", "测试大纲（日期 unknown）"),
                m("batch_path", "3 样机验收/恒温机柜控制自测报告.docx", "自测报告（日期 unknown）"),
                m("batch_path", "3 样机验收/恒温机柜控制样机测试报告.pdf", "测试报告（7 页扫描件，未 OCR）"),
                m("batch_path", "3 样机验收/恒温机柜控制研制总结报告.docx", "研制总结（日期 unknown）"),
                m("batch_path", "3 样机验收/恒温机柜样机控制验收申请书.docx", "验收申请书（日期 unknown）"),
                m("batch_path", "3 样机验收/恒温机柜样机控制验收书.docx", "验收书（日期 unknown）"),
                m("batch_path", "3 样机验收/恒温机柜控制样机验收评审报告.pptx", "验收评审报告（日期 unknown）"),
            ],
            "relation": "evidence_chain",
            "confidence": "high",
            "evidence": (
                "ANALYSIS §2 将 3 样机验收描述为测试大纲、自测报告、测试报告、研制总结、"
                "验收书、验收评审；文件名显示恒温机柜同一证据链。"
            ),
            "needs_confirmation": False,
        },
        {
            "family_id": "shine-prototype-control-system-development-environment-acceptance",
            "title": "控制系统开发环境样机测试与验收证据链",
            "description": "控制系统开发环境样机的设计、评审、测试、研制总结与验收材料。",
            "members": [
                m("batch_path", "2 重大专项/3. 控制系统开发环境样机设计报告.docx", "样机设计（日期 unknown）"),
                m("batch_path", "2 重大专项/4. 控制系统开发环境样机评审报告.pptx", "样机评审（日期 unknown）"),
                m("batch_path", "3 样机验收/控制系统开发环境样机测试大纲.docx", "测试大纲（日期 unknown）"),
                m("batch_path", "3 样机验收/控制系统开发环境自测报告.docx", "自测报告（日期 unknown）"),
                m("batch_path", "3 样机验收/控制系统开发环境样机测试报告.pdf", "测试报告（11 页扫描件，未 OCR）"),
                m("batch_path", "3 样机验收/控制系统开发环境样机研制总结报告.docx", "研制总结（日期 unknown）"),
                m("batch_path", "3 样机验收/控制系统开发环境样机验收申请书.docx", "验收申请书（日期 unknown）"),
                m("batch_path", "3 样机验收/控制系统开发环境样机验收书.docx", "验收书（日期 unknown）"),
                m("batch_path", "3 样机验收/控制系统开发环境样机验收评审报告.pdf", "验收评审报告（日期 unknown）"),
                m("batch_path", "3 样机验收/控制系统开发环境样机验收评审报告.pptx", "验收评审报告（演示稿；日期 unknown）"),
            ],
            "relation": "evidence_chain",
            "confidence": "high",
            "evidence": (
                "ANALYSIS §2 将 3 样机验收描述为测试大纲、自测报告、测试报告、研制总结、"
                "验收书、验收评审；文件名显示控制系统开发环境同一证据链。"
            ),
            "needs_confirmation": False,
        },
        {
            "family_id": "shine-prototype-vacuum-control-acceptance",
            "title": "真空设备控制样机测试与验收证据链",
            "description": "真空设备控制样机的设计评审、测试、研制总结与验收材料。",
            "members": [
                m("batch_path", "3 样机验收/真空设备控制样机设计评审报告.pptx", "设计评审报告（日期 unknown）"),
                m("batch_path", "3 样机验收/真空设备控制样机测试大纲.docx", "测试大纲（日期 unknown）"),
                m("batch_path", "3 样机验收/真空设备控制样机自测报告.docx", "自测报告（日期 unknown）"),
                m("batch_path", "3 样机验收/真空设备控制样机测试报告.pdf", "测试报告（12 页扫描件，未 OCR）"),
                m("batch_path", "3 样机验收/真空设备控制样机研制总结报告.docx", "研制总结（日期 unknown）"),
                m("batch_path", "3 样机验收/真空设备控制样机验收申请书.docx", "验收申请书（日期 unknown）"),
                m("batch_path", "3 样机验收/真空设备控制样机验收书.docx", "验收书（日期 unknown）"),
                m("batch_path", "3 样机验收/真空设备控制样机验收评审报告.pptx", "验收评审报告（日期 unknown）"),
            ],
            "relation": "evidence_chain",
            "confidence": "high",
            "evidence": (
                "ANALYSIS §2 将 3 样机验收描述为测试大纲、自测报告、测试报告、研制总结、"
                "验收书、验收评审；文件名显示真空设备控制同一证据链。"
            ),
            "needs_confirmation": False,
        },
        {
            "family_id": "shine-prototype-high-frame-rate-image-acquisition-acceptance",
            "title": "高帧率图像采集样机测试与验收证据链",
            "description": "高帧率图像采集样机的设计、评审、测试、研制总结与验收材料。",
            "members": [
                m("batch_path", "2 重大专项/5. 高帧率图像采集处理样机设计报告.docx", "样机设计（日期 unknown）"),
                m("batch_path", "2 重大专项/6. 高频率图像采集处理样机评审报告.pptx", "样机评审（日期 unknown）"),
                m("batch_path", "2 重大专项/7. 高帧率图像采集处理样机工艺设计评审报告.pptx", "工艺设计评审（日期 unknown）"),
                m("batch_path", "3 样机验收/高帧率图像采集样机测试大纲.docx", "测试大纲（日期 unknown）"),
                m("batch_path", "3 样机验收/高帧率图像采集样机自测报告.docx", "自测报告（日期 unknown）"),
                m("batch_path", "3 样机验收/高帧率图像采集样机测试报告.pdf", "测试报告（6 页扫描件，未 OCR）"),
                m("batch_path", "3 样机验收/高帧率图像采集样机研制总结报告.docx", "研制总结（日期 unknown）"),
                m("batch_path", "3 样机验收/高帧率图像采集样机验收申请书.docx", "验收申请书（日期 unknown）"),
                m("batch_path", "3 样机验收/高帧率图像采集样机验收书.docx", "验收书（日期 unknown）"),
                m("batch_path", "3 样机验收/高帧率图像采集样机验收评审报告.pdf", "验收评审报告（日期 unknown）"),
                m("batch_path", "3 样机验收/高帧率图像采集样机验收评审报告.pptx", "验收评审报告（演示稿；日期 unknown）"),
            ],
            "relation": "evidence_chain",
            "confidence": "high",
            "evidence": (
                "ANALYSIS §2 将 3 样机验收描述为测试大纲、自测报告、测试报告、研制总结、"
                "验收书、验收评审；文件名显示高帧率图像采集同一证据链。"
            ),
            "needs_confirmation": False,
        },
    ]
    return families


# ---------------------------------------------------------------------------
# Conflict candidates
# ---------------------------------------------------------------------------

def build_conflicts(rows: list[dict]) -> list[dict]:
    batch_paths = {row["path"] for row in rows}
    conflicts = [
        {
            "topic": "设计能量口径：8 GeV 与 7.2 GeV",
            "revision_a": "1 硬线工程/20. 常规功率源控制初步设计报告.docx",
            "revision_b": "1、硬X射线自由电子激光装置优化设计报告-加速器分册V6（返回通读版本）.docx",
            "evidence_location": (
                "ANALYSIS §4.3；inventory.clean.json 的 head 字段："
                "常规功率源控制初步设计报告“概述”称“能量为8GeV”；"
                "V6“一、概述”称“能量7.2 GeV”；另见 1 硬线工程/21. 束流分配及功率源控制初步设计报告.docx"
                "“概述”称已加速至 8GeV。"
            ),
            "conflict_type": "design_parameter",
            "applicable_condition": (
                "2018 初步设计代次 vs 2024 优化设计 V6；需确认是否为同一设计基线、"
                "V6 是否整篇替代旧设计还是仅更新指标，以及装置运行模式/能量升级条件。"
            ),
            "owner": "待指派",
            "status": "open",
            "resolution": "",
        },
        {
            "topic": "网络安全设计报告封面日期晚于批次日期且审核栏未填写",
            "revision_a": "硬X射线自由电子激光装置网络安全设计报告.docx",
            "revision_b": "docs/roadmap/knowledge-base-v2-plan.md",
            "evidence_location": (
                "计划 §2.3 明确记录封面日期 2026 年 11 月 5 日、审核栏未填写；"
                "inventory.clean.json 的 head 字段：网络安全报告封面列编制史武军、吕慧慧、唐小丰，"
                "审核、审定、会签栏空白，日期“2026年11月5日”；计划首行编制日期为 2026 年 11 月 2 日。"
            ),
            "conflict_type": "document_metadata",
            "applicable_condition": (
                "仅封面文字；未读全文；未确认签发流程、生效日期和是否已在现场部署。"
                "不能据此断言报告无效，也不能把它当作已批准现行依据。"
            ),
            "owner": "待指派",
            "status": "needs_source_check",
            "resolution": "",
        },
        {
            "topic": "V6“返回通读版本”的批准状态与替代范围",
            "revision_a": "1、硬X射线自由电子激光装置优化设计报告-加速器分册V6（返回通读版本）.docx",
            "revision_b": "data/documents/registry.json#shine-accelerator-preliminary-design-report-2017",
            "evidence_location": (
                "V6 文件名含“返回通读版本”；计划 §2.3 明确保留原版本标签并待确认批准状态；"
                "ANALYSIS §4.3 对比 V6 与 2017/2018 设计代次；"
                "registry.json 中 2017 初步设计报告 version=初步设计报告 (2017-12-26)，status=reference。"
            ),
            "conflict_type": "approval_status",
            "applicable_condition": (
                "V6 是否正式批准、替代整篇还是部分章节、生效时间均 unknown；"
                "2017 版仅为登记参考，未确认现行。两者不能同权检索。"
            ),
            "owner": "待指派",
            "status": "needs_source_check",
            "resolution": "",
        },
        {
            "topic": "白兔定时设计指标与原型实测口径",
            "revision_a": "2 重大专项/11. 定时样机设计报告.pdf",
            "revision_b": "归档文档（20251119）/2025硬线归档/硬X射线自由电子激光装置项目L1段定时系统研制总结.docx",
            "evidence_location": (
                "ANALYSIS §4.1 称定时样机设计报告给出时钟精度 1 ns、抖动 <30 ps，属设计指标；"
                "inventory.clean.json 的 head：定时样机评审报告列“时钟脉冲信号精度达到1ns，抖动小于30ps”；"
                "L1 段研制总结“技术指标”仅写“定时系统时钟脉冲信号抖动小于30ps”。"
                "就目前可见摘录/首段而言，三处均未给出原型 II 实测值、测量设备、积分带宽和时间窗口；需读全文确认。"
            ),
            "conflict_type": "design_vs_measured",
            "applicable_condition": (
                "设计指标 vs 研制总结技术指标 vs 原型实测；需确认样机代次（原型 I/II）、"
                "测量点和统计口径后才能回答“实测抖动是多少”。"
            ),
            "owner": "待指派",
            "status": "needs_source_check",
            "resolution": "",
        },
        {
            "topic": "快联锁响应时间的测量范围（站内/站间、FPGA/PLC）",
            "revision_a": "2 重大专项/8. 快联锁样机设计报告.docx",
            "revision_b": "3 样机验收/快联锁样机自测报告.docx",
            "evidence_location": (
                "ANALYSIS §4.1：设计报告称单节点信号响应 <10 µs、整系统故障响应 <100 µs，"
                "FPGA 快保护约 11.8 µs、PLC 约 33 ms；"
                "inventory.clean.json 的 head：快联锁样机自测报告称“站点内响应时间小于10 μs、"
                "站点间响应时间小于100 μs”；快联锁样机测试报告.pdf 为 17 页扫描件，未 OCR。"
            ),
            "conflict_type": "measurement_scope",
            "applicable_condition": (
                "站点内 vs 站点间；FPGA vs PLC；设计指标 vs 实测值。"
                "需核对测试报告/验收评审报告中的测量通道、触发条件和统计口径。"
            ),
            "owner": "待指派",
            "status": "needs_source_check",
            "resolution": "",
        },
        {
            "topic": "准直器操作手册第一版与第三版操作步骤差异",
            "revision_a": "操作手册/SHINE准直器界面操作手册.docx",
            "revision_b": "操作手册/第三版（202411）/SHINE注入器段准直器控制界面操作手册.docx",
            "evidence_location": (
                "inventory.clean.json 的 head：第一版列 VER_ORIGIN_VEL/HOR_ORIGIN_VEL、"
                "VER_AUTO_DIST/HOR_AUTO_DIST、VER_ENABLE/HOR_ENABLE、VER_ORIGIN/HOR_ORIGIN、"
                "VER_AUTO_MV/HOR_AUTO_MV；第三版新增 ALARM_CLEAR、ONEKEY_LOC、VER_LOC/HOR_LOC、"
                "VER/HOR HOLE/GAP 等按钮。"
            ),
            "conflict_type": "operation_step",
            "applicable_condition": (
                "手册代次不同；设备/软件版本与第三版适用范围 unknown；"
                "不能默认第三版替代第一版全部步骤，也不能把两版步骤混在同一答案中。"
            ),
            "owner": "待指派",
            "status": "open",
            "resolution": "",
        },
    ]

    # Make batch-relative references self-contained.  The conflict file has no
    # batch_id field, so a bare relative path would be ambiguous outside this
    # report; use the same full source_path form as dispositions.
    for conflict in conflicts:
        for field in ("revision_a", "revision_b"):
            value = conflict[field]
            if value in batch_paths:
                conflict[field] = SOURCE_PREFIX + value
    return conflicts


# ---------------------------------------------------------------------------
# Build and validate
# ---------------------------------------------------------------------------

def load_rows(root: Path) -> list[dict]:
    csv_path = root / CSV_REL
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows


def load_inventory(root: Path) -> dict[str, dict]:
    path = root / INVENTORY_REL
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)
    return {entry["path"]: entry for entry in entries}


def check_analysis_anchors(root: Path) -> None:
    """Fail loudly if the source texts no longer contain the cited evidence."""
    analysis_text = (root / ANALYSIS_REL).read_text(encoding="utf-8")
    analysis_anchors = [
        "8 GeV",
        "7.2 GeV",
        "返回通读版本",
        "30 ps",
        "10 µs",
        "<100 µs",
        "5 组完全重复",
        "完整包含",
    ]
    missing = [anchor for anchor in analysis_anchors if anchor not in analysis_text]

    plan_text = (root / PLAN_REL).read_text(encoding="utf-8")
    plan_anchors = [
        "2026 年 11 月 5 日",
        "审核栏未填写",
        "V6 一定是正式现行版",
    ]
    missing += [anchor for anchor in plan_anchors if anchor not in plan_text]

    if missing:
        raise RuntimeError(
            "Source documents no longer contain expected evidence anchors: "
            + ", ".join(repr(item) for item in missing)
        )


def build_dispositions(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        path = row["path"]
        ext = row.get("ext", "")
        handling = row.get("handling", "")
        if handling not in HANDLING_TO_DISPOSITION and path not in EXCLUDE_DISPOSITIONS:
            raise ValueError(f"unknown CSV handling {handling!r} for {path!r}")

        if path in EXCLUDE_DISPOSITIONS:
            disposition, action = EXCLUDE_DISPOSITIONS[path]
        else:
            disposition, action = HANDLING_TO_DISPOSITION[handling]

        out.append(
            {
                "batch_id": BATCH_ID,
                "batch_relative_path": path,
                "source_path": SOURCE_PREFIX + path,
                "source_format": EXT_TO_FORMAT.get(ext.lower(), "other"),
                "document_kind": classify_document_kind(path),
                "priority": row["priority"],
                "disposition": disposition,
                "planned_action": action,
                "reason": reason_for(row, disposition, action),
                "target_family_id": "",  # filled after families are built
                "notes": notes_for(row, disposition),
            }
        )
    return out


def build_family_index(families: list[dict]) -> dict[str, str]:
    index: dict[str, str] = {}
    for family in families:
        for member in family["members"]:
            if member["kind"] != "batch_path":
                continue
            value = member["value"]
            if value in index:
                raise ValueError(
                    f"batch_path appears in more than one family: {value!r} "
                    f"({index[value]!r} and {family['family_id']!r})"
                )
            index[value] = family["family_id"]
    return index


def validate(
    rows: list[dict],
    dispositions: list[dict],
    families: list[dict],
    conflicts: list[dict],
    registry_ids: set[str],
) -> None:
    csv_paths = [row["path"] for row in rows]
    if len(rows) != EXPECTED_ROWS:
        raise AssertionError(f"expected {EXPECTED_ROWS} CSV rows, got {len(rows)}")
    if len(set(csv_paths)) != len(csv_paths):
        raise AssertionError("CSV contains duplicate paths")

    if len(dispositions) != EXPECTED_ROWS:
        raise AssertionError(f"expected {EXPECTED_ROWS} dispositions, got {len(dispositions)}")

    seen_paths = set()
    for item in dispositions:
        required = [
            "batch_id", "batch_relative_path", "source_path", "source_format",
            "document_kind", "priority", "disposition", "planned_action",
            "reason", "target_family_id", "notes",
        ]
        for field in required:
            if field not in item:
                raise AssertionError(f"missing field {field!r} in {item!r}")
        if not item["reason"].strip():
            raise AssertionError(f"empty reason for {item['batch_relative_path']!r}")
        if not item["batch_id"]:
            raise AssertionError(f"empty batch_id for {item['batch_relative_path']!r}")
        if item["source_format"] not in SOURCE_FORMATS:
            raise AssertionError(f"bad source_format {item['source_format']!r}")
        if item["document_kind"] not in DOCUMENT_KINDS:
            raise AssertionError(f"bad document_kind {item['document_kind']!r}")
        if item["priority"] not in PRIORITIES:
            raise AssertionError(f"bad priority {item['priority']!r}")
        if item["disposition"] not in DISPOSITIONS:
            raise AssertionError(f"bad disposition {item['disposition']!r}")
        if item["planned_action"] not in PLANNED_ACTIONS:
            raise AssertionError(f"bad planned_action {item['planned_action']!r}")
        if item["source_path"] != SOURCE_PREFIX + item["batch_relative_path"]:
            raise AssertionError(f"source_path prefix mismatch: {item['source_path']!r}")
        if item["source_path"] in seen_paths:
            raise AssertionError(f"duplicate source_path: {item['source_path']!r}")
        seen_paths.add(item["source_path"])

    if set(item["batch_relative_path"] for item in dispositions) != set(csv_paths):
        raise AssertionError("disposition paths do not exactly match CSV paths")

    for family in families:
        if not family["members"]:
            raise AssertionError(f"family {family['family_id']!r} has no members")
        if family["confidence"] not in {"high", "medium", "low"}:
            raise AssertionError(f"bad confidence in {family['family_id']!r}")
        for member in family["members"]:
            if member["kind"] == "batch_path":
                if member["value"] not in set(csv_paths):
                    raise AssertionError(
                        f"family {family['family_id']!r} references unknown batch path "
                        f"{member['value']!r}"
                    )
            elif member["kind"] == "legacy_doc_id":
                if member["value"] not in registry_ids:
                    raise AssertionError(
                        f"family {family['family_id']!r} references unknown legacy doc_id "
                        f"{member['value']!r}"
                    )
            else:
                raise AssertionError(f"bad member kind {member['kind']!r}")

    if not conflicts:
        raise AssertionError("no conflicts")
    for conflict in conflicts:
        required = [
            "topic", "revision_a", "revision_b", "evidence_location",
            "conflict_type", "applicable_condition", "owner", "status", "resolution",
        ]
        for field in required:
            if field not in conflict:
                raise AssertionError(f"missing conflict field {field!r}")
        if conflict["status"] not in {"open", "needs_source_check", "resolved"}:
            raise AssertionError(f"bad conflict status {conflict['status']!r}")
        if conflict["owner"] != "待指派":
            raise AssertionError(f"conflict owner must be 待指派: {conflict['owner']!r}")
        if conflict["status"] != "resolved" and conflict["resolution"] != "":
            raise AssertionError("unresolved conflict must have empty resolution")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=None,
        help="Repository root (default: parent of this script's directory)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate inputs and computed objects without writing JSON",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    check_analysis_anchors(root)
    rows = load_rows(root)
    _inventory = load_inventory(root)  # loaded for provenance; head text is cited in notes

    registry_path = root / REGISTRY_REL
    registry_ids: set[str] = set()
    if registry_path.exists():
        with open(registry_path, encoding="utf-8") as f:
            registry_ids = {entry["doc_id"] for entry in json.load(f)}

    families = build_families(rows)
    family_index = build_family_index(families)
    dispositions = build_dispositions(rows)
    for item in dispositions:
        item["target_family_id"] = family_index.get(item["batch_relative_path"], "")

    conflicts = build_conflicts(rows)
    validate(rows, dispositions, families, conflicts, registry_ids)

    dispositions_payload = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": BATCH_ID,
        "generated_on": GENERATED_ON,
        "dispositions": dispositions,
    }
    families_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_on": GENERATED_ON,
        "families": families,
    }
    conflicts_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_on": GENERATED_ON,
        "conflicts": conflicts,
    }

    if not args.check_only:
        write_json(root / "data/documents/v2/dispositions.draft.json", dispositions_payload)
        write_json(root / "data/documents/v2/family-candidates.draft.json", families_payload)
        write_json(root / "data/documents/v2/conflict-candidates.draft.json", conflicts_payload)

    # Summary for the operator / report.
    by_disposition = Counter(item["disposition"] for item in dispositions)
    by_format = Counter(item["source_format"] for item in dispositions)
    by_priority = Counter(item["priority"] for item in dispositions)
    by_action = Counter(item["planned_action"] for item in dispositions)
    family_member_count = sum(len(family["members"]) for family in families)
    covered = sum(1 for item in dispositions if item["target_family_id"])

    print(f"root: {root}")
    print(f"dispositions: {len(dispositions)}")
    print("  by disposition:", dict(sorted(by_disposition.items())))
    print("  by planned_action:", dict(sorted(by_action.items())))
    print("  by source_format:", dict(sorted(by_format.items())))
    print("  by priority:", dict(sorted(by_priority.items())))
    print(f"families: {len(families)} ({family_member_count} member entries, "
          f"{len(family_index)} distinct batch paths)")
    print(f"dispositions with target_family_id: {covered}")
    print(f"conflicts: {len(conflicts)}")
    if args.check_only:
        print("check-only: no files written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
