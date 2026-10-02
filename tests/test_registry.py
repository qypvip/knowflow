"""适配器注册表 / 工厂函数测试。

其中 test_create_storage_accepts_flat_kwargs 与 test_create_kb_alias_exists 是
回归测试：修复前 create_storage("local", path=...) 会抛 TypeError，
且文档里写的 create_kb 在代码里根本不存在（ImportError）。
"""
import pytest


def test_list_backends_contains_builtins():
    from knowflow.adapters.storage import list_backends
    backends = list_backends()
    assert "local" in backends
    assert "git" in backends
    assert backends == sorted(backends), "list_backends 应返回排序后的列表"


def test_create_storage_accepts_flat_kwargs(tmp_path):
    """文档写法：create_storage("git", path="...") 必须可用"""
    from knowflow.adapters.storage import create_storage
    s = create_storage("local", path=str(tmp_path / "flat"))
    assert s.root == (tmp_path / "flat").resolve()
    assert s.write("a.txt", "hi") is not None


def test_create_storage_accepts_config_dict(tmp_path):
    """CLI 写法：create_storage("local", config={"path": ...}) 必须可用"""
    from knowflow.adapters.storage import create_storage
    s = create_storage("local", config={"path": str(tmp_path / "cfg")})
    assert s.root == (tmp_path / "cfg").resolve()


def test_create_storage_merges_config_and_kwargs(tmp_path):
    from knowflow.adapters.storage import create_storage
    s = create_storage("local", config={"path": str(tmp_path / "merge")}, ignored="x")
    assert s.root == (tmp_path / "merge").resolve()


def test_create_storage_is_case_insensitive(tmp_path):
    from knowflow.adapters.storage import create_storage
    s = create_storage("LOCAL", path=str(tmp_path / "case"))
    assert s.root == (tmp_path / "case").resolve()


def test_create_storage_unknown_backend_message():
    from knowflow.adapters.storage import create_storage
    with pytest.raises(ValueError) as ei:
        create_storage("nosuchbackend")
    msg = str(ei.value)
    assert "Unknown storage backend" in msg
    assert "local" in msg, "报错信息应列出可用后端"


def test_create_kb_alias_exists(tmp_path):
    """core/knowledge.py 文档用的是 create_kb，必须真的能 import"""
    from knowflow.adapters.knowledge import create_kb, create_knowledge
    assert create_kb is create_knowledge
    kb = create_kb("local", path=str(tmp_path / "kb"))
    assert kb.root == (tmp_path / "kb").resolve()


def test_create_knowledge_config_dict(tmp_path):
    from knowflow.adapters.knowledge import create_knowledge
    kb = create_knowledge("local", config={"path": str(tmp_path / "kb2")})
    assert kb.root == (tmp_path / "kb2").resolve()


def test_create_knowledge_unknown_backend():
    from knowflow.adapters.knowledge import create_knowledge
    with pytest.raises(ValueError) as ei:
        create_knowledge("nope")
    assert "Unknown knowledge base" in str(ei.value)


def test_registry_register_adds_custom_backend(tmp_path):
    from knowflow.adapters import storage as reg
    from knowflow.adapters.storage import local as local_mod

    class MyStorage(local_mod.LocalStorage):
        pass

    reg.register("mytest", MyStorage)
    try:
        assert "mytest" in reg.list_backends()
        s = reg.create_storage("mytest", path=str(tmp_path / "custom"))
        assert isinstance(s, MyStorage)
    finally:
        reg._REGISTRY.pop("mytest", None)
