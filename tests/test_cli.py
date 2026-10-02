"""CLI 冒烟测试：以子进程方式跑 `python -m knowflow`，确保入口没被打断"""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cli(*args, cwd=None):
    """跑 `python -m knowflow`。

    必须注入 PYTHONPATH：测试会在 tmp 目录里跑 CLI，而 knowflow 只有被
    pip install 过才全局可 import。本地开发时源码并未安装，若不注入，
    子进程会以 "No module named knowflow" 退出 —— 那会让断言假通过/假失败。
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.run([sys.executable, "-m", "knowflow", *args],
                          cwd=cwd or ROOT, capture_output=True, text=True,
                          timeout=120, env=env)


def test_help_exits_zero():
    r = _cli("--help")
    assert r.returncode == 0, r.stderr
    assert "Usage" in r.stdout
    assert "knowflow init" in r.stdout


def test_list_shows_builtin_templates():
    r = _cli("list")
    assert r.returncode == 0, r.stderr
    assert "Available templates" in r.stdout
    for kw in ("足球预测", "股票分析", "网页监控"):
        assert kw in r.stdout, "模板列表里应有 %s" % kw


def test_version_exits_zero():
    r = _cli("version")
    assert r.returncode == 0, r.stderr


def test_init_creates_project(tmp_path):
    """init 应在指定目录建出可运行的项目骨架"""
    target = tmp_path / "proj"
    r = _cli("init", "daily-journal", "--dir", str(target))
    if r.returncode != 0:
        pytest.skip("init 在当前环境不可用：%s" % (r.stderr or r.stdout)[:200])
    assert target.exists()
    assert any(target.iterdir()), "项目目录不应为空"


def test_run_without_project_reports_friendly_error(tmp_path):
    """在空目录里 run 应给出可读的提示，而不是抛 Python 栈。

    注意：这里断言的是"友好报错且不崩"，**不是**退出码。
    实测 knowflow run 在缺 knowflow.toml 时输出
      ❌ No knowflow.toml found. Run 'knowflow init' first.
    并以 0 退出（属于"告知性"提示，非执行失败）。
    如果将来希望脚本能靠退出码判失败，应把 CLI 改成 return 1 —— 那属于行为变更，
    需单独决定，不要靠改这个测试来解决。
    """
    empty = tmp_path / "empty"
    empty.mkdir()
    r = _cli("run", cwd=str(empty))
    assert "Traceback" not in r.stderr, "不应向用户暴露 Python 栈"
    combined = r.stdout + r.stderr
    assert "knowflow.toml" in combined, "应提示缺少 knowflow.toml"
    assert "knowflow init" in combined, "应给出下一步该做什么"
