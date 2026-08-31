# Day 9 PDF 文档解析报告

## 1. 解析结果 Summary

Day 9 完成了第一版真实 PDF 文档解析流水线。

当前 corpus 中登记的 13 份 PDF 均成功完成解析，没有出现文件级解析失败。

### 1.1 总体统计

| 指标 | 结果 |
| --- | ---: |
| 注册 PDF 数量 | 13 |
| 成功解析 | 13 |
| 解析失败 | 0 |
| PDF 总页数 | 2178 |
| 提取字符数 | 3,817,630 |
| Text Blocks | 38,365 |
| 图片数量 | 1,147 |
| Parsed JSON 总大小 | 约 19 MB |
| 批量解析时间 | 约 5.3 s |

最终页面级 warning 统计：

| Warning | 页面数 |
| --- | ---: |
| `empty_text` | 7 |
| `possible_garbled_text` | 43 |
| `private_use_characters` | 64 |
| `possible_two_column` | 18 |
| `possible_scanned_page` | 2 |

需要注意：

> warning 是解析质量风险提示，而不是已经确认的解析错误。

同一页面可能同时具有多个 warning，因此不能简单将 warning 数量相加作为“异常页面总数”。

### 1.2 各文档解析结果

| 文档 | 页数 | 字符数 | Blocks | Images | 主要 Warning |
| --- | ---: | ---: | ---: | ---: | --- |
| EPICS Application Developer's Guide | 354 | 736,562 | 6,670 | 0 | 无 |
| EPICS Documentation | 455 | 948,961 | 10,051 | 33 | `empty_text: 1` |
| European XFEL Technical Design Report | 646 | 1,492,851 | 6,015 | 290 | `empty_text: 5`, `possible_garbled_text: 4` |
| European XFEL Undulator Commissioning Spectrometer | 21 | 36,078 | 348 | 6 | 无 |
| X-Ray Optics and Beam Transport | 164 | 172,157 | 2,790 | 223 | `private_use_characters: 11` |
| Standard E-Beam Diagnostics for European XFEL | 3 | 13,130 | 78 | 6 | `possible_two_column: 3` |
| EPICS IOC and PVs Information Management System for SHINE | 3 | 14,343 | 61 | 11 | `possible_two_column: 3` |
| SHINE 加速器快联锁系统设计与开发 | 9 | 15,773 | 297 | 10 | `possible_two_column: 4` |
| Status of the SHINE Control System | 4 | 16,668 | 81 | 8 | `possible_two_column: 3` |
| The Cryogenic Control System of SHINE | 8 | 19,831 | 74 | 7 | 无 |
| White Rabbit Based Beam-Synchronous Timing Systems for SHINE | 5 | 18,096 | 97 | 25 | `possible_two_column: 5` |
| SHINE 加速器控制系统设计与开发 | 34 | 5,917 | 305 | 140 | `private_use_characters: 30`, `possible_scanned_page: 2` |
| 硬 X 射线自由电子激光装置初步设计报告（加速器分册） | 472 | 327,263 | 11,498 | 388 | `empty_text: 1`, `private_use_characters: 23`, `possible_garbled_text: 39` |

总体来看，当前 PDF parser 已经能够稳定处理：

- 大型英文技术手册；
- 大型中英文设计报告；
- SHINE 技术资料；
- IPAC / ICALEPCS / PCaPAC 等会议论文；
- 双栏论文；
- 图片较多的展示型 PDF。

---

## 2. Day 9 目标

Day 9 的目标不是直接生成 Chunk，也不是立即进行 Embedding 和 Qdrant 入库。

本阶段只负责建立可靠的：

```text
PDF
↓
结构化原始解析结果
```

主要完成以下任务：

- 从 Day 8 的 registry 中读取 PDF 文档；
- 提取页面正文；
- 保留 PDF 物理页码；
- 提取页面 Text Block；
- 保存 Block 的 bbox 坐标；
- 统计页面图片；
- 读取 PDF 内嵌 metadata；
- 检测明显解析风险；
- 输出统一 JSON；
- 对真实 corpus 进行批量验证；
- 对典型文档进行人工抽样检查。

Day 9 暂时不处理：

- 文本去噪；
- 页眉页脚删除；
- PDF 断词修复；
- 表格结构重建；
- OCR；
- Chunk；
- Embedding；
- Qdrant 入库。

这些任务分别留到后续 pipeline 阶段处理。

---

## 3. PDF 解析流水线

当前处理流程：

```text
data/documents/registry.json
        │
        ▼
   load_registry()
        │
        ▼
   DocumentRecord
        │
        │ source_path
        ▼
      原始 PDF
        │
        ▼
      PyMuPDF
        │
        ├── text
        ├── page number
        ├── text blocks
        ├── bbox
        ├── image count
        ├── PDF metadata
        └── warnings
        │
        ▼
 ParsedPdfDocument
        │
        ▼
data/parsed/pdf/<doc_id>.json
```

