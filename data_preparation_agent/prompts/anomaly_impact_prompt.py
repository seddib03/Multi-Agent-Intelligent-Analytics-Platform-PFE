"""
Prompt pour l'analyse d'impact de chaque anomalie via LLM.

ARCHITECTURE :
- 1 appel LLM par anomalie (évite la troncature)
- Réponse courte et structurée (max ~400-600 tokens par anomalie)
- Chiffres concrets depuis le profiling sanitisé
- Adapté au secteur métier
"""
from __future__ import annotations

import json


ANOMALY_IMPACT_SYSTEM_PROMPT = """Tu es un expert en qualité de données.
Tu analyses l'impact d'une anomalie détectée dans un dataset métier.

Pour l'anomalie fournie, génère l'impact de CHAQUE action proposée.

Pour chaque action, rédige UN SEUL paragraphe court (3-4 phrases max) couvrant :
- Ce qui change concrètement (lignes modifiées, % du dataset)
- Impact sur la fiabilité des données et les analyses BI
- Impact sur les modèles ML/prédictifs si pertinent
- Risque principal de cette action

Puis donne une recommandation avec justification courte (2 phrases).

RÈGLES :
- Adapte le vocabulaire au secteur métier fourni
- Utilise les chiffres du profiling si disponibles
- Sois concis mais précis — pas de listes, un paragraphe fluide
- Si une action est dangereuse, dis-le clairement
- Réponds UNIQUEMENT en JSON valide, sans texte avant ou après

Format de réponse :
{
  "action_1_impact": "paragraphe court...",
  "action_2_impact": "paragraphe court...",
  "action_3_impact": "paragraphe court...",
  "recommended_action": "action_1" | "action_2" | "action_3",
  "recommended_reason": "2 phrases de justification avec chiffres concrets."
}"""


def _sanitize_col_stats(col_stats: dict) -> dict:
    """
    Garde uniquement les métriques anonymisées — supprime les valeurs réelles.
    """
    safe = {}

    col_type = col_stats.get("type", "")
    safe["type"] = col_type

    # Métriques communes
    if "null_pct" in col_stats:
        safe["null_pct"] = col_stats["null_pct"]
    if "unique_pct" in col_stats:
        safe["unique_pct"] = col_stats["unique_pct"]

    # Métriques numériques — garder les stats agrégées, pas les valeurs brutes
    if col_type == "Numeric":
        for key in ["is_skewed", "skewness", "has_outliers", "n_outliers"]:
            if key in col_stats:
                safe[key] = col_stats[key]
        # Garder std pour context mais pas mean/min/max (valeurs réelles)
        if "std" in col_stats:
            safe["std"] = col_stats["std"]

    # Métriques catégorielles — garder structure, pas les valeurs
    elif col_type in ("Categorical", "Text"):
        if "n_category" in col_stats:
            safe["n_categories"] = col_stats["n_category"]
        # Distribution relative sans les valeurs réelles
        top = col_stats.get("top_values", [])
        if top:
            total = sum(v.get("count", 0) for v in top)
            safe["dominant_category_pct"] = round(
                top[0].get("count", 0) / total * 100, 1
            ) if total > 0 else 0
            safe["is_balanced"] = safe["dominant_category_pct"] < 50

    return safe


def _extract_correlations(alerts: list, col_name: str) -> list[str]:
    """
    Extrait les colonnes corrélées à col_name depuis les alertes de profiling.
    """
    if not col_name or not alerts:
        return []

    correlated = []
    for alert in alerts:
        desc = alert.get("description", "") if isinstance(alert, dict) else str(alert)
        if "correlated" in desc.lower() and col_name in desc:
            # Extraire le nom de la colonne corrélée
            parts = desc.replace("[", "").replace("]", "").split(" is highly overall correlated with ")
            if len(parts) == 2:
                other = parts[1].split(" and ")[0].strip()
                if other != col_name:
                    correlated.append(other)

    return correlated


