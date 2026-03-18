"""
Prompts pour la traduction des business rules en tests dbt via LLM. 
"""
from __future__ import annotations


BUSINESS_RULES_SYSTEM_PROMPT = """
Tu es un expert Data Quality Engineer spécialisé en dbt (data build tool).
Tu traduis des règles métier exprimées en langage naturel en tests dbt exécutables.

MACROS DBT EXISTANTES (à réutiliser en priorité) :
- not_null          : vérifie qu'une colonne n'a pas de valeurs NULL
- unique            : vérifie qu'une colonne n'a pas de doublons
- in_range(min_value, max_value) : vérifie qu'une valeur numérique est dans un intervalle
- is_type(type_str) : vérifie le type d'une colonne (integer, double, varchar)
- date_format(format_str) : vérifie le format de date
- regex_pattern(pattern)  : vérifie un pattern regex
- accepted_values(values) : vérifie que les valeurs sont dans une liste
- row_not_duplicate       : vérifie qu'il n'y a pas de lignes dupliquées (test table-level)

DIMENSIONS DE QUALITÉ :
- completeness  : les données sont-elles complètes ? (nulls, champs manquants)
- uniqueness    : y a-t-il des doublons ?
- validity      : les valeurs respectent-elles les règles ? (format, pattern, enum)
- accuracy      : les valeurs sont-elles dans les plages attendues ? (range, seuils)
- consistency   : les données sont-elles cohérentes entre elles ? (relations, contraintes croisées)

RÈGLES :
1. Si une règle peut être couverte par une macro EXISTANTE, utilise-la (test_type = "existing")
2. Sinon, crée un test custom avec du SQL DuckDB valide (test_type = "custom")
3. Assigne la BONNE dimension de qualité à chaque règle
4. Le SQL custom doit retourner les lignes EN ERREUR (convention dbt : un test passe si 0 lignes retournées)
5. Pour les tests custom, le SQL doit être compatible DuckDB

Tu réponds UNIQUEMENT en JSON valide, sans texte avant ni après.
"""


def build_business_rules_user_prompt(
    business_rules: list[str],
    columns_info: list[dict],
) -> str:
    """
    Construit le prompt user pour traduire les business rules en tests dbt.

    Args:
        business_rules: Liste de règles en langage naturel
        columns_info:   Info sur les colonnes (nom, type, nullable, etc.)

    Returns:
        Prompt user complet.
    """
    import json

    cols_summary = json.dumps(columns_info, ensure_ascii=False, indent=2)
    rules_text = "\n".join(f"  {i+1}. {rule}" for i, rule in enumerate(business_rules))

    return f"""
Traduis les règles métier suivantes en tests dbt.

COLONNES DU DATASET :
{cols_summary}

RÈGLES MÉTIER À TRADUIRE :
{rules_text}

Pour chaque règle, retourne un objet JSON dans la liste "rules".
Si la règle utilise une macro existante, mets test_type = "existing".
Si la règle nécessite un test custom, mets test_type = "custom" et fournis le SQL.

Réponds avec ce JSON exact :
{{
  "rules": [
    {{
      "rule_text": "Texte original de la règle",
      "dimension": "completeness | uniqueness | validity | accuracy | consistency",
      "test_type": "existing | custom",
      "macro_name": "nom_de_la_macro (ex: unique, in_range, ou nom_custom)",
      "macro_sql": "SQL complet de la macro dbt SI test_type=custom, sinon null",
      "schema_entry": "entrée pour _sources.yml (string pour test simple, dict pour test avec params)",
      "target_column": "nom_colonne ou null si test table-level",
      "is_table_level": false
    }}
  ]
}}

EXEMPLES :

Règle: "policy_id doit être unique"
→ test_type: "existing", macro_name: "unique", target_column: "policy_id", dimension: "uniqueness"

Règle: "premium doit être entre 100 et 50000"
→ test_type: "existing", macro_name: "in_range", schema_entry: {{"in_range": {{"min_value": 100, "max_value": 50000}}}}, target_column: "premium", dimension: "accuracy"

Règle: "start_date doit être avant end_date"
→ test_type: "custom", macro_name: "date_start_before_end", dimension: "consistency", is_table_level: true
  macro_sql: "{{% test date_start_before_end(model) %}}\\nSELECT * FROM {{{{ model }}}} WHERE start_date >= end_date\\n{{% endtest %}}"

Règle: "Le total des montants par catégorie ne doit pas dépasser le budget"
→ test_type: "custom", macro_name: "budget_check", dimension: "consistency", is_table_level: true
  macro_sql: "{{% test budget_check(model) %}}\\nSELECT * FROM {{{{ model }}}} WHERE montant > budget\\n{{% endtest %}}"

TRÈS IMPORTANT POUR test_type="custom" :
- Tu DOIS envelopper le SQL dans `{{% test nom_macro(model) %}}` (table-level) ou `{{% test nom_macro(model, column_name) %}}` (column-level).
- ATTENTION : Dans la signature `test nom_macro(model, column_name)`, le mot `column_name` DOIT être écrit tel quel. Ne mets JAMAIS le vrai nom de la colonne (ex: 'delay_minutes') dans les parenthèses de la signature du test.
- Dans le SQL du test, utilise `{{{{ column_name }}}}` pour te référer à la colonne testée.
- Tu DOIS utiliser `{{{{ model }}}}` dans le `FROM` (et JAMAIS utiliser `ref()` car on teste une source).
- Le SQL DOIT sélectionner les lignes en ERREUR (celles qui violent la règle).
- ATTENTION AUX TYPES : Dans DuckDB, toutes les données brutes sont initialement en VARCHAR (texte). 
  - Tu DOIS utiliser `TRY_CAST(colonne AS FLOAT)` ou `TRY_CAST(colonne AS INT)` pour TOUTES les opérations mathématiques ou comparaisons numériques.
  - Tu DOIS utiliser `TRY_CAST(strptime(colonne, '%Y-%m-%d') AS DATE)` pour comparer des dates (NE JAMAIS utiliser < ou > directement sur deux dates VARCHAR).
"""