这里没有重新扫描 `data/raw` 来猜测文档信息，而是直接复用 Day 8 建立的 registry。

因此 Day 8 和 Day 9 已经真正连接起来：

```text
registry
↓
source_path
↓
PDF
↓
parsed artifact
```

其中 `doc_id` 作为稳定文档主键，后续继续用于：

```text
registry
↓
parsed document
↓
chunk
↓
vector payload
↓
search result
↓
citation
```

---

## 4. PDF Parser 数据结构

实现文件：

```text
src/accelerator_rag/corpus/pdf_parser.py
```

当前采用三层数据结构：

```text
ParsedPdfDocument
└── PdfPage
    └── PdfTextBlock
```

### 4.1 `ParsedPdfDocument`

表示一份完整 PDF，主要保存：

- `source_path`
- `file_name`
- `page_count`
- `metadata`
- `pages`
- `warnings`

### 4.2 `PdfPage`

表示一个 PDF 物理页面：

- `page_number`
- `width`
- `height`
- `text`
- `char_count`
- `blocks`
- `image_count`
- `warnings`

其中：

```python
page_number = page_index + 1
```

保存的是 PDF Viewer 中看到的物理页面序号。

### 4.3 `PdfTextBlock`

保存：

- `block_number`
- `block_type`
- `bbox`
- `text`

其中：

```text
bbox = (x0, y0, x1, y1)
```

描述 Text Block 在 PDF 页面中的空间位置。

---

## 5. 为什么要保存 bbox

普通：

```python
page.get_text("text")
```

只能得到页面文本。

但是：

```python
page.get_text("blocks")
```

还可以得到布局坐标。

这使后续系统有可能分析：

- 双栏；
- 页眉；
- 页脚；
- 标题；
- 版权文字；
- 表格；
- 阅读顺序。

因此 Day 9 没有只保存纯文本，而是同时保存：

```text
文本内容
+
页面布局信息
```

为后续文档结构恢复保留原始证据。

---

## 6. PDF Block 不等于自然语言段落

真实 PDF 测试说明：

```text
PDF Text Block
≠
自然语言段落
≠
RAG Chunk
```

例如 White Rabbit IPAC2022 首页标题：

```text
WHITE RABBIT BASED BEAM-SYNCHRONOUS TIMING SYSTEMS
FOR SHINE*
```

实际被 PyMuPDF 分成两个 Block。

另一方面，有些 Block 又会同时包含：

```text
作者单位末尾
+
Abstract
```

因此不能简单使用：

```python
一个 block = 一个 paragraph
```

更不能：

```python
一个 block = 一个 chunk
```

Day 9 的职责只是保留原始 PDF layout。

后续需要经过：

```text
PDF Block
↓
文本清洗 / 结构恢复
↓
Semantic Paragraph
↓
Chunk
```

---

## 7. 双栏页面检测

会议论文普遍采用双栏结构，因此 Day 9 增加了：

```text
possible_two_column
```

风险检测。

基本方法是利用 bbox 判断是否同时存在：

```text
多个左侧正文 Block
+
多个右侧正文 Block
```

页面中线：

```text
midpoint = page_width / 2
```

### White Rabbit 实际样本

第一页：

```text
page width ≈ 592.78
midpoint ≈ 296.39
```

左栏正文主要位于：

```text
x ≈ 55 ～ 292
```

右栏正文主要位于：

```text
x ≈ 303 ～ 540
```

与人眼观察的双栏结构一致。

最终该论文：

```text
5 / 5 pages
```

全部被标记为：

```text
possible_two_column
```

### 极窄侧边文字问题

人工检查 bbox 时发现：

```text
x0 ≈ 542
x1 ≈ 551
width ≈ 9
chars ≈ 197
```

这是论文右侧竖排版权文字，而不是正常正文。

因此双栏判断增加了 Block 相对宽度限制，排除：

- 极窄竖排文字；
- 横跨页面的大标题；
- 部分页脚元素。

这次改动来源于真实 PDF failure case，而不是预先假设。

---

## 8. 字符异常检测

### 8.1 初始规则

最开始将以下字符全部视为：

```text
possible_garbled_text
```

包括：

- `U+FFFD` Replacement Character；
- `NULL`；
- Unicode Private Use Area。

第一次全 corpus 运行结果：

```text
possible_garbled_text = 105 pages
```

但随后人工抽查发现这个判断存在大量误报。

---

### 8.2 Private Use Character 误报

例如：

```text
SHINE 加速器控制系统设计与开发
```

