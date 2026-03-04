# Standard library
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Synonymes acceptés pour chaque concept clé ───────────────────────────────
#
# Le metadata de l'user peut utiliser n'importe quel terme.
# On normalise en interne pour que le reste du code soit cohérent.
# Si l'user écrit "champs", "fields", ou "columns" → on comprend tous.
#
_SYNONYMS_FIELDS = [
    "columns", "champs", "fields", "colonnes",
    "attributs", "attributes", "variables",
]

_SYNONYMS_FIELD_NAME = [
    "name", "nom", "nom_champ", "field_name",
    "column_name", "colonne", "champ",
]

_SYNONYMS_DESCRIPTION = [
    "description", "desc", "label",
    "libelle", "libellé", "definition",
]

_SYNONYMS_TYPE = [
    "type", "data_type", "type_donnee",
    "type_de_donnee", "dtype",
]

_SYNONYMS_NULLABLE = [
    "nullable", "optional", "optionnel",
    "peut_etre_null", "allow_null", "required",
]

_SYNONYMS_BUSINESS_RULES = [
    "business_rules", "business_rule", "regles_metier",
    "regle_metier", "rules", "contraintes", "constraints",
]

_SYNONYMS_POSSIBLE_VALUES = [
    "valeurs_possibles", "possible_values", "accepted_values",
    "valeurs_acceptees", "enum", "categories",
]

_SYNONYMS_SECTOR = [
    "sector", "secteur", "domain", "domaine",
    "business_domain", "industrie",
]


def load_metadata(metadata_path: str) -> dict:
    """Charge et normalise le metadata depuis un fichier JSON.

    Accepte n'importe quel format de metadata fourni par l'user.
    Normalise les clés en interne pour que le reste du pipeline
    utilise une terminologie cohérente.

    La normalisation est non-destructive : les champs originaux
    sont conservés dans "raw_fields" pour que le LLM puisse
    les lire dans leur format d'origine.

    Args:
        metadata_path: Chemin vers le fichier metadata JSON.

    Returns:
        Dictionnaire normalisé avec :
            - sector          : nom du secteur
            - description     : description libre du dataset
            - fields          : liste des champs normalisés
            - raw_metadata    : metadata original intact
            - extra_keys      : clés non reconnues (pour le LLM)

    Raises:
        FileNotFoundError : si le fichier n'existe pas.
        ValueError        : si le JSON est invalide.
    """
    path = Path(metadata_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Fichier metadata introuvable : {metadata_path}"
        )

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Fichier metadata JSON invalide : {error}"
        ) from error

    logger.info("Metadata chargé depuis %s", metadata_path)

    normalized = {
        "sector":       _extract_value(raw, _SYNONYMS_SECTOR, default="unknown"),
        "description":  _extract_value(raw, _SYNONYMS_DESCRIPTION, default=""),
        "fields":       _normalize_fields(raw),
        "raw_metadata": raw,
        "extra_keys":   _extract_extra_keys(raw),
    }

    logger.info(
        "Metadata normalisé — secteur : %s | %d champs détectés",
        normalized["sector"],
        len(normalized["fields"]),
    )

    return normalized


def _normalize_fields(raw: dict) -> list[dict]:
    """Normalise la liste des champs depuis le metadata brut.

    Parcourt les synonymes connus pour trouver la liste de champs,
    puis normalise chaque champ individuellement.

    Args:
        raw: Metadata brut tel que fourni par l'user.

    Returns:
        Liste de champs normalisés. Liste vide si aucun champ trouvé.
    """
    # Chercher la liste de champs sous n'importe quel synonyme connu
    raw_fields = _extract_value(raw, _SYNONYMS_FIELDS, default=[])

    if not raw_fields:
        logger.warning(
            "Aucune liste de champs trouvée dans le metadata. "
            "Clés disponibles : %s",
            list(raw.keys()),
        )
        return []

    return [_normalize_single_field(field) for field in raw_fields]


