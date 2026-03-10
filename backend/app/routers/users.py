from fastapi             import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database  import get_db
from app.dependencies   import get_current_user
from app.services.user_service import UserService
from app.schemas.user   import UserUpdate, PreferencesUpdate

router = APIRouter()


@router.get("/me")
async def get_me(
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    return await UserService.get_me(db, user["user_id"])


@router.put("/me")
async def update_me(
    body: UserUpdate,
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    return await UserService.update_me(db, user["user_id"], body)


@router.put("/me/preferences")
async def update_preferences(
    body: PreferencesUpdate,
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    return await UserService.update_preferences(
        db, user["user_id"], body
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    await UserService.delete_me(db, user["user_id"])