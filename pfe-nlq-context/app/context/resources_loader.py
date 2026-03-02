import yaml
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "resources"

def load_yaml(name: str) -> dict:
    with open(BASE / name, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)