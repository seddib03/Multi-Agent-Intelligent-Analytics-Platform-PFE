"""
Prompt pour l'analyse d'impact de chaque anomalie via LLM.

ARCHITECTURE :
- 1 appel LLM par anomalie (évite la troncature JSON)
- Réponse courte et structurée (~400-600 tokens par anomalie)
- Chiffres concrets depuis le profiling sanitisé
- Metadata de la colonne transmise pour contextualiser
- Recommandation basée sur des critères objectifs et prioritaires
"""
from __future__ import annotations

import json


ANOMALY_IMPACT_SYSTEM_PROMPT = """Tu es un expert senior en qualité de données avec 15 ans d'expérience dans des projets Data, BI et Machine Learning.
Tu analyses l'impact métier d'une anomalie détectée dans un dataset.

CONTEXTE DES 3 NIVEAUX D'ACTION :
- action_1 = Conservative  : intervention minimale, préserve les données (flag, imputation douce)
- action_2 = Modérée       : transformation active, corrige sans supprimer (cast, clip, replace, parse)
- action_3 = Agressive     : suppression de lignes — perte irréversible de données

ANALYSE DE CHAQUE ACTION :
Pour chaque action, rédige un paragraphe fluide de 2-3 phrases couvrant dans cet ordre :
1. VOLUME     : combien de lignes sont modifiées/supprimées, quel % exact du dataset
2. FIABILITÉ  : est-ce que cette action améliore ou dégrade la confiance dans les données
3. IMPACT BI/ML : quelles analyses, métriques ou KPIs sont affectés — quels modèles ML sont impactés
4. RISQUE     : l'effet secondaire le plus important à anticiper pour cette action précise

UTILISATION DE LA METADATA :
- Si identifier=true    → NE JAMAIS recommander d'imputation — un ID imputé crée un faux doublon
- Si nullable=false     → la valeur manquante est CRITIQUE — le signaler explicitement dans l'impact
- Si min/max définis    → citer les bornes exactes dans l'analyse ("viole la borne min=100")
- Si enum défini        → citer les valeurs autorisées ("valeur X absente de la liste [A, B, C]")
- Si pattern défini     → mentionner le format attendu dans l'analyse
- Si description fournie → utiliser le contexte métier pour adapter le vocabulaire

CRITÈRES DE RECOMMANDATION (appliquer dans cet ordre de priorité) :
1. Si % lignes affectées > 10% → action_3 (suppression) déconseillée sauf si valeur totalement irrécupérable
2. Si identifier=true          → toute imputation interdite — FLAG_ONLY ou DROP_ROWS uniquement
3. Si valeur potentiellement récupérable (ex: mauvais format date, typo) → préférer action_1 ou action_2
4. Si valeur clairement irrécupérable (ex: "test" dans un champ numérique) → action_3 acceptable
5. En cas d'égalité → privilégier l'action qui préserve le plus de données

RÈGLES DE RÉDACTION :
- Vocabulaire adapté au secteur (assurance=prime/contrat/sinistre, retail=commande/client/panier, flights=vol/retard/embarquement, banque=transaction/compte/virement)
- Chiffres concrets OBLIGATOIRES : jamais "beaucoup" ou "peu" — toujours "X lignes (Y% du dataset)"
- Ton professionnel accessible à un décideur non-technique
- Paragraphes fluides — pas de listes ni de tirets dans les impacts
- Si une action est clairement dangereuse pour ce cas précis, le dire explicitement
- La recommended_reason doit citer le % exact ET expliquer pourquoi les autres actions sont moins adaptées

Réponds UNIQUEMENT en JSON valide, sans texte avant ou après, sans backticks :
{
  "action_1_impact": "paragraphe 2-3 phrases...",
  "action_2_impact": "paragraphe 2-3 phrases...",
  "action_3_impact": "paragraphe 2-3 phrases...",
  "recommended_action": "action_1",
  "recommended_reason": "2 phrases citant le % exact et expliquant pourquoi les autres actions sont moins adaptées."
}"""


