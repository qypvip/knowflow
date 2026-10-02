"""knowflow/adapters/knowledge/__init__.py — Knowledge adapter registry"""
from typing import Optional

from knowflow.core.knowledge import KnowledgeAdapter, KnowledgePage

_REGISTRY = {}

def register(name: str, cls):
    _REGISTRY[name.lower()] = cls

def create_knowledge(name: str, config: Optional[dict] = None, **kwargs) -> KnowledgeAdapter:
    """Factory: create a knowledge-base adapter by name.

    两种调用方式都支持：
        create_knowledge("obsidian", path="~/my-vault")        # 扁平参数
        create_knowledge("obsidian", config={"path": "..."})   # 显式 config 字典
    """
    name = name.lower()
    if name not in _REGISTRY:
        available = list(_REGISTRY.keys())
        raise ValueError(
            f"Unknown knowledge base: '{name}'. Available: {available}"
        )
    if config is None:
        config = dict(kwargs) if kwargs else None
    elif kwargs:
        config = {**config, **kwargs}
    return _REGISTRY[name](config)


# 别名：core/knowledge.py 的文档里写的是 create_kb，保持一致（曾导致 ImportError）
create_kb = create_knowledge

def list_backends() -> list[str]:
    return sorted(_REGISTRY.keys())

# Built-in adapters
from . import local as _local
register("local", _local.LocalKB)

from . import obsidian as _obsidian
register("obsidian", _obsidian.ObsidianKB)
