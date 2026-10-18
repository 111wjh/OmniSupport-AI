from fastapi import FastAPI
from app.api.v1.health import router as health_router
from app.core.config import settings

settings = settings()

app = FastAPI(
    title = "OmniSupport AI",
    description = "企业级多模态智能客服业务执行平台",
    version = "0.1.0",
    debug = settings.DEBUG,
)

app.include_router(health_router)