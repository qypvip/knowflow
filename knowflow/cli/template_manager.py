"""
knowflow/cli/template_manager.py — Template system
====================================================
Init new projects from built-in templates.

Usage:
    knowflow init football     # Create football prediction project
    knowflow list              # List available templates
"""
from pathlib import Path
import shutil
import yaml

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def list_templates() -> list[dict]:
    """List all available templates with descriptions"""
    templates = []
    for tdir in sorted(TEMPLATES_DIR.iterdir()):
        if tdir.is_dir():
            cfg_path = tdir / "plugin.yaml"
            if cfg_path.exists():
                with open(cfg_path) as f:
                    cfg = yaml.safe_load(f) or {}
                templates.append({
                    "name": tdir.name,
                    "display": cfg.get("display_name", tdir.name),
                    "description": cfg.get("description", ""),
                })
    return templates


def init_project(template_name: str, output_dir: str, storage_backend: str = "git",
                 kb_backend: str = "local") -> list[str]:
    """
    Initialize a new project from a template.
    
    Args:
        template_name: Name of template (e.g. "football-prediction")
        output_dir: Where to create the project
        storage_backend: Storage type (git, local, s3, etc.)
        kb_backend: Knowledge base type (obsidian, local, notion, etc.)
    
    Returns:
        List of created files (relative to output_dir)
    """
    src = TEMPLATES_DIR / template_name
    if not src.exists():
        raise ValueError(f"Template '{template_name}' not found. "
                         f"Available: {[t['name'] for t in list_templates()]}")
    
    dst = Path(output_dir).expanduser().resolve()
    dst.mkdir(parents=True, exist_ok=True)
    
    created = []
    
    # Copy plugin config
    if (src / "plugin.yaml").exists():
        shutil.copy2(src / "plugin.yaml", dst / "plugin.yaml")
        created.append("plugin.yaml")
    
    # Create data directory
    plugin_name = template_name.split("-")[0]
    (dst / plugin_name).mkdir(parents=True, exist_ok=True)
    created.append(f"{plugin_name}/")
    
    # Create knowflow.toml config
    config = {
        "project": {"name": template_name, "version": "0.1.0"},
        "storage": {"backend": storage_backend, "path": str(dst)},
        "knowledge": {"backend": kb_backend, "path": str(dst / "output")},
        "pipeline": ["markdown_export", "profile_index"],
    }
    config_path = dst / "knowflow.toml"
    config_path.write_text(yaml.dump(config, default_flow_style=False), encoding="utf-8")
    created.append("knowflow.toml")
    
    # Create README
    readme = f"""# {template_name}

Generated from KnowFlow template: {template_name}

## Usage

```bash
# Add data
echo '{{"key": "value"}}' > {plugin_name}/data/my-data.json

# Run pipeline
knowflow run

# View output
ls {plugin_name}/output/
```
"""
    (dst / "README.md").write_text(readme, encoding="utf-8")
    created.append("README.md")
    
    return created
