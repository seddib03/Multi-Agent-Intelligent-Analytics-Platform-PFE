import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.config import settings
from app.dependencies import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.dataset import Dataset, DatasetColumn
from app.schemas.dataset import (
    UploadResponse, DatasetProfileResponse, DatasetColumnResponse,
    MetadataUpdateRequest, DatasetResponse, ColumnProfile,
    QualityReportResponse, ColumnQuality, QualityIssue,
    ApplyCorrectionsRequest, ApplyCorrectionsResponse,
)
from app.services.dataset_service import DatasetService
from app.services.quality_service import QualityService

router = APIRouter(tags=["Datasets"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

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


async def _get_columns(db: AsyncSession, dataset_id: uuid.UUID) -> list[DatasetColumn]:
    result = await db.execute(
        select(DatasetColumn)
        .where(DatasetColumn.dataset_id == dataset_id)
        .order_by(DatasetColumn.column_order)
    )
    return result.scalars().all()


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    project_id:   uuid.UUID,
    file:         UploadFile   = File(...),
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    """Upload dataset — stockage délégué au Resp. Data, on persiste uniquement les métadonnées."""
    project = await _get_project_or_404(db, project_id, current_user.company_id)

    file_bytes = await file.read()

    if len(file_bytes) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Fichier trop volumineux (max {settings.MAX_UPLOAD_SIZE_MB} Mo)",
        )

    svc = DatasetService()
    try:
        result = svc.parse(file_bytes, file.filename, project_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # ── Persist dataset ──────────────────────────────────────────────────────
    dataset = Dataset(
        project_id=project_id,
        original_filename=file.filename,
        minio_key=f"raw/{project_id}/{file.filename}",   # clé provisoire — sera mise à jour par Resp. Data
        file_format=result["file_format"],
        file_size_bytes=result["file_size_bytes"],
        row_count=result["row_count"],
        column_count=result["column_count"],
        quality_score=result["quality_score"],
    )
    db.add(dataset)
    await db.flush()

    # ── Persist columns ──────────────────────────────────────────────────────
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

    await db.flush()
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


@router.get("/{dataset_id}/profile", response_model=DatasetProfileResponse)
async def get_profile(
    project_id:   uuid.UUID,
    dataset_id:   uuid.UUID,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    await _get_project_or_404(db, project_id, current_user.company_id)
    await _get_dataset_or_404(db, dataset_id, project_id)
    columns = await _get_columns(db, dataset_id)
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
    current_user: User         = Depends(get_current_user),
):
    await _get_project_or_404(db, project_id, current_user.company_id)
    dataset = await _get_dataset_or_404(db, dataset_id, project_id)

    result = await db.execute(
        select(DatasetColumn).where(DatasetColumn.dataset_id == dataset_id)
    )
    col_map = {c.original_name: c for c in result.scalars().all()}

    for update in body.columns:
        col = col_map.get(update.original_name)
        if col:
            if update.business_name is not None:
                col.business_name = update.business_name
            if update.business_type is not None:
                col.business_type = update.business_type

    await db.flush()
    await db.refresh(dataset)
    return dataset


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    project_id:   uuid.UUID,
    dataset_id:   uuid.UUID,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    await _get_project_or_404(db, project_id, current_user.company_id)
    dataset = await _get_dataset_or_404(db, dataset_id, project_id)
    await db.delete(dataset)


# ─── Sprint 4 — Qualité ───────────────────────────────────────────────────────

@router.post("/{dataset_id}/analyze-quality", response_model=QualityReportResponse)
async def analyze_quality(
    project_id:   uuid.UUID,
    dataset_id:   uuid.UUID,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    """Analyse la qualité du dataset et persiste le rapport en base."""
    await _get_project_or_404(db, project_id, current_user.company_id)
    dataset = await _get_dataset_or_404(db, dataset_id, project_id)
    columns = await _get_columns(db, dataset_id)

    if not columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune colonne trouvée — uploadez d'abord le dataset.",
        )

    cols_data = [
        {
            "original_name": c.original_name,
            "detected_type": c.detected_type,
            "null_percent":  c.null_percent or 0.0,
            "unique_count":  c.unique_count or 0,
        }
        for c in columns
    ]

    svc = QualityService()
    report = svc.analyze(cols_data)

    # ── Persiste le rapport en base ──────────────────────────────────────────
    dataset.quality_report = report
    dataset.quality_score  = report["global_score"]
    await db.flush()
    await db.refresh(dataset)

    return QualityReportResponse(
        dataset_id=dataset_id,
        global_score=report["global_score"],
        total_columns=report["total_columns"],
        columns_ok=report["columns_ok"],
        columns_issues=report["columns_issues"],
        critical_count=report["critical_count"],
        warning_count=report["warning_count"],
        issues=[
            ColumnQuality(
                column=col["column"],
                score=col["score"],
                issues=[QualityIssue(**i) for i in col["issues"]],
            )
            for col in report["issues"]
        ],
        corrections_available=list(set(report["corrections_available"])),
    )


@router.get("/{dataset_id}/quality-report", response_model=QualityReportResponse)
async def get_quality_report(
    project_id:   uuid.UUID,
    dataset_id:   uuid.UUID,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    """Récupère le rapport qualité existant depuis la base."""
    await _get_project_or_404(db, project_id, current_user.company_id)
    dataset = await _get_dataset_or_404(db, dataset_id, project_id)

    if not dataset.quality_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun rapport qualité trouvé — lancez d'abord POST analyze-quality.",
        )

    report = dataset.quality_report
    return QualityReportResponse(
        dataset_id=dataset_id,
        global_score=report["global_score"],
        total_columns=report["total_columns"],
        columns_ok=report["columns_ok"],
        columns_issues=report["columns_issues"],
        critical_count=report["critical_count"],
        warning_count=report["warning_count"],
        issues=[
            ColumnQuality(
                column=col["column"],
                score=col["score"],
                issues=[QualityIssue(**i) for i in col["issues"]],
            )
            for col in report["issues"]
        ],
        corrections_available=list(set(report["corrections_available"])),
    )


@router.post("/{dataset_id}/apply-corrections", response_model=ApplyCorrectionsResponse)
async def apply_corrections(
    project_id:   uuid.UUID,
    dataset_id:   uuid.UUID,
    body:         ApplyCorrectionsRequest,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    """
    Applique les corrections demandées.
    Le traitement réel du fichier est délégué au Resp. Data via /api/internal/data/*.
    """
    await _get_project_or_404(db, project_id, current_user.company_id)
    dataset = await _get_dataset_or_404(db, dataset_id, project_id)

    if not dataset.quality_report:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lancez d'abord POST analyze-quality avant d'appliquer des corrections.",
        )

    columns = await _get_columns(db, dataset_id)
    cols_data = [
        {
            "original_name": c.original_name,
            "detected_type": c.detected_type,
            "null_percent":  c.null_percent or 0.0,
            "unique_count":  c.unique_count or 0,
        }
        for c in columns
    ]

    svc = QualityService()
    result = svc.apply_corrections(cols_data, body.corrections)

    return ApplyCorrectionsResponse(
        dataset_id=dataset_id,
        applied=result["applied"],
        skipped=result["skipped"],
        message=result["message"],
        note=result["note"],
    )