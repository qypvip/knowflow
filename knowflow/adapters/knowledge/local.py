"""
knowflow/adapters/knowledge/local.py — Local directory KB
Simple markdown files in a directory.
"""
from pathlib import Path
from knowflow.core.knowledge import KnowledgeAdapter, KnowledgePage, KnowledgeError


class LocalKB(KnowledgeAdapter):
    """Local markdown directory knowledge base"""
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        path = config.get("path", "~/knowflow-output") if config else "~/knowflow-output"
        self.root = Path(path).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
    
    def name(self) -> str:
        return f"Local ({self.root})"
    
    def sync(self, pages: list[KnowledgePage]) -> dict:
        synced = 0
        errors = []
        for page in pages:
            try:
                target = self.root / page.path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(page.content, encoding="utf-8")
                synced += 1
            except Exception as e:
                errors.append(f"{page.path}: {e}")
        return {"synced": synced, "skipped": 0, "errors": errors}
    
    def search(self, query: str, limit: int = 10) -> list[KnowledgePage]:
        results = []
        for md_file in sorted(self.root.rglob("*.md"))[:limit]:
            if query.lower() in md_file.read_text(encoding="utf-8").lower():
                results.append(KnowledgePage(
                    title=md_file.stem,
                    content=md_file.read_text(encoding="utf-8"),
                    path=str(md_file.relative_to(self.root)),
                ))
        return results
