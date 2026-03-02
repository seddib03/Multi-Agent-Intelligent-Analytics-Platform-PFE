from __future__ import annotations
from typing import Any, Optional
from typing_extensions import TypedDict

STATUS_RUNNING = "RUNNING"
STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED  = "FAILED"
STATUS_WARNING = "WARNING"

# ─── AgentState ──────────────────────────────────────────────────────────────

class AgentState(TypedDict):

    # ── Inputs ────────────────────────────────────────────────────────
    dataset_path:  str
    metadata_path: str

    # ── Résultats du parsing metadata ─────────────────────────────────
    metadata:     Optional[dict]
    action_plan:  Optional[dict]

    # ── DataFrames à chaque étape ─────────────────────────────────────
    raw_df:   Optional[Any]
    clean_df: Optional[Any]
    final_df: Optional[Any]

    # ── Profiling qualité AVANT et APRÈS cleaning ──────────────────────
    # Permettent la comparaison before/after
    profile_before: Optional[dict]  # ← snapshot qualité données brutes
    profile_after:  Optional[dict]  # ← snapshot qualité données nettoyées

    # ── Logs et rapports ──────────────────────────────────────────────
    cleaning_log:   list
    quality_report: Optional[dict]
    quality_score:  Optional[float]

    # ── Stockage ──────────────────────────────────────────────────────
    bronze_path: Optional[str]
    silver_path: Optional[str]

    # ── Suivi du pipeline ─────────────────────────────────────────────
    status:       str
    errors:       list
    started_at:   Optional[str]
    completed_at: Optional[str] 