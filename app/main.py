
from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.api.v1.chat import router as chat_router
from app.core.config import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="企业级多模态智能客服与业务执行平台",
    version="0.1.0",
    debug=settings.DEBUG,
)

app.include_router(health_router)
app.include_router(chat_router)
