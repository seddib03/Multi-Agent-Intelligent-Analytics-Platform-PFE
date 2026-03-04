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

    ORDRE DE REMPLISSAGE :
        ingestion_node   → raw_df, raw_metadata, bronze_path
        profiling_node   → profiling_report, profile_before
        dimension_node   → dimension_mapping, dimension_rules
        measurement_node → dimensions_before, dbt_results
        strategy_node    → cleaning_plan, llm_analysis
        [human loop]     → cleaning_plan (avec user_decisions)
        cleaning_node    → clean_df, cleaning_log, profile_after
        evaluation_node  → dimensions_after, llm_evaluation
        delivery_node    → final_df, silver_path, status
    """

    # ── Inputs (remplis par main.py avant de lancer le graph) ────────────────
    dataset_path:  str   # chemin vers le fichier uploadé
    metadata_path: str   # chemin vers le fichier metadata

    # ── NODE 1 : ingestion_node ───────────────────────────────────────────────
    # DataFrame Polars chargé tel quel, aucune modification
    raw_df: Optional[dict]

    # Metadata tel que fourni par l'user — aucune validation rigide
    # On accepte n'importe quelle structure JSON
    raw_metadata: Optional[dict]

    # Informations sur le fichier chargé
    ingestion_info: Optional[dict]  # format, encoding, nb_rows, nb_cols

    # Chemin du fichier original sauvegardé en Bronze (immuable)
    bronze_path: Optional[str]

    # ── NODE 2 : profiling_node ───────────────────────────────────────────────
    # Rapport complet de profiling (stats + anomalies ligne par ligne)
    profiling_report: Optional[ProfilingReport]

    # Snapshot qualité AVANT cleaning (pour comparaison finale)
    profile_before: Optional[dict]

    # ── NODE 3 : dimension_node (LLM) ────────────────────────────────────────
    # Secteur détecté / confirmé par le LLM depuis le metadata
    sector: Optional[str]

    # Mapping colonnes → dimensions de qualité
    # Ex: {"contrat_id": ["completeness", "uniqueness"],
    #      "prime_annuelle": ["completeness", "validity", "accuracy"]}
    dimension_mapping: Optional[dict]

    # Règles de qualité extraites du metadata par le LLM
    # Ex: {"prime_annuelle": {"range": [100, 50000], "nullable": False}}
    dimension_rules: Optional[dict]

    # ── NODE 4 : measurement_node ────────────────────────────────────────────
    # Scores des 5 dimensions AVANT cleaning
    dimensions_before: Optional[QualityDimensionsReport]

    # Résultats bruts des tests dbt (liste de dicts)
    dbt_results: Optional[list]

    # ── NODE 5 : strategy_node (LLM) ────────────────────────────────────────
    # Plan de nettoyage proposé par le LLM
    # Status initial : "proposed"
    cleaning_plan: Optional[CleaningPlan]

    # Analyse textuelle complète du LLM sur le dataset
    llm_analysis: Optional[str]

    # ── HUMAN IN THE LOOP ────────────────────────────────────────────────────
    # Le graph s'interrompt ici et attend que l'user
    # remplisse cleaning_plan.actions[*].user_decision
    # Géré par LangGraph checkpointer + interrupt_before

    # ── NODE 6 : cleaning_node ───────────────────────────────────────────────
    # DataFrame nettoyé selon le plan validé par l'user
    clean_df: Optional[Any]

    # Log détaillé de chaque opération effectuée
    # Chaque entrée : {action_id, colonne, operation, rows_affected, detail}
    cleaning_log: list

    # Snapshot qualité APRÈS cleaning (pour comparaison finale)
    profile_after: Optional[dict]

    # ── NODE 7 : evaluation_node (LLM) ───────────────────────────────────────
    # Scores des 5 dimensions APRÈS cleaning
    dimensions_after: Optional[QualityDimensionsReport]

    # Analyse LLM des résultats : pourquoi les scores ont changé,
    # recommandations, dimensions encore insuffisantes
    llm_evaluation: Optional[str]

    # ── NODE 8 : delivery_node ───────────────────────────────────────────────
    # Dataset final avec colonnes tracking ajoutées
    final_df: Optional[Any]

    # Chemin du Parquet nettoyé dans Silver
    silver_path: Optional[str]

    # ── Suivi du pipeline ────────────────────────────────────────────────────
    # Statuts possibles :
    # "running"             → pipeline en cours
    # "waiting_validation"  → attend décision user
    # "success"             → pipeline terminé avec succès
    # "failed"              → qualité insuffisante
    # "error"               → erreur technique
    status: str

    # Identifiant unique du job (UUID)
    job_id: str

    # Erreurs techniques rencontrées (pas les anomalies de données)
    errors: list

    # Horodatages
    started_at:   Optional[str]
    completed_at: Optional[str]


def build_initial_state(
    job_id: str,
    dataset_path: str,
    metadata_path: str,
) -> AgentState:
    """
    Construit l'état initial avant de lancer le graph.

    POURQUOI CETTE FONCTION :
        Sans elle, main.py devrait se souvenir de tous
        les champs à initialiser à None.
        Un champ oublié = KeyError dans un node.
        Cette fonction garantit un state toujours complet.

    Args:
        job_id:        UUID unique du job
        dataset_path:  Chemin vers le fichier dataset uploadé
        metadata_path: Chemin vers le fichier metadata uploadé

    Returns:
        AgentState complet avec tous les champs initialisés.
    """
    from datetime import datetime

    return AgentState(
        # Inputs
        dataset_path=dataset_path,
        metadata_path=metadata_path,

        # Tous les autres champs à None / valeur vide
        raw_df=None,
        raw_metadata=None,
        ingestion_info=None,
        bronze_path=None,

        profiling_report=None,
        profile_before=None,

        sector=None,
        dimension_mapping=None,
        dimension_rules=None,

        dimensions_before=None,
        dbt_results=None,

        cleaning_plan=None,
        llm_analysis=None,

        clean_df=None,
        cleaning_log=[],
        profile_after=None,

        dimensions_after=None,
        llm_evaluation=None,

        final_df=None,
        silver_path=None,

        # Suivi
        status="running",
        job_id=job_id,
        errors=[],
        started_at=datetime.now().isoformat(),
        completed_at=None,
    )