import uuid
import json
import ast
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.project import Project, ProjectStatus
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ConversationPayload,
    DashboardInsightPayload,
)
from app.services.sector_detection_service import detect_sector

router = APIRouter(tags=["Projects"])


def _load_visual_preferences(project: Project) -> dict:
    if not project.visual_preferences:
        return {}
    try:
        parsed = json.loads(project.visual_preferences)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        # Legacy compatibility: old code stored Python dict repr instead of JSON.
        try:
            parsed = ast.literal_eval(project.visual_preferences)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, SyntaxError):
            return {}


def _store_visual_preferences(project: Project, prefs: dict) -> None:
    project.visual_preferences = json.dumps(prefs, ensure_ascii=False)


def _normalize_visual_preferences(project: Project) -> None:
    prefs = _load_visual_preferences(project)
    if prefs:
        _store_visual_preferences(project, prefs)


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
    projects = result.scalars().all()
    for project in projects:
        _normalize_visual_preferences(project)
    await db.flush()
    return projects


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
        visual_preferences=(
            json.dumps(body.visual_preferences, ensure_ascii=False)
            if body.visual_preferences
            else None
        ),
        business_rules=body.business_rules,
        owner_id=current_user.id,
    )
    db.add(project)
    await db.flush()
    _normalize_visual_preferences(project)
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id:   uuid.UUID,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    project = await _get_project_or_404(db, project_id, current_user.id)
    _normalize_visual_preferences(project)
    await db.flush()
    return project


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
    if body.visual_preferences is not None:
        project.visual_preferences = json.dumps(body.visual_preferences, ensure_ascii=False)
    if body.business_rules     is not None: project.business_rules     = body.business_rules
    if body.status             is not None: project.status             = body.status
    if body.use_case           is not None:
        project.use_case        = body.use_case
        if body.detected_sector is None:
            project.detected_sector = detect_sector(body.use_case)
    if body.detected_sector is not None:
        project.detected_sector = body.detected_sector

    await db.flush()
    _normalize_visual_preferences(project)
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


@router.get("/{project_id}/conversation", response_model=ConversationPayload)
async def get_project_conversation(
    project_id:   uuid.UUID,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    project = await _get_project_or_404(db, project_id, current_user.id)
    prefs = _load_visual_preferences(project)
    conversation = prefs.get("conversation")
    if isinstance(conversation, dict):
        return ConversationPayload(**conversation)
    return ConversationPayload()


@router.put("/{project_id}/conversation", response_model=ConversationPayload)
async def update_project_conversation(
    project_id:   uuid.UUID,
    body:         ConversationPayload,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    project = await _get_project_or_404(db, project_id, current_user.id)
    prefs = _load_visual_preferences(project)
    prefs["conversation"] = body.model_dump()
    _store_visual_preferences(project, prefs)
    await db.flush()
    return body


@router.get("/{project_id}/dashboard", response_model=DashboardInsightPayload)
async def get_project_dashboard(
    project_id:   uuid.UUID,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    project = await _get_project_or_404(db, project_id, current_user.id)
    prefs = _load_visual_preferences(project)
    dashboard = prefs.get("dashboard")
    if isinstance(dashboard, dict):
        return DashboardInsightPayload(**dashboard)
    return DashboardInsightPayload()


@router.put("/{project_id}/dashboard", response_model=DashboardInsightPayload)
async def update_project_dashboard(
    project_id:   uuid.UUID,
    body:         DashboardInsightPayload,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    project = await _get_project_or_404(db, project_id, current_user.id)
    prefs = _load_visual_preferences(project)

    payload = body.model_dump()
    prefs["dashboard"] = payload
    prefs["dashboardGenerated"] = body.generated
    _store_visual_preferences(project, prefs)

    if body.generated and project.status != ProjectStatus.READY:
        project.status = ProjectStatus.READY

    await db.flush()
    return body