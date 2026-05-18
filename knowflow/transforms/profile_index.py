"""
knowflow/transforms/profile_index.py — Auto-generate PROFILE.md
===============================================================
Creates a human-readable index of all data in the knowledge base.
"""
from pathlib import Path
from datetime import datetime
import os
from knowflow.core.pipeline import TransformStage, PipelineContext


class ProfileIndex(TransformStage):
    """Generate PROFILE.md index of the knowledge base"""
    
    def __init__(self):
        super().__init__("profile_index")
    
    def process(self, ctx: PipelineContext) -> dict:
        root = ctx.data_dir.parent.parent  # ~/knowflow-data or ~/knowledge
        profile_path = root / "PROFILE.md"
        manifest_path = root / "index" / "manifest.json"
        
        plugins = {}
        data_dir = ctx.data_dir.parent  # data/
        if data_dir.exists():
            for plugin_dir in sorted(data_dir.iterdir()):
                if plugin_dir.is_dir():
                    plugins[plugin_dir.name] = self._scan_dir(plugin_dir)
        
        profile = self._build_profile(plugins, ctx.plugin_config)
        profile_path.write_text(profile, encoding="utf-8")
        
        import json
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps({
                "generated_at": datetime.now().isoformat(),
                "plugins": list(plugins.keys()),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        return {
            "status": "ok",
            "profile_size": len(profile),
            "plugins": list(plugins.keys()),
        }
    
    def _scan_dir(self, plugin_dir: Path) -> dict:
        count = 0
        size = 0
        latest = 0.0
        for root, dirs, files in os.walk(str(plugin_dir)):
            for f in files:
                try:
                    st = (Path(root) / f).stat()
                    count += 1
                    size += st.st_size
                    latest = max(latest, st.st_mtime)
                except OSError:
                    continue
        return {
            "files": count,
            "size_kb": round(size / 1024, 1),
            "updated": datetime.fromtimestamp(latest).isoformat() if latest else "—",
        }
    
    def _build_profile(self, plugins: dict, config: dict) -> str:
        lines = ["# 🧠 KnowFlow Knowledge Base", "",
                 f"自动生成 {datetime.now().strftime('%Y-%m-%d %H:%M')}", "",
                 "## 📊 概览", "",
                 f"| 指标 | 数值 |",
                 f"|------|------|",
                 f"| 插件数 | {len(plugins)} |",
                 f"| 总文件 | {sum(p['files'] for p in plugins.values())} |",
                 f"| 总大小 | {sum(p['size_kb'] for p in plugins.values()):.1f} KB |",
                 "", "## 🔌 插件", ""]
        
        for name, st in plugins.items():
            icon = {"football": "⚽", "stock": "📈", "worldcup": "🏆"}
            lines.append(f"### {icon.get(name, '📦')} {name.title()}")
            lines.append(f"- 文件: {st['files']}")
            lines.append(f"- 大小: {st['size_kb']} KB")
            lines.append(f"- 更新: {st['updated']}")
            lines.append("")
        
        lines.append("---")
        lines.append("> KnowFlow — Agent Knowledge Pipeline")
        return "\n".join(lines)
