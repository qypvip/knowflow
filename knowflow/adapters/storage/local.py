from __future__ import annotations

"""
knowflow/adapters/storage/local.py — Local filesystem storage
===============================================================
Simplest backend: plain directory on disk, no versioning.

Config:
  path: str  (default: ~/knowflow-data)
"""
from pathlib import Path
import os
import time
from knowflow.core.storage import (
    StorageAdapter, StorageItem, StorageError, StorageNotFoundError
)


class LocalStorage(StorageAdapter):
    """Local filesystem storage backend"""
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        root = config.get("path", "~/knowflow-data") if config else "~/knowflow-data"
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
    
    def _resolve(self, path: str) -> Path:
        clean = Path(path).as_posix().lstrip("/")
        resolved = (self.root / clean).resolve()
        if not str(resolved).startswith(str(self.root)):
            raise StorageError(f"Path traversal blocked: {path}")
        return resolved
    
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
        return ""
    
    def write_binary(self, path: str, content: bytes) -> str:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
        return ""
    
    def delete(self, path: str) -> bool:
        p = self._resolve(path)
        if not p.exists():
            return False
        if p.is_file():
            p.unlink()
        else:
            import shutil
            shutil.rmtree(p)
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
                    path=rel,
                    size=stat.st_size if child.is_file() else 0,
                    modified_at=stat.st_mtime,
                    is_dir=child.is_dir(),
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
