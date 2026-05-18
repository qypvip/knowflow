"""
knowflow/core/pipeline.py — Data Pipeline Framework
====================================================
Transforms raw data (JSON) → formatted output (MD/docs).
Each transform is a pluggable stage.

Built-in stages:
  - markdown_export:  JSON → Markdown
  - profile_index:    Auto-generate PROFILE.md
  - archive:          Hot → Warm → Cold lifecycle
  - token_compress:   TokenJuice-style compression
  - validate_schema:  Validate against plugin schema
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
import importlib
import inspect
import yaml


@dataclass
class PipelineContext:
    """Context passed through each pipeline stage"""
    storage: object           # StorageAdapter instance
    plugin_name: str          # e.g. "football"
    plugin_config: dict       # Parsed plugin.yaml
    data_dir: Path            # Where data files live
    output_dir: Path          # Where output goes (obsidian/)
    dry_run: bool = False
    verbose: bool = False


class PipelineError(Exception): pass


class TransformStage(ABC):
    """
    A single stage in the data pipeline.
    
    Stages are loaded from knowflow.toml [pipeline] config.
    To add a custom stage: subclass TransformStage and register.
    """
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def process(self, ctx: PipelineContext) -> dict:
        """
        Execute this stage.
        Returns: {"status": "ok"|"skipped"|"error", "detail": "..."}
        """
        ...
    
    def should_run(self, ctx: PipelineContext) -> bool:
        """Override to add conditional execution."""
        return True


class PipelineRunner:
    """Orchestrates pipeline execution"""
    
    def __init__(self, config: dict):
        self.config = config
        self.stages: dict[str, TransformStage] = {}
    
    def register(self, stage: TransformStage):
        """Register a pipeline stage"""
        self.stages[stage.name] = stage
    
    def load_plugin_config(self, plugin_dir: Path) -> dict:
        """Load plugin.yaml from a plugin directory"""
        path = plugin_dir / "plugin.yaml"
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f) or {}
        return {}
    
    def run_plugin(self, plugin_name: str, storage, data_dir: Path, output_dir: Path,
                   dry_run: bool = False, verbose: bool = False) -> dict:
        """Run pipeline for one plugin"""
        result = {"plugin": plugin_name, "stages": {}, "success": True}
        
        ctx = PipelineContext(
            storage=storage,
            plugin_name=plugin_name,
            plugin_config={},
            data_dir=data_dir / plugin_name,
            output_dir=output_dir / plugin_name,
            dry_run=dry_run,
            verbose=verbose,
        )
        
        for stage_name, stage in self.stages.items():
            if not stage.should_run(ctx):
                result["stages"][stage_name] = {"status": "skipped"}
                continue
            
            try:
                stage_result = stage.process(ctx)
                result["stages"][stage_name] = stage_result
                if stage_result.get("status") == "error":
                    result["success"] = False
            except Exception as e:
                result["stages"][stage_name] = {"status": "error", "detail": str(e)}
                result["success"] = False
        
        return result
    
    def run_all(self, plugins: list, storage, data_dir: Path, output_dir: Path,
                dry_run: bool = False, verbose: bool = False) -> list[dict]:
        """Run pipeline for all plugins"""
        results = []
        for plugin in plugins:
            result = self.run_plugin(plugin, storage, data_dir, output_dir, dry_run, verbose)
            results.append(result)
        return results
