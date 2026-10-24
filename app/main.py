
from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.api.v1.chat import router as chat_router
from app.api.v1.customers import router as customers_router
from app.api.v1.images import router as images_router
from app.core.config import get_settings
import logging
import time
from uuid import uuid4
from fastapi import Request
from app.core.request_context import request_id_var

settings = get_settings()
logger = logging.getLogger("uvicorn.error")
# 获取 LangGraph 节点专属的日志记录器
agent_logger = logging.getLogger("app.agent.nodes")

# 允许输出 INFO 及以上级别的日志
agent_logger.setLevel(logging.INFO)

# 为 Agent 日志添加终端输出处理器
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter(
        "%(levelname)s %(name)s: %(message)s"
    )
)

agent_logger.addHandler(handler)

# 避免日志继续向上传播造成重复输出
agent_logger.propagate = False
app = FastAPI(
    title=settings.APP_NAME,
    description="企业级多模态智能客服与业务执行平台",
    version="0.1.0",
    debug=settings.DEBUG,
)



@app.middleware("http")
async def log_request_duration(
    request: Request,
    call_next,
):
    """记录 HTTP 请求耗时，并管理 Request ID。"""

    # 1. 生成本次请求的唯一编号
    request_id = uuid4().hex

    # 2. 将 Request ID 写入当前异步上下文
    token = request_id_var.set(request_id)

    # 3. 记录请求开始时间
    start_time = time.perf_counter()

    try:
        try:
            # 4. 继续执行后续业务接口
            response = await call_next(request)

        except Exception:
            duration_ms = (
                time.perf_counter() - start_time
            ) * 1000

            logger.exception(
                "HTTP 请求异常：request_id=%s, method=%s, path=%s, duration_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                duration_ms,
            )
            raise

        # 5. 计算请求耗时
        duration_ms = (
            time.perf_counter() - start_time
        ) * 1000

        # 6. 将 Request ID 写入响应头
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "HTTP 请求完成：request_id=%s, method=%s, path=%s, status=%s, duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response

    finally:
        # 7. 恢复进入中间件之前的上下文
        request_id_var.reset(token)


app.include_router(health_router)
app.include_router(chat_router)
app.include_router(customers_router)
app.include_router(images_router)