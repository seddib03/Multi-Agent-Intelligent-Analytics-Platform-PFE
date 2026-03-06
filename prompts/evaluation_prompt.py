from __future__ import annotations

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