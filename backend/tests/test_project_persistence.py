import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.project import Project, ProjectStatus


FAKE_PAYLOAD = {
    "sub": "keycloak-persistence-user",
    "email": "persist@dxc.com",
    "given_name": "Persist",
    "family_name": "Tester",
    "company": "DXC",
}


@pytest.mark.asyncio
async def test_conversation_and_dashboard_persisted_in_postgres(
    client: AsyncClient,
    db_session,
):
    headers = {"Authorization": "Bearer fake-token"}

    with patch(
        "app.core.keycloak.verify_token",
        new_callable=AsyncMock,
        return_value=FAKE_PAYLOAD,
    ):
        create_res = await client.post(
            "/api/projects",
            json={
                "name": "Persistence Project",
                "use_case": "Analyse churn",
                "visual_preferences": {
                    "darkMode": True,
                    "density": "expert",
                },
            },
            headers=headers,
        )

        assert create_res.status_code == 201, create_res.text
        project_id = create_res.json()["id"]

        conversation_payload = {
            "updatedAt": "2026-03-18T10:00:00Z",
            "messages": [
                {
                    "id": "u-1",
                    "role": "user",
                    "content": "Genere un dashboard",
                    "timestamp": "2026-03-18T09:59:00Z",
                },
                {
                    "id": "s-1",
                    "role": "system",
                    "content": "Dashboard genere",
                    "kpis": [{"name": "Revenue", "value": 1200, "unit": "EUR"}],
                    "charts": [{"type": "bar", "title": "Revenue", "data": [], "dataKeys": ["value"]}],
                    "predictions": [],
                    "timestamp": "2026-03-18T10:00:00Z",
                },
            ],
        }

        conv_res = await client.put(
            f"/api/projects/{project_id}/conversation",
            json=conversation_payload,
            headers=headers,
        )
        assert conv_res.status_code == 200, conv_res.text
        assert conv_res.json()["messages"][1]["kpis"][0]["name"] == "Revenue"

        dashboard_payload = {
            "generated": True,
            "hasCharts": True,
            "hasPredictions": False,
            "generatedAt": "2026-03-18T10:00:00Z",
            "title": "Churn Dashboard",
            "kpis": [{"name": "Revenue", "value": 1200, "unit": "EUR"}],
            "charts": [{"type": "bar", "title": "Revenue", "data": [], "dataKeys": ["value"]}],
            "predictions": [],
        }

        dash_res = await client.put(
            f"/api/projects/{project_id}/dashboard",
            json=dashboard_payload,
            headers=headers,
        )
        assert dash_res.status_code == 200, dash_res.text
        assert dash_res.json()["generated"] is True

        project_res = await client.get(f"/api/projects/{project_id}", headers=headers)
        assert project_res.status_code == 200, project_res.text
        visual_preferences = project_res.json()["visual_preferences"]
        parsed = json.loads(visual_preferences)

        assert parsed["conversation"]["messages"][1]["kpis"][0]["name"] == "Revenue"
        assert parsed["dashboard"]["title"] == "Churn Dashboard"
        assert parsed["dashboardGenerated"] is True

        db_project = (
            await db_session.execute(select(Project).where(Project.id == uuid.UUID(project_id)))
        ).scalar_one()
        db_parsed = json.loads(db_project.visual_preferences)

        assert db_parsed["conversation"]["updatedAt"] == "2026-03-18T10:00:00Z"
        assert db_parsed["dashboard"]["generated"] is True
        assert db_project.status == ProjectStatus.READY
