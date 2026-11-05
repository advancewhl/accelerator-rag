"""XLSX/CSV/ODS adapters: cell ranges, formulas, encodings, refusal."""

from pathlib import Path
import re
import zipfile

import openpyxl
import pytest

from accelerator_rag.corpus import structured_parser
from accelerator_rag.corpus.structured_parser import (
    UnsupportedStructuredFormat,
    parse_csv,
    parse_ods,
    parse_xlsx,
)
from accelerator_rag.domain.position import BlockType


XLSX_SOURCE = "data/l0_raw/tests/params.xlsx"
CSV_SOURCE = "data/l0_raw/tests/data.csv"


def _inject_cached_value(path: Path, cell: str, value: str) -> None:
    temporary = path.with_name(f"{path.stem}.tmp.xlsx")
    pattern = re.compile(
        rf'(<c r="{cell}"[^>]*>.*?</f>)<v></v>(</c>)', re.DOTALL
    )
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(
        temporary, "w", zipfile.ZIP_DEFLATED
    ) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                text = data.decode("utf-8")
                text, count = pattern.subn(
                    rf"\1<v>{value}</v>\2", text, count=1
                )
                assert count == 1
                data = text.encode("utf-8")
            target.writestr(item, data)
    temporary.replace(path)


def _build_xlsx(tmp_path: Path) -> Path:
    path = tmp_path / "params.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "参数"
    sheet.append(["名称", "数值", "公式"])
    sheet.append(["联锁响应", "100", "=B2*2"])
    sheet.append(["增益", "2", "=B3*2"])

    devices = workbook.create_sheet("设备")
    devices.append(["设备", "位置"])
    devices.append(["BPM", "隧道"])
    workbook.create_sheet("空表")
    workbook.save(path)
    _inject_cached_value(path, "C2", "200")
    return path


def test_xlsx_sheets_ranges_formulas_and_empty_sheet_warning(tmp_path):
    path = _build_xlsx(tmp_path)

    parsed = parse_xlsx(
        path, revision_id="xlsx-sample-r1", source_path=XLSX_SOURCE
    )

    tables = parsed.blocks_of(BlockType.TABLE.value)
    assert len(tables) == 2
    first = tables[0]
    assert first.position.kind == "cell_range"
    assert first.position.label == "参数!A1:C3"
    assert first.position.start == 1
    assert first.position.end == 3
    assert dict(first.position.locator)["sheet"] == "参数"
    assert dict(first.position.locator)["range"] == "A1:C3"

    table = first.table
    assert table.header_rows == 1
    assert table.rows[0] == ("名称", "数值", "公式")
    assert table.rows[1][2] == "200"
    assert table.rows[2][2] == "=B3*2"

    metadata = dict(first.metadata)
    assert metadata["formula_status"] == "partially_cached"
    assert "C2: =B2*2 cached=200" in metadata["formula_cells"]
    assert "C3: =B3*2" in metadata["formula_cells"]
    assert metadata["formula_count"] == "2"

    assert any(
        warning == "empty_sheet:空表" for warning in parsed.warnings
    )
    assert parsed.title == "params"
    assert tables[1].position.label == "设备!A1:B2"
    assert tables[1].table.rows == (("设备", "位置"), ("BPM", "隧道"))


def test_xlsx_reads_formulas_and_cached_values_without_links(
    tmp_path, monkeypatch
):
    path = _build_xlsx(tmp_path)
    calls = []
    real_loader = structured_parser.load_workbook

    def spy(*args, **kwargs):
        calls.append(dict(kwargs))
        return real_loader(*args, **kwargs)

    monkeypatch.setattr(structured_parser, "load_workbook", spy)

    parse_xlsx(
        path, revision_id="xlsx-sample-r1", source_path=XLSX_SOURCE
    )

    assert len(calls) == 3
    assert [call["read_only"] for call in calls] == [True, True, False]
    assert {
        call["data_only"] for call in calls if call["read_only"]
    } == {False, True}
    assert all(call["keep_links"] is False for call in calls)
    assert all(call["keep_vba"] is False for call in calls)


def test_xlsx_title_row_becomes_caption_and_header_moves_down(tmp_path):
    path = tmp_path / "terminals.xlsx"
    workbook = openpyxl.Workbook()
    main = workbook.active
    main.title = "主控柜"
    main.append(["主控柜端子接线对应表"])
    main.append(["信号源", "前线号", "端子编号"])
    main.append(["传感器", "F1001", "1"])
    temperature = workbook.create_sheet("温控柜")
    temperature.append(["温控柜端子接线对应表"])
    temperature.append(["温度传感器", "前线号", "端子编号"])
    temperature.append(["FC1-TT01", "F1001", "1"])
    workbook.save(path)

    parsed = parse_xlsx(
        path, revision_id="xlsx-sample-r1", source_path=XLSX_SOURCE
    )

    tables = parsed.blocks_of(BlockType.TABLE.value)
    assert len(tables) == 2
    for block, sheet, caption, header, first_data in (
        (
            tables[0],
            "主控柜",
            "主控柜端子接线对应表",
            ("信号源", "前线号", "端子编号"),
            "传感器",
        ),
        (
            tables[1],
            "温控柜",
            "温控柜端子接线对应表",
            ("温度传感器", "前线号", "端子编号"),
            "FC1-TT01",
        ),
    ):
        table = block.table
        assert table.caption == caption
        assert table.header_rows == 1
        assert table.rows[0] == header
        assert table.rows[1][0] == first_data
        assert block.text.startswith(caption + "\n")
        assert block.position.start == 2
        assert block.position.end == 3
        assert block.position.label == f"{sheet}!A2:C3"
        assert dict(block.metadata)["caption"] == caption
        assert dict(block.metadata)["title_row"] == "1"
    assert not any(
        warning.startswith("title_row_without_header")
        for warning in parsed.warnings
    )


