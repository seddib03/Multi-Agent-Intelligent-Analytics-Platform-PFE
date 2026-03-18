from __future__ import annotations


# ── PROMPT 1 — dimension_node ─────────────────────────────────────────────────


DIMENSION_SYSTEM_PROMPT = """
Tu es un expert en qualité des données (Data Quality Engineer). 
Tu analyses des métadonnées de datasets pour identifier les règles
de qualité applicables selon les 5 dimensions standards :

1. COMPLETENESS  : Les données sont-elles complètes ? (nulls, champs manquants)
2. UNIQUENESS    : Y a-t-il des doublons ?
3. VALIDITY      : Les valeurs respectent-elles les règles métier ? (range, format, pattern)
4. CONSISTENCY   : Les données sont-elles cohérentes entre elles ? (dates, relations)
5. ACCURACY      : Les valeurs sont-elles correctes ? (types erronés, valeurs impossibles)

Tu réponds UNIQUEMENT en JSON valide, sans texte avant ni après.
Tu réponds en français pour les descriptions et justifications.
"""


def build_dimension_user_prompt(
    raw_metadata: dict,
    profiling_summary: str,
) -> str:
    """
    Construit le prompt pour que le LLM mappe les colonnes
    aux dimensions de qualité et extrait les règles.

    Args:
        raw_metadata:      Metadata fourni par l'user (format libre)
        profiling_summary: Résumé du profiling (build_llm_summary())

    Returns:
        Prompt user complet prêt à envoyer au LLM.
    """
    return f"""
Analyse le metadata suivant et identifie pour chaque colonne :
- Quelles dimensions de qualité s'appliquent
- Les règles métier extraites du metadata
- Le rôle probable de la colonne (identifier, metric, dimension, temporal)

METADATA FOURNI PAR L'UTILISATEUR :
{raw_metadata}

ÉTAT ACTUEL DU DATASET (profiling) :
{profiling_summary}

Réponds avec ce JSON exact :
{{
  "sector": "nom du secteur détecté",
  "dimension_mapping": {{
    "nom_colonne": ["completeness", "uniqueness", ...]
  }},
  "dimension_rules": {{
    "nom_colonne": {{
      "role": "identifier | metric | dimension | temporal",
      "nullable": true,
      "range": {{"min": 0, "max": 1000}},
      "pattern": "regex si applicable",
      "description": "description de la colonne"
    }}
  }}
}}
"""


# ── PROMPT 2 — strategy_node ─────────────────────────────────────────────────


STRATEGY_SYSTEM_PROMPT = """
Tu es un expert Data Quality Engineer.
Tu analyses des datasets et proposes des plans de nettoyage précis et justifiés.

Tes propositions doivent être :
- PRÉCISES : spécifier exactement quelles lignes sont concernées
- JUSTIFIÉES : expliquer pourquoi chaque action est proposée
- PRUDENTES : ne jamais supprimer une donnée si ce n'est pas nécessaire
- COHÉRENTES avec les 5 dimensions de qualité (Completeness, Uniqueness,
  Validity, Consistency, Accuracy)

Actions disponibles (utilise EXACTEMENT ces noms) :
  drop_null_identifier, drop_duplicates, impute_median, impute_mode,
  impute_constant, cast_to_float, cast_to_int, cast_to_string,
  parse_date, trim_whitespace, to_uppercase, to_lowercase,
  fix_date_order, flag_outlier, log_range_violation

Tu réponds UNIQUEMENT en JSON valide, en français.
"""


