# core/file_loader.py

# Standard library
from __future__ import annotations

import logging
from pathlib import Path

# Third-party
import chardet
import polars as pl


logger = logging.getLogger(__name__)

# Extensions supportées et leur loader Polars associé
# On définit ça comme constante en haut du fichier
SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".parquet"}


# ─── Fonction publique ───────────────────────────────────────────────────────


def load_dataset(file_path: str) -> tuple[pl.DataFrame, dict]:
    """Charge un dataset depuis un fichier peu importe son format.

    Détecte automatiquement le format via l'extension,
    détecte l'encodage pour les CSV, et charge le fichier
    avec Polars.

    Args:
        file_path: Chemin vers le fichier dataset.

    Returns:
        Tuple contenant :
            - pl.DataFrame : données chargées
            - dict : informations d'ingestion
              (format, encodage, nb_lignes, nb_colonnes)

    Raises:
        FileNotFoundError: Si le fichier n'existe pas.
        ValueError: Si le format n'est pas supporté.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Dataset introuvable : {file_path}"
        )

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Format non supporté : '{extension}'. "
            f"Formats acceptés : {SUPPORTED_EXTENSIONS}"
        )

    logger.info("Chargement du fichier : %s (format : %s)", file_path, extension)

    # Router vers le bon loader selon l'extension
    if extension == ".csv":
        data_frame, ingestion_info = _load_csv(path)
    elif extension in (".xlsx", ".xls"):
        data_frame, ingestion_info = _load_excel(path)
    elif extension == ".json":
        data_frame, ingestion_info = _load_json(path)
    elif extension == ".parquet":
        data_frame, ingestion_info = _load_parquet(path)

    logger.info(
        "Fichier chargé — lignes : %d | colonnes : %d",
        ingestion_info["nb_rows"],
        ingestion_info["nb_columns"],
    )

    return data_frame, ingestion_info


# ─── Loaders privés ──────────────────────────────────────────────────────────


def _detect_encoding(file_path: Path) -> str:
    """Détecte l'encodage d'un fichier texte avec chardet.

    Lit les premiers 50 000 octets du fichier pour détecter
    l'encodage. Retourne UTF-8 par défaut si non détecté.

    Args:
        file_path: Chemin vers le fichier.

    Returns:
        Nom de l'encodage détecté (ex: 'utf-8', 'latin-1').
    """
    # On ne lit que le début du fichier pour la performance
    with open(file_path, "rb") as file:
        raw_bytes = file.read(50_000)

    result   = chardet.detect(raw_bytes)
    encoding = result.get("encoding") or "utf-8"

    logger.info("Encodage détecté : %s (confiance : %.0f%%)",
                encoding, (result.get("confidence") or 0) * 100)

    return encoding


def _build_ingestion_info(
    data_frame: pl.DataFrame,
    file_format: str,
    encoding: str = "N/A",
) -> dict:
    """Construit le dictionnaire d'informations d'ingestion.

    Centralise la construction de l'ingestion_info pour
    éviter la duplication dans chaque loader.

    Args:
        data_frame:  DataFrame chargé.
        file_format: Format du fichier (csv, excel, json, parquet).
        encoding:    Encodage détecté (pertinent pour CSV).

    Returns:
        Dictionnaire avec nb_rows, nb_columns, format, encoding,
        et la liste des colonnes chargées.
    """
    return {
        "nb_rows":      data_frame.height,
        "nb_columns":   data_frame.width,
        "file_format":  file_format,
        "encoding":     encoding,
        "columns_loaded": data_frame.columns,
    }


def _load_csv(file_path: Path) -> tuple[pl.DataFrame, dict]:
    """Charge un fichier CSV avec détection automatique de l'encodage.

    Args:
        file_path: Chemin vers le fichier CSV.

    Returns:
        Tuple (DataFrame, ingestion_info).
    """
    encoding   = _detect_encoding(file_path)
    data_frame = pl.read_csv(
        file_path,
        encoding=encoding,
        # infer_schema_length=0 charge tout en string d'abord
        # pour éviter les erreurs de typage au chargement
        # le typage correct sera fait dans cleaning_node
        infer_schema_length=0,
        ignore_errors=True,
    )
    return data_frame, _build_ingestion_info(data_frame, "csv", encoding)


def _load_excel(file_path: Path) -> tuple[pl.DataFrame, dict]:
    """Charge un fichier Excel (.xlsx ou .xls).

    Args:
        file_path: Chemin vers le fichier Excel.

    Returns:
        Tuple (DataFrame, ingestion_info).
    """
    data_frame = pl.read_excel(file_path)
    return data_frame, _build_ingestion_info(data_frame, "excel")


def _load_json(file_path: Path) -> tuple[pl.DataFrame, dict]:
    """Charge un fichier JSON.

    Args:
        file_path: Chemin vers le fichier JSON.

    Returns:
        Tuple (DataFrame, ingestion_info).
    """
    data_frame = pl.read_json(file_path)
    return data_frame, _build_ingestion_info(data_frame, "json")


def _load_parquet(file_path: Path) -> tuple[pl.DataFrame, dict]:
    """Charge un fichier Parquet.

    Args:
        file_path: Chemin vers le fichier Parquet.

    Returns:
        Tuple (DataFrame, ingestion_info).
    """
    data_frame = pl.read_parquet(file_path)
    return data_frame, _build_ingestion_info(data_frame, "parquet")