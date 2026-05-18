#!/usr/bin/env python3
"""
KnowFlow CLI — Agent Knowledge Pipeline

Usage:
    knowflow init <template> [--dir DIR] [--storage git|local] [--kb obsidian|local]
    knowflow run [--plugin NAME]
    knowflow status
    knowflow commit [MESSAGE]
    knowflow archive [--dry-run]
    knowflow list
    knowflow version
"""
import sys
import os
from pathlib import Path

def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return
    
    cmd = args[0]
    
    if cmd == "version":
        from knowflow import __version__
        print(f"KnowFlow v{__version__}")
    
    elif cmd == "list":
        from knowflow.cli.template_manager import list_templates
        templates = list_templates()
        print(f"\n📦 Available templates ({len(templates)}):\n")
        for t in templates:
            print(f"  {t['display']:25s}  {t['description']}")
        print()
    
    elif cmd == "init":
        _init(args[1:])
    
    elif cmd == "run":
        _run(args[1:])
    
    elif cmd == "status":
        _status()
    
    elif cmd == "commit":
        msg = " ".join(args[1:]) if len(args) > 1 else ""
        _commit(msg)
    
    elif cmd == "archive":
        dry_run = "--dry-run" in args
        _archive(dry_run)
    
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__.strip())


def _init(args):
    from knowflow.cli.template_manager import init_project, list_templates
    
    template = args[0] if args else None
    output_dir = "."
    storage = "git"
    kb = "local"
    
    for i, a in enumerate(args):
        if a == "--dir" and i + 1 < len(args): output_dir = args[i + 1]
        if a == "--storage" and i + 1 < len(args): storage = args[i + 1]
        if a == "--kb" and i + 1 < len(args): kb = args[i + 1]
    
    if not template:
        print("❌ Please specify a template. Available:")
        for t in list_templates():
            print(f"  {t['name']:25s}  {t['description']}")
        return
    
    try:
        files = init_project(template, output_dir, storage, kb)
        print(f"\n✅ Created project '{template}' in {output_dir}/")
        for f in files:
            print(f"   📄 {f}")
        print(f"\n   Next: cd {output_dir} && knowflow run")
    except ValueError as e:
        print(f"❌ {e}")


def _run(args):
    from knowflow.core.pipeline import PipelineRunner
    from knowflow.transforms import MarkdownExport, ProfileIndex
    from knowflow.adapters.storage import create_storage
    
    # Detect project root
    root = Path.cwd()
    config_path = root / "knowflow.toml"
    if not config_path.exists():
        print("❌ No knowflow.toml found. Run 'knowflow init' first.")
        return
    
    import yaml
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Parse args
    plugin_name = None
    dry_run = "--dry-run" in args
    verbose = "--verbose" in args
    for i, a in enumerate(args):
        if a == "--plugin" and i + 1 < len(args):
            plugin_name = args[i + 1]
    
    # Create storage
    storage_cfg = config.get("storage", {"backend": "git", "path": str(root)})
    store = create_storage(storage_cfg["backend"], config=storage_cfg)
    
    # Setup pipeline
    runner = PipelineRunner(config)
    runner.register(MarkdownExport())
    runner.register(ProfileIndex())
    
    data_dir = root / "data" if (root / "data").exists() else root
    output_dir = root / "output"
    output_dir.mkdir(exist_ok=True)
    
    if plugin_name:
        results = [runner.run_plugin(plugin_name, store, data_dir, output_dir, dry_run, verbose)]
    else:
        plugins = [p.stem for p in sorted(data_dir.iterdir()) if p.is_dir() and p.name not in ("output", ".git", ".github")]
        if not plugins:
            # Fall back to the data directory itself as a single plugin
            plugins = [root.name]
        results = runner.run_all(plugins, store, data_dir, output_dir, dry_run, verbose)
    
    for r in results:
        icon = "✅" if r["success"] else "❌"
        print(f"  {icon} {r['plugin']}")
        for sname, sres in r["stages"].items():
            status = sres.get("status", "?")
            if status == "ok":
                gen = sres.get("generated", 0)
                print(f"     ├─ {sname}: {gen} files generated" if gen else f"     ├─ {sname}: ✅")
            elif status == "skipped":
                print(f"     ├─ {sname}: ⏭️  {sres.get('reason', '')}")


def _status():
    from knowflow.adapters.storage import create_storage
    
    root = Path.cwd()
    config_path = root / "knowflow.toml"
    backend = "git"
    if config_path.exists():
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
            backend = cfg.get("storage", {}).get("backend", "git")
    
    try:
        store = create_storage(backend, config={"path": str(root)})
        items = store.walk() if hasattr(store, 'walk') else []
        commits = store.log(5) if hasattr(store, 'log') else []
        
        print(f"\n📊 KnowFlow Status")
        print(f"   Root: {root}")
        print(f"   Backend: {backend}")
        print(f"   Files: {len(items)}")
        if commits:
            print(f"   Last commits:")
            for c in commits:
                short = c['id'][:8]
                msg = c['message'][:50]
                print(f"     {short}  {msg}")
        else:
            print(f"   (no version history)")
        print()
    except Exception as e:
        print(f"❌ Status error: {e}")


def _commit(message: str = ""):
    from knowflow.adapters.storage import create_storage
    root = Path.cwd()
    store = create_storage("git", config={"path": str(root)})
    rev = store.commit(message)
    if rev:
        print(f"✅ Committed: {rev[:8]} — {message or 'auto'}")
    else:
        print("   (nothing to commit)")


def _archive(dry_run: bool = False):
    from knowflow.transforms.archive import ArchiveStage
    from knowflow.core.pipeline import PipelineContext
    
    root = Path.cwd()
    data_dir = root / "data"
    if not data_dir.exists():
        print("❌ No data/ directory found")
        return
    
    stage = ArchiveStage()
    for plugin_dir in sorted(data_dir.iterdir()):
        if plugin_dir.is_dir():
            ctx = PipelineContext(
                storage=None, plugin_name=plugin_dir.name,
                plugin_config={}, data_dir=plugin_dir,
                output_dir=root / "output" / plugin_dir.name,
                dry_run=dry_run,
            )
            result = stage.process(ctx)
            if dry_run:
                print(f"  {plugin_dir}: {result.get('candidates', 0)} files to archive")
            else:
                print(f"  {plugin_dir}: {result.get('archives', 0)} archives, {result.get('freed_kb', 0)}KB freed")


if __name__ == "__main__":
    main()
