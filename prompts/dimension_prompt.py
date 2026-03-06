from __future__ import annotations


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
