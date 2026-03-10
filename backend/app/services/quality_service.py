"""
QualityService — analyse la qualité d'un dataset et applique des corrections.
Travaille sur les données déjà profilées en base (DatasetColumn).
"""

from typing import Any


class QualityService:

    def analyze(self, columns: list[dict]) -> dict[str, Any]:
        """
        Génère un rapport qualité complet à partir des colonnes profilées.
        Retourne un dict stocké en JSONB dans Dataset.quality_report.
        """
        issues = []
        column_scores = []

        for col in columns:
            col_issues = []
            null_pct = col.get("null_percent") or 0.0
            unique_count = col.get("unique_count") or 0

            # ── Valeurs manquantes ──────────────────────────────────────
            if null_pct > 50:
                col_issues.append({
                    "type":     "high_missing",
                    "severity": "critical",
                    "message":  f"{null_pct:.1f}% de valeurs manquantes",
                    "fix":      "drop_column",
                })
            elif null_pct > 20:
                col_issues.append({
                    "type":     "medium_missing",
                    "severity": "warning",
                    "message":  f"{null_pct:.1f}% de valeurs manquantes",
                    "fix":      "impute_mean" if col.get("detected_type") in ("integer", "float") else "impute_mode",
                })
            elif null_pct > 0:
                col_issues.append({
                    "type":     "low_missing",
                    "severity": "info",
                    "message":  f"{null_pct:.1f}% de valeurs manquantes",
                    "fix":      "impute_mean" if col.get("detected_type") in ("integer", "float") else "impute_mode",
                })

            # ── Colonne constante (unique_count == 1) ──────────────────
            if unique_count == 1:
                col_issues.append({
                    "type":     "constant_column",
                    "severity": "warning",
                    "message":  "Colonne constante — aucune variance",
                    "fix":      "drop_column",
                })

            # ── Score par colonne ──────────────────────────────────────
            completeness = 1 - (null_pct / 100)
            col_score = round(completeness * 100, 2)
            column_scores.append(col_score)

            if col_issues:
                issues.append({
                    "column":  col["original_name"],
                    "issues":  col_issues,
                    "score":   col_score,
                })

        # ── Score global ───────────────────────────────────────────────
        global_score = round(sum(column_scores) / len(column_scores), 2) if column_scores else 0.0

        # ── Résumé ─────────────────────────────────────────────────────
        critical_count = sum(
            1 for col in issues
            for issue in col["issues"]
            if issue["severity"] == "critical"
        )
        warning_count = sum(
            1 for col in issues
            for issue in col["issues"]
            if issue["severity"] == "warning"
        )

        return {
            "global_score":    global_score,
            "total_columns":   len(columns),
            "columns_ok":      len(columns) - len(issues),
            "columns_issues":  len(issues),
            "critical_count":  critical_count,
            "warning_count":   warning_count,
            "issues":          issues,
            "corrections_available": [
                issue["fix"]
                for col in issues
                for issue in col["issues"]
            ],
        }

    def apply_corrections(self, columns: list[dict], corrections: list[str]) -> dict[str, Any]:
        """
        Simule l'application des corrections demandées.
        Retourne un résumé des corrections appliquées.
        En production, ce travail est délégué au Resp. Data.
        """
        applied = []
        skipped = []

        allowed = {"impute_mean", "impute_mode", "drop_column", "drop_duplicates", "normalize"}

        for correction in corrections:
            if correction in allowed:
                applied.append(correction)
            else:
                skipped.append(correction)

        return {
            "applied":  applied,
            "skipped":  skipped,
            "message":  f"{len(applied)} correction(s) appliquée(s), {len(skipped)} ignorée(s).",
            "note":     "Le fichier corrigé sera généré par le Resp. Data via /api/internal/data/*",
        }