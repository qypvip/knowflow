"""knowflow/adapters/storage/__init__.py — Storage adapter registry"""
from knowflow.core.storage import StorageAdapter


# Registry: name → class
_REGISTRY = {}


def register(name: str, cls):
    """Register a storage adapter"""
    _REGISTRY[name.lower()] = cls


def create_storage(name: str, **kwargs) -> StorageAdapter:
    """Factory: create a storage adapter by name"""
    name = name.lower()
    if name not in _REGISTRY:
        available = list(_REGISTRY.keys())
        raise ValueError(
            f"Unknown storage backend: '{name}'. "
            f"Available: {available}"
        )
    return _REGISTRY[name](**kwargs)


def list_backends() -> list[str]:
    """List all registered storage backends"""
    return sorted(_REGISTRY.keys())


# ─── Import and register built-in adapters ─────────────────
from . import local as _local_mod
register("local", _local_mod.LocalStorage)

from . import git as _git_mod
register("git", _git_mod.GitStorage)

# Optional adapters — import fails silently, available if deps installed
try:
    from . import s3 as _s3_mod
    register("s3", _s3_mod.S3Storage)
except ImportError:
    pass

# Quark 夸克网盘 — 依赖 kuake_cli，无额外Python包
from . import quark as _quark_mod  # noqa
register("quark", _quark_mod.QuarkStorage)

# WebDAV — 依赖 requests，已预装
from . import webdav as _webdav_mod  # noqa
register("webdav", _webdav_mod.WebDAVStorage)
