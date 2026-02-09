"""헬스 체크 라우터"""

from fastapi import APIRouter

from ..config import get_app_version

router = APIRouter()


@router.get("/health")
async def health_check():
    """서버 상태 확인"""
    return {"status": "ok", "service": "avt-api", "version": get_app_version()}
