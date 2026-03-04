from __future__ import annotations

import logging
from datetime import datetime

import polars as pl

from agent.state import AgentState
from models.cleaning_plan import CleaningAction, CleaningPlan
from core.df_serializer import dict_to_df, df_to_dict

logger = logging.getLogger(__name__)

def cleaning_node(state: AgentState) -> dict:
    """
    Exécute les actions approuvées par l'user.

    Vérifie d'abord que le plan est complètement validé.
    Puis exécute les actions dans l'ordre optimal.

    Args:
        state: Doit contenir raw_df et cleaning_plan validé

    Returns:
        Dict avec clean_df et cleaning_log mis à jour.
    """
    logger.info(">>> NODE 5 : Cleaning — démarrage")

    raw_df = dict_to_df(state.get("raw_df"))

    cleaning_plan: CleaningPlan = state.get("cleaning_plan")

    # ── Préconditions ─────────────────────────────────────────────────────────
    if raw_df is None:
        return {"status": "error", "errors": ["raw_df absent du state"]}

    if cleaning_plan is None:
        return {"status": "error", "errors": ["cleaning_plan absent du state"]}

    # Fail fast : le plan doit être entièrement validé
    if not cleaning_plan.is_fully_validated:
        return {
            "status": "waiting_validation",
            "errors": ["Plan pas encore entièrement validé par l'user"],
        }

    # ── Exécution ────────────────────────────────────────────────────────────
    df     = raw_df.clone()
    cleaning_log = list(state.get("cleaning_log", []))
    rows_before = df.height

    # Récupérer les actions approuvées dans l'ordre optimal
    approved_actions = _sort_actions_for_execution(
        cleaning_plan.approved_actions
    )

    logger.info(
        "%d actions approuvées sur %d proposées",
        len(approved_actions),
        len(cleaning_plan.actions),
    )

    # Exécuter chaque action approuvée
    for action in approved_actions:
        df, log_entry = _execute_action(df, action)
        cleaning_log.append(log_entry)

        logger.info(
            "  ✓ %s sur '%s' — %d lignes affectées",
            action.action.value,
            action.colonne,
            log_entry["rows_affected"],
        )

    rows_after = df.height

    # Log de synthèse
    cleaning_log.append({
        "timestamp":    datetime.now().isoformat(),
        "colonne":      "ALL",
        "operation":    "cleaning_completed",
        "rows_affected": rows_before - rows_after,
        "detail": (
            f"Cleaning terminé — {rows_before} lignes → "
            f"{rows_after} lignes | "
            f"{rows_before - rows_after} supprimées | "
            f"{len(approved_actions)} opérations"
        ),
    })

    logger.info(
        "NODE 5 terminé — %d → %d lignes (%d supprimées)",
        rows_before,
        rows_after,
        rows_before - rows_after,
    )

    return {
        "clean_df":    df_to_dict(df),
        "cleaning_log": cleaning_log,
    }

def _sort_actions_for_execution(
    actions: list,
) -> list:
    """
    Trie les actions dans l'ordre optimal d'exécution.

    RÈGLE DE SÉCURITÉ :
        Les suppressions de lignes (drop_*) passent toujours
        en premier. Si on impute d'abord puis on supprime,
        on a gaspillé du travail.

    Ordre :
        1. drop_null_identifier (lignes inutilisables)
        2. drop_duplicates      (doublons exacts)
        3. Tout le reste        (dans l'ordre original)

    Args:
        actions: Liste d'ActionItem approuvés

    Returns:
        Liste triée.
    """
    priority = {
        CleaningAction.DROP_NULL_IDENTIFIER: 0,
        CleaningAction.DROP_DUPLICATES:      1,
    }

    return sorted(
        actions,
        key=lambda a: priority.get(a.action, 99),
    )

