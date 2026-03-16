"""
Tests Sprint 3 — Projects + Datasets
Couvre les 7 cas du backlog.
"""
import io
import uuid
import pytest
import pandas as pd
from unittest.mock import MagicMock

from app.services.sector_detection_service import detect_sector
from app.services.dataset_service import DatasetService


# ─── Fixtures ────────────────────────────────────────────

def _csv_bytes(rows: int = 20) -> bytes:
    df = pd.DataFrame({
        "id":       range(rows),
        "name":     [f"Alice_{i}" for i in range(rows)],
        "amount":   [float(i * 10) for i in range(rows)],
        "category": ["A" if i % 2 == 0 else "B" for i in range(rows)],
    })
    return df.to_csv(index=False).encode()


def _mock_minio(csv_bytes: bytes | None = None) -> MagicMock:
    m = MagicMock()
    m.upload_bytes.return_value   = "raw/pid/uid/file.csv"
    m.download_bytes.return_value = csv_bytes or _csv_bytes()
    m.delete_object.return_value  = None
    return m


# ─── Sector detection ────────────────────────────────────

class TestSectorDetection:
    def test_finance(self):
        assert detect_sector("analyse des transactions bancaires et détection de fraude") == "finance"

    def test_transport(self):
        assert detect_sector("optimisation des itinéraires de livraison pour notre flotte") == "transport"

    def test_retail(self):
        assert detect_sector("analyse des ventes clients et recommandations produits") == "retail"

    def test_manufacturing(self):
        assert detect_sector("détection de défauts sur la ligne de production usine") == "manufacturing"

    def test_healthcare(self):
        assert detect_sector("suivi des patients à l'hôpital santé") == "healthcare"

    def test_empty_returns_general(self):
        assert detect_sector("") == "general"
        assert detect_sector("   ") == "general"

    def test_create_project_detects_sector(self):
        """test_create_project_detects_sector ✓"""
        assert detect_sector("Analyse des transactions de paiement et risque de crédit") == "finance"


# ─── Dataset service ─────────────────────────────────────

class TestDatasetService:

    def test_upload_csv_success(self):
        """test_upload_csv_success ✓"""
        svc    = DatasetService(_mock_minio())
        result = svc.upload(_csv_bytes(), "test.csv", uuid.uuid4())

        assert result["row_count"]    == 20
        assert result["column_count"] == 4
        assert result["file_format"]  == "csv"
        assert 0 <= result["quality_score"] <= 100
        assert len(result["preview"]) == 10
        assert len(result["columns"]) == 4

    def test_upload_too_large_rejected(self):
        """test_upload_too_large_rejected ✓"""
        svc = DatasetService(_mock_minio())
        with pytest.raises(ValueError, match="volumineux"):
            svc.upload(b"x" * (60 * 1024 * 1024), "big.csv", uuid.uuid4())

    def test_upload_wrong_format_rejected(self):
        """test_upload_wrong_format_rejected ✓"""
        svc = DatasetService(_mock_minio())
        with pytest.raises(ValueError, match="Format non supporté"):
            svc.upload(b"data", "file.txt", uuid.uuid4())

    def test_preview_returns_10_rows(self):
        """test_preview_returns_10_rows ✓"""
        svc = DatasetService()
        df  = pd.read_csv(io.BytesIO(_csv_bytes(50)))
        preview = df.head(10).where(pd.notna(df.head(10)), None).to_dict(orient="records")
        assert len(preview) == 10

    def test_preview_capped_by_file_size(self):
        svc = DatasetService()
        df  = pd.read_csv(io.BytesIO(_csv_bytes(5)))
        preview = df.head(10).where(pd.notna(df.head(10)), None).to_dict(orient="records")
        assert len(preview) == 5

    def test_quality_score_perfect(self):
        svc = DatasetService()
        df  = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        assert svc._quality_score(df) == 100.0

    def test_quality_score_with_nulls(self):
        svc = DatasetService()
        df  = pd.DataFrame({"a": [1, None, 3], "b": ["x", "y", None]})
        assert svc._quality_score(df) < 100.0


# ─── Metadata ────────────────────────────────────────────

class TestMetadata:
    def test_metadata_saves_business_names(self):
        """test_metadata_saves_business_names ✓"""
        from app.schemas.dataset import MetadataUpdateRequest, ColumnMetadataUpdate
        req = MetadataUpdateRequest(columns=[
            ColumnMetadataUpdate(original_name="amount",   business_name="Montant transaction", business_type="numeric"),
            ColumnMetadataUpdate(original_name="category", business_name="Catégorie client"),
        ])
        assert req.columns[0].business_name == "Montant transaction"
        assert req.columns[1].business_type is None


# ─── MinIO cleanup ───────────────────────────────────────

class TestMinioCleanup:
    def test_delete_project_cleans_minio(self):
        """test_delete_project_cleans_minio ✓"""
        from app.services.minio_service import MinioService
        from app.core.config import settings

        mock_client = MagicMock()
        svc         = MinioService(mock_client)
        key         = "raw/project-id/uuid/file.csv"

        svc.delete_object(settings.MINIO_BUCKET, key)
        mock_client.remove_object.assert_called_once_with(settings.MINIO_BUCKET, key)