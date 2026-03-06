"""
Tests Feature 3 — Infrastructure · Projects · Upload
──────────────────────────────────────────────────────
7 tests couvrant :
  □ test_create_project_detects_sector
  □ test_upload_csv_success
  □ test_upload_too_large_rejected
  □ test_upload_wrong_format_rejected
  □ test_preview_returns_10_rows
  □ test_metadata_saves_business_names
  □ test_delete_project_cleans_minio
"""

import io
import json
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import TEST_USER_ID, make_csv_bytes, make_large_file_bytes


# ══════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════

async def _create_project(client: AsyncClient, description: str = "Je veux prédire le churn client") -> dict:
    resp = await client.post("/api/projects", json={
        "name": "Projet test",
        "use_case_description": description,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _upload_csv(client: AsyncClient, project_id: str, content: bytes = None) -> dict:
    if content is None:
        content = make_csv_bytes()
    resp = await client.post(
        f"/api/projects/{project_id}/datasets/upload",
        files={"file": ("test_data.csv", io.BytesIO(content), "text/csv")},
    )
    return resp


# ══════════════════════════════════════════════════════════
# TEST 1 — Sector detection automatique
# ══════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_create_project_detects_sector(client: AsyncClient):
    """
    Un use case contenant 'churn client' doit être détecté comme secteur 'finance'.
    Un use case contenant 'retard ligne' doit être détecté comme 'transport'.
    """
    # Finance
    project = await _create_project(client, "Je veux identifier les clients qui risquent de churner")
    assert project["detected_sector"] == "finance", (
        f"Attendu 'finance', obtenu '{project['detected_sector']}'"
    )

    # Transport
    project2 = await _create_project(client, "Analyser les retards sur la ligne Paris-Lyon")
    assert project2["detected_sector"] == "transport"

    # Manufacturing
    project3 = await _create_project(client, "Prédire les pannes machine à partir des capteurs de vibration")
    assert project3["detected_sector"] == "manufacturing"


# ══════════════════════════════════════════════════════════
# TEST 2 — Upload CSV réussi
# ══════════════════════════════════════════════════════════
@pytest.mark.asyncio
@patch("app.services.dataset_service.upload_file")
@patch("app.services.dataset_service.download_file")
async def test_upload_csv_success(mock_download, mock_upload, client: AsyncClient):
    """
    L'upload d'un CSV valide doit :
    - Retourner status 201
    - row_count > 0
    - quality_score entre 0 et 100
    - preview avec des lignes
    - colonnes profilées
    """
    mock_upload.return_value = "fake/path/test_data.csv"

    csv_content = make_csv_bytes(
        "customer_id,age,churn,last_login,revenue\n"
        "1,34,0,2024-01-15,1200.5\n"
        "2,55,1,2023-11-03,800.0\n"
        "3,28,0,2024-02-20,2300.0\n"
        "4,41,0,2024-03-01,950.0\n"
    )

    project = await _create_project(client)
    resp = await _upload_csv(client, project["id"], csv_content)

    assert resp.status_code == 201, resp.text
    data = resp.json()

    dataset = data["dataset"]
    assert dataset["row_count"] == 4
    assert dataset["column_count"] == 5
    assert dataset["upload_status"] == "ready"
    assert 0 <= dataset["quality_score"] <= 100
    assert len(dataset["columns"]) == 5

    preview = data["preview"]
    assert len(preview) == 4  # 4 lignes (< 10)
    assert "customer_id" in preview[0]


# ══════════════════════════════════════════════════════════
# TEST 3 — Upload trop grand rejeté
# ══════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_upload_too_large_rejected(client: AsyncClient):
    """Un fichier > MAX_UPLOAD_SIZE_MB doit retourner HTTP 413."""
    from app.core.config import settings

    # Forcer la limite à 1 MB pour le test
    original = settings.MAX_UPLOAD_SIZE_MB
    settings.MAX_UPLOAD_SIZE_MB = 1

    try:
        project = await _create_project(client)
        large_content = make_large_file_bytes(2)  # 2 MB > 1 MB limit

        resp = await client.post(
            f"/api/projects/{project['id']}/datasets/upload",
            files={"file": ("huge.csv", io.BytesIO(large_content), "text/csv")},
        )
        assert resp.status_code == 413, f"Attendu 413, obtenu {resp.status_code}: {resp.text}"
        assert "volumineux" in resp.json()["detail"].lower() or "maximum" in resp.json()["detail"].lower()
    finally:
        settings.MAX_UPLOAD_SIZE_MB = original


# ══════════════════════════════════════════════════════════
# TEST 4 — Format non supporté rejeté
# ══════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_upload_wrong_format_rejected(client: AsyncClient):
    """Un fichier .pdf doit retourner HTTP 400."""
    project = await _create_project(client)

    resp = await client.post(
        f"/api/projects/{project['id']}/datasets/upload",
        files={"file": ("document.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf")},
    )
    assert resp.status_code == 400, f"Attendu 400, obtenu {resp.status_code}: {resp.text}"
    assert "supporté" in resp.json()["detail"].lower() or "format" in resp.json()["detail"].lower()


# ══════════════════════════════════════════════════════════
# TEST 5 — Preview retourne les bonnes lignes
# ══════════════════════════════════════════════════════════
@pytest.mark.asyncio
@patch("app.services.dataset_service.upload_file")
@patch("app.services.dataset_service.download_file")
async def test_preview_returns_10_rows(mock_download, mock_upload, client: AsyncClient):
    """
    GET /preview doit retourner exactement N lignes (défaut 10).
    Si le dataset a 15 lignes → preview = 10 lignes.
    """
    mock_upload.return_value = "fake/path/data.csv"

    # Générer un CSV avec 15 lignes
    rows = ["id,value,label"] + [f"{i},{i*10},{i%2}" for i in range(1, 16)]
    csv_15_rows = "\n".join(rows).encode("utf-8")

    # Le download_file doit retourner ce CSV pour le /preview
    mock_download.return_value = csv_15_rows

    project = await _create_project(client)
    upload_resp = await _upload_csv(client, project["id"], csv_15_rows)
    assert upload_resp.status_code == 201
    dataset_id = upload_resp.json()["dataset"]["id"]

    # GET preview (défaut = 10)
    preview_resp = await client.get(
        f"/api/projects/{project['id']}/datasets/{dataset_id}/preview"
    )
    assert preview_resp.status_code == 200, preview_resp.text
    data = preview_resp.json()

    assert data["total_rows"] == 15
    assert len(data["rows"]) == 10
    assert data["columns"] == ["id", "value", "label"]


# ══════════════════════════════════════════════════════════
# TEST 6 — Métadonnées sauvegardées correctement
# ══════════════════════════════════════════════════════════
@pytest.mark.asyncio
@patch("app.services.dataset_service.upload_file")
async def test_metadata_saves_business_names(mock_upload, client: AsyncClient):
    """
    PUT /metadata doit persister business_name et semantic_type
    qui sont ensuite visibles dans le détail du dataset.
    """
    mock_upload.return_value = "fake/path/data.csv"

    csv_content = make_csv_bytes("customer_id,age,churn\n1,34,0\n2,55,1\n")

    project = await _create_project(client)
    upload_resp = await _upload_csv(client, project["id"], csv_content)
    assert upload_resp.status_code == 201
    dataset_id = upload_resp.json()["dataset"]["id"]

    # Mettre à jour les métadonnées
    metadata_payload = {
        "columns": [
            {"original_name": "customer_id", "business_name": "ID Client", "semantic_type": "identifier"},
            {"original_name": "age", "business_name": "Âge du client", "semantic_type": "numeric"},
            {"original_name": "churn", "business_name": "Désabonnement", "semantic_type": "target"},
        ]
    }
    meta_resp = await client.put(
        f"/api/projects/{project['id']}/datasets/{dataset_id}/metadata",
        json=metadata_payload,
    )
    assert meta_resp.status_code == 200, meta_resp.text

    # Vérifier que les noms métier sont persistés
    dataset = meta_resp.json()
    cols_map = {c["original_name"]: c for c in dataset["columns"]}

    assert cols_map["customer_id"]["business_name"] == "ID Client"
    assert cols_map["customer_id"]["semantic_type"] == "identifier"
    assert cols_map["age"]["business_name"] == "Âge du client"
    assert cols_map["churn"]["semantic_type"] == "target"


# ══════════════════════════════════════════════════════════
# TEST 7 — Suppression projet nettoie MinIO
# ══════════════════════════════════════════════════════════
@pytest.mark.asyncio
@patch("app.services.dataset_service.upload_file")
@patch("app.services.project_service.delete_folder")
async def test_delete_project_cleans_minio(mock_delete_folder, mock_upload, client: AsyncClient):
    """
    DELETE /projects/:id doit :
    - Retourner HTTP 204
    - Appeler delete_folder avec le prefix du projet
    - Rendre le projet introuvable (404) après suppression
    """
    mock_upload.return_value = "fake/path/data.csv"

    project = await _create_project(client)
    project_id = project["id"]

    # Uploader un dataset pour s'assurer qu'il y a quelque chose à nettoyer
    csv_content = make_csv_bytes()
    await _upload_csv(client, project_id, csv_content)

    # Supprimer le projet
    del_resp = await client.delete(f"/api/projects/{project_id}")
    assert del_resp.status_code == 204, del_resp.text

    # Vérifier que delete_folder a été appelé avec le bon prefix
    mock_delete_folder.assert_called_once_with(prefix=f"{project_id}/")

    # Vérifier que le projet n'existe plus
    get_resp = await client.get(f"/api/projects/{project_id}")
    assert get_resp.status_code == 404