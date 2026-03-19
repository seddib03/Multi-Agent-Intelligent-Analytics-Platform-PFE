"""
ml_layer/pipeline_builder.py — Dev 2

Rôle : construire les pipelines sklearn adaptés à chaque task_type.
Consomme : TaskConfig produit par Dev 1.
Produit  : liste de pipelines prêts pour parallel_trainer.py.

Un pipeline sklearn = preprocessing + modèle en une seule chaîne.
Avantage : pas de fuite de données (preprocessing fit sur train only).
"""

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.cluster import KMeans
from xgboost import XGBClassifier, XGBRegressor

from schemas.task_config import TaskConfig


# ── Définition des modèles par tâche ──────────────────────────────

CLASSIFICATION_MODELS = [
    {
        "name": "RandomForest",
        "model": RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            n_jobs=-1
        )
    },
    {
        "name": "XGBoost",
        "model": XGBClassifier(
            n_estimators=100,
            random_state=42,
            eval_metric="logloss",
            verbosity=0
        )
    },
    {
        "name": "LogisticRegression",
        "model": LogisticRegression(
            max_iter=1000,
            random_state=42
        )
    },
]

REGRESSION_MODELS = [
    {
        "name": "RandomForest",
        "model": RandomForestRegressor(
            n_estimators=100,
            random_state=42,
            n_jobs=-1
        )
    },
    {
        "name": "XGBoost",
        "model": XGBRegressor(
            n_estimators=100,
            random_state=42,
            verbosity=0
        )
    },
    {
        "name": "LinearRegression",
        "model": LinearRegression()
    },
]

CLUSTERING_MODELS = [
    {
        "name": "KMeans_3",
        "model": KMeans(n_clusters=3, random_state=42, n_init=10)
    },
    {
        "name": "KMeans_4",
        "model": KMeans(n_clusters=4, random_state=42, n_init=10)
    },
    {
        "name": "KMeans_5",
        "model": KMeans(n_clusters=5, random_state=42, n_init=10)
    },
]

MODELS_BY_TASK = {
    "classification": CLASSIFICATION_MODELS,
    "regression":     REGRESSION_MODELS,
    "clustering":     CLUSTERING_MODELS,
}


def build_pipeline(task_config: TaskConfig) -> list[dict]:
    """
    Construit les pipelines sklearn selon le task_type.

    Si Dev 1 a fourni des modèles recommandés via llm_strategy,
    on filtre pour garder uniquement ceux recommandés.

    Args:
        task_config: TaskConfig produit par Dev 1

    Returns:
        Liste de dicts {"name": str, "pipeline": Pipeline}
    """
    task_type = task_config.task_type

    if task_type not in MODELS_BY_TASK:
        raise ValueError(
            f"task_type '{task_type}' inconnu. "
            f"Valeurs acceptées : {list(MODELS_BY_TASK.keys())}"
        )

    models = MODELS_BY_TASK[task_type]

    # ── Filtre selon recommandations LLM de Dev 1 ─────────────────
    recommended = task_config.llm_strategy.get("recommended_models", [])
    if recommended:
        models = [m for m in models if m["name"] in recommended]
        # Si le filtre vide la liste → on garde tous les modèles
        if not models:
            print(f"[WARN] Aucun modèle correspondant aux recommandations LLM "
                  f"{recommended} — utilisation de tous les modèles.")
            models = MODELS_BY_TASK[task_type]

    # ── Construit un Pipeline sklearn pour chaque modèle ──────────
    pipelines = []
    for m in models:
        pipeline = Pipeline([
            ("scaler", StandardScaler()),   # normalise les features
            ("model",  m["model"])          # modèle ML
        ])
        pipelines.append({
            "name":     m["name"],
            "pipeline": pipeline,
        })

    print(f"[pipeline_builder] task={task_type} | "
          f"pipelines construits : {[p['name'] for p in pipelines]}")

    return pipelines