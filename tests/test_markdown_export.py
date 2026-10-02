"""markdown_export：JSON → Markdown（标量 / 嵌套 / 表格 / 坏文件容错）"""
import json

import pytest

from knowflow.core.pipeline import PipelineContext
from knowflow.transforms.markdown_export import MarkdownExport


def _ctx(tmp_path, plugin="football"):
    return PipelineContext(
        storage=None,
        plugin_name=plugin,
        plugin_config={"_warnings": []},
        data_dir=tmp_path / "data" / plugin,
        output_dir=tmp_path / "out" / plugin,
    )


def _write(data_dir, name, obj):
    p = data_dir / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj,
                 encoding="utf-8")
    return p


def test_scalar_fields_render_as_bullets(tmp_path):
    ctx = _ctx(tmp_path)
    _write(ctx.data_dir, "match.json", {"home": "巴西", "away": "阿根廷", "goals": 3})
    res = MarkdownExport().process(ctx)

    assert res["status"] == "ok"
    assert res["generated"] == 1
    md = (ctx.output_dir / "match.md").read_text(encoding="utf-8")
    assert "# Football — match" in md
    assert "- **Home**: 巴西" in md
    assert "- **Goals**: 3" in md
    assert "> 自动生成" in md


def test_nested_dict_becomes_heading(tmp_path):
    ctx = _ctx(tmp_path)
    _write(ctx.data_dir, "a.json", {"meta": {"source": "ESPN", "ok": True}})
    MarkdownExport().process(ctx)
    md = (ctx.output_dir / "a.md").read_text(encoding="utf-8")
    assert "## Meta" in md
    assert "- **Source**: ESPN" in md
    assert "- **Ok**: ✅" in md


def test_list_of_dicts_becomes_table(tmp_path):
    ctx = _ctx(tmp_path)
    _write(ctx.data_dir, "rows.json", {"rows": [
        {"name": "甲", "score": 1.5},
        {"name": "乙", "score": 2},
    ]})
    MarkdownExport().process(ctx)
    md = (ctx.output_dir / "rows.md").read_text(encoding="utf-8")
    assert "## Rows" in md
    assert "| Name | Score |" in md
    assert "| --- | --- |" in md
    assert "| 甲 | 1.50 |" in md, "浮点应格式化为两位小数"


def test_bool_null_formatting(tmp_path):
    ctx = _ctx(tmp_path)
    _write(ctx.data_dir, "f.json", {"yes": True, "no": False, "none": None})
    MarkdownExport().process(ctx)
    md = (ctx.output_dir / "f.md").read_text(encoding="utf-8")
    assert "- **Yes**: ✅" in md
    assert "- **No**: ❌" in md
    assert "- **None**: —" in md


def test_nested_subdirectory_preserved(tmp_path):
    ctx = _ctx(tmp_path)
    _write(ctx.data_dir, "daily/2026-10-02.json", {"title": "国庆"})
    MarkdownExport().process(ctx)
    assert (ctx.output_dir / "daily" / "2026-10-02.md").exists()


def test_invalid_json_is_skipped_with_warning(tmp_path):
    ctx = _ctx(tmp_path)
    _write(ctx.data_dir, "good.json", {"ok": 1})
    _write(ctx.data_dir, "broken.json", "{ 这不是合法 JSON ")
    res = MarkdownExport().process(ctx)

    assert res["status"] == "ok"
    assert res["generated"] == 1, "坏文件应被跳过，好文件仍要生成"
    assert (ctx.output_dir / "good.md").exists()
    assert not (ctx.output_dir / "broken.md").exists()
    assert any("broken.json" in w for w in ctx.plugin_config["_warnings"])


def test_empty_json_produces_no_file(tmp_path):
    ctx = _ctx(tmp_path)
    _write(ctx.data_dir, "empty.json", {})
    res = MarkdownExport().process(ctx)
    assert res["generated"] == 0
    assert not (ctx.output_dir / "empty.md").exists()


def test_missing_data_dir_is_skipped(tmp_path):
    ctx = _ctx(tmp_path)          # data 目录根本没建
    res = MarkdownExport().process(ctx)
    assert res["status"] == "skipped"
    assert "No data directory" in res["reason"]


def test_no_json_files_generates_zero(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.data_dir.mkdir(parents=True)
    (ctx.data_dir / "readme.txt").write_text("不是 json", encoding="utf-8")
    res = MarkdownExport().process(ctx)
    assert res["status"] == "ok"
    assert res["generated"] == 0
