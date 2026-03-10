from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AnomalyDetail:
    """
    Détail d'une anomalie détectée sur une ligne précise.

    Exemple :
        AnomalyDetail(
            ligne=7,
            colonne="contrat_id",
            valeur=None,
            type_anomalie="null",
            description="Valeur nulle sur colonne obligatoire"
        )
    """

    # Numéro de ligne dans le dataset (1-indexed pour l'user)
    ligne: int

    # Colonne concernée
    colonne: str

    # Valeur problématique (None si null)
    valeur: Optional[object]

    # Type d'anomalie détectée
    # "null", "duplicate", "outlier", "type_error", "inconsistency"
    type_anomalie: str

    # Description lisible par l'user et le LLM
    description: str


@dataclass
class ColumnProfile:
    """
    Profil statistique d'une colonne du dataset.

    Contient tout ce que le LLM a besoin de savoir
    sur une colonne pour proposer une stratégie de nettoyage.
    """

    # Nom de la colonne
    nom: str

    # Type Python détecté (pas encore le type metadata)
    # "string", "float", "int", "date_string", "mixed"
    type_detecte: str

    # Statistiques de base
    null_count:   int
    null_pct:     float
    unique_count: int
    total_count:  int

    # Exemples de valeurs (3 premiers non-nulls)
    sample_values: list

    # Statistiques numériques (None si colonne non numérique)
    min:    Optional[float] = None
    max:    Optional[float] = None
    mean:   Optional[float] = None
    median: Optional[float] = None
    std:    Optional[float] = None

    # Nombre de valeurs négatives (utile pour détecter erreurs)
    negative_count: Optional[int] = None

    # Nombre d'outliers détectés par la méthode IQR
    outlier_count: Optional[int] = None

    # Pour les colonnes texte : pattern détecté automatiquement
    # Ex: "CTR-[0-9]{6}" si toutes les valeurs suivent ce format
    pattern_detecte: Optional[str] = None

    # Nombre de doublons dans cette colonne spécifiquement
    duplicate_count: int = 0


@dataclass
class ProfilingReport:
    """
    Rapport complet de profiling du dataset.

    Produit par data_profiler.py après avoir scanné le dataset.
    Consommé par strategy_node pour alimenter le LLM.

    CONTIENT :
        - Stats globales du dataset
        - Profil de chaque colonne
        - Liste détaillée de toutes les anomalies (avec lignes)
        - Résumé textuel prêt à être injecté dans le prompt LLM
    """

    # Stats globales
    total_rows:       int
    total_columns:    int
    total_nulls:      int
    null_pct:         float
    total_duplicates: int
    duplicate_pct:    float

    # Profil par colonne
    # Clé = nom de colonne, valeur = ColumnProfile
    columns: dict[str, ColumnProfile] = field(default_factory=dict)

    # Toutes les anomalies détectées, ligne par ligne
    anomalies: list[AnomalyDetail] = field(default_factory=list)

    @property
    def anomalies_by_type(self) -> dict[str, list[AnomalyDetail]]:
        """
        Regroupe les anomalies par type.

        Utile pour afficher :
            "Nulls (3) : lignes 7, 12, 15"
            "Doublons (1) : lignes 2 et 6"

        Returns:
            Dict avec type_anomalie comme clé
            et liste d'AnomalyDetail comme valeur.
        """
        result: dict[str, list[AnomalyDetail]] = {}

        for anomaly in self.anomalies:
            if anomaly.type_anomalie not in result:
                result[anomaly.type_anomalie] = []
            result[anomaly.type_anomalie].append(anomaly)

        return result

    @property
    def total_anomalies(self) -> int:
        """Nombre total d'anomalies toutes catégories confondues."""
        return len(self.anomalies)

    def build_llm_summary(self) -> str:
        """
        Construit un résumé textuel structuré pour le LLM.

        Ce texte est injecté directement dans le prompt LLM.
        Il doit être :
            - Concis (éviter de gaspiller des tokens)
            - Précis (lignes exactes, valeurs exactes)
            - Structuré (le LLM parse plus facilement)

        Returns:
            Résumé textuel des anomalies détectées.
        """
        lines = [
            f"Dataset : {self.total_rows} lignes, "
            f"{self.total_columns} colonnes.",

            f"Anomalies totales : {self.total_anomalies} "
            f"sur {self.total_rows * self.total_columns} cellules "
            f"({round(self.total_anomalies / max(1, self.total_rows * self.total_columns) * 100, 1)}%).",
        ]

        # Détailler par type d'anomalie
        by_type = self.anomalies_by_type

        if "null" in by_type:
            null_details = ", ".join(
                f"ligne {a.ligne} col {a.colonne}"
                for a in by_type["null"]
            )
            lines.append(f"Nulls ({len(by_type['null'])}) : {null_details}.")

        if "duplicate" in by_type:
            dup_details = ", ".join(
                f"ligne {a.ligne}"
                for a in by_type["duplicate"]
            )
            lines.append(
                f"Doublons ({len(by_type['duplicate'])}) : {dup_details}."
            )

        if "outlier" in by_type:
            out_details = ", ".join(
                f"ligne {a.ligne} ({a.colonne}={a.valeur})"
                for a in by_type["outlier"]
            )
            lines.append(
                f"Outliers ({len(by_type['outlier'])}) : {out_details}."
            )

        if "type_error" in by_type:
            type_details = ", ".join(
                f"ligne {a.ligne} ({a.colonne}='{a.valeur}')"
                for a in by_type["type_error"]
            )
            lines.append(
                f"Erreurs type ({len(by_type['type_error'])}) : "
                f"{type_details}."
            )

        if "inconsistency" in by_type:
            inc_details = ", ".join(
                f"ligne {a.ligne} ({a.description})"
                for a in by_type["inconsistency"]
            )
            lines.append(
                f"Incohérences ({len(by_type['inconsistency'])}) : "
                f"{inc_details}."
            )

        return " ".join(lines)

    def to_dict(self) -> dict:
        """Sérialise le rapport pour l'API JSON."""
        return {
            "global": {
                "total_rows":       self.total_rows,
                "total_columns":    self.total_columns,
                "total_nulls":      self.total_nulls,
                "null_pct":         self.null_pct,
                "total_duplicates": self.total_duplicates,
                "duplicate_pct":    self.duplicate_pct,
                "total_anomalies":  self.total_anomalies,
            },
            "columns": {
                name: {
                    "type_detecte":   col.type_detecte,
                    "null_count":     col.null_count,
                    "null_pct":       col.null_pct,
                    "unique_count":   col.unique_count,
                    "sample_values":  [str(v) for v in col.sample_values],
                    "min":            col.min,
                    "max":            col.max,
                    "mean":           col.mean,
                    "median":         col.median,
                    "outlier_count":  col.outlier_count,
                    "pattern_detecte":col.pattern_detecte,
                }
                for name, col in self.columns.items()
            },
            "anomalies": [
                {
                    "ligne":         a.ligne,
                    "colonne":       a.colonne,
                    "valeur":        str(a.valeur) if a.valeur else None,
                    "type_anomalie": a.type_anomalie,
                    "description":   a.description,
                }
                for a in self.anomalies
            ],
            "llm_summary": self.build_llm_summary(),
        }