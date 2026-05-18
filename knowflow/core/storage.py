from __future__ import annotations

"""
knowflow/core/storage.py — Storage Adapter Interface
=====================================================
Storage = WHERE data lives physically.
Every backend implements this interface.

Built-in backends:
  - local:   Local filesystem (simplest)
  - git:     Local + Git versioning (recommended)
  - s3:      AWS S3 and compatible (MinIO, R2, etc.)
  - webdav:  WebDAV protocol (NextCloud, Synology NAS)
  - quark:   夸克网盘 (Chinese cloud drive)
  - baidu:   百度网盘 (Chinese cloud drive)

Usage:
    from knowflow.adapters.storage import create_storage
    store = create_storage("git", path="~/my-data")
    store.write("hello.txt", "world")
    store.commit("added hello")
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import json


class StorageError(Exception): pass
class StorageNotFoundError(StorageError): pass
class StorageAuthError(StorageError): pass
class StorageQuotaError(StorageError): pass


@dataclass
class StorageItem:
    """Metadata about a stored item"""
    path: str                  # Relative path
    size: int                  # Bytes
    modified_at: float         # Unix timestamp
    is_dir: bool = False
    etag: Optional[str] = None # Optional backend-native identifier


class StorageAdapter(ABC):
    """
    Storage Adapter Interface
    
    Every storage backend must implement this ABC.
    Backend-specific config goes in config dict, never in the class itself.
    
    Naming:
      - All paths use forward slashes, relative to store root
      - No leading slash
      - Never use absolute paths
    
    Thread safety: not guaranteed (single-user tool)
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
    
    # ─── Read ──────────────────────────────────────────────
    
    @abstractmethod
    def read(self, path: str) -> str:
        """Read text file. Raises StorageNotFoundError."""
        ...
    
    @abstractmethod
    def read_binary(self, path: str) -> bytes:
        """Read binary file."""
        ...
    
    def read_json(self, path: str) -> dict:
        """Convenience: read and parse JSON."""
        return json.loads(self.read(path))
    
    # ─── Write ─────────────────────────────────────────────
    
    @abstractmethod
    def write(self, path: str, content: str) -> str:
        """
        Write text file. Overwrites if exists.
        Returns revision ID (or empty if unsupported).
        """
        ...
    
    @abstractmethod
    def write_binary(self, path: str, content: bytes) -> str:
        """Write binary file."""
        ...
    
    def write_json(self, path: str, data: dict) -> str:
        """Convenience: serialize and write JSON."""
        return self.write(path, json.dumps(data, ensure_ascii=False, indent=2, default=str))
    
    # ─── Delete ────────────────────────────────────────────
    
    @abstractmethod
    def delete(self, path: str) -> bool:
        """Delete path. Returns True if it existed."""
        ...
    
    # ─── Query ─────────────────────────────────────────────
    
    @abstractmethod
    def exists(self, path: str) -> bool:
        ...
    
    @abstractmethod
    def list(self, prefix: str = "") -> list[StorageItem]:
        """List immediate children (non-recursive)."""
        ...
    
    @abstractmethod
    def walk(self, prefix: str = "") -> list[StorageItem]:
        """Recursively list all items."""
        ...
    
    # ─── Versioning (optional) ─────────────────────────────
    
    def commit(self, message: str = "") -> str:
        """Save snapshot. Default: no-op."""
        return ""
    
    def log(self, max_count: int = 10) -> list[dict]:
        """Return history. Default: empty."""
        return []
    
    def diff(self, rev_a: str, rev_b: str, path: str = "") -> str:
        """Diff between revisions. Default: empty."""
        return ""
    
    # ─── Archive ───────────────────────────────────────────
    
    def archive(self, source_prefix: str, archive_path: str) -> str:
        """
        Archive files under prefix into single compressed file.
        Default: tar.gz. Override for backend-native archiving.
        """
        import tarfile, io
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w:gz') as tar:
            for item in self.walk(source_prefix):
                if not item.is_dir:
                    content = self.read_binary(item.path)
                    info = tarfile.TarInfo(name=item.path)
                    info.size = len(content)
                    info.mtime = item.modified_at
                    tar.addfile(info, io.BytesIO(content))
        self.write_binary(archive_path, buf.getvalue())
        return archive_path
    
    def prune(self, prefix: str, older_than_days: int, dry_run: bool = False) -> list[str]:
        """Delete items older than N days."""
        import time
        cutoff = time.time() - (older_than_days * 86400)
        deleted = []
        for item in self.walk(prefix):
            if not item.is_dir and item.modified_at < cutoff:
                deleted.append(item.path)
                if not dry_run:
                    self.delete(item.path)
        return deleted
