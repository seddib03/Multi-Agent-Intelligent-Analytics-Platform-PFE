"""
tests/ml_layer/test_pipeline_builder.py — Dev 2

Lance depuis generic_predictive_agent/ :
    python -m pytest tests/ml_layer/test_pipeline_builder.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from sklearn.pipeline import Pipeline
from ml_layer.pipeline_builder import build_pipeline
from tests.ml_layer.fixtures.mock_loader import load_mock_task_config  # ✅ bon chemin


def test_classification_pipelines():
    cfg = load_mock_task_config("classification")
    pipelines = build_pipeline(cfg)
    assert len(pipelines) > 0
    for p in pipelines:
        assert "name" in p
        assert isinstance(p["pipeline"], Pipeline)
    print(f"\n  ✅ Classification — {[p['name'] for p in pipelines]}")


def test_regression_pipelines():
    cfg = load_mock_task_config("regression")
    pipelines = build_pipeline(cfg)
    assert len(pipelines) > 0
    print(f"\n  ✅ Regression — {[p['name'] for p in pipelines]}")


def test_clustering_pipelines():
    cfg = load_mock_task_config("clustering")
    pipelines = build_pipeline(cfg)
    assert len(pipelines) > 0
    print(f"\n  ✅ Clustering — {[p['name'] for p in pipelines]}")


def test_llm_strategy_filter():
    cfg = load_mock_task_config("classification")
    pipelines = build_pipeline(cfg)
    names = [p["name"] for p in pipelines]
    assert "XGBoost" in names
    assert "RandomForest" in names
    print(f"\n  ✅ LLM filter — {names}")


def test_invalid_task_type():
    cfg = load_mock_task_config("classification")
    cfg.task_type = "invalid_task"
    with pytest.raises(ValueError):
        build_pipeline(cfg)
    print("\n  ✅ Invalid task_type correctement rejeté")


if __name__ == "__main__":
    for task in ["classification", "regression", "clustering"]:
        cfg = load_mock_task_config(task)
        pipelines = build_pipeline(cfg)
        print(f"{task}: {[p['name'] for p in pipelines]}")