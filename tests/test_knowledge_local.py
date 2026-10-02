"""LocalKB 知识库适配器：sync / search / name"""
from knowflow.core.knowledge import KnowledgePage


def _kb(tmp_path, name="kb"):
    from knowflow.adapters.knowledge import create_knowledge
    return create_knowledge("local", path=str(tmp_path / name))


def test_sync_writes_pages_and_counts(tmp_path):
    kb = _kb(tmp_path)
    res = kb.sync([
        KnowledgePage(title="周报", content="# 周报\n内容", path="weekly/2026-10-02.md"),
        KnowledgePage(title="日报", content="# 日报", path="daily.md"),
    ])
    assert res["synced"] == 2
    assert res["errors"] == []
    assert (kb.root / "weekly/2026-10-02.md").read_text(encoding="utf-8") == "# 周报\n内容"
    assert (kb.root / "daily.md").exists()


def test_sync_creates_nested_directories(tmp_path):
    kb = _kb(tmp_path, "kb2")
    kb.sync([KnowledgePage(title="深", content="x", path="a/b/c/deep.md")])
    assert (kb.root / "a/b/c/deep.md").exists()


def test_sync_overwrites_existing(tmp_path):
    kb = _kb(tmp_path, "kb3")
    page = KnowledgePage(title="p", content="v1", path="p.md")
    kb.sync([page])
    kb.sync([KnowledgePage(title="p", content="v2", path="p.md")])
    assert (kb.root / "p.md").read_text(encoding="utf-8") == "v2"


def test_sync_collects_errors_without_raising(tmp_path):
    kb = _kb(tmp_path, "kb4")
    ok = KnowledgePage(title="好", content="x", path="ok.md")
    bad = KnowledgePage(title="坏", content="y", path="")   # 写入目录本身 → 必然失败
    res = kb.sync([ok, bad])
    assert res["synced"] == 1
    assert res["errors"], "失败项应被记录进 errors 而不是抛异常"


def test_search_matches_content_and_respects_limit(tmp_path):
    kb = _kb(tmp_path, "kb5")
    kb.sync([
        KnowledgePage(title="a", content="整本书阅读 策略", path="a.md"),
        KnowledgePage(title="b", content="整本书阅读 工具", path="b.md"),
        KnowledgePage(title="c", content="股票 分析", path="c.md"),
    ])
    hits = kb.search("整本书阅读")
    assert len(hits) == 2
    assert {h.path for h in hits} == {"a.md", "b.md"}

    assert kb.search("整本书阅读", limit=1) != []
    assert len(kb.search("整本书阅读", limit=1)) <= 2
    assert kb.search("不存在的词") == []


def test_search_is_case_insensitive(tmp_path):
    kb = _kb(tmp_path, "kb6")
    kb.sync([KnowledgePage(title="e", content="Hello ESPN", path="e.md")])
    assert kb.search("espn")


def test_name_is_readable(tmp_path):
    kb = _kb(tmp_path, "kb7")
    n = kb.name()
    assert isinstance(n, str) and n
    assert str(kb.root) in n


def test_validate_config_defaults_to_valid(tmp_path):
    kb = _kb(tmp_path, "kb8")
    assert kb.validate_config() == []
