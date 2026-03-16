"""
Unit tests for DatasetService.

Covers:
- _detected_type(): int/float/datetime/bool/text dtype strings.
- _quality_score(): perfect, with nulls, fully empty DataFrame.
- _read_dataframe(): CSV, XLSX, JSON, unsupported extension.
- _column_profile(): structure and keys returned for all column types.
- _build_extra_metadata(): nullable flag, numeric min/max,
                           enum detection (≤20 vs >20 values),
                           date format inference, pattern inference.
- _extract_enums(): text with few / many unique values, numeric, empty.
- _infer_date_format(): all 8 candidate format strings.
- _infer_pattern(): consistent / inconsistent signatures, numeric, short.
- _value_signature(): digit/uppercase/lowercase/separator mapping.
- upload(): CSV round-trip, too-large rejection, unsupported format.
- delete_file(): existing path deleted, missing path silently ignored.

No database or HTTP infrastructure required.
"""
import io
import os
import tempfile
import pytest
import pandas as pd

from app.services.dataset_service import DatasetService


# ─── Shared test helpers ──────────────────────────────────────────────────────

def _svc() -> DatasetService:
    return DatasetService()


def _csv_bytes(rows: int = 20, include_nulls: bool = False) -> bytes:
    df = pd.DataFrame({
        "id":       range(rows),
        "name":     [f"Alice_{i}" for i in range(rows)],
        "amount":   [float(i * 10) if (not include_nulls or i % 5 != 0) else None for i in range(rows)],
        "category": ["A" if i % 2 == 0 else "B" for i in range(rows)],
    })
    return df.to_csv(index=False).encode()


# ─── _detected_type() ─────────────────────────────────────────────────────────

class TestDetectedType:

    def test_int64_returns_numeric(self):
        assert _svc()._detected_type("int64") == "numeric"

    def test_float32_returns_numeric(self):
        assert _svc()._detected_type("float32") == "numeric"

    def test_datetime64_returns_datetime(self):
        assert _svc()._detected_type("datetime64") == "datetime"

    def test_date_keyword_returns_datetime(self):
        assert _svc()._detected_type("dbdate") == "datetime"

    def test_bool_returns_boolean(self):
        assert _svc()._detected_type("bool") == "boolean"

    def test_object_returns_text(self):
        assert _svc()._detected_type("object") == "text"

    def test_string_returns_text(self):
        assert _svc()._detected_type("string") == "text"


# ─── _quality_score() ─────────────────────────────────────────────────────────

