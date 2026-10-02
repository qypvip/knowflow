"""LocalStorage 全量行为测试（读写 / 列表 / 删除 / 归档 / 剪枝 / 路径穿越防护）"""
import os
import tarfile

import pytest

from knowflow.core.storage import StorageError, StorageNotFoundError


def test_write_read_roundtrip(local_store):
    local_store.write("hello.txt", "世界你好\n第二行")
    assert local_store.read("hello.txt") == "世界你好\n第二行"


def test_write_creates_nested_dirs(local_store):
    local_store.write("a/b/c/deep.txt", "x")
    assert local_store.read("a/b/c/deep.txt") == "x"


def test_write_overwrites(local_store):
    local_store.write("f.txt", "one")
    local_store.write("f.txt", "two")
    assert local_store.read("f.txt") == "two"


def test_read_missing_raises(local_store):
    with pytest.raises(StorageNotFoundError):
        local_store.read("nope.txt")
    with pytest.raises(StorageNotFoundError):
        local_store.read_binary("nope.bin")


def test_binary_roundtrip(local_store):
    payload = bytes(range(256))
    local_store.write_binary("blob.bin", payload)
    assert local_store.read_binary("blob.bin") == payload


def test_json_roundtrip_keeps_unicode(local_store):
    data = {"名称": "测试", "列表": [1, 2, 3], "嵌套": {"a": True}}
    local_store.write_json("d.json", data)
    assert local_store.read_json("d.json") == data
    raw = local_store.read("d.json")
    assert "名称" in raw, "write_json 应使用 ensure_ascii=False，中文不应被转义"


def test_exists(local_store):
    assert local_store.exists("no.txt") is False
    local_store.write("yes.txt", "1")
    assert local_store.exists("yes.txt") is True


def test_delete_file_and_dir(local_store):
    local_store.write("keep/del.txt", "x")
    assert local_store.delete("keep/del.txt") is True
    assert local_store.exists("keep/del.txt") is False
    assert local_store.delete("keep/del.txt") is False, "重复删除应返回 False"

    local_store.write("dir/a.txt", "1")
    local_store.write("dir/sub/b.txt", "2")
    assert local_store.delete("dir") is True
    assert local_store.exists("dir") is False
    assert local_store.walk("dir") == []


def test_list_is_non_recursive(local_store):
    local_store.write("top.txt", "1")
    local_store.write("sub/inner.txt", "2")
    names = {i.path for i in local_store.list("")}
    assert "top.txt" in names
    assert "sub" in names
    assert "sub/inner.txt" not in names, "list 只应返回直接子项"
    sub = next(i for i in local_store.list("") if i.path == "sub")
    assert sub.is_dir is True
    top = next(i for i in local_store.list("") if i.path == "top.txt")
    assert top.is_dir is False and top.size == 1


def test_walk_is_recursive_and_sorted(local_store):
    for p in ["b/x.txt", "a/y.txt", "a/z.txt", "root.txt"]:
        local_store.write(p, "1")
    paths = [i.path for i in local_store.walk("")]
    assert paths == sorted(paths)
    assert set(paths) == {"a/y.txt", "a/z.txt", "b/x.txt", "root.txt"}


def test_walk_missing_prefix_returns_empty(local_store):
    assert local_store.walk("does/not/exist") == []
    assert local_store.list("does/not/exist") == []


def test_path_traversal_blocked(local_store):
    for bad in ["../escape.txt", "../../etc/passwd"]:
        with pytest.raises(StorageError):
            local_store.write(bad, "pwned")
    assert not (local_store.root.parent / "escape.txt").exists()


def test_archive_creates_targz(local_store):
    local_store.write("logs/2026-10-01.json", '{"a":1}')
    local_store.write("logs/2026-10-02.json", '{"b":2}')
    out = local_store.archive("logs", "archive/oct.tar.gz")
    assert out == "archive/oct.tar.gz"
    assert local_store.exists(out)
    raw = local_store.root / out
    with tarfile.open(raw, "r:gz") as tar:
        names = set(tar.getnames())
    assert "logs/2026-10-01.json" in names
    assert "logs/2026-10-02.json" in names


def test_prune_dry_run_then_real(local_store):
    local_store.write("data/old.txt", "old")
    old = 100 * 86400
    p = local_store.root / "data/old.txt"
    os.utime(p, (p.stat().st_atime - old, p.stat().st_mtime - old))
    local_store.write("data/new.txt", "new")

    preview = local_store.prune("data", older_than_days=30, dry_run=True)
    assert preview == ["data/old.txt"]
    assert local_store.exists("data/old.txt"), "dry_run 不应真的删除"

    deleted = local_store.prune("data", older_than_days=30, dry_run=False)
    assert deleted == ["data/old.txt"]
    assert not local_store.exists("data/old.txt")
    assert local_store.exists("data/new.txt"), "新文件不应被剪枝"
