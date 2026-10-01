"""Resolve only relative to this module; never HOME or the current directory."""
import json
from pathlib import Path

def resource_root():
    here = Path(__file__).resolve()
    bundled = here.parent.parent.parent / "references"
    if bundled.is_dir(): return bundled
    development = here.parents[2] / "source"
    if development.is_dir(): return development
    raise RuntimeError("Packaged resources missing")

def resource_json(relative):
    return json.loads((resource_root() / relative).read_text(encoding="utf-8"))

def registry():
    return resource_json("commands/registry.json")
