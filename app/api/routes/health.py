from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Health check")
async def health_check(session: AsyncSession = Depends(get_db)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}