def _sanitize_col_stats(col_stats: dict) -> dict:
    """
    Garde uniquement les métriques anonymisées — supprime les valeurs réelles.
    Objectif : donner au LLM le contexte statistique sans exposer les données brutes.
    """
    safe = {}

    col_type = col_stats.get("type", "")
    safe["type"] = col_type

    # Métriques communes
    for key in ("null_pct", "unique_pct", "unique_count", "null_count"):
        if key in col_stats:
            safe[key] = col_stats[key]

    # Métriques numériques — stats agrégées uniquement (pas min/max/mean = valeurs réelles)
    if col_type in ("Numeric", "Real", "Integer"):
        for key in ("is_skewed", "skewness", "has_outliers", "n_outliers", "std"):
            if key in col_stats:
                safe[key] = col_stats[key]

    # Métriques catégorielles — structure de distribution sans les valeurs
    elif col_type in ("Categorical", "Text", "Boolean"):
        if "n_category" in col_stats:
            safe["n_categories"] = col_stats["n_category"]
        top = col_stats.get("top_values", [])
        if top:
            total = sum(v.get("count", 0) for v in top)
            if total > 0:
                safe["dominant_category_pct"] = round(
                    top[0].get("count", 0) / total * 100, 1
                )
                safe["is_balanced"] = safe["dominant_category_pct"] < 50

    # Métriques date — pas de min_date/max_date (valeurs réelles)
    elif col_type == "DateTime":
        pass  # Pas de stats utiles sans exposer les valeurs

    return safe


def _extract_correlations(alerts: list, col_name: str) -> list[str]:
    """
    Extrait les colonnes corrélées à col_name depuis les alertes ydata-profiling.
    Utile pour signaler l'impact en cascade sur les colonnes liées.
    """
    if not col_name or not alerts:
        return []

    correlated = []
    for alert in alerts:
        desc = (
            alert.get("description", "")
            if isinstance(alert, dict)
            else str(alert)
        )
        if "correlated" in desc.lower() and col_name in desc:
            parts = (
                desc.replace("[", "")
                .replace("]", "")
                .split(" is highly overall correlated with ")
            )
            if len(parts) == 2:
                other = parts[1].split(" and ")[0].strip()
                if other and other != col_name:
                    correlated.append(other)

    return correlated


def _build_metadata_context(col_meta: dict) -> str:
    """
    Construit le bloc metadata sanitisé à injecter dans le prompt.
    Filtre les champs None pour ne pas polluer le contexte LLM.
    """
    if not col_meta:
        return ""

    # Champs pertinents pour l'analyse d'impact
    meta_safe = {
        "column_name":   col_meta.get("column_name"),
        "business_name": col_meta.get("business_name"),
        "type":          col_meta.get("type"),
        "nullable":      col_meta.get("nullable"),
        "identifier":    col_meta.get("identifier", False),
        "min":           col_meta.get("min"),
        "max":           col_meta.get("max"),
        "enum":          col_meta.get("enum"),
        "pattern":       col_meta.get("pattern"),
        "format":        col_meta.get("format"),
        "description":   col_meta.get("description"),
    }

    # Supprimer les champs None et False non pertinents
    meta_safe = {
        k: v for k, v in meta_safe.items()
        if v is not None and v != "" and v is not False
    }

    if not meta_safe:
        return ""

    return (
        "\nMETADATA DE LA COLONNE :\n"
        + json.dumps(meta_safe, ensure_ascii=False, indent=2)
    )


