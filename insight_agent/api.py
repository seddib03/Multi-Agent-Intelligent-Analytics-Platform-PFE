from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from dashboard_generator import generate_dashboard_data

app = FastAPI(title="Insight Agent API")


class SectorContext(BaseModel):
    sector: str
    context: Optional[str] = None
    recommended_kpis: Optional[List[str]] = []
    recommended_charts: Optional[List[str]] = []
    dashboard_focus: Optional[str] = None


class DashboardRequest(BaseModel):
    sector_context: SectorContext
    dataset_path: str
    metadata_path: str
    user_query: Optional[str] = None


@app.get("/")
def root():
    return {"message": "Insight Agent API running"}


@app.post("/generate-dashboard")
def generate_dashboard(request: DashboardRequest):

    dashboard_data = generate_dashboard_data(
        config_path="dashboard_config.json",
        dataset_path=request.dataset_path
    )

    dashboard_mode = "specific" if request.user_query else "general"

    return {
        "status": "success",
        "agent": "insight_agent_pipeline",
        "dashboard_mode": dashboard_mode,
        "sector": request.sector_context.sector,
        "template": dashboard_data["template"],
        "title": request.sector_context.dashboard_focus,
        "kpis": dashboard_data["kpis"],
        "charts": dashboard_data["charts"],
        "insights": dashboard_data["insights"]
    }
    