"""StorageAdapter 抽象基类：抽象方法强制 + 版本控制默认实现为 no-op"""
import pytest

from knowflow.core.storage import StorageAdapter, StorageItem


class MinimalStorage(StorageAdapter):
    """只实现抽象方法的最小后端，用于验证基类默认行为"""

    def read(self, path): return ""
    def read_binary(self, path): return b""
    def write(self, path, content): return ""
    def write_binary(self, path, content): return ""
    def delete(self, path): return False
    def exists(self, path): return False
    def list(self, prefix=""): return []
    def walk(self, prefix=""): return []


def test_abstract_base_cannot_be_instantiated():
    with pytest.raises(TypeError):
        StorageAdapter()


def test_incomplete_subclass_cannot_be_instantiated():
    class Incomplete(StorageAdapter):
        def read(self, path):
            return ""

    with pytest.raises(TypeError) as ei:
        Incomplete()
    assert "abstract" in str(ei.value).lower()


def test_versioning_defaults_are_noop():
    s = MinimalStorage()
    assert s.commit("msg") == ""
    assert s.log() == []
    assert s.diff("a", "b") == ""


def test_config_defaults_to_empty_dict():
    s = MinimalStorage()
    assert s.config == {}
    s2 = MinimalStorage(config={"k": "v"})
    assert s2.config == {"k": "v"}


def test_storage_item_defaults():
    item = StorageItem(path="a/b.txt", size=10, modified_at=1.0)
    assert item.is_dir is False
    assert item.etag is None
