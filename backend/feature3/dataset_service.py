"""
Dataset Service
───────────────
Gère l'upload, le profiling et la qualité des datasets.

Pipeline d'upload :
  1. Valider format (CSV/XLSX/JSON) + taille (≤ 100 MB)
  2. Parser avec pandas
  3. Uploader fichier brut sur MinIO
  4. Profiler chaque colonne (types, null%, unique, samples)
  5. Calculer quality_score
  6. Persister Dataset + DatasetColumn en base
  7. Retourner Dataset + preview
"""

from __future__ import annotations

import io
import json
from typing import Any

import pandas as pd
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.minio import delete_file, download_file, upload_file
from app.models.dataset import Dataset, DatasetColumn
from app.schemas.dataset import (
    ColumnMetadataUpdate,
    DatasetMetadataUpdate,
    PreviewResponse,
    QualityDetail,
    QualityResponse,
)

# ─── Constantes ───────────────────────────────────────────
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json"}
ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/json",
    "text/plain",        # certains CSV sont envoyés en text/plain
    "application/octet-stream",  # fallback générique
}
PREVIEW_ROWS = 10


# ─── Upload ───────────────────────────────────────────────
async def upload(
    db: AsyncSession,
    project_id: str,
    file: UploadFile,
) -> tuple[Dataset, list[dict]]:
    """
    Orchestre tout le pipeline d'upload.
    Retourne (Dataset, preview_rows).
    """
    # 1. Valider format
    _validate_file(file)

    # 2. Lire les bytes en mémoire
    raw_bytes = await file.read()

    # 3. Valider taille
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Fichier trop volumineux ({len(raw_bytes) // 1_000_000} MB). "
                   f"Maximum : {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    # 4. Parser avec pandas
    df = _parse_file(raw_bytes, file.filename or "upload")

    # 5. Créer le Dataset en base (status=processing)
    import uuid
    dataset_id = str(uuid.uuid4())
    object_name = f"{project_id}/{dataset_id}/{file.filename}"

    dataset = Dataset(
        id=dataset_id,
        project_id=project_id,
        file_name=file.filename or "upload",
        file_path=object_name,
        file_size_bytes=len(raw_bytes),
        row_count=len(df),
        column_count=len(df.columns),
        upload_status="processing",
    )
    db.add(dataset)
    await db.flush()

    # 6. Uploader sur MinIO
    content_type = file.content_type or "application/octet-stream"
    upload_file(object_name, raw_bytes, content_type)

    # 7. Profiler les colonnes
    column_profiles = _profile_columns(df)
    for col_data in column_profiles:
        col = DatasetColumn(
            dataset_id=dataset_id,
            original_name=col_data["original_name"],
            business_name=col_data["original_name"],  # par défaut = nom original
            pandas_dtype=col_data["pandas_dtype"],
            semantic_type=col_data["semantic_type"],
            null_percent=col_data["null_percent"],
            unique_count=col_data["unique_count"],
            sample_values=json.dumps(col_data["sample_values"], ensure_ascii=False),
        )
        db.add(col)

    # 8. Calculer quality score
    score = _quality_score(df)
    dataset.quality_score = score
    dataset.upload_status = "ready"

    await db.flush()

    # 9. Preview (10 premières lignes)
    preview = _build_preview(df, PREVIEW_ROWS)

    return dataset, preview


# ─── Profile columns ──────────────────────────────────────
def _profile_columns(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Pour chaque colonne retourne :
    - original_name, pandas_dtype, semantic_type
    - null_percent, unique_count, sample_values (3 valeurs)
    """
    total_rows = len(df)
    profiles = []

    for col in df.columns:
        series = df[col]
        dtype_str = str(series.dtype)

        null_count = series.isna().sum()
        null_pct = round(null_count / total_rows * 100, 2) if total_rows > 0 else 0.0
        unique_count = series.nunique(dropna=True)

        # Inférer le type sémantique
        semantic = _infer_semantic_type(col, series, dtype_str)

        # 3 exemples non-null
        samples = (
            series.dropna()
            .head(3)
            .astype(str)
            .tolist()
        )

        profiles.append({
            "original_name": col,
            "pandas_dtype": dtype_str,
            "semantic_type": semantic,
            "null_percent": null_pct,
            "unique_count": int(unique_count),
            "sample_values": samples,
        })

    return profiles


def _infer_semantic_type(col_name: str, series: pd.Series, dtype: str) -> str:
    """Heuristique simple pour deviner le type sémantique."""
    col_lower = col_name.lower()

    # Identifiants
    if any(k in col_lower for k in ("_id", "id_", "uuid", "code", "ref")):
        return "identifier"

    # Dates
    if "date" in col_lower or "time" in col_lower or "at" in col_lower:
        return "datetime"
    if "datetime" in dtype or "date" in dtype:
        return "datetime"

    # Variable cible courante
    if col_lower in ("churn", "target", "label", "y", "cible", "class"):
        return "target"

    # Numériques
    if dtype in ("int64", "float64", "int32", "float32"):
        return "numeric"

    # Catégorielles
    if dtype in ("object", "category", "bool"):
        return "categorical"

    return "text"


# ─── Quality score ────────────────────────────────────────
def _quality_score(df: pd.DataFrame) -> float:
    """
    Score de qualité de 0 à 100.
    Pondération :
    - 70% complétude  : (1 - global_null_ratio)
    - 20% unicité     : ratio colonnes avec < 90% duplicatas
    - 10% cohérence   : ratio colonnes avec dtype homogène (non-object)
    """
    if df.empty:
        return 0.0

    total_cells = df.size
    null_cells = df.isna().sum().sum()
    completeness = 1 - (null_cells / total_cells) if total_cells > 0 else 0

    n_cols = len(df.columns)
    unique_cols = sum(
        1 for c in df.columns
        if df[c].nunique() / len(df) < 0.9  # moins de 90% de valeurs uniques = ok
    )
    uniqueness = unique_cols / n_cols if n_cols > 0 else 0

    non_object_cols = sum(1 for c in df.columns if str(df[c].dtype) != "object")
    consistency = non_object_cols / n_cols if n_cols > 0 else 0

    score = (completeness * 0.70 + uniqueness * 0.20 + consistency * 0.10) * 100
    return round(min(score, 100.0), 1)


# ─── Preview ──────────────────────────────────────────────
async def get_preview(
    db: AsyncSession,
    project_id: str,
    dataset_id: str,
    n_rows: int = PREVIEW_ROWS,
) -> PreviewResponse:
    dataset = await _get_dataset(db, dataset_id, project_id)

    raw = download_file(dataset.file_path)
    df = _parse_file(raw, dataset.file_name)

    return PreviewResponse(
        rows=_build_preview(df, n_rows),
        total_rows=len(df),
        columns=list(df.columns),
    )


def _build_preview(df: pd.DataFrame, n: int) -> list[dict]:
    """Convertit les N premières lignes en list[dict] JSON-safe."""
    preview_df = df.head(n).copy()
    # Convertir NaN → None, timestamps → string
    preview_df = preview_df.where(pd.notna(preview_df), None)
    for col in preview_df.select_dtypes(include=["datetime64", "datetimetz"]):
        preview_df[col] = preview_df[col].astype(str)
    return preview_df.to_dict(orient="records")


# ─── Column profile (endpoint détaillé) ───────────────────
async def get_column_profile(
    db: AsyncSession,
    project_id: str,
    dataset_id: str,
) -> QualityResponse:
    dataset = await _get_dataset(db, dataset_id, project_id)

    raw = download_file(dataset.file_path)
    df = _parse_file(raw, dataset.file_name)

    total_rows = len(df)
    missing_pct = round(df.isna().sum().sum() / df.size * 100, 2) if df.size else 0.0
    dup_rows = int(df.duplicated().sum())

    details: list[QualityDetail] = []
    recommendations: list[str] = []

    for col in df.columns:
        series = df[col]
        completeness = round((1 - series.isna().mean()) * 100, 2)
        unique_ratio = round(series.nunique() / total_rows, 4) if total_rows else 0

        if completeness < 60:
            status = "error"
            recommendations.append(
                f"'{col}' a {100 - completeness:.0f}% de valeurs manquantes → imputation ou exclusion recommandée"
            )
        elif completeness < 90:
            status = "warning"
            recommendations.append(
                f"'{col}' a {100 - completeness:.0f}% de valeurs manquantes → imputation par médiane/mode recommandée"
            )
        else:
            status = "ok"

        details.append(QualityDetail(
            column=col,
            completeness=completeness,
            unique_ratio=unique_ratio,
            status=status,
        ))

    score = dataset.quality_score or _quality_score(df)

    return QualityResponse(
        score=score,
        total_rows=total_rows,
        total_columns=len(df.columns),
        missing_percent=missing_pct,
        duplicate_rows=dup_rows,
        details=details,
        recommendations=recommendations,
    )


# ─── Metadata update ──────────────────────────────────────
async def update_metadata(
    db: AsyncSession,
    project_id: str,
    dataset_id: str,
    data: DatasetMetadataUpdate,
) -> Dataset:
    """Persiste les noms métier et types sémantiques définis par l'utilisateur."""
    dataset = await _get_dataset(db, dataset_id, project_id, with_columns=True)

    col_map = {c.original_name: c for c in dataset.columns}

    for update in data.columns:
        col = col_map.get(update.original_name)
        if col is None:
            continue
        if update.business_name is not None:
            col.business_name = update.business_name
        if update.semantic_type is not None:
            col.semantic_type = update.semantic_type
        if update.unit is not None:
            col.unit = update.unit

    await db.flush()
    return dataset


# ─── Delete ───────────────────────────────────────────────
async def delete(
    db: AsyncSession,
    project_id: str,
    dataset_id: str,
) -> None:
    dataset = await _get_dataset(db, dataset_id, project_id)

    # Supprimer le fichier sur MinIO
    try:
        delete_file(dataset.file_path)
    except Exception:
        pass

    await db.delete(dataset)
    await db.flush()


# ─── Helpers privés ───────────────────────────────────────
def _validate_file(file: UploadFile) -> None:
    import os
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nom de fichier manquant")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format non supporté : {ext}. Formats acceptés : {', '.join(ALLOWED_EXTENSIONS)}",
        )


def _parse_file(raw: bytes, filename: str) -> pd.DataFrame:
    """Parse CSV, Excel ou JSON depuis des bytes."""
    import os
    ext = os.path.splitext(filename)[1].lower()

    try:
        if ext == ".csv":
            # Essayer utf-8 puis latin-1 (fichiers FR)
            try:
                df = pd.read_csv(io.BytesIO(raw), encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(io.BytesIO(raw), encoding="latin-1")

        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(io.BytesIO(raw))

        elif ext == ".json":
            df = pd.read_json(io.BytesIO(raw))

        else:
            raise HTTPException(status_code=400, detail=f"Format non supporté : {ext}")

    except (ValueError, Exception) as e:
        raise HTTPException(
            status_code=422,
            detail=f"Impossible de lire le fichier : {str(e)}",
        )

    if df.empty:
        raise HTTPException(status_code=422, detail="Le fichier est vide")

    return df


async def _get_dataset(
    db: AsyncSession,
    dataset_id: str,
    project_id: str,
    with_columns: bool = False,
) -> Dataset:
    q = select(Dataset).where(
        Dataset.id == dataset_id,
        Dataset.project_id == project_id,
    )
    if with_columns:
        q = q.options(selectinload(Dataset.columns))

    result = await db.execute(q)
    dataset = result.scalar_one_or_none()

    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset introuvable")
    return dataset