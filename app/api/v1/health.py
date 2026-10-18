
from fastapi import APIRouter

# 创建健康检查路由
router = APIRouter()


@router.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}