大量页面存在：

```text

```

其正文实际为：

```text
主要内容
硬X射线自由电子激光简介
SHINE加速器控制系统总体规模
系统设计、实施过程中的一些问题
```

页面完全可读。

因此：

```text
Private Use Character
≠
正文乱码
```

类似情况还出现在技术单位：

```text
s

```

它们虽然不是标准 Unicode 表达，但在上下文中仍然可以理解。

因此最终将 Private Use Character 单独分类：

```text
private_use_characters
```

---

### 8.3 最终分类

当前：

```text
possible_garbled_text
```

主要检测：

- Unicode Replacement Character `U+FFFD`；
- NULL `\x00`。

而：

```text
private_use_characters
```

单独表示：

> 页面存在非标准私用 Unicode 字符，需要后续标准化，但不能直接判定正文已经损坏。

规则修正以后：

```text
旧结果：

possible_garbled_text = 105
```

变为：

```text
新结果：

possible_garbled_text = 43
private_use_characters = 64
```

这说明真实 corpus 人工验证有效降低了误报。

---

## 9. 空文本页

共检测到：

```text
empty_text = 7
```

人工检查这些页面后发现全部满足：

```text
char_count = 0
block_count = 0
image_count = 0
```

分布为：

- EPICS Documentation：1 页；
- European XFEL Technical Design Report：5 页；
- SHINE 加速器初步设计报告：1 页。

这类页面更可能是：

```text
空白页 / 分隔页
```

而不是扫描页。

因此当前不会自动把所有：

```text
empty_text
```

送入 OCR。

---

## 10. 疑似扫描 / 图片型页面

当前规则：

```text
char_count < 50
+
image_count > 0
```

则标记：

```text
possible_scanned_page
```

共发现：

```text
2 pages
```

都位于：

```text
SHINE 加速器控制系统设计与开发
```

分别为：

```text
page 8
chars = 34
images = 1

page 34
chars = 4
images = 1
```

说明这两页呈现明显的：

```text
图片为主
+
可提取文字很少
```

特征。

Day 9 只记录风险，暂不引入 OCR。

---

## 11. 人工抽样检查

### 11.1 White Rabbit Based Beam-Synchronous Timing Systems for SHINE

结果：

```text
pages = 5
chars = 18,096
blocks = 97
images = 25
possible_two_column = 5
```

人工检查结果：

- 标题正常；
- 作者正常；
- Abstract 正常；
- 英文正文可以正常提取；
- 5 页均正确识别出明显双栏风险；
- bbox 左右栏结构明显。

发现的主要问题：

```text
con-
taining
```

这种 PDF 排版断词仍然保留。

该问题属于 Day 11 文本清洗任务，不在 Day 9 parser 中直接修复。

---

### 11.2 SHINE 加速器控制系统设计与开发

结果：

```text
pages = 34
chars = 5,917
blocks = 305
images = 140

private_use_characters = 30
possible_scanned_page = 2
```

该文件属于展示型 PDF，因此特点非常明显：

```text
文字较少
+
图片较多
```

人工检查第 2～5 页：

- 中文标题正常；
- 中文正文正常；
- 表格内容基本可读取；
- 大量 `` 实际是 PPT 项目符号；
- 不是正文乱码。

这也是修改字符 warning heuristic 的主要真实样本之一。

---

### 11.3 硬 X 射线自由电子激光装置初步设计报告（加速器分册）

结果：

```text
pages = 472
chars = 327,263
blocks = 11,498
images = 388

empty_text = 1
private_use_characters = 23
possible_garbled_text = 39
```

人工检查第 44～46 页：

- 中文技术正文可以正常提取；
- 章节编号基本保留；
- 表格中的参数、数值、单位基本保留；
- 技术符号存在特殊字体映射；
- 部分页面仍然存在真正的 `U+FFFD` Replacement Character。

因此该文档同时存在：

```text
private_use_characters
```

和：

```text
possible_garbled_text
```

两类不同问题。

---

## 12. 表格解析问题

真实技术报告中有大量表格。

原始表格可能为：

```text
参数        数值       单位
工作频率    2856       MHz
重复频率    50         Hz
```

PyMuPDF 提取结果可能变成：

```text
参数
数值
单位
工作频率
2856
MHz
重复频率
50
Hz
```

说明当前 parser：

```text
大部分文字内容能够保留
```

但是：

```text
二维行列结构可能丢失
```

因此不能直接假设 PDF 文本提取能够恢复完整表格语义。

Day 9 暂时只记录这个风险。

---

## 13. PDF 物理页码与正文印刷页码

人工抽查加速器分册还确认了：

```text
PDF physical page
≠
printed page number
```

例如：

```text
PDF physical page = 44
```

对应正文顶部显示：

