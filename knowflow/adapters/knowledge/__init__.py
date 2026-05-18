"""knowflow/adapters/knowledge/__init__.py — Knowledge adapter registry"""
from knowflow.core.knowledge import KnowledgeAdapter, KnowledgePage

_REGISTRY = {}

def register(name: str, cls):
    _REGISTRY[name.lower()] = cls

def create_knowledge(name: str, **kwargs) -> KnowledgeAdapter:
    name = name.lower()
    if name not in _REGISTRY:
        available = list(_REGISTRY.keys())
        raise ValueError(
            f"Unknown knowledge base: '{name}'. Available: {available}"
        )
    return _REGISTRY[name](**kwargs)

def list_backends() -> list[str]:
    return sorted(_REGISTRY.keys())

# Built-in adapters
from . import local as _local
register("local", _local.LocalKB)

from . import obsidian as _obsidian
register("obsidian", _obsidian.ObsidianKB)
