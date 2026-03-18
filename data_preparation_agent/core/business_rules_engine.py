"""
Moteur de traduction des business rules en tests dbt via LLM.

Flow :
    1. Reçoit les business_rules (strings langage naturel) + metadata colonnes
    2. Appelle le LLM pour traduire en configs de tests dbt
    3. Pour les tests custom → crée les macros .sql dans dbt_project/macros/
    4. Retourne les entrées à injecter dans _sources.yml
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from config.settings import get_settings
from core.llm_client import LLMClient
from prompts.business_rules_prompt import (
    BUSINESS_RULES_SYSTEM_PROMPT,
    build_business_rules_user_prompt,
)

logger = logging.getLogger(__name__)

class BusinessRuleTest:
    """Représente un test dbt généré à partir d'une business rule."""

    def __init__(
        self,
        rule_text: str,
        dimension: str,
        test_type: str,
        macro_name: str,
        schema_entry: object,
        target_column: Optional[str] = None,
        is_table_level: bool = False,
        macro_sql: Optional[str] = None,
    ):
        self.rule_text = rule_text
        self.dimension = dimension            # completeness, uniqueness, validity, accuracy, consistency
        self.test_type = test_type            # "existing" ou "custom"
        self.macro_name = macro_name
        self.schema_entry = schema_entry      # entrée pour _sources.yml
        self.target_column = target_column
        self.is_table_level = is_table_level
        self.macro_sql = macro_sql            # SQL de la macro custom (si test_type="custom")

    def to_dict(self) -> dict:
        return {
            "rule_text": self.rule_text,
            "dimension": self.dimension,
            "test_type": self.test_type,
            "macro_name": self.macro_name,
            "schema_entry": self.schema_entry,
            "target_column": self.target_column,
            "is_table_level": self.is_table_level,
        }


def process_business_rules(
    business_rules: list[str],
    metadata: list,
    macros_dir: Optional[str] = None,
) -> list[BusinessRuleTest]:
    """
    Traduit les business rules en tests dbt via LLM.

    Args:
        business_rules: Liste de règles en langage naturel
        metadata:       Liste de ColumnMeta (ou dicts)
        macros_dir:     Dossier où créer les macros custom (défaut: dbt_project/macros)

    Returns:
        Liste de BusinessRuleTest prêts à injecter dans le schema dbt.
    """
    if not business_rules:
        logger.info("Aucune business rule fournie — skip")
        return []

    settings = get_settings()
    if macros_dir is None:
        macros_dir = str(settings.dbt_project_dir / "macros")

    generated_dir = str(Path(macros_dir) / "generated")

    # Vider le dossier des anciennes macros générées
    _cleanup_generated_macros(generated_dir)

    # Préparer les infos colonnes pour le prompt
    columns_info = []
    for col in metadata:
        if isinstance(col, dict):
            col_dict = col
        else:
            # ColumnMeta dataclass
            import dataclasses
            col_dict = dataclasses.asdict(col)

        columns_info.append({
            "column_name": col_dict.get("column_name"),
            "type": col_dict.get("type"),
            "nullable": col_dict.get("nullable", True),
            "identifier": col_dict.get("identifier", False),
            "min": col_dict.get("min"),
            "max": col_dict.get("max"),
            "pattern": col_dict.get("pattern"),
            "enum": col_dict.get("enum"),
            "description": col_dict.get("description"),
        })

    # Appeler le LLM
    logger.info("Traduction de %d business rules via LLM...", len(business_rules))
    llm = LLMClient()

    user_prompt = build_business_rules_user_prompt(business_rules, columns_info)

    try:
        llm_response = llm.call_structured(
            system_prompt=BUSINESS_RULES_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
    except Exception as e:
        logger.error("Erreur LLM pour business rules : %s", e)
        return []

    # Parser la réponse
    rules_data = llm_response.get("rules", [])
    if not rules_data:
        logger.warning("Le LLM n'a retourné aucune règle")
        return []

    results = []
    for rule_data in rules_data:
        try:
            macro_name = rule_data.get("macro_name", "")
            test_type = rule_data.get("test_type", "existing")
            schema_entry = rule_data.get("schema_entry")

            # Correction : pour les tests custom, si schema_entry est null, 
            # on utilise le macro_name pour qu'il soit bien injecté dans le .yml dbt
            if test_type == "custom" and not schema_entry and macro_name:
                schema_entry = macro_name

            rule = BusinessRuleTest(
                rule_text=rule_data.get("rule_text", ""),
                dimension=rule_data.get("dimension", "validity"),
                test_type=test_type,
                macro_name=macro_name,
                schema_entry=schema_entry,
                target_column=rule_data.get("target_column"),
                is_table_level=rule_data.get("is_table_level", False),
                macro_sql=rule_data.get("macro_sql"),
            )

            # Si c'est un test custom, créer la macro .sql
            if rule.test_type == "custom" and rule.macro_sql:
                _create_custom_macro(rule, generated_dir)

            results.append(rule)
            logger.info(
                "Business rule traduite : '%s' → %s (%s, dim=%s)",
                rule.rule_text[:60],
                rule.macro_name,
                rule.test_type,
                rule.dimension,
            )

        except Exception as e:
            logger.warning(
                "Impossible de parser la business rule : %s — erreur : %s",
                rule_data,
                e,
            )

    logger.info("%d business rules traduites avec succès", len(results))
    return results


def _cleanup_generated_macros(generated_dir: str) -> None:
    """
    Vide intégralement le dossier macros/generated/ des anciennes macros.
    """
    gen_path = Path(generated_dir)
    if not gen_path.exists():
        return

    for macro_file in gen_path.glob("*.sql"):
        try:
            macro_file.unlink()
            logger.info("Ancienne macro générée supprimée : %s", macro_file)
        except Exception as e:
            logger.warning("Impossible de supprimer %s : %s", macro_file, e)


def _create_custom_macro(rule: BusinessRuleTest, generated_dir: str) -> None:
    """
    Crée un fichier .sql pour une macro custom dans dbt_project/macros/generated/.
    """
    macro_filename = f"test_{rule.macro_name}.sql"
    macro_path = Path(generated_dir) / macro_filename

    Path(generated_dir).mkdir(parents=True, exist_ok=True)
    with open(macro_path, "w", encoding="utf-8") as f:
        f.write(rule.macro_sql)

    logger.info("Macro custom créée : %s", macro_path)
