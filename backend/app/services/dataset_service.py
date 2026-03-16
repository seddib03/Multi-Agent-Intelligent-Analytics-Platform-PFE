from __future__ import annotations

import io
import os
import time
from datetime import datetime
from typing import Any

import pandas as pd


class DatasetService:
    """Compatibility dataset service used by dataset router."""

    def __init__(self, minio_service: Any | None = None):
        self.minio_service = minio_service

    def upload(self, file_bytes: bytes, filename: str | None, project_id: str) -> dict[str, Any]:
        """Persist the uploaded bytes to a temporary directory and profile the dataset.

        Result dictionary includes `file_path` instead of a MinIO key.
        """
        from app.core.config import settings

        safe_filename = filename or "upload.csv"
        file_format = os.path.splitext(safe_filename)[1].lower().lstrip(".") or "csv"

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise ValueError(
                f"Fichier trop volumineux (max {settings.MAX_UPLOAD_SIZE_MB} MB)"
            )

        # profile using pandas as before
        df = self._read_dataframe(file_bytes, file_format)

        # ensure project-specific subdirectory exists
        dest_dir = os.path.join(settings.TEMP_UPLOAD_DIR, str(project_id))
        os.makedirs(dest_dir, exist_ok=True)
        timestamp = int(time.time())
        local_path = os.path.join(dest_dir, f"{timestamp}_{safe_filename}")

        # write raw bytes to disk
        with open(local_path, "wb") as f:
            f.write(file_bytes)

        columns = [self._column_profile(df, col, idx) for idx, col in enumerate(df.columns)]
        preview_df = df.head(10).where(pd.notna(df.head(10)), None)

        return {
            "file_path": local_path,
            "file_format": file_format,
            "file_size_bytes": len(file_bytes),
            "row_count": int(len(df.index)),
            "column_count": int(len(df.columns)),
            "quality_score": float(self._quality_score(df)),
            "preview": preview_df.to_dict(orient="records"),
            "columns": columns,
        }

    def get_preview(self, file_path: str, file_format: str, n: int = 10) -> dict[str, Any]:
        """Read a local file and return a small preview."""
        with open(file_path, "rb") as f:
            data = f.read()

        df = self._read_dataframe(data, file_format)
        preview_df = df.head(n).where(pd.notna(df.head(n)), None)
        return {
            "rows": preview_df.to_dict(orient="records"),
            "total_rows": int(len(df.index)),
            "columns": [str(c) for c in df.columns],
        }

    def delete_file(self, file_path: str) -> None:
        try:
            os.remove(file_path)
        except FileNotFoundError:
            pass

    def _read_dataframe(self, raw: bytes, file_format: str) -> pd.DataFrame:
        fmt = (file_format or "").lower()
        if fmt == "csv":
            return pd.read_csv(io.BytesIO(raw))
        if fmt in {"xlsx", "xls"}:
            return pd.read_excel(io.BytesIO(raw))
        if fmt == "json":
            return pd.read_json(io.BytesIO(raw))
        raise ValueError(f"Format non supporté : {file_format}")

    def _column_profile(self, df: pd.DataFrame, col: Any, index: int) -> dict[str, Any]:
        series = df[col]
        dtype = str(series.dtype)
        detected_type = self._detected_type(dtype)
        null_percent = float(round(series.isna().mean() * 100, 2)) if len(series) else 0.0
        unique_count = int(series.nunique(dropna=True))
        sample_values = [str(v) for v in series.dropna().head(5).tolist()]
        extra_metadata = self._build_extra_metadata(series)

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
            "extra_metadata": extra_metadata or None,
            "column_order": index,
        }

    def _build_extra_metadata(self, series: pd.Series) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "nullable": bool(series.isna().any()),
        }

        clean = series.dropna()
        if clean.empty:
            return metadata

        if pd.api.types.is_numeric_dtype(series):
            metadata["min"] = float(clean.min())
            metadata["max"] = float(clean.max())

        enum_values = self._extract_enums(clean)
        if enum_values is not None:
            metadata["enums"] = enum_values

        date_format = self._infer_date_format(clean)
        if date_format is not None:
            metadata["dateFormat"] = date_format

        pattern = self._infer_pattern(clean)
        if pattern is not None:
            metadata["pattern"] = pattern

        return metadata

    def _extract_enums(self, series: pd.Series) -> list[str] | None:
        if pd.api.types.is_numeric_dtype(series):
            return None

        values = [str(value) for value in series.astype(str).drop_duplicates().tolist() if str(value).strip()]
        if not values:
            return None

        if len(values) <= 20:
            return values

        return None

    def _infer_date_format(self, series: pd.Series) -> str | None:
        sample_values = [str(value).strip() for value in series.astype(str).head(10).tolist() if str(value).strip()]
        if not sample_values:
            return None

        candidate_formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
        ]

        for date_format in candidate_formats:
            try:
                for value in sample_values:
                    datetime.strptime(value, date_format)
                return date_format
            except ValueError:
                continue

        return None

    def _infer_pattern(self, series: pd.Series) -> str | None:
        if pd.api.types.is_numeric_dtype(series):
            return None

        sample_values = [str(value).strip() for value in series.astype(str).head(5).tolist() if str(value).strip()]
        if len(sample_values) < 2:
            return None

        signatures = {self._value_signature(value) for value in sample_values}
        if len(signatures) != 1:
            return None

        signature = signatures.pop()
        if signature and any(char.isalpha() or char.isdigit() for char in signature):
            return signature

        return None

    def _value_signature(self, value: str) -> str:
        signature: list[str] = []
        for char in value:
            if char.isdigit():
                signature.append("9")
            elif char.isalpha() and char.isupper():
                signature.append("A")
            elif char.isalpha():
                signature.append("a")
            else:
                signature.append(char)
        return "".join(signature)

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