def _execute_action(
    df: pl.DataFrame,
    action,
) -> tuple[pl.DataFrame, dict]:
    """
    Exécute une action de nettoyage sur le DataFrame.

    PATTERN :
        Chaque action retourne (df_modifié, log_entry).
        Le log_entry documente ce qui a été fait.

    Args:
        df:     DataFrame courant
        action: ActionItem à exécuter

    Returns:
        Tuple (DataFrame mis à jour, entrée de log).
    """
    rows_before = df.height
    col         = action.colonne

    try:
        if action.action == CleaningAction.DROP_NULL_IDENTIFIER:
            df = df.filter(pl.col(col).is_not_null())

        elif action.action == CleaningAction.DROP_DUPLICATES:
            df = df.unique()

        elif action.action == CleaningAction.IMPUTE_MEDIAN:
            # Calculer la médiane sur les valeurs non-nulles
            numeric = df[col].cast(pl.Float64, strict=False).drop_nulls()
            if not numeric.is_empty():
                median_val = float(numeric.median())
                df = df.with_columns(
                    pl.when(pl.col(col).is_null())
                    .then(pl.lit(str(median_val)))
                    .otherwise(pl.col(col))
                    .alias(col)
                )
                action.parametre["valeur_imputation"] = median_val

        elif action.action == CleaningAction.IMPUTE_MODE:
            # Valeur la plus fréquente
            mode_val = (
                df[col]
                .drop_nulls()
                .value_counts()
                .sort("count", descending=True)
                .head(1)[col]
                .to_list()
            )
            if mode_val:
                df = df.with_columns(
                    pl.when(pl.col(col).is_null())
                    .then(pl.lit(str(mode_val[0])))
                    .otherwise(pl.col(col))
                    .alias(col)
                )
                action.parametre["valeur_imputation"] = mode_val[0]

        elif action.action == CleaningAction.IMPUTE_CONSTANT:
            constant = action.parametre.get("valeur", "")
            df = df.with_columns(
                pl.when(pl.col(col).is_null())
                .then(pl.lit(str(constant)))
                .otherwise(pl.col(col))
                .alias(col)
            )

        elif action.action == CleaningAction.CAST_TO_FLOAT:
            df = df.with_columns(
                pl.col(col).cast(pl.Float64, strict=False).alias(col)
            )

        elif action.action == CleaningAction.CAST_TO_STRING:
            df = df.with_columns(
                pl.col(col).cast(pl.Utf8).alias(col)
            )

        elif action.action == CleaningAction.TRIM_WHITESPACE:
            df = df.with_columns(
                pl.col(col).str.strip_chars().alias(col)
            )

        elif action.action == CleaningAction.TO_UPPERCASE:
            df = df.with_columns(
                pl.col(col).str.to_uppercase().alias(col)
            )

        elif action.action == CleaningAction.TO_LOWERCASE:
            df = df.with_columns(
                pl.col(col).str.to_lowercase().alias(col)
            )

        elif action.action == CleaningAction.FIX_DATE_ORDER:
            # Inverser 2 colonnes de dates si la première > la seconde
            # Le nom des 2 colonnes est dans parametre
            col2 = action.parametre.get("colonne_2", "")
            # Correction ici : on vérifie que col2 est une chaîne non vide et présente dans les colonnes
            if isinstance(col2, str) and col2 and col2 in df.columns:
                df = df.with_columns([
                    pl.when(pl.col(col) > pl.col(col2))
                    .then(pl.col(col2))
                    .otherwise(pl.col(col))
                    .alias(col),

                    pl.when(pl.col(col) > pl.col(col2))
                    .then(pl.col(col))
                    .otherwise(pl.col(col2))
                    .alias(col2),
                ])

        elif action.action in (
            CleaningAction.FLAG_OUTLIER,
            CleaningAction.LOG_RANGE_VIOLATION,
        ):
            # Ces actions ne modifient pas le DataFrame
            # Elles sont juste loggées pour traçabilité
            pass

    except Exception as e:
        logger.warning(
            "Échec action %s sur '%s' : %s",
            action.action.value,
            col,
            str(e),
        )

    rows_after   = df.height
    rows_affected = rows_before - rows_after if rows_before != rows_after \
                    else _count_rows_touched(action)

    log_entry = {
        "timestamp":     datetime.now().isoformat(),
        "action_id":     action.action_id,
        "colonne":       col,
        "dimension":     action.dimension,
        "operation":     action.action.value,
        "rows_affected": rows_affected,
        "detail":        action.justification,
        "user_decision": action.user_decision.value
                         if action.user_decision else None,
    }

    return df, log_entry

def _count_rows_touched(action) -> int:
    """
    Pour les actions qui ne suppriment pas de lignes,
    retourne le nombre de lignes concernées depuis le plan.
    """
    return len(action.lignes_concernees)