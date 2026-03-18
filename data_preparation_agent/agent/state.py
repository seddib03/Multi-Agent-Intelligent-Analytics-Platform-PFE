# AgentState : structure de données centrale pour stocker l'état du job à travers les différentes étapes du pipeline.
from __future__ import annotations

from typing import Any, Optional

from typing_extensions import TypedDict

from models.cleaning_plan import CleaningPlan
from models.profiling_report import ProfilingReport
from models.quality_dimensions import QualityDimensionsReport



class AgentState(TypedDict, total=False):
    """
    State complet qui voyage entre tous les nodes. 

    total=False → Aucun champ n'est obligatoire dans le dict.
    Les nodes retournent uniquement les champs qu'ils modifient,
    LangGraph merge automatiquement avec l'état existant.

    """

    # Inputs
    dataset_path:  str
    metadata_path: str
    job_id:        str
    sector:        str

    # NODE 1 : ingestion
    raw_df:        Optional[dict]   # DataFrame sérialisé
    metadata:      Optional[list]   # liste de ColumnMeta sérialisés
    business_rules: Optional[list]  # règles métier en langage naturel
    bronze_path:   Optional[str]    # chemin MinIO Bronze
    duckdb_path:   Optional[str]    # chemin base locale DuckDB du job

    # NODE 2 : profiling
    profiling_summary: Optional[dict]  # stats rapides par colonne
    profiling_html_path: Optional[str]    # chemin MinIO Gold du rapport HTML
    profiling_json_path: Optional[str]    # chemin MinIO Gold du rapport JSON complet

    # NODE 3 : quality_scoring
    quality_before: Optional[dict]
    business_rule_tests: Optional[list]  # BusinessRuleTest sérialisés — réutilisés par rescoring

    # NODE 4 : anomaly_detection
    cleaning_plan: Optional[CleaningPlan]

    # NODE 5 : strategy (LLM)
    llm_summary:        Optional[str]
    llm_reformulations: Optional[dict]

    # NODE 6 : cleaning
    clean_df:    Optional[dict]
    cleaning_log: list

    # NODE 7 : rescoring
    quality_after: Optional[dict]

    # NODE 8 : delivery
    silver_path: Optional[str]
    gold_path:   Optional[str]

    # Suivi
    status: str
    errors: list
    started_at:   Optional[str]
    completed_at: Optional[str]


def build_import_state(
    job_id: str,
    dataset_path: str,
    sector: str = "unknown",
) -> AgentState:
    """
    State initial pour POST /import — sans metadata.
    Seuls NODE 1 (ingestion) et NODE 2 (profiling) seront exécutés.
    """
    from datetime import datetime
    return AgentState(
        job_id=job_id,
        dataset_path=dataset_path,
        metadata_path="",
        sector=sector,
        raw_df=None, metadata=None, business_rules=None, bronze_path=None, duckdb_path=None,
        profiling_summary=None,
        profiling_html_path=None,
        profiling_json_path=None,
        quality_before=None,
        business_rule_tests=None,
        cleaning_plan=None,
        llm_summary=None, llm_reformulations=None,
        clean_df=None, cleaning_log=[],
        quality_after=None,
        silver_path=None, gold_path=None,
        status="imported", errors=[],
        started_at=datetime.now().isoformat(),
        completed_at=None,
    )


def build_initial_state(
    job_id: str,
    dataset_path: str,
    metadata_path: str,
) -> AgentState:
    from datetime import datetime
    return AgentState(
        job_id=job_id,
        dataset_path=dataset_path,
        metadata_path=metadata_path,
        sector="unknown",
        raw_df=None, metadata=None, business_rules=None, bronze_path=None, duckdb_path=None,
        profiling_summary=None,
        profiling_html_path=None,
        profiling_json_path=None,
        quality_before=None,
        business_rule_tests=None,
        cleaning_plan=None,
        llm_summary=None, llm_reformulations=None,
        clean_df=None, cleaning_log=[],
        quality_after=None,
        silver_path=None, gold_path=None,
        status="running", errors=[],
        started_at=datetime.now().isoformat(),
        completed_at=None,
    )
