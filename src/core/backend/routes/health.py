"""헬스 체크 라우터"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """서버 상태 확인"""
    return {"status": "ok", "service": "avt-api"}
