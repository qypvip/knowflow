"""pytest 根配置：让测试无需安装即可 import knowflow，并提供公共 fixture。"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture()
def local_store(tmp_path):
    """本地文件存储后端（临时目录）"""
    from knowflow.adapters.storage import create_storage
    return create_storage("local", path=str(tmp_path / "store"))


@pytest.fixture()
def git_store(tmp_path):
    """Git 版本化存储后端（临时目录）"""
    from knowflow.adapters.storage import create_storage
    return create_storage("git", path=str(tmp_path / "gitstore"))
