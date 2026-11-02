#!/usr/bin/env python3
"""复算 case-07 / case-06 的关键数字，用于独立核对 Waveform 仓库交付记录。

只读：只读取已归档的 bunchID fixture（npz），不改动 Waveform 仓库任何内容。
fixture 来源：
  /home/whloong/waveform-storage/waveform-storage-system/outputs/history-ui-validation-20261016/bunch-id-fixtures/
核对的记录：
  交付/20261016-history-quality-r1/README.md 的「2026-10-12 历史数据核验」表
  outputs/history-ui-validation-20261016/real-data-20261012-all-segments.json

运行（系统 python 无 numpy，需用项目 conda 环境）：
  /home/whloong/miniconda3/envs/waveform-storage/bin/python verify_fixtures.py
"""

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path("/home/whloong/waveform-storage/waveform-storage-system")
FIXTURE = REPO / "outputs/history-ui-validation-20261016/bunch-id-fixtures"
ALL_SEGMENTS = REPO / "outputs/history-ui-validation-20261016/real-data-20261012-all-segments.json"
REQUEST_ID = "22833275-5e77-41c5-b703-f306accde164"
SAMPLE_RATE_HZ = 500.0
POINTS_PER_DEVICE = 20000

# 交付记录 README 表格中的原始值
EXPECTED_STRICT = {0: 422, 1: 621, 2: 455, 3: 375, 4: 288}
EXPECTED_LEAVE_ONE_OUT = {0: 19570, 1: 19528, 2: 19532, 3: 19547, 4: 19542}
EXPECTED_TARGET_DEVICE = "AC_LA_L1_BI_COLDBPM05"


def strict_intersection(arrays):
    acc = arrays[0]
    for a in arrays[1:]:
        acc = np.intersect1d(acc, a, assume_unique=False)
    return acc


def check_segment(seq: int) -> dict:
    path = FIXTURE / f"{REQUEST_ID}_S{seq:05d}.npz"
    d = np.load(path, allow_pickle=True)
    devices = json.loads(str(d["device_ids_json"]))
    ids = [d[f"bunch_ids_{i:02d}"] for i in range(len(devices))]
    target = devices.index(EXPECTED_TARGET_DEVICE)

    assert all(len(x) == POINTS_PER_DEVICE for x in ids), "原始点数不是 20000"

    common = strict_intersection(ids)
    leave_one_out = strict_intersection([x for i, x in enumerate(ids) if i != target])

    steps_target = np.diff(ids[target].astype(np.int64))
    steps_majority = np.diff(ids[(target + 1) % len(ids)].astype(np.int64))

    # 分析器推算跨度：共同点按单一采样率展开（analysis/loaders.py:_id_times + engine._prepare）
    analyzer_span = (common.size - 1) / SAMPLE_RATE_HZ
    # 主流设备原始记录跨度：bunchID 按 1 MHz 计时钟换算，用于说明 case-06 的除法何时成立
    raw_span_us = (int(ids[(target + 1) % len(ids)][-1]) - int(ids[(target + 1) % len(ids)][0])) / 1e6

    return {
        "capture_sequence": seq,
        "device_count": len(devices),
        "target_device": devices[target],
        "strict_common": int(common.size),
        "fixture_recorded_common": int(d["common_bunch_ids"].size),
        "leave_one_out_common": int(leave_one_out.size),
        "target_step_min": int(steps_target.min()),
        "target_step_max": int(steps_target.max()),
        "target_step_mode": int(np.bincount(steps_target).argmax()),
        "majority_step_unique": sorted({int(x) for x in steps_majority}),
        "analyzer_span_seconds": round(float(analyzer_span), 3),
        "raw_span_seconds_via_1e6": round(float(raw_span_us), 3),
    }


def main() -> int:
    if not ALL_SEGMENTS.is_file():
        print(f"缺少证据文件：{ALL_SEGMENTS}", file=sys.stderr)
        return 2
    recorded = json.loads(ALL_SEGMENTS.read_text(encoding="utf-8"))
    recorded_by_seq = {s["capture_sequence"]: s for s in recorded["segments"]}

    rows = [check_segment(seq) for seq in range(5)]
    ok = True
    for row in rows:
        seq = row["capture_sequence"]
        rec = recorded_by_seq[seq]
        checks = [
            ("strict_common == README", row["strict_common"], EXPECTED_STRICT[seq]),
            ("strict_common == fixture", row["strict_common"], row["fixture_recorded_common"]),
            ("leave_one_out == README", row["leave_one_out_common"], EXPECTED_LEAVE_ONE_OUT[seq]),
            ("leave_one_out == all-segments.json", row["leave_one_out_common"],
             rec["leave_one_out_target"]["common_points_without_device"]),
            ("majority step == 2000", row["majority_step_unique"], [2000]),
            ("target device id", row["target_device"], EXPECTED_TARGET_DEVICE),
        ]
        for name, got, want in checks:
            if got != want:
                ok = False
                print(f"FAIL seq={seq} {name}: got={got!r} want={want!r}")
        # 保留率 1.44%–3.11% 的区间必须落在 README 记录的范围内
        retain = row["strict_common"] / POINTS_PER_DEVICE
        if not 0.014 <= retain <= 0.032:
            ok = False
            print(f"FAIL seq={seq} retained fraction out of range: {retain:.4f}")

    print(json.dumps(rows, ensure_ascii=False, indent=2))
    print()
    print("保留率：", ", ".join(
        f"S{r['capture_sequence']}={r['strict_common'] / POINTS_PER_DEVICE * 100:.2f}%"
        for r in rows))
    print("分析器推算跨度：", ", ".join(
        f"S{r['capture_sequence']}={r['analyzer_span_seconds']:.3f}s" for r in rows))
    print("主流设备原始跨度（1 MHz 计时钟换算）：", ", ".join(
        f"S{r['capture_sequence']}={r['raw_span_seconds_via_1e6']:.3f}s" for r in rows))
    print()
    print("RESULT:", "ALL CHECKS PASSED" if ok else "MISMATCH — 记录与 fixture 不一致")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
