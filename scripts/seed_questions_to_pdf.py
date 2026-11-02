"""Render the PRAB seed-question set into a printable HTML/PDF review copy.

Stdlib only; Chrome headless does the PDF conversion (CJK via fontconfig).

Usage:
    python scripts/seed_questions_to_pdf.py --out reports/phase1-m0-20261029/seed-questions-v1
"""

import argparse
import html
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/evaluation/seed-questions-v1.json"
CATEGORY_ZH = {
    "task1_parameter_condition": "Task 1 设备参数与适用工况",
    "task2_alignment_prep": "Task 2 Waveform 对齐与分析准备",
    "task3_cross_version_comparison": "Task 3 跨版本 / 跨子系统比较",
    "task4_fault_diagnosis": "Task 4 故障复盘与诊断路径",
}
STATUS_ZH = {"answerable": "可回答", "partial": "部分可回答", "insufficient": "证据不足"}
SHORT_CATEGORY = {
    "task1_parameter_condition": "Task1 参数与工况",
    "task2_alignment_prep": "Task2 对齐准备",
    "task3_cross_version_comparison": "Task3 跨版本比较",
    "task4_fault_diagnosis": "Task4 故障诊断",
}
STATUS_CLASS = {"answerable": "ok", "partial": "mid", "insufficient": "bad"}
EXCERPT_LIMIT = 200


def esc(text):
    return html.escape(str(text or ""))


def clip(text, limit):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit] + " …"


def badge(status):
    return f'<span class="badge {STATUS_CLASS[status]}">{STATUS_ZH[status]}</span>'


def fact_row(fact):
    bits = []
    if fact.get("value") is not None:
        bits.append(f'{fact["value"]}{" " + fact["unit"] if fact.get("unit") else ""}')
    if fact.get("comparator"):
        bits.append(f'比较符 {fact["comparator"]}')
    meta = f' <span class="meta">[{" · ".join(esc(b) for b in bits)}]</span>' if bits else ""
    return f"<li>{esc(fact['fact'])}{meta}</li>"


def evidence_block(evidence):
    rows = []
    for item in evidence:
        rows.append(
            '<div class="ev">'
            f'<div class="loc">{esc(item.get("locator"))}</div>'
            f'<div class="quote">{esc(clip(item.get("excerpt"), EXCERPT_LIMIT))}</div>'
            "</div>"
        )
    return "\n".join(rows)


def constraints_block(constraints):
    lines = []
    numbers = constraints.get("numbers") or []
    if numbers:
        values = []
        for number in numbers:
            unit = number.get("unit") or ""
            values.append(f'{number.get("value")}{" " + unit if unit else ""}'.strip())
        lines.append(f'<div><b>数值：</b>{esc("；".join(values))}</div>')
    comparators = constraints.get("comparators") or []
    if comparators:
        lines.append(f'<div><b>比较符：</b>{esc("、".join(comparators))}</div>')
    for name, label in (
        ("preconditions", "前置条件"),
        ("version_constraints", "版本约束"),
    ):
        values = constraints.get(name) or []
        if values:
            items = "".join(f"<li>{esc(v)}</li>" for v in values)
            lines.append(f"<div><b>{label}：</b><ul class=\"tight\">{items}</ul></div>")
    return "\n".join(lines)


def scoring_block(scoring):
    hazards = "".join(f"<li>{esc(p)}</li>" for p in scoring.get("hazardous_patterns", []))
    return (
        f'<div><b>完全正确：</b>{esc(scoring.get("full"))}</div>'
        f'<div><b>部分正确：</b>{esc(scoring.get("partial"))}</div>'
        f'<div><b>错误：</b>{esc(scoring.get("zero"))}</div>'
        f'<div class="hazard"><b>危险模式：</b><ul class="tight">{hazards}</ul></div>'
    )