def test_xlsx_title_row_without_column_names_warns(tmp_path):
    path = tmp_path / "title-only.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "说明"
    sheet.append(["只有标题"])
    workbook.save(path)

    parsed = parse_xlsx(
        path, revision_id="xlsx-sample-r1", source_path=XLSX_SOURCE
    )

    table = parsed.blocks_of(BlockType.TABLE.value)[0].table
    assert table.caption == ""
    assert table.header_rows == 1
    assert table.rows == (("只有标题",),)
    assert any(
        warning == "title_row_without_header:说明"
        for warning in parsed.warnings
    )


def test_xlsx_without_header(tmp_path):
    path = _build_xlsx(tmp_path)

    parsed = parse_xlsx(
        path,
        revision_id="xlsx-sample-r1",
        source_path=XLSX_SOURCE,
        header=False,
    )

    assert parsed.blocks_of(BlockType.TABLE.value)[0].table.header_rows == 0
    assert dict(parsed.metadata)["sheet_count"] == "3"


def test_xlsx_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_xlsx(
            tmp_path / "missing.xlsx",
            revision_id="xlsx-sample-r1",
            source_path=XLSX_SOURCE,
        )


def test_csv_utf8_bom(tmp_path):
    path = tmp_path / "data.csv"
    path.write_bytes("名称,数值\n联锁响应,100 µs\n".encode("utf-8-sig"))

    parsed = parse_csv(
        path, revision_id="csv-sample-r1", source_path=CSV_SOURCE
    )

    block = parsed.blocks[0]
    assert block.block_type == BlockType.TABLE.value
    assert block.position.kind == "cell_range"
    assert block.position.label == "data.csv!A1:B2"
    assert block.position.start == 1
    assert block.position.end == 2
    assert block.table.header_rows == 1
    assert block.table.rows == (("名称", "数值"), ("联锁响应", "100 µs"))
    assert dict(parsed.metadata)["encoding"] == "utf-8-sig"


def test_csv_gb18030_fallback(tmp_path):
    path = tmp_path / "gb.csv"
    path.write_bytes("名称,数值\n联锁响应,100 µs\n".encode("gb18030"))

    parsed = parse_csv(
        path, revision_id="csv-sample-r1", source_path="data/l0_raw/tests/gb.csv"
    )

    assert parsed.blocks[0].table.rows[1] == ("联锁响应", "100 µs")
    assert dict(parsed.metadata)["encoding"] == "gb18030"


def test_csv_header_off_and_custom_delimiter(tmp_path):
    path = tmp_path / "semi.csv"
    path.write_text("a;b\n1;2\n", encoding="utf-8")

    parsed = parse_csv(
        path,
        revision_id="csv-sample-r1",
        source_path=CSV_SOURCE,
        header=False,
        delimiter=";",
    )

    block = parsed.blocks[0]
    assert block.table.header_rows == 0
    assert block.table.rows == (("a", "b"), ("1", "2"))
    assert dict(parsed.metadata)["delimiter"] == ";"
    assert dict(block.position.locator)["header_rows"] == "0"


def test_csv_empty_file_warns(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_bytes(b"\n\n")

    parsed = parse_csv(
        path, revision_id="csv-sample-r1", source_path=CSV_SOURCE
    )

    assert parsed.blocks == ()
    assert parsed.warnings == ("empty_document",)


def test_ods_refuses_with_install_hint(tmp_path):
    path = tmp_path / "table.ods"
    path.write_bytes(b"PK not-an-ods")

    with pytest.raises(UnsupportedStructuredFormat, match="odfpy"):
        parse_ods(
            path, revision_id="ods-sample-r1", source_path="data/l0_raw/t/a.ods"
        )


def test_ods_validation(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_ods(
            tmp_path / "missing.ods",
            revision_id="ods-sample-r1",
            source_path="data/l0_raw/t/a.ods",
        )

    wrong = tmp_path / "wrong.csv"
    wrong.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="ODS"):
        parse_ods(
            wrong, revision_id="ods-sample-r1", source_path="data/l0_raw/t/a.ods"
        )


def test_xlsx_interior_blank_rows_keep_physical_range(tmp_path):
    path = tmp_path / "blank-rows.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "端子"
    sheet.append(["端子表"])
    sheet.append(["前线号", "后线号"])
    sheet.append(["F1001", "X1001"])
    sheet.append([None, None])
    sheet.append(["F1002", "X1002"])
    workbook.save(path)

    parsed = parse_xlsx(
        path,
        revision_id="blank-row-revision",
        source_path="data/l0_raw/tests/blank-rows.xlsx",
    )
    block = parsed.blocks[0]
    table = block.table

    assert block.position.start == 2
    assert block.position.end == 5
    assert table.caption == "端子表"
    assert table.header_rows == 1
    assert len(table.rows) == 4
    assert table.rows[2] == ("", "")
    assert "F1001 | X1001" in table.text
    assert "F1002 | X1002" in table.text
