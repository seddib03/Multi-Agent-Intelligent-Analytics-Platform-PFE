from __future__ import annotations

import io
import os
import time
from typing import Any

import pandas as pd
from minio.error import S3Error

from app.core.minio import BUCKET, minio_client


class DatasetService:
    """Compatibility dataset service used by dataset router."""

    def __init__(self, minio_service: Any | None = None):
        self.minio_service = minio_service

    def upload(self, file_bytes: bytes, filename: str | None, project_id: str) -> dict[str, Any]:
        safe_filename = filename or "upload.csv"
        file_format = os.path.splitext(safe_filename)[1].lower().lstrip(".") or "csv"

        df = self._read_dataframe(file_bytes, file_format)

        object_key = f"{project_id}/raw/{int(time.time())}_{safe_filename}"
        minio_client.put_object(
            bucket_name=BUCKET,
            object_name=object_key,
            data=io.BytesIO(file_bytes),
            length=len(file_bytes),
            content_type=self._content_type(file_format),
        )

        columns = [self._column_profile(df, col, idx) for idx, col in enumerate(df.columns)]
        preview_df = df.head(10).where(pd.notna(df.head(10)), None)

        return {
            "minio_key": object_key,
            "file_format": file_format,
            "file_size_bytes": len(file_bytes),
            "row_count": int(len(df.index)),
            "column_count": int(len(df.columns)),
            "quality_score": float(self._quality_score(df)),
            "preview": preview_df.to_dict(orient="records"),
            "columns": columns,
        }

    def get_preview_from_minio(self, minio_key: str, file_format: str, n: int = 10) -> dict[str, Any]:
        response = minio_client.get_object(BUCKET, minio_key)
        try:
            data = response.read()
        finally:
            response.close()
            response.release_conn()

        df = self._read_dataframe(data, file_format)
        preview_df = df.head(n).where(pd.notna(df.head(n)), None)
        return {
            "rows": preview_df.to_dict(orient="records"),
            "total_rows": int(len(df.index)),
            "columns": [str(c) for c in df.columns],
        }

    def delete_file(self, minio_key: str) -> None:
        try:
            minio_client.remove_object(BUCKET, minio_key)
        except S3Error as exc:
            if exc.code != "NoSuchKey":
                raise

    def _read_dataframe(self, raw: bytes, file_format: str) -> pd.DataFrame:
        fmt = (file_format or "").lower()
        if fmt == "csv":
            return pd.read_csv(io.BytesIO(raw))
        if fmt in {"xlsx", "xls"}:
            return pd.read_excel(io.BytesIO(raw))
        if fmt == "json":
            return pd.read_json(io.BytesIO(raw))
        raise ValueError(f"Unsupported file format: {file_format}")

    def _column_profile(self, df: pd.DataFrame, col: Any, index: int) -> dict[str, Any]:
        series = df[col]
        dtype = str(series.dtype)
        detected_type = self._detected_type(dtype)
        null_percent = float(round(series.isna().mean() * 100, 2)) if len(series) else 0.0
        unique_count = int(series.nunique(dropna=True))
        sample_values = [str(v) for v in series.dropna().head(5).tolist()]

        stats: dict[str, Any] | None = None
        if pd.api.types.is_numeric_dtype(series):
            clean = series.dropna()
            if not clean.empty:
                stats = {
                    "min": float(clean.min()),
                    "max": float(clean.max()),
                    "mean": float(clean.mean()),
                }

        return {
            "original_name": str(col),
            "detected_type": detected_type,
            "null_percent": null_percent,
            "unique_count": unique_count,
            "sample_values": sample_values,
            "stats": stats,
            "column_order": index,
        }

    def _quality_score(self, df: pd.DataFrame) -> float:
        if df.empty:
            return 0.0
        completeness = 1.0 - float(df.isna().sum().sum()) / float(df.size)
        return round(max(0.0, min(100.0, completeness * 100.0)), 1)

    def _detected_type(self, dtype: str) -> str:
        if "int" in dtype or "float" in dtype:
            return "numeric"
        if "datetime" in dtype or "date" in dtype:
            return "datetime"
        if "bool" in dtype:
            return "boolean"
        return "text"

    def _content_type(self, file_format: str) -> str:
        if file_format == "csv":
            return "text/csv"
        if file_format in {"xlsx", "xls"}:
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if file_format == "json":
            return "application/json"
        return "application/octet-stream"
