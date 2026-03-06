from __future__ import annotations

import logging
import re
from typing import Optional

import polars as pl

from config.settings import get_settings
from models.profiling_report import AnomalyDetail, ColumnProfile, ProfilingReport

logger = logging.getLogger(__name__)

# Seuil de % de valeurs similaires pour considérer
# qu'un pattern regex est "dominant" dans une colonne
PATTERN_DOMINANCE_THRESHOLD = 0.80


def run_profiling(df: pl.DataFrame) -> ProfilingReport:
    """
    Point d'entrée principal du profiler.

    Orchestre l'analyse complète du dataset en 4 étapes :
        1. Stats globales
        2. Profil de chaque colonne
        3. Détection des anomalies
        4. Construction du rapport

    Args:
        df: DataFrame Polars brut (chargé par file_loader)
            Toutes les colonnes sont en String car
            file_loader charge avec infer_schema=False.

    Returns:
        ProfilingReport complet avec stats et anomalies.
    """
    logger.info(
        "Démarrage profiling — %d lignes x %d colonnes",
        df.height,
        df.width,
    )

    # ── Étape 1 : profil par colonne ─────────────────────────────────────────
    # On profile chaque colonne individuellement
    column_profiles = {
        col_name: _profile_single_column(df, col_name)
        for col_name in df.columns
    }

    # ── Étape 2 : détection des anomalies ────────────────────────────────────
    anomalies = _detect_all_anomalies(df, column_profiles)

    # ── Étape 3 : stats globales ──────────────────────────────────────────────
    total_nulls = sum(p.null_count for p in column_profiles.values())
    total_dupes = df.height - df.unique().height

    report = ProfilingReport(
        total_rows=df.height,
        total_columns=df.width,
        total_nulls=total_nulls,
        null_pct=round(total_nulls / max(1, df.height * df.width) * 100, 2),
        total_duplicates=total_dupes,
        duplicate_pct=round(total_dupes / max(1, df.height) * 100, 2),
        columns=column_profiles,
        anomalies=anomalies,
    )

    logger.info(
        "Profiling terminé — %d anomalies détectées "
        "(%d nulls, %d doublons)",
        report.total_anomalies,
        total_nulls,
        total_dupes,
    )

    return report


# ── Profil d'une colonne ─────────────────────────────────────────────────────


def _profile_single_column(
    df: pl.DataFrame,
    col_name: str,
) -> ColumnProfile:
    """
    Calcule le profil statistique d'une seule colonne.

    Détecte d'abord le type réel de la colonne
    (même si tout est chargé en String),
    puis calcule les métriques adaptées à ce type.

    Args:
        df:       DataFrame complet
        col_name: Nom de la colonne à profiler

    Returns:
        ColumnProfile avec toutes les métriques calculées.
    """
    col       = df[col_name]
    non_null  = col.drop_nulls()
    null_count = col.null_count()

    # Détecter le type réel de la colonne
    type_detecte = _detect_column_type(non_null)

    # Profil de base (commun à tous les types)
    profile = ColumnProfile(
        nom=col_name,
        type_detecte=type_detecte,
        null_count=null_count,
        null_pct=round(null_count / max(1, df.height) * 100, 2),
        unique_count=col.n_unique(),
        total_count=df.height,
        sample_values=non_null.head(3).to_list(),
        duplicate_count=len(col) - col.n_unique(),
    )

    # Métriques spécifiques aux colonnes numériques
    if type_detecte in ("float", "int"):
        _enrich_numeric_profile(profile, non_null)

    # Métriques spécifiques aux colonnes texte
    elif type_detecte == "string":
        _enrich_string_profile(profile, non_null)

    return profile


def _detect_column_type(non_null_series: pl.Series) -> str:
    """
    Détecte le type réel d'une colonne chargée en String.

    LOGIQUE :
        Puisque file_loader charge tout en String,
        on essaie de convertir les valeurs non-nulles
        pour déterminer leur type réel.

        Ordre de test :
            1. Int  (les entiers sont un sous-ensemble des floats)
            2. Float
            3. Date (formats courants)
            4. String par défaut

    Args:
        non_null_series: Valeurs non-nulles de la colonne

    Returns:
        Type détecté : "int", "float", "date_string", "string", "mixed"
    """
    if non_null_series.is_empty():
        return "string"

    sample = non_null_series.head(20).to_list()

    # Tester int
    int_count = sum(1 for v in sample if _is_int(str(v)))
    if int_count / len(sample) >= 0.90:
        return "int"

    # Tester float
    float_count = sum(1 for v in sample if _is_float(str(v)))
    if float_count / len(sample) >= 0.90:
        return "float"

    # Tester date (formats courants)
    date_count = sum(1 for v in sample if _is_date_string(str(v)))
    if date_count / len(sample) >= 0.80:
        return "date_string"

    # Type mixte si mélange (ex: "850.50" et "2025-01-01")
    if float_count > 0 and date_count > 0:
        return "mixed"

    return "string"