```text
printed page = 40
```

原因是 PDF 前部还存在：

- 封面；
- 目录；
- 空白页；
- 其他前置页面。

因此当前系统保存：

```text
page_number = physical PDF page
```

这样后续检索结果可以直接定位到 PDF Viewer。

如果以后需要同时展示书籍或报告内部印刷页码，可以另外增加：

```text
printed_page_number
```

而不覆盖当前物理页码。

---

## 14. Parsed Artifact

批量脚本：

```text
scripts/day9_parse_pdfs.py
```

输出：

```text
data/parsed/pdf/<doc_id>.json
```

JSON 顶层结构：

```json
{
  "schema_version": 1,
  "document": {},
  "parser": {},
  "pdf": {}
}
```

### schema_version

```text
schema_version = 1
```

用于描述解析中间数据的数据格式版本。

未来即使 JSON Schema 发生变化，也能够判断旧 artifact 使用的是哪一版结构。

### parser 信息

当前保存：

```text
name = pymupdf
version = 1.28.2
```

用于基本的数据 lineage 与可复现性记录。

---

## 15. Parsed 数据与 Git

本次生成：

```text
data/parsed/pdf/
```

共：

```text
13 JSON
约 19 MB
```

这些文件属于：

```text
derived / reproducible artifacts
```

因为可以通过：

```text
registry
+
原始 PDF
+
parser
```

重新生成。

因此：

```text
data/parsed/pdf/*.json
```

不进入 Git。

Git 只保留：

```text
data/parsed/.gitkeep
```

用于保留目录结构。

相比之下：

```text
data/documents/registry.json
```

属于人工维护的 corpus source of truth，因此需要进入版本控制。

---

## 16. 测试与质量检查

当前 PDF parser 单元测试覆盖：

- 正常 PDF 解析；
- 多页 PDF；
- 页码保存；
- 正文提取；
- 文件不存在；
- 非 PDF 文件；
- 疑似扫描页；
- 双栏布局；
- 极窄侧边文字排除；
- Unicode Replacement Character；
- NULL 字符；
- Private Use Character 分类。

当前 Day 9 PDF parser 测试：

```text
9 passed
```

全项目：

```text
52 passed
```

Ruff：

```text
All checks passed
```

说明 Day 9 新功能没有破坏之前已有功能。

---

## 17. 当前已知局限

第一版 PDF parser 仍然存在以下限制：

1. PDF Text Block 不等于自然语言段落。
2. 标题可能跨多个 Block，目前没有自动重建标题。
3. 双栏只进行风险检测，没有进行阅读顺序重建。
4. 表格可以提取文本，但不能保证二维结构。
5. 原始换行仍然保留。
6. `con- / taining` 等换行断词尚未处理。
7. Private Use Character 尚未映射为标准 Unicode。
8. `possible_garbled_text` 页面仍需要后续决定如何处理。
9. 疑似扫描页没有执行 OCR。
10. 数学公式没有进行 LaTeX 或结构化恢复。
11. 页眉、页脚、会议版权文字尚未清除。
12. 当前没有识别 semantic section。
13. 当前没有进行 Chunk 切分。
14. 当前保存物理 PDF 页码，没有解析独立 printed page number。

这些问题不应该全部塞进 PDF parser。

后续 pipeline 会按照职责继续处理。

---

## 18. Day 9 工程结论

Day 9 已完成：

```text
registry
↓
真实 PDF
↓
PyMuPDF
↓
page-level parsing
↓
layout blocks
↓
bbox
↓
quality warnings
↓
structured JSON
```

13 份真实 PDF、共 2178 页全部成功完成机器解析。

Day 9 最重要的成果不仅是：

```text
“PDF 能转成文字”
```

而是建立了一套能够保留：

```text
文档身份
+
来源路径
+
物理页码
+
正文
+
页面布局
+
解析质量风险
```

的数据结构。

同时，本次真实 corpus 测试还完成了一轮：

```text
设计 heuristic
↓
运行 2178 页真实数据
↓
发现异常统计
↓
人工抽样
↓
定位 false positive
↓
修正规则
↓
增加 regression test
↓
重新批量验证
```

初始：

```text
possible_garbled_text = 105
```

经过真实数据检查后重新分类为：

```text
possible_garbled_text = 43
private_use_characters = 64
```

说明 Day 9 不只是完成了 PDF API 调用，而是完成了一次完整的文档解析数据工程闭环。

当前解析结果已经可以作为后续阶段的输入：

```text
Day 10
PPT / Word 文档解析

Day 11
文本清洗与标准化

Day 12
Chunk 切分

Day 13
Metadata Schema

Day 14
完整 ingestion pipeline
```

**Day 9 PDF 文档解析阶段完成。**