def item_html(index, item):
    verification = item["verification"]
    pending = verification.get("pending") or []
    pending_html = (
        '<div class="pending"><b>待人工确认：</b><ul class="tight">'
        + "".join(f"<li>{esc(p)}</li>" for p in pending)
        + "</ul></div>"
        if pending
        else ""
    )
    negative = item.get("negative_construction")
    negative_html = (
        f'<div class="negative"><b>负例构造（非真实故障）：</b>'
        f'{esc(negative["method"])} — {esc(negative["detail"])}</div>'
        if negative
        else ""
    )
    provenance = item["provenance"]
    overlap = "是（变体，不得进入独立测试集）" if provenance.get("overlaps_36q") else "否"
    return f"""
<section class="item">
  <h2><span class="num">{index:02d}</span> {esc(item['id'])} {badge(item['expected_status'])}</h2>
  <div class="meta-line">{esc(CATEGORY_ZH[item['category']])} · {esc(item['language'])} ·
    核验 {esc(verification['status'])} · 与 36 题重叠：{esc(overlap)}</div>

  <div class="field"><div class="label">问题</div><div class="q">{esc(item['question'])}</div></div>
  <div class="field"><div class="label">标准答案</div><div>{esc(item['gold_answer'])}</div></div>
  <div class="field"><div class="label">必须覆盖</div>
    <ul>{''.join(fact_row(f) for f in item['must_cover'])}</ul></div>
  <div class="field"><div class="label">约束</div>{constraints_block(item['constraints'])}</div>
  <div class="field"><div class="label">证据</div>{evidence_block(item['evidence'])}</div>
  <div class="field"><div class="label">评分规则</div>{scoring_block(item['scoring'])}</div>
  {negative_html}
  <div class="field small"><div class="label">适用版本与来源</div>
    <div><b>系统版本：</b>{esc(item['applicable']['system_version'])}</div>
    <div><b>工况／条件：</b>{esc(item['applicable']['conditions'])}</div>
    <div><b>来源案例：</b>{esc(item['source_case'])}</div>
    <div><b>改写说明：</b>{esc(provenance['derivation'])}</div>
    <div><b>核验方法：</b>{esc(verification['method'])}（{esc(verification['checked_at'])}）</div>
    {pending_html}
  </div>
</section>"""