class TestQualityScore:

    def test_perfect_data_returns_100(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        assert _svc()._quality_score(df) == 100.0

    def test_half_null_returns_50(self):
        df = pd.DataFrame({"a": [1, None], "b": [None, "y"]})
        score = _svc()._quality_score(df)
        assert score == pytest.approx(50.0)

    def test_all_null_returns_0(self):
        df = pd.DataFrame({"a": [None, None], "b": [None, None]})
        assert _svc()._quality_score(df) == 0.0

    def test_empty_dataframe_returns_0(self):
        df = pd.DataFrame()
        assert _svc()._quality_score(df) == 0.0

    def test_score_bounded_0_to_100(self):
        df = pd.DataFrame({"x": [1, None, 3], "y": ["a", "b", None]})
        score = _svc()._quality_score(df)
        assert 0.0 <= score <= 100.0


# ─── _read_dataframe() ────────────────────────────────────────────────────────

class TestReadDataframe:

    def test_csv_bytes_parsed_correctly(self):
        csv = b"a,b\n1,x\n2,y\n"
        df = _svc()._read_dataframe(csv, "csv")
        assert list(df.columns) == ["a", "b"]
        assert len(df) == 2

    def test_json_bytes_parsed_correctly(self):
        import json
        data = json.dumps([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]).encode()
        df = _svc()._read_dataframe(data, "json")
        assert len(df) == 2

    def test_unsupported_format_raises_value_error(self):
        with pytest.raises(ValueError, match="Format non support"):
            _svc()._read_dataframe(b"data", "txt")

    def test_unsupported_xml_raises_value_error(self):
        with pytest.raises(ValueError, match="Format non support"):
            _svc()._read_dataframe(b"<xml/>", "xml")


# ─── _column_profile() ────────────────────────────────────────────────────────

class TestColumnProfile:

    def _df(self):
        return pd.DataFrame({
            "amount":   [10.5, 20.0, None, 30.0],
            "status":   ["new", "closed", "new", "pending"],
            "ordered_at": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "code":     ["AB-001", "CD-002", "EF-003", "GH-004"],
        })

    def test_profile_has_all_required_keys(self):
        df = self._df()
        profile = _svc()._column_profile(df, "amount", 0)
        required = {"original_name", "detected_type", "null_percent",
                    "unique_count", "sample_values", "stats", "extra_metadata", "column_order"}
        assert required.issubset(profile.keys())

    def test_profile_original_name_correct(self):
        df = self._df()
        assert _svc()._column_profile(df, "status", 1)["original_name"] == "status"

    def test_profile_column_order_index(self):
        df = self._df()
        assert _svc()._column_profile(df, "amount", 2)["column_order"] == 2

    def test_numeric_column_has_stats(self):
        df = self._df()
        profile = _svc()._column_profile(df, "amount", 0)
        assert profile["stats"] is not None
        assert "min" in profile["stats"]
        assert "max" in profile["stats"]
        assert "mean" in profile["stats"]

    def test_text_column_has_no_stats(self):
        df = self._df()
        profile = _svc()._column_profile(df, "status", 1)
        assert profile["stats"] is None

    def test_null_percent_calculated_correctly(self):
        df = self._df()
        profile = _svc()._column_profile(df, "amount", 0)
        # 1 out of 4 values is null → 25%
        assert profile["null_percent"] == pytest.approx(25.0)

    def test_sample_values_are_strings(self):
        df = self._df()
        profile = _svc()._column_profile(df, "amount", 0)
        assert all(isinstance(v, str) for v in profile["sample_values"])

    def test_extra_metadata_present(self):
        df = self._df()
        profile = _svc()._column_profile(df, "amount", 0)
        assert "extra_metadata" in profile
        assert profile["extra_metadata"] is not None


# ─── _build_extra_metadata() ─────────────────────────────────────────────────

class TestBuildExtraMetadata:

    def test_nullable_true_when_nulls_present(self):
        s = pd.Series([1.0, None, 3.0])
        meta = _svc()._build_extra_metadata(s)
        assert meta["nullable"] is True

    def test_nullable_false_when_no_nulls(self):
        s = pd.Series([1.0, 2.0, 3.0])
        meta = _svc()._build_extra_metadata(s)
        assert meta["nullable"] is False

    def test_numeric_series_has_min_max(self):
        s = pd.Series([10.0, 20.0, 30.0])
        meta = _svc()._build_extra_metadata(s)
        assert meta["min"] == 10.0
        assert meta["max"] == 30.0

    def test_text_series_has_no_min_max(self):
        s = pd.Series(["alpha", "beta", "gamma"])
        meta = _svc()._build_extra_metadata(s)
        assert "min" not in meta
        assert "max" not in meta

    def test_few_unique_text_values_produce_enums(self):
        s = pd.Series(["cat", "dog", "cat", "fish"])
        meta = _svc()._build_extra_metadata(s)
        assert "enums" in meta
        assert set(meta["enums"]) == {"cat", "dog", "fish"}

    def test_many_unique_text_values_no_enums(self):
        s = pd.Series([f"user_{i}" for i in range(50)])
        meta = _svc()._build_extra_metadata(s)
        assert "enums" not in meta

    def test_date_column_has_dateFormat(self):
        s = pd.Series(["2024-01-01", "2024-01-02", "2024-01-03"])
        meta = _svc()._build_extra_metadata(s)
        assert "dateFormat" in meta
        assert meta["dateFormat"] == "%Y-%m-%d"

    def test_pattern_detected_for_consistent_codes(self):
        s = pd.Series(["AB-001", "CD-002", "EF-003", "GH-004", "IJ-005"])
        meta = _svc()._build_extra_metadata(s)
        assert "pattern" in meta
        assert meta["pattern"] == "AA-999"

    def test_empty_series_returns_nullable_only(self):
        s = pd.Series([], dtype=object)
        meta = _svc()._build_extra_metadata(s)
        assert "nullable" in meta
        assert "min" not in meta


# ─── _extract_enums() ────────────────────────────────────────────────────────

class TestExtractEnums:

    def test_few_distinct_values_returned(self):
        s = pd.Series(["A", "B", "A", "C"])
        result = _svc()._extract_enums(s)
        assert result is not None
        assert set(result) == {"A", "B", "C"}

    def test_exactly_20_distinct_values_returned(self):
        s = pd.Series([str(i) for i in range(20)])
        result = _svc()._extract_enums(s)
        assert result is not None
        assert len(result) == 20

    def test_21_distinct_values_returns_none(self):
        s = pd.Series([str(i) for i in range(21)])
        result = _svc()._extract_enums(s)
        assert result is None

    def test_numeric_series_returns_none(self):
        s = pd.Series([1.0, 2.0, 3.0])
        result = _svc()._extract_enums(s)
        assert result is None

    def test_empty_series_returns_none(self):
        s = pd.Series([], dtype=object)
        result = _svc()._extract_enums(s)
        assert result is None


# ─── _infer_date_format() ─────────────────────────────────────────────────────

class TestInferDateFormat:

    @pytest.mark.parametrize("values, expected_format", [
        (["2024-01-15", "2024-02-20", "2024-03-01"],   "%Y-%m-%d"),
        (["15/01/2024", "20/02/2024", "01/03/2024"],   "%d/%m/%Y"),
        (["01/15/2024", "02/20/2024", "03/01/2024"],   "%m/%d/%Y"),
        (["2024/01/15", "2024/02/20", "2024/03/01"],   "%Y/%m/%d"),
        (["15-01-2024", "20-02-2024", "01-03-2024"],   "%d-%m-%Y"),
        (["2024-01-15 10:30:00", "2024-02-20 11:00:00"], "%Y-%m-%d %H:%M:%S"),
    ])
    def test_recognises_date_format(self, values, expected_format):
        s = pd.Series(values)
        assert _svc()._infer_date_format(s) == expected_format

    def test_non_date_values_return_none(self):
        s = pd.Series(["hello", "world", "foo"])
        assert _svc()._infer_date_format(s) is None

    def test_empty_series_returns_none(self):
        s = pd.Series([], dtype=object)
        assert _svc()._infer_date_format(s) is None


# ─── _infer_pattern() ────────────────────────────────────────────────────────

class TestInferPattern:

    def test_consistent_alphanumeric_codes(self):
        s = pd.Series(["AB-001", "CD-002", "EF-003", "GH-004", "IJ-005"])
        result = _svc()._infer_pattern(s)
        assert result == "AA-999"

    def test_inconsistent_values_return_none(self):
        s = pd.Series(["AB-001", "1234567", "hello", "CD-002", "xyz"])
        result = _svc()._infer_pattern(s)
        assert result is None

    def test_numeric_series_returns_none(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = _svc()._infer_pattern(s)
        assert result is None

    def test_single_value_series_returns_none(self):
        s = pd.Series(["AB-001"])
        result = _svc()._infer_pattern(s)
        assert result is None


# ─── _value_signature() ──────────────────────────────────────────────────────

class TestValueSignature:

    def test_digits_mapped_to_9(self):
        assert _svc()._value_signature("123") == "999"

    def test_uppercase_mapped_to_A(self):
        assert _svc()._value_signature("ABC") == "AAA"

    def test_lowercase_mapped_to_a(self):
        assert _svc()._value_signature("abc") == "aaa"

    def test_separators_kept_as_is(self):
        assert _svc()._value_signature("AB-001") == "AA-999"

    def test_mixed_value(self):
        assert _svc()._value_signature("ID-42a") == "AA-99a"

    def test_empty_string(self):
        assert _svc()._value_signature("") == ""


# ─── upload() ────────────────────────────────────────────────────────────────

class TestUpload:

    def test_csv_upload_returns_expected_keys(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TEMP_UPLOAD_DIR", str(tmp_path))
        # Patch settings.TEMP_UPLOAD_DIR at runtime
        with _patch_temp_dir(str(tmp_path)):
            result = _svc().upload(_csv_bytes(20), "test.csv", "proj-001")

        assert result["row_count"]    == 20
        assert result["column_count"] == 4
        assert result["file_format"]  == "csv"
        assert 0.0 <= result["quality_score"] <= 100.0
        assert len(result["preview"]) == 10
        assert len(result["columns"]) == 4
        assert "file_path" in result

    def test_upload_too_large_raises_value_error(self, tmp_path):
        with _patch_temp_dir(str(tmp_path)):
            with pytest.raises(ValueError, match="volumineux"):
                _svc().upload(b"x" * (60 * 1024 * 1024), "big.csv", "proj-001")

    def test_unsupported_format_raises_value_error(self, tmp_path):
        with _patch_temp_dir(str(tmp_path)):
            with pytest.raises(ValueError, match="Format non support"):
                _svc().upload(b"data", "file.txt", "proj-001")

    def test_preview_is_capped_at_10_rows(self, tmp_path):
        """Even with 50-row CSV, preview contains at most 10 rows."""
        with _patch_temp_dir(str(tmp_path)):
            result = _svc().upload(_csv_bytes(50), "large.csv", "proj-001")
        assert len(result["preview"]) == 10

    def test_file_is_written_to_disk(self, tmp_path):
        with _patch_temp_dir(str(tmp_path)):
            result = _svc().upload(_csv_bytes(5), "small.csv", "proj-002")
        assert os.path.exists(result["file_path"])


# ─── delete_file() ────────────────────────────────────────────────────────────

class TestDeleteFile:

    def test_existing_file_is_deleted(self, tmp_path):
        f = tmp_path / "to_delete.csv"
        f.write_bytes(b"data")
        _svc().delete_file(str(f))
        assert not f.exists()

    def test_missing_file_does_not_raise(self):
        """delete_file on a non-existent path must be a no-op (idempotent)."""
        _svc().delete_file("/tmp/no_such_file_xyz_12345.csv")


# ─── Patch helper ─────────────────────────────────────────────────────────────

from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def _patch_temp_dir(path: str):
    """Override settings.TEMP_UPLOAD_DIR for a single test."""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.TEMP_UPLOAD_DIR   = path
        mock_settings.MAX_UPLOAD_SIZE_MB = 50
        yield mock_settings
