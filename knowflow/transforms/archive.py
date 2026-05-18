"""
knowflow/transforms/archive.py — Hot/Warm/Cold data lifecycle
===============================================================
Implements automatic data archiving based on half-life decay model.
"""
from pathlib import Path
import tarfile
import io
import os
import time
from datetime import datetime
from knowflow.core.pipeline import TransformStage, PipelineContext


class ArchiveStage(TransformStage):
    """Hot → Warm → Cold data archiving"""
    
    def __init__(self):
        super().__init__("archive")
        self.hot_days = 30       # Hot retention
        self.cold_months = 12    # Warm retention
    
    def process(self, ctx: PipelineContext) -> dict:
        if ctx.dry_run:
            return self._dry_run(ctx)
        
        warm_dir = ctx.data_dir.parent.parent / "archive" / ctx.plugin_name
        warm_dir.mkdir(parents=True, exist_ok=True)
        
        now = time.time()
        cutoff = now - (self.hot_days * 86400)
        by_month = {}
        freed = 0
        
        for root, dirs, files in os.walk(str(ctx.data_dir)):
            for fname in files:
                fpath = Path(root) / fname
                try:
                    mtime = fpath.stat().st_mtime
                    if mtime < cutoff:
                        rel = fpath.relative_to(ctx.data_dir.parent.parent / "data").as_posix()
                        month = datetime.fromtimestamp(mtime).strftime("%Y-%m")
                        by_month.setdefault(month, []).append((rel, fpath, mtime))
                        freed += fpath.stat().st_size
                except OSError:
                    continue
        
        archives = []
        for month, files in sorted(by_month.items()):
            archive_path = warm_dir / f"{month}.tar.gz"
            with tarfile.open(str(archive_path), "w:gz") as tar:
                for rel, abspath, mtime in files:
                    content = abspath.read_bytes()
                    info = tarfile.TarInfo(name=rel)
                    info.size = len(content)
                    info.mtime = mtime
                    tar.addfile(info, io.BytesIO(content))
                    abspath.unlink()
            archives.append(archive_path.name)
        
        return {
            "status": "ok",
            "archives": len(archives),
            "files": sum(len(v) for v in by_month.values()),
            "freed_kb": round(freed / 1024, 1),
        }
    
    def _dry_run(self, ctx: PipelineContext) -> dict:
        now = time.time()
        cutoff = now - (self.hot_days * 86400)
        candidates = []
        
        for root, dirs, files in os.walk(str(ctx.data_dir)):
            for fname in files:
                fpath = Path(root) / fname
                try:
                    if fpath.stat().st_mtime < cutoff:
                        rel = fpath.relative_to(ctx.data_dir.parent.parent / "data").as_posix()
                        candidates.append(rel)
                except OSError:
                    continue
        
        return {
            "status": "ok",
            "dry_run": True,
            "candidates": len(candidates),
        }
