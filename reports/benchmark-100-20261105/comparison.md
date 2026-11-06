# 100 题对照：rc.3 候选 vs rc.2 生产

生成时间：2026-11-05T15:51:34.837240+00:00

> 工程指标，不是语义准确率。`expected_status_match` 只比较接口状态与预期标签。

| 子集 | 题数 | HTTP 成功 | 状态匹配 | 引用命中父块 | P50 (s) | P95 (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| all · baseline | 100 | 98/100 | 69/100 | 0/0 | 24.72835 | 57.300412 |
| all · candidate | 100 | 97/100 | 74/100 | 0/0 | 24.740514 | 84.172765 |
| old-50 · baseline | 50 | 48/50 | 42/50 | 0/0 | 28.363815 | 66.74855 |
| old-50 · candidate | 50 | 48/50 | 41/50 | 0/0 | 27.401893 | 118.578474 |
| cable-20 · baseline | 20 | 20/20 | 3/20 | 0/0 | 37.937639 | 54.308838 |
| cable-20 · candidate | 20 | 20/20 | 16/20 | 0/0 | 25.342571 | 82.19039 |
| kb2-30 · baseline | 30 | 30/30 | 24/30 | 0/0 | 8.854885 | 19.956402 |
| kb2-30 · candidate | 30 | 29/30 | 17/30 | 0/0 | 10.980537 | 26.977025 |

## 结果变化

| 题号 | 子集 | 之前 | 之后 |
| --- | --- | --- | --- |
| P50-004 | old-50 | http_error/None/chunk=False | success/partial/chunk=False |
| P50-009 | old-50 | success/answered/chunk=False | success/partial/chunk=False |
| P50-046 | old-50 | success/partial/chunk=False | http_error/None/chunk=False |
| CAB-PORT-001 | cable-20 | success/insufficient/chunk=False | success/answered/chunk=False |
| CAB-PORT-002 | cable-20 | success/insufficient/chunk=False | success/answered/chunk=False |
| CAB-PORT-003 | cable-20 | success/insufficient/chunk=False | success/answered/chunk=False |
| CAB-PORT-004 | cable-20 | success/insufficient/chunk=False | success/answered/chunk=False |
| CAB-PORT-005 | cable-20 | success/insufficient/chunk=False | success/answered/chunk=False |
| CAB-JOIN-001 | cable-20 | success/insufficient/chunk=False | success/answered/chunk=False |
| CAB-ID-001 | cable-20 | success/partial/chunk=False | success/answered/chunk=False |
| CAB-ID-002 | cable-20 | success/partial/chunk=False | success/answered/chunk=False |
| CAB-ID-004 | cable-20 | success/insufficient/chunk=False | success/answered/chunk=False |
| CAB-ID-006 | cable-20 | success/insufficient/chunk=False | success/answered/chunk=False |
| CAB-PORTE-001 | cable-20 | success/insufficient/chunk=False | success/answered/chunk=False |
| CAB-PORTE-002 | cable-20 | success/insufficient/chunk=False | success/answered/chunk=False |
| CAB-AGG-001 | cable-20 | success/insufficient/chunk=False | success/answered/chunk=False |
| CAB-BND-001 | cable-20 | success/insufficient/chunk=False | success/answered/chunk=False |
| KB2-FACT-004 | kb2-30 | success/answered/chunk=False | success/partial/chunk=False |
| KB2-FACT-011 | kb2-30 | success/answered/chunk=False | success/partial/chunk=False |
| KB2-VER-004 | kb2-30 | success/answered/chunk=False | success/partial/chunk=False |
| KB2-VER-007 | kb2-30 | success/answered/chunk=False | success/partial/chunk=False |
| KB2-VER-008 | kb2-30 | success/answered/chunk=False | success/partial/chunk=False |
| KB2-VER-015 | kb2-30 | success/answered/chunk=False | success/partial/chunk=False |
| KB2-BND-004 | kb2-30 | success/answered/chunk=False | http_error/None/chunk=False |
