import pandas as pd

from app.schemas.dataset import ColumnMetadataUpdate
from app.services.dataset_service import DatasetService


def test_column_metadata_update_accepts_extra_fields_and_aliases():
    update = ColumnMetadataUpdate.model_validate({
        "originalName": "customer_code",
        "businessName": "Code client",
        "semanticType": "identifier",
        "description": "Identifiant métier du client",
        "pattern": "AA-999",
        "nullable": False,
        "min": 1,
        "max": 999,
        "enums": ["AA-001", "BB-002"],
        "dateFormat": "%Y-%m-%d",
        "custom_rule": "must_be_unique",
    })

    assert update.original_name == "customer_code"
    assert update.business_name == "Code client"
    assert update.business_type == "identifier"
    assert update.description == "Identifiant métier du client"
    assert update.to_extra_metadata_patch() == {
        "pattern": "AA-999",
        "nullable": False,
        "min": 1,
        "max": 999,
        "enums": ["AA-001", "BB-002"],
        "dateFormat": "%Y-%m-%d",
        "custom_rule": "must_be_unique",
    }


def test_dataset_service_profiles_extra_metadata():
    dataframe = pd.DataFrame(
        {
            "amount": [10.5, 20.0, None],
            "status": ["new", "closed", "new"],
            "ordered_at": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "customer_code": ["AB-001", "CD-002", "EF-003"],
        }
    )

    service = DatasetService()

    amount_profile = service._column_profile(dataframe, "amount", 0)
    status_profile = service._column_profile(dataframe, "status", 1)
    ordered_at_profile = service._column_profile(dataframe, "ordered_at", 2)
    customer_code_profile = service._column_profile(dataframe, "customer_code", 3)

    assert amount_profile["extra_metadata"]["nullable"] is True
    assert amount_profile["extra_metadata"]["min"] == 10.5
    assert amount_profile["extra_metadata"]["max"] == 20.0
    assert status_profile["extra_metadata"]["enums"] == ["new", "closed"]
    assert ordered_at_profile["extra_metadata"]["dateFormat"] == "%Y-%m-%d"
    assert customer_code_profile["extra_metadata"]["pattern"] == "AA-999"