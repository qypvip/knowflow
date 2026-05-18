"""
knowflow/adapters/knowledge/obsidian.py — Obsidian vault KB
Syncs markdown pages to an Obsidian-compatible vault directory.
"""
from pathlib import Path
from knowflow.core.knowledge import KnowledgeAdapter, KnowledgePage, KnowledgeError


class ObsidianKB(KnowledgeAdapter):
    """Obsidian vault knowledge base"""
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        path = config.get("path", "~/obsidian-vault") if config else "~/obsidian-vault"
        self.root = Path(path).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._ensure_vault()
    
    def _ensure_vault(self):
        """Ensure .obsidian/ config exists for vault detection"""
        obsidian_dir = self.root / ".obsidian"
        obsidian_dir.mkdir(exist_ok=True)
        app_file = obsidian_dir / "app.json"
        if not app_file.exists():
            import json
            app_file.write_text(json.dumps({"promptDelete": False}, indent=2))
    
    def name(self) -> str:
        return f"Obsidian ({self.root})"
    
    def sync(self, pages: list[KnowledgePage]) -> dict:
        synced = 0
        errors = []
        for page in pages:
            try:
                target = self.root / page.path
                target.parent.mkdir(parents=True, exist_ok=True)
                # Add Obsidian frontmatter tags if provided
                content = page.content
                if page.tags:
                    tags_line = "\n".join(f"  - {t}" for t in page.tags)
                    frontmatter = f"---\ntags:\n{tags_line}\n---\n\n"
                    if not content.startswith("---"):
                        content = frontmatter + content
                target.write_text(content, encoding="utf-8")
                synced += 1
            except Exception as e:
                errors.append(f"{page.path}: {e}")
        return {"synced": synced, "skipped": 0, "errors": errors}
    
    def search(self, query: str, limit: int = 10) -> list[KnowledgePage]:
        results = []
        for md_file in sorted(self.root.rglob("*.md"))[:limit]:
            try:
                content = md_file.read_text(encoding="utf-8")
                if query.lower() in content.lower():
                    results.append(KnowledgePage(
                        title=md_file.stem,
                        content=content,
                        path=str(md_file.relative_to(self.root)),
                    ))
            except Exception:
                continue
        return results
