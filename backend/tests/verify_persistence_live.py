import asyncio
import json
import uuid
import sys
from pathlib import Path
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.core.database import AsyncSessionLocal
from app.dependencies import get_current_user
from app.models.project import Project, ProjectStatus
from app.models.user import Company, User, UserPreferences


async def ensure_test_user() -> User:
    async with AsyncSessionLocal() as session:
        company = (await session.execute(select(Company).where(Company.name == "DXC Test Co"))).scalar_one_or_none()
        if not company:
            company = Company(id=uuid.uuid4(), name="DXC Test Co")
            session.add(company)
            await session.flush()

        user = (await session.execute(select(User).where(User.email == "persist.check@dxc.com"))).scalar_one_or_none()
        if not user:
            user = User(
                id=uuid.uuid4(),
                keycloak_id="persist-check-keycloak-id",
                email="persist.check@dxc.com",
                first_name="Persist",
                last_name="Check",
                company_id=company.id,
            )
            session.add(user)
            await session.flush()
            session.add(UserPreferences(id=uuid.uuid4(), user_id=user.id))

        await session.commit()
        await session.refresh(user)
        return user


async def main() -> None:
    user = await ensure_test_user()

    async def override_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            create_res = await client.post(
                "/api/projects",
                json={
                    "name": "Persistence Live Check",
                    "use_case": "Generate dashboard and keep chat",
                    "visual_preferences": {"darkMode": True, "density": "expert"},
                },
            )
            create_res.raise_for_status()
            project_id = create_res.json()["id"]

            conv_payload = {
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "messages": [
                    {
                        "id": "u-1",
                        "role": "user",
                        "content": "genere un dashboard",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    {
                        "id": "s-1",
                        "role": "system",
                        "content": "dashboard genere",
                        "kpis": [{"name": "Revenue", "value": 1000, "unit": "EUR"}],
                        "charts": [{"type": "bar", "title": "Revenue", "data": [], "dataKeys": ["value"]}],
                        "predictions": [],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                ],
            }

            put_conv = await client.put(f"/api/projects/{project_id}/conversation", json=conv_payload)
            put_conv.raise_for_status()

            dash_payload = {
                "generated": True,
                "hasCharts": True,
                "hasPredictions": False,
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "title": "Revenue Dashboard",
                "kpis": [{"name": "Revenue", "value": 1000, "unit": "EUR"}],
                "charts": [{"type": "bar", "title": "Revenue", "data": [], "dataKeys": ["value"]}],
                "predictions": [],
            }
            put_dash = await client.put(f"/api/projects/{project_id}/dashboard", json=dash_payload)
            put_dash.raise_for_status()

            get_proj = await client.get(f"/api/projects/{project_id}")
            get_proj.raise_for_status()
            visual_preferences_raw = get_proj.json().get("visual_preferences")
            parsed = json.loads(visual_preferences_raw) if visual_preferences_raw else {}

            print(f"PROJECT_ID={project_id}")
            print(f"HAS_CONVERSATION={isinstance(parsed.get('conversation'), dict)}")
            print(f"HAS_DASHBOARD={isinstance(parsed.get('dashboard'), dict)}")
            print(f"DASHBOARD_GENERATED={parsed.get('dashboardGenerated')}")

        async with AsyncSessionLocal() as session:
            project = (await session.execute(select(Project).where(Project.id == uuid.UUID(project_id)))).scalar_one()
            db_parsed = json.loads(project.visual_preferences)
            print(f"DB_MESSAGES={len(db_parsed.get('conversation', {}).get('messages', []))}")
            print(f"DB_DASHBOARD_TITLE={db_parsed.get('dashboard', {}).get('title')}")
            status_val = project.status.value if isinstance(project.status, ProjectStatus) else str(project.status)
            print(f"DB_STATUS={status_val}")

    finally:
        app.dependency_overrides.pop(get_current_user, None)


if __name__ == "__main__":
    asyncio.run(main())
