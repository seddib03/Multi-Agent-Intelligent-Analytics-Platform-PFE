"""
tests/ml_layer/fixtures/mock_loader.py — Dev 2

Charge un TaskConfig mocké avec de vraies données numpy
pour tester ml_layer sans attendre Dev 1.
"""

import json
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from schemas.task_config import TaskConfig

# ✅ Chemin absolu — fonctionne peu importe d'où on lance
FIXTURE_PATH = Path(__file__).resolve().parent / "mock_task_config.json"


def load_mock_task_config(task_type: str = "classification") -> TaskConfig:
    """
    Retourne un TaskConfig mocké avec de vraies données
    prêtes pour l'entraînement.

    Args:
        task_type: "classification" | "regression" | "clustering"
    """
    with open(FIXTURE_PATH) as f:
        fixtures = json.load(f)

    cfg_data = fixtures[task_type]

    np.random.seed(42)

    if task_type == "classification":
        n = 500
        X = pd.DataFrame({
            "age":            np.random.randint(18, 80, n),
            "premium":        np.random.uniform(500, 3000, n),
            "risk_score":     np.random.uniform(0, 1, n),
            "region_encoded": np.random.randint(0, 4, n),
        })
        y = pd.Series((X["risk_score"] > 0.6).astype(int), name="claim")

    elif task_type == "regression":
        n = 300
        X = pd.DataFrame({
            "passenger_count": np.random.randint(50, 300, n),
            "route_encoded":   np.random.randint(0, 10, n),
            "gate_encoded":    np.random.randint(0, 5, n),
            "hour":            np.random.randint(0, 24, n),
        })
        y = pd.Series(np.maximum(0, np.random.normal(45, 38, n)), name="delay_minutes")

    elif task_type == "clustering":
        n = 200
        X = pd.DataFrame({
            "quantity":         np.random.randint(1, 50, n),
            "unit_price":       np.random.uniform(5, 500, n),
            "total_amount":     np.random.uniform(10, 5000, n),
            "category_encoded": np.random.randint(0, 5, n),
        })
        y = None

    else:
        raise ValueError(f"task_type inconnu : {task_type}")

    if y is not None:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
    else:
        split = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split], X.iloc[split:]
        y_train, y_test = None, None

    return TaskConfig(
        job_id=cfg_data["job_id"],
        task_type=cfg_data["task_type"],
        target_column=cfg_data["target_column"],
        feature_names=cfg_data["feature_names"],
        user_query=cfg_data["user_query"],
        sector=cfg_data["sector"],
        dataset_summary=cfg_data["dataset_summary"],
        llm_strategy=cfg_data["llm_strategy"],
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
    )


if __name__ == "__main__":
    for task in ["classification", "regression", "clustering"]:
        cfg = load_mock_task_config(task)
        print(f"\n{task.upper()}")
        print(f"  job_id    : {cfg.job_id}")
        print(f"  X_train   : {cfg.X_train.shape}")
        print(f"  features  : {cfg.feature_names}")