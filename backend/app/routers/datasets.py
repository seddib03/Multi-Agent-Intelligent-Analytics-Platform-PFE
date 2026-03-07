import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.config import settings
from app.dependencies import get_current_user, get_minio_service
from app.models.user import User
from app.models.project import Project
from app.models.dataset import Dataset, DatasetColumn
from app.schemas.dataset import (
    UploadResponse, DatasetPreviewResponse, DatasetProfileResponse,
    DatasetColumnResponse, MetadataUpdateRequest, DatasetResponse, ColumnProfile,
)
from app.services.dataset_service import DatasetService
from app.services.minio_service import MinioService

router = APIRouter(tags=["Datasets"])


# ─── Helpers ──────────────────────────────────────────────

async def _get_project_or_404(db: AsyncSession, project_id: uuid.UUID, company_id: str) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable")
    return project


async def _get_dataset_or_404(db: AsyncSession, dataset_id: uuid.UUID, project_id: uuid.UUID) -> Dataset:
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.project_id == project_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset introuvable")
    return ds


# ─── Routes ───────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    project_id:   uuid.UUID,
    file:         UploadFile    = File(...),
    db:           AsyncSession  = Depends(get_db),
    current_user: dict          = Depends(get_current_user),
    minio:        MinioService  = Depends(get_minio_service),
):
    project = await _get_project_or_404(db, project_id, current_user["company_id"])

    file_bytes = await file.read()

    if len(file_bytes) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Fichier trop volumineux (max {settings.MAX_UPLOAD_SIZE_MB} Mo)",
        )

    svc = DatasetService(minio)
    try:
        result = svc.upload(file_bytes, file.filename, project_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # ── Persist dataset ───────────────────────────────────
    dataset = Dataset(
        project_id=project_id,
        original_filename=file.filename,
        minio_key=result["minio_key"],
        file_format=result["file_format"],
        file_size_bytes=result["file_size_bytes"],
        row_count=result["row_count"],
        column_count=result["column_count"],
        quality_score=result["quality_score"],
    )
    db.add(dataset)
    await db.flush()

    # ── Persist columns ───────────────────────────────────
    for col in result["columns"]:
        db.add(DatasetColumn(
            dataset_id=dataset.id,
            original_name=col["original_name"],
            detected_type=col["detected_type"],
            null_percent=col["null_percent"],
            unique_count=col["unique_count"],
            sample_values=col["sample_values"],
            stats=col["stats"],
            column_order=col["column_order"],
        ))

    await db.refresh(dataset)

    return UploadResponse(
        file_id=dataset.id,
        original_filename=file.filename,
        row_count=result["row_count"],
        column_count=result["column_count"],
        file_size_bytes=result["file_size_bytes"],
        detected_sector=project.detected_sector,
        quality_score=result["quality_score"],
        preview=result["preview"],
        columns=[ColumnProfile(**c) for c in result["columns"]],
    )


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
async def get_preview(
    project_id:   uuid.UUID,
    dataset_id:   uuid.UUID,
    n:            int          = 10,
    db:           AsyncSession = Depends(get_db),
    current_user: dict         = Depends(get_current_user),
    minio:        MinioService = Depends(get_minio_service),
):
    await _get_project_or_404(db, project_id, current_user["company_id"])
    dataset = await _get_dataset_or_404(db, dataset_id, project_id)

    svc = DatasetService(minio)
    result = svc.get_preview_from_minio(dataset.minio_key, dataset.file_format, n)
    return DatasetPreviewResponse(**result)


@router.get("/{dataset_id}/profile", response_model=DatasetProfileResponse)
async def get_profile(
    project_id:   uuid.UUID,
    dataset_id:   uuid.UUID,
    db:           AsyncSession = Depends(get_db),
    current_user: dict         = Depends(get_current_user),
):
    await _get_project_or_404(db, project_id, current_user["company_id"])
    await _get_dataset_or_404(db, dataset_id, project_id)

    result = await db.execute(
        select(DatasetColumn)
        .where(DatasetColumn.dataset_id == dataset_id)
        .order_by(DatasetColumn.column_order)
    )
    columns = result.scalars().all()
    return DatasetProfileResponse(
        dataset_id=dataset_id,
        columns=[DatasetColumnResponse.model_validate(c) for c in columns],
    )


@router.put("/{dataset_id}/metadata", response_model=DatasetResponse)
async def update_metadata(
    project_id:   uuid.UUID,
    dataset_id:   uuid.UUID,
    body:         MetadataUpdateRequest,
    db:           AsyncSession = Depends(get_db),
    current_user: dict         = Depends(get_current_user),
):
    await _get_project_or_404(db, project_id, current_user["company_id"])
    dataset = await _get_dataset_or_404(db, dataset_id, project_id)

    result = await db.execute(
        select(DatasetColumn).where(DatasetColumn.dataset_id == dataset_id)
    )
    col_map = {c.original_name: c for c in result.scalars().all()}

    for update in body.columns:
        col = col_map.get(update.original_name)
        if col:
            if update.business_name is not None: col.business_name = update.business_name
            if update.business_type is not None: col.business_type = update.business_type

    await db.flush()
    await db.refresh(dataset)
    return dataset


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    project_id:   uuid.UUID,
    dataset_id:   uuid.UUID,
    db:           AsyncSession = Depends(get_db),
    current_user: dict         = Depends(get_current_user),
    minio:        MinioService = Depends(get_minio_service),
):
    await _get_project_or_404(db, project_id, current_user["company_id"])
    dataset = await _get_dataset_or_404(db, dataset_id, project_id)

    svc = DatasetService(minio)
    svc.delete_file(dataset.minio_key)
    if dataset.minio_processed_key:
        svc.delete_file(dataset.minio_processed_key)

    await db.delete(dataset)