def _enrich_numeric_profile(
    profile: ColumnProfile,
    non_null: pl.Series,
) -> None:
    """
    Ajoute les métriques numériques au profil.

    Modifie le profil en place (les attributs sont optionnels
    et initialisés à None dans ColumnProfile).

    Args:
        profile:  Profil à enrichir (modifié en place)
        non_null: Valeurs non-nulles de la colonne
    """
    # Convertir en float pour les calculs
    try:
        numeric = non_null.cast(pl.Float64, strict=False).drop_nulls()

        if numeric.is_empty():
            return

        profile.min    = round(float(numeric.min()), 4)
        profile.max    = round(float(numeric.max()), 4)
        profile.mean   = round(float(numeric.mean()), 4)
        profile.median = round(float(numeric.median()), 4)
        profile.std    = round(float(numeric.std()), 4)

        profile.negative_count = int((numeric < 0).sum())
        profile.outlier_count  = _count_outliers_iqr(numeric)

    except Exception as e:
        logger.warning(
            "Impossible de calculer métriques numériques pour %s : %s",
            profile.nom,
            str(e),
        )


def _enrich_string_profile(
    profile: ColumnProfile,
    non_null: pl.Series,
) -> None:
    """
    Détecte un pattern regex dominant dans une colonne texte.

    LOGIQUE :
        Si 80%+ des valeurs suivent un pattern comme
        "CTR-000001", "CTR-000002"...
        → On détecte le pattern "CTR-[0-9]+"

        C'est utile pour le LLM qui peut alors vérifier
        si les valeurs respectent ce pattern.

    Args:
        profile:  Profil à enrichir (modifié en place)
        non_null: Valeurs non-nulles de la colonne
    """
    sample = non_null.head(50).to_list()

    if not sample:
        return

    # Patterns courants à tester
    patterns_to_test = [
        (r"^[A-Z]{2,4}-\d{4,6}$",  "CODE-XXXXXX (ex: CTR-000001)"),
        (r"^\d{4}-\d{2}-\d{2}$",   "DATE YYYY-MM-DD"),
        (r"^[A-Z]{2}-\d{3}$",      "XX-NNN (ex: ST-001)"),
        (r"^\+?\d{8,15}$",         "Numéro de téléphone"),
        (r"^\d+$",                 "Entier en string"),
    ]

    for pattern, description in patterns_to_test:
        matches = sum(
            1 for v in sample
            if re.match(pattern, str(v))
        )
        if matches / len(sample) >= PATTERN_DOMINANCE_THRESHOLD:
            profile.pattern_detecte = pattern
            logger.debug(
                "Pattern détecté pour %s : %s (%d/%d valeurs)",
                profile.nom,
                description,
                matches,
                len(sample),
            )
            break


# ── Détection des anomalies ──────────────────────────────────────────────────


def _detect_all_anomalies(
    df: pl.DataFrame,
    column_profiles: dict[str, ColumnProfile],
) -> list[AnomalyDetail]:
    """
    Orchestre la détection de toutes les anomalies.

    Appelle chaque détecteur spécialisé et agrège les résultats.

    Args:
        df:              DataFrame complet
        column_profiles: Profils calculés par _profile_single_column

    Returns:
        Liste de toutes les anomalies détectées, toutes catégories.
    """
    anomalies = []
    anomalies += _detect_nulls(df)
    anomalies += _detect_duplicates(df)
    anomalies += _detect_type_errors(df, column_profiles)

    # 1. Nulls (ligne par ligne)
    #anomalies.extend(_detect_nulls(df))

    # 2. Doublons (lignes identiques)
    #anomalies.extend(_detect_duplicates(df))

    # 3. Outliers (colonnes numériques)
    #anomalies.extend(_detect_outliers(df, column_profiles))

    # 4. Erreurs de type (ex: texte dans colonne numérique)
    #anomalies.extend(_detect_type_errors(df, column_profiles))

    # 5. Incohérences entre colonnes (ex: dates inversées)
    #anomalies.extend(_detect_inconsistencies(df))

    return anomalies