def _normalize_single_field(field: dict) -> dict:
    """Normalise un champ individuel du metadata.

    Extrait les informations connues sous leurs synonymes
    et les stocke sous des clés normalisées.
    Conserve les champs originaux dans "raw_field".

    Args:
        field: Dictionnaire brut d'un champ.

    Returns:
        Dictionnaire normalisé du champ avec toutes les infos
        disponibles + champ "raw_field" pour le LLM.
    """
    # Extraire si le champ est obligatoire
    # Attention : "required" est l'inverse de "nullable"
    nullable_raw = _extract_value(field, _SYNONYMS_NULLABLE, default=None)
    if nullable_raw is None:
        nullable = True  # par défaut on considère nullable
    elif isinstance(nullable_raw, bool):
        # Si le champ s'appelle "required", la logique est inversée
        key_used = _find_key(field, _SYNONYMS_NULLABLE)
        nullable = not nullable_raw if key_used == "required" else nullable_raw
    else:
        nullable = True

    return {
        # Clés normalisées utilisées par le reste du pipeline
        "name":            _extract_value(field, _SYNONYMS_FIELD_NAME, default=""),
        "description":     _extract_value(field, _SYNONYMS_DESCRIPTION, default=""),
        "type":            _extract_value(field, _SYNONYMS_TYPE, default="unknown"),
        "nullable":        nullable,
        "business_rules":  _extract_value(field, _SYNONYMS_BUSINESS_RULES, default=""),
        "possible_values": _extract_value(field, _SYNONYMS_POSSIBLE_VALUES, default=[]),

        # Champ original conservé intact pour le LLM
        # Le LLM peut l'utiliser pour comprendre le contexte métier complet
        "raw_field": field,
    }


def _extract_value(
    data: dict,
    synonyms: list[str],
    default: Any = None,
) -> Any:
    """Cherche une valeur dans un dict en testant une liste de synonymes.

    Teste les synonymes dans l'ordre fourni.
    Retourne la première valeur trouvée, ou default si aucune.

    La recherche est insensible à la casse pour plus de robustesse.

    Args:
        data:     Dictionnaire dans lequel chercher.
        synonyms: Liste de clés synonymes à tester dans l'ordre.
        default:  Valeur par défaut si aucune clé n'est trouvée.

    Returns:
        Valeur trouvée ou default.
    """
    # Construire un mapping lowercase → clé originale pour la recherche
    data_lower = {key.lower(): value for key, value in data.items()}

    for synonym in synonyms:
        value = data_lower.get(synonym.lower())
        if value is not None:
            return value

    return default


def _find_key(data: dict, synonyms: list[str]) -> str | None:
    """Retourne le nom exact de la clé trouvée parmi les synonymes.

    Utile pour connaître quel synonyme a été utilisé par l'user,
    ce qui permet d'appliquer la logique correcte (ex: "required"
    est l'inverse de "nullable").

    Args:
        data:     Dictionnaire dans lequel chercher.
        synonyms: Liste de clés synonymes à tester.

    Returns:
        Clé trouvée (en minuscules) ou None si aucune.
    """
    data_lower = {key.lower(): key for key in data.keys()}

    for synonym in synonyms:
        if synonym.lower() in data_lower:
            return synonym.lower()

    return None


def _extract_extra_keys(raw: dict) -> dict:
    """Extrait les clés non reconnues du metadata.

    Ces clés seront transmises au LLM pour enrichir son analyse.
    L'user peut avoir ajouté des informations spécifiques à son
    secteur que les synonymes prédéfinis ne couvrent pas.

    Args:
        raw: Metadata brut.

    Returns:
        Dictionnaire des clés non reconnues avec leurs valeurs.
    """
    # Toutes les clés que notre parser connaît
    all_known_synonyms = set(
        synonym.lower()
        for synonyms_list in [
            _SYNONYMS_FIELDS,
            _SYNONYMS_SECTOR,
            _SYNONYMS_DESCRIPTION,
        ]
        for synonym in synonyms_list
    )

    return {
        key: value
        for key, value in raw.items()
        if key.lower() not in all_known_synonyms
    }