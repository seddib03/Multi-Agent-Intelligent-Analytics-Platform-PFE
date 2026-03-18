import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.services.sector_detection_service import detect_sector

router = APIRouter(tags=["Projects"])


async def _get_project_or_404(
    db: AsyncSession,
    project_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == owner_id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable")
    return project


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == current_user.id)
        .order_by(Project.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body:         ProjectCreate,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    project = Project(
        name=body.name,
        description=body.description,
        use_case=body.use_case,
        detected_sector=detect_sector(body.use_case or ""),
        visual_preferences=str(body.visual_preferences) if body.visual_preferences else None,
        business_rules=body.business_rules,
        owner_id=current_user.id,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id:   uuid.UUID,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    return await _get_project_or_404(db, project_id, current_user.id)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id:   uuid.UUID,
    body:         ProjectUpdate,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    project = await _get_project_or_404(db, project_id, current_user.id)

    if body.name               is not None: project.name               = body.name
    if body.description        is not None: project.description        = body.description
    if body.visual_preferences is not None: project.visual_preferences = str(body.visual_preferences)
    if body.business_rules     is not None: project.business_rules     = body.business_rules
    if body.status             is not None: project.status             = body.status
    if body.use_case           is not None:
        project.use_case        = body.use_case
        project.detected_sector = detect_sector(body.use_case)

    await db.flush()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id:   uuid.UUID,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    project = await _get_project_or_404(db, project_id, current_user.id)
    await db.delete(project)