def _detect_nulls(df: pl.DataFrame) -> list[AnomalyDetail]:
    anomalies = []
    for col_name in df.columns:
        col = df[col_name]
        null_mask = col.is_null().to_list()
        for idx, is_null in enumerate(null_mask):
            if is_null:
                anomalies.append(
                    AnomalyDetail(
                        ligne=idx + 1,
                        colonne=col_name,
                        valeur=None,
                        type_anomalie="null",
                        description=f"Valeur nulle dans la colonne '{col_name}'",
                    )
                )
    return anomalies

def _detect_duplicates(df: pl.DataFrame) -> list[AnomalyDetail]:
    anomalies = []
    if df.is_empty():
        return anomalies

    # Polars n'a pas .duplicated() — on ajoute un index de ligne,
    # on regroupe par toutes les colonnes et on garde les non-premières occurrences.
    df_indexed = df.with_row_index("__row_idx__")

    # Pour chaque groupe de lignes identiques, récupérer tous les index
    # et marquer comme doublons toutes les occurrences sauf la première.
    duplicate_indices = set()
    df_all_cols = df.columns

    grouped = (
        df_indexed
        .group_by(df_all_cols)
        .agg(pl.col("__row_idx__").alias("__indices__"))
        .filter(pl.col("__indices__").list.len() > 1)
    )

    for row in grouped.iter_rows(named=True):
        # On ignore le premier index (première occurrence), les autres sont doublons
        indices = sorted(row["__indices__"])
        for idx in indices[1:]:
            duplicate_indices.add(idx)

    for idx in sorted(duplicate_indices):
        anomalies.append(
            AnomalyDetail(
                ligne=idx + 1,
                colonne=None,
                valeur=None,
                type_anomalie="duplicate",
                description="Ligne dupliquée",
            )
        )
    return anomalies



def _detect_outliers(
    df: pl.DataFrame,
    column_profiles: dict[str, ColumnProfile],
) -> list[AnomalyDetail]:
    """
    Détecte les outliers dans les colonnes numériques.

    Méthode IQR de Tukey (standard académique) :
        Q1 = 25ème percentile
        Q3 = 75ème percentile
        IQR = Q3 - Q1
        Outlier si valeur < Q1 - 1.5*IQR ou > Q3 + 1.5*IQR

    Args:
        df:              DataFrame à analyser
        column_profiles: Pour identifier les colonnes numériques

    Returns:
        Liste d'AnomalyDetail, une par outlier trouvé.
    """
    anomalies = []
    settings  = get_settings()

    for col_name, profile in column_profiles.items():
        # Uniquement les colonnes numériques
        if profile.type_detecte not in ("float", "int"):
            continue

        try:
            numeric = (
                df[col_name]
                .cast(pl.Float64, strict=False)
                .drop_nulls()
            )

            if numeric.len() < 4:
                # IQR non fiable avec moins de 4 valeurs
                continue

            q1  = float(numeric.quantile(0.25))
            q3  = float(numeric.quantile(0.75))
            iqr = q3 - q1

            if iqr == 0:
                # Toutes les valeurs sont identiques → pas d'outlier
                continue

            lower_bound = q1 - settings.iqr_multiplier * iqr
            upper_bound = q3 + settings.iqr_multiplier * iqr

            # Chercher les outliers ligne par ligne
            for idx in range(df.height):
                raw_val = df[col_name][idx]
                if raw_val is None:
                    continue

                try:
                    val = float(str(raw_val))
                    if val < lower_bound or val > upper_bound:
                        anomalies.append(
                            AnomalyDetail(
                                ligne=idx + 1,
                                colonne=col_name,
                                valeur=val,
                                type_anomalie="outlier",
                                description=(
                                    f"Outlier IQR : {val} "
                                    f"hors [{round(lower_bound, 2)}, "
                                    f"{round(upper_bound, 2)}]"
                                ),
                            )
                        )
                except (ValueError, TypeError):
                    continue

        except Exception as e:
            logger.warning(
                "Impossible de détecter outliers pour %s : %s",
                col_name,
                str(e),
            )

    return anomalies


