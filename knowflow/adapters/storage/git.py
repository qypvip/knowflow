from __future__ import annotations

"""
knowflow/adapters/storage/git.py — Git-backed storage
======================================================
Recommended backend: local files + full version history.

Config:
  path: str  (default: ~/knowflow-data)
"""
from pathlib import Path
import subprocess
import os
import time
import json
from knowflow.core.storage import (
    StorageAdapter, StorageItem, StorageError, StorageNotFoundError
)


class GitStorage(StorageAdapter):
    """Git-backed storage with version history"""
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        root = config.get("path", "~/knowflow-data") if config else "~/knowflow-data"
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._git("init", check=False)
        self._ensure_user()
    
    def _resolve(self, path: str) -> Path:
        clean = Path(path).as_posix().lstrip("/")
        resolved = (self.root / clean).resolve()
        if not str(resolved).startswith(str(self.root)):
            raise StorageError(f"Path traversal blocked: {path}")
        return resolved
    
    def _git(self, *args, check: bool = True) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root), *args],
                capture_output=True, text=True, timeout=30
            )
            if check and result.returncode != 0:
                raise StorageError(f"Git: {result.stderr.strip() or 'unknown error'}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise StorageError("Git command timed out")
    
    def _ensure_user(self):
        if not self._git("config", "user.name", check=False):
            self._git("config", "user.name", "KnowFlow")
            self._git("config", "user.email", "knowflow@local")
    
    def read(self, path: str) -> str:
        p = self._resolve(path)
        if not p.exists():
            raise StorageNotFoundError(f"Not found: {path}")
        return p.read_text(encoding="utf-8")
    
    def read_binary(self, path: str) -> bytes:
        p = self._resolve(path)
        if not p.exists():
            raise StorageNotFoundError(f"Not found: {path}")
        return p.read_bytes()
    
    def write(self, path: str, content: str) -> str:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return self._git("add", str(p.relative_to(self.root)))
    
    def write_binary(self, path: str, content: bytes) -> str:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
        return self._git("add", str(p.relative_to(self.root)))
    
    def delete(self, path: str) -> bool:
        p = self._resolve(path)
        if not p.exists():
            return False
        p.unlink()
        self._git("add", str(p.relative_to(self.root)))
        return True
    
    def exists(self, path: str) -> bool:
        try:
            return self._resolve(path).exists()
        except StorageError:
            return False
    
    def list(self, prefix: str = "") -> list[StorageItem]:
        p = self._resolve(prefix) if prefix else self.root
        if not p.exists():
            return []
        items = []
        for child in sorted(p.iterdir()):
            try:
                stat = child.stat()
                rel = child.relative_to(self.root).as_posix()
                items.append(StorageItem(
                    path=rel, size=stat.st_size if child.is_file() else 0,
                    modified_at=stat.st_mtime, is_dir=child.is_dir(),
                ))
            except OSError:
                continue
        return items
    
    def walk(self, prefix: str = "") -> list[StorageItem]:
        p = self._resolve(prefix) if prefix else self.root
        if not p.exists():
            return []
        items = []
        for root_dir, dirs, files in os.walk(str(p)):
            root_path = Path(root_dir)
            for name in files:
                child = root_path / name
                try:
                    stat = child.stat()
                    rel = child.relative_to(self.root).as_posix()
                    items.append(StorageItem(path=rel, size=stat.st_size, modified_at=stat.st_mtime))
                except OSError:
                    continue
        return sorted(items, key=lambda x: x.path)
    
    def commit(self, message: str = "") -> str:
        self._git("add", "-A")
        status = self._git("status", "--porcelain")
        if not status:
            return ""
        if not message:
            message = f"Auto-commit {time.strftime('%Y-%m-%d %H:%M:%S')}"
        self._ensure_user()
        self._git("commit", "-m", message)
        return self._git("rev-parse", "HEAD")
    
    def log(self, max_count: int = 10) -> list[dict]:
        fmt = '{"id":"%H","message":"%s","timestamp":"%aI","author":"%an"}'
        output = self._git("log", f"--max-count={max_count}", f"--format={fmt}", check=False)
        if not output:
            return []
        return [json.loads(line) for line in output.split("\n") if line.strip()]
    
    def diff(self, rev_a: str, rev_b: str, path: str = "") -> str:
        args = ["diff", f"{rev_a}..{rev_b}"]
        if path:
            args.append("--", str(self._resolve(path)))
        return self._git(*args, check=False)
