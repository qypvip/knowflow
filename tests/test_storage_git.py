"""GitStorage：CRUD 行为 + 版本历史（与 LocalStorage 接口保持一致）"""
import shutil

import pytest

from knowflow.core.storage import StorageNotFoundError

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="需要 git 可执行文件")


def test_write_and_commit_records_history(git_store):
    git_store.write("pred/2026-10-02.json", '{"match":"A vs B"}')
    sha = git_store.commit("首次预测")
    assert len(sha) == 40, "commit 应返回完整 sha"
    log = git_store.log()
    assert len(log) == 1
    assert log[0]["message"] == "首次预测"
    assert log[0]["id"] == sha


def test_commit_without_changes_returns_empty(git_store):
    git_store.write("a.txt", "1")
    assert git_store.commit("one") != ""
    assert git_store.commit("two") == "", "无改动时不应产生空提交"


def test_read_matches_written(git_store):
    git_store.write("nested/dir/f.txt", "内容")
    git_store.commit("add")
    assert git_store.read("nested/dir/f.txt") == "内容"
    with pytest.raises(StorageNotFoundError):
        git_store.read("missing.txt")


def test_binary_and_json(git_store):
    git_store.write_binary("b.bin", b"\x00\x01\x02")
    git_store.write_json("j.json", {"键": "值"})
    git_store.commit("bin+json")
    assert git_store.read_binary("b.bin") == b"\x00\x01\x02"
    assert git_store.read_json("j.json") == {"键": "值"}


def test_delete_file_then_directory(git_store):
    """接口约定 delete(path) 对文件与目录都应生效（曾经目录会抛 IsADirectoryError）"""
    git_store.write("d/x.txt", "1")
    git_store.write("d/sub/y.txt", "2")
    git_store.commit("init")

    assert git_store.delete("d/x.txt") is True
    assert git_store.exists("d/x.txt") is False
    assert git_store.delete("d/x.txt") is False

    assert git_store.delete("d") is True
    assert git_store.exists("d") is False


def test_log_max_count(git_store):
    for i in range(4):
        git_store.write("f.txt", str(i))
        git_store.commit("c%d" % i)
    assert len(git_store.log(max_count=2)) == 2


def test_diff_between_revisions(git_store):
    git_store.write("f.txt", "版本一")
    a = git_store.commit("v1")
    git_store.write("f.txt", "版本二")
    b = git_store.commit("v2")
    d = git_store.diff(a, b)
    assert "版本一" in d or "版本二" in d, "diff 应反映内容变化"


def test_list_and_walk(git_store):
    git_store.write("top.txt", "1")
    git_store.write("sub/inner.txt", "22")
    git_store.commit("init")
    names = {i.path for i in git_store.list("")}
    assert {"top.txt", "sub"} <= names
    assert "sub/inner.txt" not in names
    all_paths = {i.path for i in git_store.walk("")}
    assert {"top.txt", "sub/inner.txt"} <= all_paths
