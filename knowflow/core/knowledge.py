"""
knowflow/core/knowledge.py — Knowledge Base Adapter Interface
==============================================================
Knowledge Base = HOW humans read and interact with the data.
Different from Storage (where data lives).

Built-in adapters:
  - local:    Plain markdown directory
  - obsidian: Obsidian vault (markdown + .obsidian config)
  - notion:   Notion database (via API)
  - ima:      腾讯IMA知识库 (via OpenAPI)
  - mkdocs:   MkDocs static site
  - gitbook:  GitBook-style documentation

Usage:
    from knowflow.adapters.knowledge import create_knowledge, create_kb  # create_kb 为别名
    kb = create_knowledge("obsidian", path="~/my-vault")
    kb.sync([KnowledgePage(title="周报", content="# 周报\\n…", path="weekly/2026-10-02.md")])
    kb.search("阅读习惯", limit=5)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


class KnowledgeError(Exception): pass


@dataclass
class KnowledgePage:
    """A page/document in the knowledge base"""
    title: str
    content: str           # Markdown content
    path: str              # Relative path within KB
    tags: list[str] = None
    metadata: dict = None


class KnowledgeAdapter(ABC):
    """
    Knowledge Base Adapter Interface
    
    Transforms structured data from Storage into human-readable
    documents in the target knowledge base system.
    
    A single data source can sync to multiple KBs simultaneously
    (e.g., Push to Obsidian + Notion + IMA at the same time).
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
    
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this KB backend"""
        ...
    
    @abstractmethod
    def sync(self, pages: list[KnowledgePage]) -> dict:
        """
        Sync pages to the knowledge base.
        
        Args:
            pages: List of KnowledgePage objects to sync
        
        Returns:
            {"synced": 5, "skipped": 2, "errors": [...]}
        """
        ...
    
    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[KnowledgePage]:
        """
        Search the knowledge base.
        Returns matching pages.
        """
        ...
    
    def validate_config(self) -> list[str]:
        """
        Check if configuration is valid.
        Returns list of error messages (empty = valid).
        """
        return []
