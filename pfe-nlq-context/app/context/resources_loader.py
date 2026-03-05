import yaml
from pathlib import Path
from typing import Dict, Any

RESOURCES_DIR = Path(__file__).resolve().parents[1] / "resources"

def load_yaml(filename: str) -> Dict[str, Any]:
    path = RESOURCES_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)