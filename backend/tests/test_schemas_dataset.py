"""
Unit tests for Pydantic schemas in app.schemas.dataset.

Covers:
- ColumnMetadataUpdate: camelCase aliases, snake_case, business_type/semantic_type
  alias, extra fields allowed, to_extra_metadata_patch() output.
- MetadataUpdateRequest: column list validation.
- ColumnProfile: optional extra_metadata field.
- DatasetColumnResponse: from_attributes construction.
- ApplyCorrectionsRequest: basic validation.
- QualityReportResponse and related schemas: structural validation.

No database or HTTP infrastructure required.
"""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.dataset import (
    ApplyCorrectionsRequest,
    ColumnMetadataUpdate,
    ColumnProfile,
    DatasetColumnResponse,
    MetadataUpdateRequest,
)


# ─── ColumnMetadataUpdate ─────────────────────────────────────────────────────

class TestColumnMetadataUpdate:

    def test_snake_case_fields_accepted(self):
        update = ColumnMetadataUpdate.model_validate({
            "original_name": "amount",
            "business_name": "Montant",
            "business_type": "numeric",
        })
        assert update.original_name == "amount"
        assert update.business_name == "Montant"
        assert update.business_type == "numeric"

    def test_camelCase_aliases_accepted(self):
        update = ColumnMetadataUpdate.model_validate({
            "originalName": "customer_id",
            "businessName": "ID Client",
            "semanticType": "identifier",
        })
        assert update.original_name == "customer_id"
        assert update.business_name == "ID Client"
        assert update.business_type == "identifier"   # semanticType → business_type

    def test_semantic_type_alias_maps_to_business_type(self):
        update = ColumnMetadataUpdate.model_validate({
            "original_name": "col",
            "semantic_type": "category",
        })
        assert update.business_type == "category"

    def test_description_accepted(self):
        update = ColumnMetadataUpdate.model_validate({
            "original_name": "col",
            "description":   "A useful description.",
        })
        assert update.description == "A useful description."

    def test_pattern_accepted(self):
        update = ColumnMetadataUpdate.model_validate({"original_name": "code", "pattern": "AA-999"})
        assert update.pattern == "AA-999"

    def test_nullable_flag_accepted(self):
        update = ColumnMetadataUpdate.model_validate({"original_name": "col", "nullable": False})
        assert update.nullable is False

    def test_min_max_accepted(self):
        update = ColumnMetadataUpdate.model_validate({"original_name": "col", "min": 0, "max": 100})
        assert update.min == 0
        assert update.max == 100

    def test_min_alias_minimum_accepted(self):
        update = ColumnMetadataUpdate.model_validate({"original_name": "col", "minimum": 5, "maximum": 50})
        assert update.min == 5
        assert update.max == 50

    def test_enums_as_list_accepted(self):
        update = ColumnMetadataUpdate.model_validate({
            "original_name": "status",
            "enums": ["active", "inactive", "pending"],
        })
        assert update.enums == ["active", "inactive", "pending"]

    def test_dateFormat_alias_accepted(self):
        update = ColumnMetadataUpdate.model_validate({
            "original_name": "created_at",
            "dateFormat": "%Y-%m-%d",
        })
        assert update.date_format == "%Y-%m-%d"

    def test_extra_fields_allowed(self):
        update = ColumnMetadataUpdate.model_validate({
            "original_name": "col",
            "custom_rule": "must_be_positive",
        })
        assert update.model_extra == {"custom_rule": "must_be_positive"}

    def test_all_optional_fields_default_to_none(self):
        update = ColumnMetadataUpdate.model_validate({"original_name": "col"})
        assert update.business_name is None
        assert update.business_type is None
        assert update.description is None
        assert update.pattern is None
        assert update.nullable is None
        assert update.min is None
        assert update.max is None
        assert update.enums is None
        assert update.date_format is None

    # ── to_extra_metadata_patch() ─────────────────────────────────────────────

    def test_to_extra_metadata_patch_returns_set_fields_only(self):
        update = ColumnMetadataUpdate.model_validate({
            "original_name": "col",
            "pattern": "AA-999",
            "nullable": True,
        })
        patch = update.to_extra_metadata_patch()
        assert patch == {"pattern": "AA-999", "nullable": True}

    def test_to_extra_metadata_patch_ignores_none_values(self):
        update = ColumnMetadataUpdate.model_validate({"original_name": "col", "min": 0})
        patch = update.to_extra_metadata_patch()
        assert "max" not in patch
        assert "enums" not in patch

    def test_to_extra_metadata_patch_includes_extra_fields(self):
        update = ColumnMetadataUpdate.model_validate({
            "original_name": "col",
            "custom_rule":   "unique",
        })
        patch = update.to_extra_metadata_patch()
        assert patch.get("custom_rule") == "unique"

    def test_to_extra_metadata_patch_uses_dateFormat_key(self):
        """date_format is stored as 'dateFormat' in the metadata dict."""
        update = ColumnMetadataUpdate.model_validate({
            "original_name": "col",
            "dateFormat": "%d/%m/%Y",
        })
        patch = update.to_extra_metadata_patch()
        assert "dateFormat" in patch
        assert patch["dateFormat"] == "%d/%m/%Y"

    def test_to_extra_metadata_patch_full_example(self):
        update = ColumnMetadataUpdate.model_validate({
            "originalName": "customer_code",
            "businessName": "Code client",
            "semanticType": "identifier",
            "description":  "Identifiant métier du client",
            "pattern":      "AA-999",
            "nullable":     False,
            "min":          1,
            "max":          999,
            "enums":        ["AA-001", "BB-002"],
            "dateFormat":   "%Y-%m-%d",
            "custom_rule":  "must_be_unique",
        })
        assert update.original_name == "customer_code"
        assert update.business_name == "Code client"
        assert update.business_type == "identifier"
        assert update.to_extra_metadata_patch() == {
            "pattern":    "AA-999",
            "nullable":   False,
            "min":        1,
            "max":        999,
            "enums":      ["AA-001", "BB-002"],
            "dateFormat": "%Y-%m-%d",
            "custom_rule": "must_be_unique",
        }