def build_strategy_user_prompt(
    profiling_summary: str,
    dimension_mapping: dict,
    dimension_rules: dict,
    raw_metadata: dict,
) -> str:
    """
    Construit le prompt pour que le LLM propose le plan de nettoyage.

    Le LLM reçoit :
    - Le résumé du profiling (anomalies détectées)
    - Le mapping colonnes → dimensions
    - Les règles extraites du metadata
    - Le metadata original de l'user

    Args:
        profiling_summary: Résumé textuel des anomalies
        dimension_mapping: Mapping colonnes → dimensions
        dimension_rules:   Règles par colonne
        raw_metadata:      Metadata original de l'user

    Returns:
        Prompt user complet.
    """
    import json

    return f"""
Analyse les anomalies suivantes et propose un plan de nettoyage complet.

ANOMALIES DÉTECTÉES :
{profiling_summary}

MAPPING COLONNES → DIMENSIONS :
{json.dumps(dimension_mapping, ensure_ascii=False, indent=2)}

RÈGLES MÉTIER PAR COLONNE :
{json.dumps(dimension_rules, ensure_ascii=False, indent=2)}

METADATA ORIGINAL :
{json.dumps(raw_metadata, ensure_ascii=False, indent=2)}

Pour CHAQUE anomalie détectée, propose une action de nettoyage.
Sois explicite sur les lignes concernées.

Réponds avec ce JSON exact :
{{
  "llm_analysis": "Analyse globale du dataset en 3-5 phrases",
  "risques": [
    "Description d'un risque identifié"
  ],
  "actions": [
    {{
      "action_id": "action_1",
      "colonne": "nom_colonne",
      "lignes_concernees": [7, 12],
      "dimension": "completeness",
      "probleme": "Description du problème",
      "action": "impute_median",
      "justification": "Pourquoi cette action est la meilleure",
      "severite": "BLOCKING | MAJOR | MINOR",
      "parametre": {{}}
    }}
  ]
}}

RÈGLES IMPORTANTES :
- Pour les identifiants nuls → drop_null_identifier (ligne inutilisable)
- Pour les doublons → drop_duplicates
- Pour les nulls numériques → impute_median (robuste aux outliers)
- Pour les nulls texte → impute_mode (valeur la plus fréquente)
- Pour les outliers → flag_outlier (NE PAS supprimer automatiquement)
- Pour les erreurs de type → cast_to_float ou cast_to_string
- Pour les dates incohérentes → fix_date_order
- Pour le texte avec espaces → trim_whitespace
- Pour la casse incohérente → to_uppercase
"""


# ── PROMPT 3 — evaluation_node ───────────────────────────────────────────────


EVALUATION_SYSTEM_PROMPT = """
Tu es un expert Data Quality Engineer.
Tu analyses les résultats d'un pipeline de nettoyage de données
et produis un rapport d'évaluation professionnel.

Ton évaluation doit :
- Comparer les scores AVANT et APRÈS le nettoyage
- Identifier les dimensions qui ont le plus progressé
- Expliquer les dimensions dont le score n'est pas à 100%
- Formuler des recommandations pour améliorer davantage la qualité

Tu réponds avec une analyse en JSON, en français.
"""


def build_evaluation_user_prompt(
    dimensions_before: dict,
    dimensions_after: dict,
    cleaning_log: list,
    dbt_results: list,
) -> str:
    """
    Construit le prompt pour que le LLM évalue les résultats.

    Args:
        dimensions_before: Scores 5 dimensions avant cleaning
        dimensions_after:  Scores 5 dimensions après cleaning
        cleaning_log:      Log des opérations effectuées
        dbt_results:       Résultats des tests dbt

    Returns:
        Prompt user complet.
    """
    import json

    # Résumé compact du cleaning log (éviter trop de tokens)
    cleaning_summary = [
        f"{entry.get('operation', '?')} sur {entry.get('colonne', '?')} "
        f"→ {entry.get('rows_affected', 0)} lignes"
        for entry in cleaning_log[-20:]  # 20 dernières opérations max
    ]

    # Tests dbt échoués seulement (plus pertinent)
    failed_tests = [
        r for r in dbt_results
        if r.get("status") == "fail"
    ]

    return f"""
Évalue les résultats du pipeline de nettoyage de données.

SCORES AVANT NETTOYAGE :
{json.dumps(dimensions_before, ensure_ascii=False, indent=2)}

SCORES APRÈS NETTOYAGE :
{json.dumps(dimensions_after, ensure_ascii=False, indent=2)}

OPÉRATIONS EFFECTUÉES :
{chr(10).join(cleaning_summary)}

TESTS DBT ÉCHOUÉS :
{json.dumps(failed_tests, ensure_ascii=False, indent=2)}

Réponds avec ce JSON exact :
{{
  "resume_executif": "Synthèse en 2-3 phrases pour un manager",
  "analyse_par_dimension": {{
    "completeness": {{
      "evolution": "amélioration / stable / dégradation",
      "commentaire": "Explication de l'évolution"
    }},
    "uniqueness": {{
      "evolution": "...",
      "commentaire": "..."
    }},
    "validity": {{
      "evolution": "...",
      "commentaire": "..."
    }},
    "consistency": {{
      "evolution": "...",
      "commentaire": "..."
    }},
    "accuracy": {{
      "evolution": "...",
      "commentaire": "..."
    }}
  }},
  "recommandations": [
    "Recommandation actionnable 1",
    "Recommandation actionnable 2"
  ],
  "score_global_avant": 0.0,
  "score_global_apres": 0.0,
  "gain_total": 0.0
}}
"""