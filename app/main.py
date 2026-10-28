
from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.api.v1.chat import router as chat_router
from app.api.v1.customers import router as customers_router
from app.api.v1.images import router as images_router
from app.api.v1.staff import router as staff_router
from app.api.v1.refunds import router as refunds_router
from app.api.v1.conversations import router as conversations_router
from app.core.config import get_settings
import logging
import time
from uuid import uuid4
from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.request_context import request_id_var
#定义异步应用生命周期。
from contextlib import asynccontextmanager
#持久化 LangGraph 工作流状态。
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
#将 Checkpointer 接入现有 Agent。
from app.agent.graph import configure_agent_graph
#读取之前配置好的 PostgreSQL 连接字符串。
from app.core.checkpointer import get_checkpointer_conninfo
#跨域请求中间件
from fastapi.middleware.cors import CORSMiddleware



settings = get_settings()
logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理 LangGraph PostgreSQL Checkpointer 的生命周期。"""

    conninfo = get_checkpointer_conninfo()

    async with AsyncPostgresSaver.from_conn_string(
        conninfo
    ) as checkpointer:
        # 初始化 LangGraph 所需的 PostgreSQL 表
        await checkpointer.setup()

        # 使用持久化 Checkpointer 重建 Agent 工作流
        configure_agent_graph(checkpointer)

        logger.info(
            "LangGraph PostgreSQL Checkpointer 初始化成功"
        )

        # 应用在这里运行，关闭时自动退出 async with
        yield


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
    lifespan=lifespan
)


@app.middleware("http")
async def security_headers_middleware(
    request: Request,
    call_next,
):
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    return response

@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception,
):
    """统一处理未捕获异常，避免泄露内部错误信息。"""

    request_id = getattr(
        request.state,
        "request_id",
        None,
    )

    response = JSONResponse(
        status_code=500,
        content={
            "detail": "服务器内部错误",
            "request_id": request_id,
        },
    )

    # 确保 500 异常响应也包含安全响应头
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"

    # 保留请求追踪 ID
    if request_id is not None:
        response.headers["X-Request-ID"] = str(request_id)

    return response

@app.middleware("http")
async def log_request_duration(
    request: Request,
    call_next,
):
    """记录 HTTP 请求耗时，并管理 Request ID。"""

    # 1. 生成本次请求的唯一编号
    request_id = uuid4().hex
    # 保存到 request.state，供异常处理器读取
    request.state.request_id = request_id

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
app.include_router(staff_router)
app.include_router(refunds_router)
app.include_router(conversations_router)
# 保留原始 FastAPI 实例
fastapi_app = app

# 使用 CORS 包裹整个 ASGI 应用
app = CORSMiddleware(
    app=fastapi_app,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=[
        "GET", "POST", "PUT",
        "PATCH", "DELETE", "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
    ],
    expose_headers=["X-Request-ID"],
)