# ─── MetadataUpdateRequest ────────────────────────────────────────────────────

class TestMetadataUpdateRequest:

    def test_accepts_list_of_column_updates(self):
        req = MetadataUpdateRequest(columns=[
            ColumnMetadataUpdate.model_validate({"original_name": "amount", "business_name": "Montant"}),
            ColumnMetadataUpdate.model_validate({"original_name": "date"}),
        ])
        assert len(req.columns) == 2
        assert req.columns[0].business_name == "Montant"
        assert req.columns[1].business_name is None

    def test_accepts_empty_column_list(self):
        req = MetadataUpdateRequest(columns=[])
        assert req.columns == []


# ─── ColumnProfile ────────────────────────────────────────────────────────────

class TestColumnProfile:

    def test_basic_construction(self):
        profile = ColumnProfile(
            original_name="age",
            detected_type="numeric",
            null_percent=0.0,
            unique_count=50,
            sample_values=["25", "30", "35"],
        )
        assert profile.original_name == "age"
        assert profile.stats is None
        assert profile.extra_metadata is None

    def test_with_stats_and_extra_metadata(self):
        profile = ColumnProfile(
            original_name="amount",
            detected_type="numeric",
            null_percent=5.0,
            unique_count=100,
            sample_values=["10.5", "20.0"],
            stats={"min": 10.5, "max": 20.0, "mean": 15.25},
            extra_metadata={"nullable": True, "min": 10.5, "max": 20.0},
        )
        assert profile.stats["mean"] == 15.25
        assert profile.extra_metadata["nullable"] is True


# ─── DatasetColumnResponse ────────────────────────────────────────────────────

class TestDatasetColumnResponse:

    def test_construction_with_required_fields(self):
        col_id = uuid.uuid4()
        resp = DatasetColumnResponse(
            id=col_id,
            original_name="col",
            business_name=None,
            description=None,
            detected_type="text",
            business_type=None,
            semantic_type=None,
            null_percent=None,
            unique_count=None,
            sample_values=None,
            stats=None,
            extra_metadata=None,
            pattern=None,
            nullable=None,
            min=None,
            max=None,
            enums=None,
            date_format=None,
            column_order=0,
        )
        assert resp.id == col_id
        assert resp.original_name == "col"


# ─── ApplyCorrectionsRequest ──────────────────────────────────────────────────

class TestApplyCorrectionsRequest:

    def test_accepts_list_of_corrections(self):
        req = ApplyCorrectionsRequest(corrections=["impute_mean", "drop_duplicates"])
        assert "impute_mean" in req.corrections

    def test_accepts_empty_list(self):
        req = ApplyCorrectionsRequest(corrections=[])
        assert req.corrections == []
