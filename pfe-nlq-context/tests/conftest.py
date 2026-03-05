import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import pytest
from app.context.resources_loader import load_yaml


@pytest.fixture(scope="session")
def kpi_catalog():
    return load_yaml("sector_kpi_map.yaml")


@pytest.fixture(scope="session")
def schema_registry():
    return load_yaml("sector_schema_registry.yaml")