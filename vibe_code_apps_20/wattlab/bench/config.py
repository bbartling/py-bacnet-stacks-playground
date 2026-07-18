from __future__ import annotations
from pathlib import Path
import tomllib
import yaml
from .models import ProjectConfig

def load_config(path: str | Path) -> ProjectConfig:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    elif suffix == ".toml":
        data = tomllib.loads(text)
    else:
        raise ValueError(f"Unsupported config format: {suffix}")
    return ProjectConfig.model_validate(data)
