"""
agent/nodes/cleaning_node.py
NODE 6 — Cleaning
─────────────────────────────
Exécute le plan de nettoyage validé par l'utilisateur.

Pour chaque anomalie approuvée :
    - Récupère l'action choisie par l'user (action_1, 2 ou 3)
    - Exécute la transformation Pandas correspondante
    - Log l'opération (rows_before / rows_after / action)

ORDRE D'EXÉCUTION :
    1. DROP_ROWS et DROP_DUPLICATES en premier
       (réduire le dataset avant les imputations)
    2. Imputations (IMPUTE_MEDIAN, IMPUTE_MODE)
    3. Transformations (CAST_TYPE, PARSE_DATE, CLIP_RANGE)
    4. FLAG_ONLY : log uniquement, aucune modification

Le résultat est sérialisé en dict pour le state LangGraph.
"""
from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from agent.state import AgentState
from models.anomaly_report import CleaningAction, UserDecision

logger = logging.getLogger(__name__)

# Ordre de priorité des actions (plus petit = exécuté en premier)
ACTION_PRIORITY = {
    CleaningAction.DROP_ROWS:       0,
    CleaningAction.DROP_DUPLICATES: 1,
    CleaningAction.IMPUTE_MEDIAN:   2,
    CleaningAction.IMPUTE_MODE:     2,
    CleaningAction.IMPUTE_CONSTANT: 2,
    CleaningAction.CAST_TYPE:       3,
    CleaningAction.PARSE_DATE:      3,
    CleaningAction.CLIP_RANGE:      3,
    CleaningAction.REPLACE_ENUM:    3,
    CleaningAction.FLAG_ONLY:       9,
}


def _load_df(df_dict: dict) -> pd.DataFrame:
    if df_dict is None:
        return pd.DataFrame()
    return pd.DataFrame(
        data=df_dict.get("data", []),
        columns=df_dict.get("columns", []),
    )


def cleaning_node(state: AgentState) -> dict:
    logger.info(">>> NODE 6 : Cleaning — démarrage")

    df            = _load_df(state["raw_df"])
    cleaning_plan = state["cleaning_plan"]
    cleaning_log  = list(state.get("cleaning_log", []))

    # Vérification : toutes les anomalies doivent avoir une décision
    if not cleaning_plan.is_fully_validated:
        logger.error("Plan non entièrement validé — certaines anomalies sans décision")
        return {"status": "waiting_validation", "errors": ["Plan non validé"]}

    # Trier les anomalies approuvées par priorité d'action
    approved = sorted(
        cleaning_plan.approved_anomalies,
        key=lambda a: ACTION_PRIORITY.get(
            a.chosen_action or a.action_1, 9
        ),
    )

    logger.info(
        "%d anomalie(s) approuvée(s) sur %d — début exécution",
        len(approved), len(cleaning_plan.anomalies),
    )

    for anomaly in approved:
        action      = anomaly.chosen_action or anomaly.action_1
        col         = anomaly.column_name
        rows        = anomaly.affected_rows
        rows_before = len(df)

        try:
            # ── Suppressions ─────────────────────────────────────────────
            if action == CleaningAction.DROP_ROWS:
                df = df.drop(index=rows, errors="ignore").reset_index(drop=True)

            elif action == CleaningAction.DROP_DUPLICATES:
                df = df.drop_duplicates(subset=[col], keep="first").reset_index(drop=True)

            # ── Imputations numériques ────────────────────────────────────
            elif action == CleaningAction.IMPUTE_MEDIAN:
                numeric = pd.to_numeric(df[col], errors="coerce")
                median  = numeric.median()
                df.loc[df[col].isna(), col] = str(median)

            elif action == CleaningAction.IMPUTE_MODE:
                mode_val = df[col].mode()
                if not mode_val.empty:
                    df[col] = df[col].fillna(mode_val[0])

            elif action == CleaningAction.IMPUTE_CONSTANT:
                constant = (anomaly.user_params or anomaly.params or {}).get("value", "")
                df[col]  = df[col].fillna(str(constant))

            # ── Transformations de type ───────────────────────────────────
            elif action == CleaningAction.CAST_TYPE:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            elif action == CleaningAction.PARSE_DATE:
                fmt = (anomaly.params or {}).get("expected_format")
                if fmt:
                    df[col] = pd.to_datetime(df[col], format=fmt, errors="coerce")
                else:
                    df[col] = pd.to_datetime(df[col], infer_datetime_format=True, errors="coerce")

            # ── Clipping range ────────────────────────────────────────────
            elif action == CleaningAction.CLIP_RANGE:
                params  = anomaly.user_params or anomaly.params or {}
                numeric = pd.to_numeric(df[col], errors="coerce")
                clipped = numeric.clip(
                    lower=params.get("min"),
                    upper=params.get("max"),
                )
                # Remettre en string (comme le reste du DataFrame)
                df[col] = clipped.astype(str).where(~numeric.isna(), df[col])

            # ── Flag only : aucune modification ───────────────────────────
            elif action == CleaningAction.FLAG_ONLY:
                pass  # Log uniquement

            # ── Log de l'opération ────────────────────────────────────────
            rows_after   = len(df)
            rows_changed = rows_before - rows_after if action in (
                CleaningAction.DROP_ROWS, CleaningAction.DROP_DUPLICATES
            ) else len(rows)

            cleaning_log.append({
                "timestamp":    datetime.now().isoformat(),
                "anomaly_id":   anomaly.anomaly_id,
                "column":       col,
                "dimension":    anomaly.dimension,
                "action":       action.value,
                "rows_before":  rows_before,
                "rows_after":   rows_after,
                "rows_affected": rows_changed,
            })
            logger.info(
                "  ✓ %s sur '%s' — %d ligne(s) affectée(s)",
                action.value, col, rows_changed,
            )

        except Exception as e:
            logger.warning(
                "  ✗ Échec %s sur '%s' : %s",
                action.value, col, e,
            )

    logger.info(
        "NODE 6 terminé — %d lignes restantes (était %d)",
        len(df), len(_load_df(state["raw_df"])),
    )
    return {
        "clean_df": {
            "columns": df.columns.tolist(),
            "data":    df.values.tolist(),
        },
        "cleaning_log": cleaning_log,
    }