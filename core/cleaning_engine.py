# core/cleaning_engine.py

# Standard library
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

# Third-party
import polars as pl


logger = logging.getLogger(__name__)


# ─── Constantes ──────────────────────────────────────────────────────────────

# Multiplicateur IQR pour détecter les outliers
# 1.5 = règle standard de Tukey
# Plus la valeur est grande, moins on est strict
IQR_MULTIPLIER = 1.5


# ─── Classe principale ───────────────────────────────────────────────────────


class CleaningEngine:
    """Moteur de nettoyage dynamique piloté par le action_plan.

    Applique les stratégies de nettoyage adaptées à chaque
    rôle de colonne défini dans le metadata.
    Toutes les opérations sont tracées dans le cleaning_log.

    Attributes:
        _df:           DataFrame en cours de nettoyage.
        _action_plan:  Plan d'action construit par metadata_parser.
        _cleaning_log: Liste des opérations effectuées.

    Example:
        >>> engine = CleaningEngine(raw_df, action_plan)
        >>> engine.run()
        >>> clean_df      = engine.clean_df
        >>> cleaning_log  = engine.cleaning_log
    """

    def __init__(
        self,
        df: pl.DataFrame,
        action_plan: dict,
    ) -> None:
        """Initialise le moteur avec le DataFrame et le plan d'action.

        Args:
            df:          DataFrame Polars brut chargé par ingestion_node.
            action_plan: Plan d'action construit par metadata_parser.
        """
        # On travaille sur une copie pour ne pas modifier l'original
        self._df           = df.clone()
        self._action_plan  = action_plan
        self._cleaning_log: list[dict] = []

    # ── Propriétés publiques ──────────────────────────────────────────

    @property
    def clean_df(self) -> pl.DataFrame:
        """Retourne le DataFrame nettoyé."""
        return self._df

    @property
    def cleaning_log(self) -> list[dict]:
        """Retourne le log complet des opérations effectuées."""
        return self._cleaning_log

    # ── Méthode publique principale ───────────────────────────────────

    def run(self) -> None:
        """Lance le pipeline de nettoyage complet.

        Ordre d'exécution important :
            1. Identifiers en premier — supprimer les doublons
               avant tout autre traitement
            2. Temporals — parser les dates avant les métriques
               car certaines métriques peuvent dépendre des dates
            3. Metrics — imputation après dédoublonnage
            4. Dimensions — nettoyage catégoriel en dernier

        Returns:
            None. Résultats accessibles via clean_df et cleaning_log.
        """
        rows_before = self._df.height
        logger.info(
            "Cleaning démarré — %d lignes | %d colonnes",
            rows_before,
            self._df.width,
        )

        # Ordre d'exécution fixe et intentionnel
        self._clean_identifiers()
        self._clean_temporals()
        self._clean_metrics()
        self._clean_dimensions()

        rows_after = self._df.height
        rows_dropped = rows_before - rows_after

        logger.info(
            "Cleaning terminé — %d lignes restantes "
            "(%d lignes supprimées | %d opérations loggées)",
            rows_after,
            rows_dropped,
            len(self._cleaning_log),
        )

    # ── Nettoyage par rôle ────────────────────────────────────────────

    def _clean_identifiers(self) -> None:
        """Nettoie les colonnes de rôle IDENTIFIER.

        Opérations appliquées :
            1. Supprimer les lignes où l'identifier est null
               Car une ligne sans identifiant est inutilisable
            2. Supprimer les doublons complets
               Garder la première occurrence

        Les colonnes identifier sont récupérées depuis
        action_plan["identifier_columns"].
        """
        identifier_columns = self._action_plan.get(
            "identifier_columns", []
        )

        if not identifier_columns:
            logger.warning("Aucune colonne identifier dans le action_plan")
            return

        for col_name in identifier_columns:

            # Vérifier que la colonne existe dans le DataFrame
            if col_name not in self._df.columns:
                continue

            # ── Opération 1 : drop rows où identifier est null ────────
            null_count = self._df[col_name].null_count()

            if null_count > 0:
                rows_before = self._df.height
                self._df = self._df.filter(
                    pl.col(col_name).is_not_null()
                )
                rows_after = self._df.height

                self._log_operation(
                    column=col_name,
                    role="identifier",
                    operation="drop_null_identifier",
                    rows_affected=rows_before - rows_after,
                    detail=f"{null_count} lignes supprimées car "
                           f"identifier null",
                )

        # ── Opération 2 : drop doublons complets ─────────────────────
        # Cherche les lignes 100% identiques sur toutes les colonnes
        rows_before    = self._df.height
        self._df       = self._df.unique(keep="first")
        duplicates_dropped = rows_before - self._df.height

        if duplicates_dropped > 0:
            self._log_operation(
                column="ALL",
                role="identifier",
                operation="drop_full_duplicates",
                rows_affected=duplicates_dropped,
                detail=f"{duplicates_dropped} lignes 100% identiques "
                       f"supprimées",
            )

    def _clean_temporals(self) -> None:
        """Nettoie les colonnes de rôle TEMPORAL.

        Opérations appliquées :
            1. Convertir en type Date Polars selon date_format
            2. Supprimer les lignes où la date est null
               (car temporal_key non nullable en général)
            3. Vérifier la cohérence si 2 colonnes temporelles
               existent (date_debut < date_fin)

        Les formats de date sont dans
        action_plan["columns_with_date_format"].
        """
        temporal_columns    = self._action_plan.get("temporal_columns", [])
        date_formats        = self._action_plan.get(
            "columns_with_date_format", {}
        )
        required_columns    = self._action_plan.get("required_columns", [])

        if not temporal_columns:
            return

        for col_name in temporal_columns:

            if col_name not in self._df.columns:
                continue

            # ── Opération 1 : parser la date ──────────────────────────
            date_format = date_formats.get(col_name, "%Y-%m-%d")

            try:
                self._df = self._df.with_columns(
                    pl.col(col_name)
                    .str.strptime(pl.Date, date_format, strict=False)
                    .alias(col_name)
                )
                self._log_operation(
                    column=col_name,
                    role="temporal_key",
                    operation="parse_date",
                    rows_affected=0,
                    detail=f"Date parsée avec format {date_format}",
                )
            except Exception as error:
                logger.warning(
                    "Impossible de parser la date '%s' : %s",
                    col_name, error,
                )

            # ── Opération 2 : drop null si required ───────────────────
            if col_name in required_columns:
                null_count = self._df[col_name].null_count()

                if null_count > 0:
                    rows_before = self._df.height
                    self._df    = self._df.filter(
                        pl.col(col_name).is_not_null()
                    )
                    self._log_operation(
                        column=col_name,
                        role="temporal_key",
                        operation="drop_null_date",
                        rows_affected=rows_before - self._df.height,
                        detail=f"{null_count} lignes supprimées "
                               f"car date obligatoire manquante",
                    )

        # ── Opération 3 : cohérence temporelle ────────────────────────
        # Si 2 colonnes temporelles existent, vérifier l'ordre
        if len(temporal_columns) >= 2:
            self._check_temporal_consistency(temporal_columns)

    def _clean_metrics(self) -> None:
        """Nettoie les colonnes de rôle METRIC.

        Opérations appliquées :
            1. Convertir en type numérique Float64
            2. Imputer les valeurs nulles par la médiane
            3. Détecter et flagguer les outliers via IQR
               (on flaggue sans supprimer — décision conservatrice)

        Les plages valides sont dans
        action_plan["columns_with_range"].
        """
        metric_columns = self._action_plan.get("metric_columns", [])
        ranges         = self._action_plan.get("columns_with_range", {})

        if not metric_columns:
            return

        for col_name in metric_columns:

            if col_name not in self._df.columns:
                continue

            # ── Opération 1 : cast en Float64 ─────────────────────────
            # infer_schema_length=0 au chargement charge tout en String
            # On recast ici proprement
            try:
                self._df = self._df.with_columns(
                    pl.col(col_name)
                    .cast(pl.Float64, strict=False)
                    .alias(col_name)
                )
                self._log_operation(
                    column=col_name,
                    role="metric",
                    operation="cast_to_float",
                    rows_affected=0,
                    detail="Colonne castée en Float64",
                )
            except Exception as error:
                logger.warning(
                    "Cast Float64 échoué pour '%s' : %s",
                    col_name, error,
                )
                continue

            # ── Opération 2 : imputer les nulls par la médiane ────────
            null_count = self._df[col_name].null_count()

            if null_count > 0:
                median_value = self._df[col_name].median()

                if median_value is not None:
                    self._df = self._df.with_columns(
                        pl.col(col_name)
                        .fill_null(median_value)
                        .alias(col_name)
                    )
                    self._log_operation(
                        column=col_name,
                        role="metric",
                        operation="impute_median",
                        rows_affected=null_count,
                        detail=f"{null_count} nulls imputés "
                               f"par médiane = {median_value:.4f}",
                    )

            # ── Opération 3 : détecter outliers IQR ───────────────────
            outlier_count = self._detect_outliers_iqr(col_name)

            if outlier_count > 0:
                self._log_operation(
                    column=col_name,
                    role="metric",
                    operation="flag_outliers_iqr",
                    rows_affected=outlier_count,
                    detail=f"{outlier_count} outliers détectés "
                           f"(IQR x{IQR_MULTIPLIER}) — flaggués, "
                           f"non supprimés",
                )

            # ── Opération 4 : vérifier range du metadata ──────────────
            if col_name in ranges:
                self._check_range(col_name, ranges[col_name])

    def _clean_dimensions(self) -> None:
        """Nettoie les colonnes de rôle DIMENSION.

        Opérations appliquées :
            1. Convertir en String et trim les espaces
            2. Uniformiser la casse en uppercase
            3. Imputer les nulls par le mode (valeur la plus fréquente)
            4. Valider le pattern regex si défini dans le metadata

        Les patterns sont dans
        action_plan["columns_with_pattern"].
        """
        dimension_columns = self._action_plan.get("dimension_columns", [])
        patterns          = self._action_plan.get("columns_with_pattern", {})

        if not dimension_columns:
            return

        for col_name in dimension_columns:

            if col_name not in self._df.columns:
                continue

            # ── Opération 1 : cast String + trim ──────────────────────
            self._df = self._df.with_columns(
                pl.col(col_name)
                .cast(pl.Utf8, strict=False)
                .str.strip_chars()
                .alias(col_name)
            )
            self._log_operation(
                column=col_name,
                role="dimension",
                operation="cast_string_and_trim",
                rows_affected=0,
                detail="Cast String + suppression espaces superflus",
            )

            # ── Opération 2 : uppercase ───────────────────────────────
            self._df = self._df.with_columns(
                pl.col(col_name).str.to_uppercase().alias(col_name)
            )

            # ── Opération 3 : imputer nulls par mode ──────────────────
            null_count = self._df[col_name].null_count()

            if null_count > 0:
                mode_value = self._get_mode(col_name)

                if mode_value is not None:
                    self._df = self._df.with_columns(
                        pl.col(col_name)
                        .fill_null(mode_value)
                        .alias(col_name)
                    )
                    self._log_operation(
                        column=col_name,
                        role="dimension",
                        operation="impute_mode",
                        rows_affected=null_count,
                        detail=f"{null_count} nulls imputés "
                               f"par mode = '{mode_value}'",
                    )

            # ── Opération 4 : valider pattern si défini ───────────────
            if col_name in patterns:
                invalid_count = self._count_pattern_violations(
                    col_name, patterns[col_name]
                )
                if invalid_count > 0:
                    self._log_operation(
                        column=col_name,
                        role="dimension",
                        operation="pattern_violations_detected",
                        rows_affected=invalid_count,
                        detail=f"{invalid_count} valeurs ne respectent "
                               f"pas le pattern : {patterns[col_name]}",
                    )

    # ── Méthodes utilitaires privées ──────────────────────────────────

    def _detect_outliers_iqr(self, col_name: str) -> int:
        """Détecte les outliers d'une colonne numérique via la méthode IQR.

        Méthode de Tukey :
            Q1 = 25ème percentile
            Q3 = 75ème percentile
            IQR = Q3 - Q1
            Outlier si valeur < Q1 - 1.5*IQR
                       ou valeur > Q3 + 1.5*IQR

        Args:
            col_name: Nom de la colonne numérique.

        Returns:
            Nombre d'outliers détectés.
        """
        col_series = self._df[col_name].drop_nulls()

        if col_series.is_empty():
            return 0

        q1  = col_series.quantile(0.25)
        q3  = col_series.quantile(0.75)

        if q1 is None or q3 is None:
            return 0

        iqr         = q3 - q1
        lower_bound = q1 - IQR_MULTIPLIER * iqr
        upper_bound = q3 + IQR_MULTIPLIER * iqr

        outlier_mask = (
            (pl.col(col_name) < lower_bound)
            | (pl.col(col_name) > upper_bound)
        )
        return self._df.filter(outlier_mask).height

    def _check_range(
        self,
        col_name: str,
        range_config: dict,
    ) -> None:
        """Vérifie que les valeurs respectent le range du metadata.

        Loggue les violations sans supprimer les lignes.
        La suppression est une décision trop impactante
        pour être faite automatiquement.

        Args:
            col_name:     Nom de la colonne.
            range_config: Dict {"min": ..., "max": ...}.
        """
        min_val = range_config.get("min")
        max_val = range_config.get("max")

        violations = self._df.filter(
            (pl.col(col_name) < min_val)
            | (pl.col(col_name) > max_val)
        ).height

        if violations > 0:
            self._log_operation(
                column=col_name,
                role="metric",
                operation="range_violations_detected",
                rows_affected=violations,
                detail=f"{violations} valeurs hors range "
                       f"[{min_val}, {max_val}] — loggées, "
                       f"non supprimées",
            )

    def _check_temporal_consistency(
        self,
        temporal_columns: list[str],
    ) -> None:
        """Vérifie la cohérence entre 2 colonnes temporelles.

        Reprend la logique de ton data_prep_engine.py existant
        (datedeb / datefin) et la généralise pour n'importe
        quelles 2 colonnes temporelles.

        Convention : la première colonne = date début,
                     la deuxième colonne = date fin.

        Args:
            temporal_columns: Liste des colonnes temporelles.
        """
        if len(temporal_columns) < 2:
            return

        col_start = temporal_columns[0]
        col_end   = temporal_columns[1]

        # Vérifier que les 2 colonnes existent
        if col_start not in self._df.columns:
            return
        if col_end not in self._df.columns:
            return

        # Compter les incohérences : date_debut >= date_fin
        incoherent_mask = pl.col(col_start) >= pl.col(col_end)
        incoherent_count = self._df.filter(incoherent_mask).height

        if incoherent_count > 0:
            # Corriger en inversant les dates — même logique
            # que ton data_prep_engine.py existant
            self._df = self._df.with_columns([
                pl.when(incoherent_mask)
                  .then(pl.col(col_end))
                  .otherwise(pl.col(col_start))
                  .alias(col_start),

                pl.when(incoherent_mask)
                  .then(pl.col(col_start))
                  .otherwise(pl.col(col_end))
                  .alias(col_end),
            ])

            self._log_operation(
                column=f"{col_start} / {col_end}",
                role="temporal_key",
                operation="fix_temporal_consistency",
                rows_affected=incoherent_count,
                detail=f"{incoherent_count} lignes corrigées : "
                       f"{col_start} et {col_end} inversées",
            )

    def _get_mode(self, col_name: str) -> Optional[str]:
        """Retourne la valeur la plus fréquente d'une colonne.

        Args:
            col_name: Nom de la colonne.

        Returns:
            Valeur modale sous forme de string, None si vide.
        """
        non_null = self._df[col_name].drop_nulls()

        if non_null.is_empty():
            return None

        # value_counts() retourne un DataFrame avec
        # les colonnes [col_name, "count"]
        # sort + head(1) donne la valeur la plus fréquente
        mode_df = (
            non_null
            .value_counts()
            .sort("count", descending=True)
            .head(1)
        )

        return str(mode_df[col_name][0])

    def _count_pattern_violations(
        self,
        col_name: str,
        pattern: str,
    ) -> int:
        """Compte les valeurs ne respectant pas un pattern regex.

        Args:
            col_name: Nom de la colonne.
            pattern:  Expression régulière à valider.

        Returns:
            Nombre de valeurs invalides.
        """
        try:
            invalid_mask = ~pl.col(col_name).str.contains(pattern)
            return self._df.filter(invalid_mask).height
        except Exception as error:
            logger.warning(
                "Validation pattern échouée pour '%s' : %s",
                col_name, error,
            )
            return 0

    def _log_operation(
        self,
        column: str,
        role: str,
        operation: str,
        rows_affected: int,
        detail: str,
    ) -> None:
        """Enregistre une opération de nettoyage dans le log.

        Chaque entrée du log documente précisément ce qui a
        été fait, sur quelle colonne, et combien de lignes
        ont été affectées.

        Args:
            column:        Nom de la colonne concernée.
            role:          Rôle de la colonne (metric, dimension...).
            operation:     Code de l'opération effectuée.
            rows_affected: Nombre de lignes modifiées.
            detail:        Description lisible de l'opération.
        """
        entry = {
            "timestamp":     datetime.now().isoformat(),
            "column":        column,
            "role":          role,
            "operation":     operation,
            "rows_affected": rows_affected,
            "detail":        detail,
        }
        self._cleaning_log.append(entry)
        logger.info(
            "Cleaning op — [%s] %s : %s (%d lignes)",
            role, column, operation, rows_affected,
        )

