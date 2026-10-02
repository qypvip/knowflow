"""PipelineRunner / TransformStage：注册、执行、跳过、错误处理"""
from pathlib import Path

import pytest

from knowflow.core.pipeline import PipelineContext, PipelineRunner, TransformStage


class RecordingStage(TransformStage):
    def __init__(self, name="rec", status="ok", raise_exc=None):
        super().__init__(name)
        self.seen = []
        self._status = status
        self._raise = raise_exc

    def process(self, ctx: PipelineContext) -> dict:
        self.seen.append(ctx)
        if self._raise:
            raise self._raise
        return {"status": self._status, "detail": "ran"}


class NeverRunStage(TransformStage):
    def __init__(self):
        super().__init__("never")
        self.called = False

    def should_run(self, ctx):
        return False

    def process(self, ctx):
        self.called = True
        return {"status": "ok"}


def _run(runner, plugin="demo", tmp_path=None, **kw):
    return runner.run_plugin(plugin, storage=None,
                             data_dir=tmp_path / "data",
                             output_dir=tmp_path / "out", **kw)


def test_register_and_run_ok(tmp_path):
    runner = PipelineRunner({})
    stage = RecordingStage()
    runner.register(stage)
    assert "rec" in runner.stages

    res = _run(runner, tmp_path=tmp_path)
    assert res["success"] is True
    assert res["plugin"] == "demo"
    assert res["stages"]["rec"]["status"] == "ok"


def test_context_paths_are_namespaced_by_plugin(tmp_path):
    runner = PipelineRunner({})
    stage = RecordingStage()
    runner.register(stage)
    _run(runner, plugin="football", tmp_path=tmp_path)

    ctx = stage.seen[0]
    assert ctx.plugin_name == "football"
    assert ctx.data_dir == tmp_path / "data" / "football"
    assert ctx.output_dir == tmp_path / "out" / "football"


def test_should_run_false_marks_skipped(tmp_path):
    runner = PipelineRunner({})
    stage = NeverRunStage()
    runner.register(stage)
    res = _run(runner, tmp_path=tmp_path)

    assert stage.called is False
    assert res["stages"]["never"] == {"status": "skipped"}
    assert res["success"] is True


def test_stage_returning_error_marks_failure(tmp_path):
    runner = PipelineRunner({})
    runner.register(RecordingStage(name="bad", status="error"))
    res = _run(runner, tmp_path=tmp_path)
    assert res["success"] is False
    assert res["stages"]["bad"]["status"] == "error"


def test_stage_exception_is_captured_not_raised(tmp_path):
    runner = PipelineRunner({})
    runner.register(RecordingStage(name="boom", raise_exc=RuntimeError("磁盘满了")))
    res = _run(runner, tmp_path=tmp_path)

    assert res["success"] is False
    assert res["stages"]["boom"]["status"] == "error"
    assert "磁盘满了" in res["stages"]["boom"]["detail"]


def test_one_bad_stage_does_not_block_others(tmp_path):
    runner = PipelineRunner({})
    runner.register(RecordingStage(name="first"))
    runner.register(RecordingStage(name="middle", status="error"))
    runner.register(RecordingStage(name="last"))
    res = _run(runner, tmp_path=tmp_path)

    assert res["stages"]["first"]["status"] == "ok"
    assert res["stages"]["middle"]["status"] == "error"
    assert res["stages"]["last"]["status"] == "ok", "后续 stage 仍应执行"
    assert res["success"] is False


def test_run_all_covers_every_plugin(tmp_path):
    runner = PipelineRunner({})
    runner.register(RecordingStage(name="s"))
    results = runner.run_all(["a", "b", "c"], storage=None,
                             data_dir=tmp_path / "data", output_dir=tmp_path / "out")
    assert [r["plugin"] for r in results] == ["a", "b", "c"]
    assert all(r["success"] for r in results)


def test_load_plugin_config(tmp_path):
    runner = PipelineRunner({})
    pdir = tmp_path / "plugin"
    pdir.mkdir()
    (pdir / "plugin.yaml").write_text("name: demo\nschedule: daily\n", encoding="utf-8")
    cfg = runner.load_plugin_config(pdir)
    assert cfg == {"name": "demo", "schedule": "daily"}


def test_load_plugin_config_missing_returns_empty(tmp_path):
    runner = PipelineRunner({})
    assert runner.load_plugin_config(tmp_path / "nothing") == {}