def _detect_type_errors(
    df: pl.DataFrame,
    column_profiles: dict[str, ColumnProfile],
) -> list[AnomalyDetail]:
    """
    Détecte les valeurs dont le type est incohérent avec la colonne.

    EXEMPLE TYPIQUE :
        colonne "prime_annuelle" est majoritairement numérique
        mais contient "2025-01-01" à la ligne 10
        → Erreur de type

    LOGIQUE :
        Si une colonne est détectée comme "float" ou "int"
        mais certaines valeurs ne peuvent pas être castées
        → Ce sont des erreurs de type.

    Args:
        df:              DataFrame à analyser
        column_profiles: Pour connaître le type dominant par colonne

    Returns:
        Liste d'AnomalyDetail, une par erreur de type.
    """
    anomalies = []

    for col_name, profile in column_profiles.items():
        # Uniquement vérifier les colonnes dont on a détecté
        # un type numérique (les strings acceptent tout)
        if profile.type_detecte not in ("float", "int"):
            continue

        for idx in range(df.height):
            val = df[col_name][idx]
            if val is None:
                continue

            # Tenter de convertir en float
            if not _is_float(str(val)):
                anomalies.append(
                    AnomalyDetail(
                        ligne=idx + 1,
                        colonne=col_name,
                        valeur=val,
                        type_anomalie="type_error",
                        description=(
                            f"Valeur '{val}' non numérique "
                            f"dans colonne de type {profile.type_detecte}"
                        ),
                    )
                )

    return anomalies


def _detect_inconsistencies(df: pl.DataFrame) -> list[AnomalyDetail]:
    """
    Détecte les incohérences entre paires de colonnes.

    EXEMPLE :
        Si le dataset a "date_debut" et "date_fin",
        on vérifie que date_debut < date_fin.

    LOGIQUE :
        Rechercher des paires de colonnes qui suivent des
        conventions de nommage cohérentes :
            *_start / *_end
            *_debut / *_fin
            *_from  / *_to
            date_effet / date_echeance
        Puis vérifier la cohérence sur chaque ligne.

    Args:
        df: DataFrame à analyser

    Returns:
        Liste d'AnomalyDetail pour les incohérences détectées.
    """
    anomalies = []
    columns   = df.columns

    # Paires de conventions de nommage à vérifier
    date_pair_patterns = [
        ("date_debut", "date_fin"),
        ("date_effet", "date_echeance"),
        ("date_start", "date_end"),
        ("start_date", "end_date"),
        ("date_from",  "date_to"),
        ("valid_from", "valid_to"),
    ]

    for col_start, col_end in date_pair_patterns:
        # Vérifier si les 2 colonnes existent dans le dataset
        if col_start not in columns or col_end not in columns:
            continue

        logger.debug(
            "Vérification cohérence temporelle : %s < %s",
            col_start,
            col_end,
        )

        for idx in range(df.height):
            val_start = df[col_start][idx]
            val_end   = df[col_end][idx]

            if val_start is None or val_end is None:
                continue

            # Comparer comme strings (format YYYY-MM-DD est comparable)
            if str(val_start) >= str(val_end):
                anomalies.append(
                    AnomalyDetail(
                        ligne=idx + 1,
                        colonne=f"{col_start} / {col_end}",
                        valeur=f"{val_start} >= {val_end}",
                        type_anomalie="inconsistency",
                        description=(
                            f"Incohérence temporelle : "
                            f"{col_start}={val_start} "
                            f">= {col_end}={val_end}"
                        ),
                    )
                )

    return anomalies


# ── Helpers ──────────────────────────────────────────────────────────────────


def _is_int(value: str) -> bool:
    """Vérifie si une string représente un entier valide."""
    try:
        int(value)
        return True
    except (ValueError, TypeError):
        return False


def _is_float(value: str) -> bool:
    """Vérifie si une string représente un float valide."""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def _is_date_string(value: str) -> bool:
    """
    Vérifie si une string ressemble à une date.

    Teste les formats les plus courants.
    N'utilise pas strptime pour rester léger.
    """
    date_patterns = [
        r"^\d{4}-\d{2}-\d{2}$",           # 2024-01-15
        r"^\d{2}/\d{2}/\d{4}$",           # 15/01/2024
        r"^\d{2}-\d{2}-\d{4}$",           # 15-01-2024
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", # 2024-01-15T10:30
    ]
    return any(re.match(p, value) for p in date_patterns)


def _count_outliers_iqr(numeric: pl.Series) -> int:
    """
    Compte les outliers IQR dans une série numérique.

    Utilisé par _enrich_numeric_profile pour remplir
    le champ outlier_count du ColumnProfile.

    Args:
        numeric: Série Polars de type numérique, sans nulls

    Returns:
        Nombre d'outliers détectés.
    """
    settings = get_settings()

    if numeric.len() < 4:
        return 0

    q1  = float(numeric.quantile(0.25))
    q3  = float(numeric.quantile(0.75))
    iqr = q3 - q1

    if iqr == 0:
        return 0

    lower = q1 - settings.iqr_multiplier * iqr
    upper = q3 + settings.iqr_multiplier * iqr

    return int(((numeric < lower) | (numeric > upper)).sum())