def build_html(payload):
    items = payload["items"]
    categories = Counter(i["category"] for i in items)
    statuses = Counter(i["expected_status"] for i in items)
    negatives = sum(1 for i in items if i.get("negative_construction"))
    overlap = sum(1 for i in items if i["provenance"].get("overlaps_36q"))

    dist_rows = "".join(
        f"<tr><td>{esc(CATEGORY_ZH[name])}</td><td class='c'>{categories[name]}</td>"
        f"<td class='c'>{sum(1 for i in items if i['category'] == name and i['expected_status'] == 'answerable')}</td>"
        f"<td class='c'>{sum(1 for i in items if i['category'] == name and i['expected_status'] == 'partial')}</td>"
        f"<td class='c'>{sum(1 for i in items if i['category'] == name and i['expected_status'] == 'insufficient')}</td></tr>"
        for name in CATEGORY_ZH
    )
    index_rows = "".join(
        f"<tr><td class='mono'>{esc(i['id'])}</td><td>{esc(SHORT_CATEGORY[i['category']])}</td>"
        f"<td class='c'>{STATUS_ZH[i['expected_status']]}</td>"
        f"<td>{esc(clip(i['question'], 54))}</td></tr>"
        for i in items
    )
    body = "".join(item_html(n, i) for n, i in enumerate(items, 1))
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>PRAB Phase 1 种子题集（50 道）</title>
<style>
  @page {{ size: A4; margin: 14mm 14mm 14mm 14mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Noto Sans CJK SC", "Noto Serif CJK SC", sans-serif;
          font-size: 9.7pt; line-height: 1.45; color: #1b1b1b; margin: 0; }}
  h1 {{ font-size: 22pt; margin: 0 0 6mm; }}
  h2 {{ font-size: 12.4pt; margin: 0 0 2mm; border-bottom: 1.2px solid #333; padding-bottom: 1mm; }}
  .cover {{ padding-top: 45mm; }}
  .sub {{ color: #555; font-size: 11pt; }}
  .warn {{ border-left: 3px solid #b45309; background: #fff7ed; padding: 3mm 4mm; margin: 6mm 0; font-size: 9.8pt; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 9.4pt; margin: 3mm 0 5mm; }}
  th, td {{ border-bottom: 0.6px solid #ccc; padding: 1.4mm 1.6mm; text-align: left; vertical-align: top; }}
  th {{ background: #f2f2f2; }}
  td.c, th.c {{ text-align: center; }}
  .mono {{ font-family: "Noto Sans Mono CJK SC", monospace; font-size: 8.6pt; white-space: nowrap; }}
  .item {{ margin: 0 0 6mm; }}
  .item + .item {{ border-top: 0.7px solid #dcdcdc; padding-top: 3.5mm; }}
  .item + .item h2 {{ margin-top: 1mm; }}
  h2 {{ break-after: avoid; page-break-after: avoid; }}
  .num {{ color: #888; font-weight: normal; }}
  .meta-line {{ color: #666; font-size: 8.8pt; margin-bottom: 2.4mm; }}
  .badge {{ font-size: 8.4pt; padding: 0.4mm 2mm; border-radius: 2mm; color: #fff; vertical-align: 1px; }}
  .badge.ok {{ background: #15803d; }} .badge.mid {{ background: #b45309; }} .badge.bad {{ background: #b91c1c; }}
  .field {{ margin: 0 0 2.6mm; }}
  .label {{ font-size: 8.6pt; color: #666; letter-spacing: 0.4px; margin-bottom: 0.6mm; }}
  .q {{ font-weight: 600; }}
  .small {{ font-size: 9pt; break-inside: avoid; page-break-inside: avoid; }}
  .meta {{ color: #666; font-size: 9pt; }}
  ul {{ margin: 0.6mm 0 0 4.5mm; padding: 0; }}
  ul.tight li {{ margin: 0.2mm 0; }}
  li {{ margin: 0.4mm 0; }}
  .ev {{ margin: 0 0 1.8mm; padding-left: 3mm; border-left: 2px solid #d4d4d4; }}
  .loc {{ font-family: "Noto Sans Mono CJK SC", monospace; font-size: 8pt; color: #444; }}
  .quote {{ color: #333; }}
  .hazard li {{ color: #7f1d1d; }}
  .negative {{ background: #fef2f2; border-left: 3px solid #b91c1c; padding: 2mm 3mm; margin: 0 0 2.6mm; font-size: 9.2pt; }}
  .pending {{ margin-top: 1.6mm; }}
  .foot {{ color: #888; font-size: 8.4pt; margin-top: 6mm; }}
</style></head><body>
<div class="cover">
  <h1>PRAB Phase 1 种子题集（50 道）</h1>
  <div class="sub">开发种子集 · 生成于 2026-10-29 · 源文件 data/evaluation/seed-questions-v1.json</div>
  <div class="warn">
    <b>阅读前请注意：</b>① 本集是<b>开发种子集</b>，不是独立测试集；27 道与 36 题开发回归集同源或为变体，
    不得进入未来独立测试集。② 50 道全部为 <b>machine_verified</b>（结构、定位、匹配自检通过），
    <b>没有任何人工语义复核</b>；`answered` 不等于人工判定正确。③ Waveform 类题目依赖的 4 份文档
    <b>尚未入库</b>，在 M0 上预期为 insufficient。
  </div>
  <table>
    <tr><th>类别</th><th class="c">道数</th><th class="c">可回答</th><th class="c">部分可回答</th><th class="c">证据不足</th></tr>
    {dist_rows}
    <tr><th>合计</th><th class="c">{len(items)}</th><th class="c">{statuses['answerable']}</th>
        <th class="c">{statuses['partial']}</th><th class="c">{statuses['insufficient']}</th></tr>
  </table>
  <div class="sub">负例 {negatives} 道（均标注构造方式）· 与 36 题重叠 {overlap} 道 ·
    危险模式合计 {sum(len(i['scoring']['hazardous_patterns']) for i in items)} 条</div>
</div>

<div class="item">
  <h2>题目索引</h2>
  <table>
    <tr><th>ID</th><th>类别</th><th class="c">预期状态</th><th>问题（截断）</th></tr>
    {index_rows}
  </table>
</div>

<div class="item">
  <h2>评分规则（全题集通用）</h2>
  <div><b>完全正确 = 1.0</b>：must_cover 全部满足 + constraints（数值/单位/比较符/前置条件/版本）全部满足 + 未命中危险模式。</div>
  <div><b>部分正确 = 0.5</b>：核心结论正确，但至少 1 项必需条件缺失且被显式标注。</div>
  <div><b>错误 = 0.0</b>：核心结论错误、张冠李戴，或引用不支撑结论。</div>
  <div><b>hazardous 是标记不是分值</b>：命中危险模式的 partial/zero 仍记 0.5/0.0，但计入“危险误导率”。
    报告指标必须同时给出 strict 与 hazardous 两个数。</div>
  <div class="foot">本页说明对全部 50 道适用；逐题的“评分规则”栏只写该题的具体判据。</div>
</div>

{body}
</body></html>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports/phase1-m0-20261029/seed-questions-v1")
    args = parser.parse_args()
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    if len(payload.get("items", [])) != 50:
        raise SystemExit(f"expected 50 items, found {len(payload.get('items', []))}")
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    html_path = out.with_suffix(".html")
    html_path.write_text(build_html(payload), encoding="utf-8")
    print(html_path)


if __name__ == "__main__":
    main()
