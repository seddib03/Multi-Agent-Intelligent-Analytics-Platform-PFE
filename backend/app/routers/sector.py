from fastapi import APIRouter
from pydantic import BaseModel
from app.services.sector_detection_service import detect_sector_full

router = APIRouter(tags=["Sector Detection"])


class DetectSectorRequest(BaseModel):
    user_query: str


@router.post("/detect-sector")
async def detect_sector_endpoint(body: DetectSectorRequest):
    """
    Détecte le secteur métier à partir d'une description textuelle.
    Correspond à l'interface DetectSectorResponse du frontend.
    """
    return detect_sector_full(body.user_query)