def build_single_anomaly_impact_prompt(
    anomaly: dict,
    profiling_summary: dict | None,
    sector: str,
    col_meta: dict | None = None,
) -> str:
    """
    Construit le prompt pour UNE SEULE anomalie.
    À appeler dans une boucle — 1 appel LLM par anomalie.

    Args:
        anomaly          : dict résumant l'anomalie (1 seule)
        profiling_summary: stats de profiling (depuis profiling_node)
        sector           : secteur métier du dataset
        col_meta         : metadata de la colonne concernée (ColumnMeta sérialisé en dict)
    """

    # ── 1. Metadata de la colonne ──────────────────────────────────────────
    metadata_text = _build_metadata_context(col_meta) if col_meta else ""

    # ── 2. Profiling sanitisé — colonne concernée uniquement ───────────────
    profiling_text = ""
    if profiling_summary:
        col_name = anomaly.get("colonne", "")
        cols = profiling_summary.get("columns", {})

        # Stats de la colonne fautive uniquement (pas tout le profiling)
        if col_name and col_name in cols:
            col_stats = _sanitize_col_stats(cols[col_name])
            if col_stats:
                profiling_text += f"\nSTATS PROFILING COLONNE '{col_name}' :\n"
                profiling_text += json.dumps(col_stats, ensure_ascii=False, indent=2)

        # Corrélations — impact en cascade
        correlated = _extract_correlations(
            profiling_summary.get("alerts", []), col_name
        )
        if correlated:
            profiling_text += (
                f"\nCOLONNES CORRÉLÉES (impact en cascade possible) : "
                f"{', '.join(correlated)}"
            )

        # Stats globales légères
        dataset_stats = profiling_summary.get("dataset", {})
        if dataset_stats:
            profiling_text += (
                f"\nDATASET GLOBAL : {dataset_stats.get('total_rows', '?')} lignes | "
                f"{dataset_stats.get('total_columns', '?')} colonnes | "
                f"{dataset_stats.get('missing_pct', 0):.1f}% valeurs manquantes globales | "
                f"{dataset_stats.get('duplicate_pct', 0):.1f}% doublons"
            )

    if not profiling_text:
        profiling_text = (
            "\n(Pas de statistiques de profiling disponibles — "
            "base ton analyse sur les chiffres de l'anomalie et la metadata)"
        )

    # ── 3. Contexte des actions pour cette anomalie ────────────────────────
    actions = anomaly.get("actions", {})
    action_labels = {
        "action_1": "Conservative — intervention minimale",
        "action_2": "Modérée — transformation active",
        "action_3": "Agressive — suppression irréversible",
    }
    actions_context = "\n".join([
        f"  {k} = {v} ({action_labels.get(k, '')})"
        for k, v in actions.items()
    ])

    # ── 4. Critères de recommandation pré-calculés ─────────────────────────
    pct = anomaly.get("pct", 0)
    is_identifier = (col_meta or {}).get("identifier", False)

    criteria_lines = []
    if pct > 10:
        criteria_lines.append(
            f"⚠ {pct}% de lignes affectées → action_3 (suppression) déconseillée "
            f"sauf si valeur totalement irrécupérable"
        )
    if is_identifier:
        criteria_lines.append(
            "⚠ Colonne identifiant → imputation INTERDITE (IMPUTE_MEDIAN, IMPUTE_MODE) — "
            "un ID imputé crée un faux doublon"
        )
    if not criteria_lines:
        criteria_lines.append(
            f"{pct}% de lignes affectées — évaluer le ratio bénéfice/risque de chaque action"
        )

    criteria_text = "\n".join(criteria_lines)

    # ── 5. Prompt final ────────────────────────────────────────────────────
    anomaly_text = json.dumps(anomaly, ensure_ascii=False, indent=2)

    return f"""Secteur métier : {sector}
{metadata_text}
{profiling_text}

ANOMALIE À ANALYSER :
{anomaly_text}

ACTIONS PROPOSÉES :
{actions_context}

CRITÈRES DE RECOMMANDATION À APPLIQUER :
{criteria_text}

Génère l'analyse d'impact détaillée pour chaque action et ta recommandation motivée.
Utilise les chiffres exacts de la metadata et du profiling dans chaque paragraphe."""