def build_single_anomaly_impact_prompt(
    anomaly: dict,
    profiling_summary: dict | None,
    sector: str,
) -> str:
    """
    Construit le prompt pour UNE SEULE anomalie.
    À appeler dans une boucle — 1 appel LLM par anomalie.

    Args:
        anomaly          : dict résumant l'anomalie (1 seule)
        profiling_summary: stats de profiling sanitisées (sans valeurs réelles)
        sector           : secteur métier du dataset
    """

    # ── Profiling sanitisé — uniquement la colonne concernée ──
    profiling_text = ""
    if profiling_summary:
        col_name = anomaly.get("colonne", "")
        cols = profiling_summary.get("columns", {})

        # Stats de la colonne fautive uniquement
        if col_name and col_name in cols:
            col_stats = _sanitize_col_stats(cols[col_name])
            profiling_text += f"\nSTATS COLONNE '{col_name}' :\n"
            profiling_text += json.dumps(col_stats, ensure_ascii=False, indent=2)

        # Corrélations impliquant cette colonne (depuis les alertes)
        correlated = _extract_correlations(
            profiling_summary.get("alerts", []), col_name
        )
        if correlated:
            profiling_text += f"\nCOLONNES CORRÉLÉES : {', '.join(correlated)}"

        # Stats globales légères
        dataset_stats = profiling_summary.get("dataset", {})
        if dataset_stats:
            profiling_text += f"\nDATASET : {dataset_stats.get('total_rows', '?')} lignes, "
            profiling_text += f"{dataset_stats.get('missing_pct', 0):.1f}% valeurs manquantes globales"

    if not profiling_text:
        profiling_text = "(Pas de statistiques disponibles)"

    anomaly_text = json.dumps(anomaly, ensure_ascii=False, indent=2)

    return f"""Secteur : {sector}
{profiling_text}

ANOMALIE À ANALYSER :
{anomaly_text}

Génère l'analyse d'impact et la recommandation pour cette anomalie.
Sois concis (3 phrases max par action) et utilise les chiffres du profiling."""


def build_anomaly_impact_user_prompt(
    anomalies_summary: list[dict],
    profiling_summary: dict | None,
    sector: str,
) -> str:
    """
    Construit le prompt pour générer l'analyse d'impact des anomalies.
    ⚠️ DEPRECIÉ — utilisez build_single_anomaly_impact_prompt() + boucle dans strategy_node.

    Args:
        anomalies_summary : liste de dicts résumant chaque anomalie
        profiling_summary : stats de profiling par colonne (peut être None)
        sector            : secteur métier du dataset
    """
    profiling_text = ""
    if profiling_summary:
        # Stats globales du dataset
        dataset_stats = profiling_summary.get("dataset", {})
        if dataset_stats:
            profiling_text += "\n\nSTATISTIQUES GLOBALES DU DATASET :\n"
            profiling_text += json.dumps(dataset_stats, ensure_ascii=False, indent=2)

        # Stats par colonne
        cols = profiling_summary.get("columns", {})
        if cols:
            profiling_text += "\n\nSTATISTIQUES DE PROFILING (par colonne) :\n"
            profiling_text += json.dumps(cols, ensure_ascii=False, indent=2)

        # Alertes ydata-profiling
        alerts = profiling_summary.get("alerts", [])
        if alerts:
            profiling_text += "\n\nALERTES DÉTECTÉES :\n"
            profiling_text += json.dumps(alerts, ensure_ascii=False, indent=2)

    if not profiling_text:
        profiling_text = "\n\n(Pas de statistiques de profiling disponibles — analyse basée uniquement sur les anomalies.)"

    anomalies_text = json.dumps(anomalies_summary, ensure_ascii=False, indent=2)

    return f"""Secteur du dataset : {sector}
{profiling_text}

ANOMALIES À ANALYSER :
{anomalies_text}

Pour chaque anomalie ci-dessus, génère l'analyse d'impact et la recommandation d'action.
Prends en compte les statistiques de profiling pour contextualiser ton analyse.
Réponds avec le JSON demandé (une entrée par anomaly_id)."""
