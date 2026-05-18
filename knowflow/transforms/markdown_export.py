"""
knowflow/transforms/markdown_export.py — JSON → Markdown export
================================================================
Converts structured JSON data into human-readable Markdown.
"""
from pathlib import Path
import json
from datetime import datetime
from knowflow.core.pipeline import TransformStage, PipelineContext, PipelineError


class MarkdownExport(TransformStage):
    """Convert JSON data files to Markdown documents"""
    
    def __init__(self):
        super().__init__("markdown_export")
    
    def process(self, ctx: PipelineContext) -> dict:
        data_dir = ctx.data_dir
        output_dir = ctx.output_dir
        
        if not data_dir.exists():
            return {"status": "skipped", "reason": "No data directory"}
        
        output_dir.mkdir(parents=True, exist_ok=True)
        generated = []
        
        for json_file in sorted(data_dir.rglob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                ctx.plugin_config.get("_warnings", []).append(f"Skipped invalid JSON: {json_file.name}")
                continue
            
            md = self._to_markdown(data, json_file, ctx.plugin_name)
            if md:
                md_name = json_file.stem + ".md"
                md_rel = json_file.relative_to(data_dir).parent / md_name
                md_path = output_dir / md_rel
                md_path.parent.mkdir(parents=True, exist_ok=True)
                md_path.write_text(md, encoding="utf-8")
                generated.append(str(md_rel))
        
        return {
            "status": "ok",
            "generated": len(generated),
            "files": generated[:5],
        }
    
    def _to_markdown(self, data: dict, json_path: Path, plugin: str) -> str:
        if not data:
            return None
        
        lines = []
        lines.append(f"# {plugin.title()} — {json_path.stem}")
        lines.append("")
        lines.append(f"> 自动生成 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"> 源: `{json_path.relative_to(json_path.parent.parent.parent)}`")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        self._render(lines, data, 2)
        
        return "\n".join(lines)
    
    def _render(self, lines: list, data, level: int):
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)) and not isinstance(v, str):
                    h = k.replace("_", " ").title()
                    lines.append(f"{'#' * level} {h}")
                    lines.append("")
                    self._render(lines, v, min(level + 1, 6))
                elif isinstance(v, list) and v and isinstance(v[0], dict):
                    h = k.replace("_", " ").title()
                    lines.append(f"{'#' * level} {h}")
                    lines.append("")
                    self._render_table(lines, v)
                else:
                    label = k.replace("_", " ").title()
                    lines.append(f"- **{label}**: {self._fmt(v)}")
            lines.append("")
        elif isinstance(data, list):
            if data and isinstance(data[0], dict):
                self._render_table(lines, data)
            else:
                for item in data:
                    lines.append(f"- {self._fmt(item)}")
                lines.append("")
    
    def _render_table(self, lines: list, items: list[dict]):
        if not items:
            return
        keys = list(dict.fromkeys(k for item in items for k in item.keys()
                                   if not isinstance(item.get(k), (dict, list))))
        if not keys:
            return
        lines.append("| " + " | ".join(k.replace("_", " ").title() for k in keys) + " |")
        lines.append("| " + " | ".join("---" for _ in keys) + " |")
        for item in items:
            row = "| " + " | ".join(str(self._fmt(item.get(k, "")))[:60] for k in keys) + " |"
            lines.append(row)
        lines.append("")
    
    def _fmt(self, v) -> str:
        if v is None: return "—"
        if isinstance(v, bool): return "✅" if v else "❌"
        if isinstance(v, float): return f"{v:.2f}"
        return str(v)
