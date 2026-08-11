"""FastAPI application entry point."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router, mcp_router, worker_api_router
from app.core.access_log import AutotaskAccessLogMiddleware
from app.core.config import settings
from app.core.deps import engine
from app.core.exceptions import register_exception_handlers
from app.core.middleware import NoCacheAPIMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _restore_logging_after_alembic(saved_handlers: list, saved_level: int) -> None:
    root_log = logging.getLogger()
    root_log.handlers = saved_handlers
    root_log.level = saved_level
    for name in logging.Logger.manager.loggerDict:
        obj = logging.Logger.manager.loggerDict[name]
        if isinstance(obj, logging.Logger) and obj.disabled:
            obj.disabled = False


async def _auto_migrate() -> None:
    from alembic.config import Config

    from alembic import command

    def _run() -> None:
        root_log = logging.getLogger()
        saved_handlers = root_log.handlers[:]
        saved_level = root_log.level

        backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cfg = Config(os.path.join(backend_root, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(backend_root, "alembic"))
        try:
            command.upgrade(cfg, "head")
        finally:
            _restore_logging_after_alembic(saved_handlers, saved_level)

    await asyncio.to_thread(_run)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("nodeskclaw-task %s starting", settings.APP_VERSION)

    if not settings.SKIP_AUTO_MIGRATE:
        try:
            logger.info("正在执行数据库迁移 (alembic upgrade head) ...")
            await _auto_migrate()
            logger.info("数据库迁移完成")
        except Exception:
            logger.exception("数据库迁移失败")
            raise
    else:
        logger.info("SKIP_AUTO_MIGRATE=1，跳过自动迁移")

    if settings.SEED_DATA_ENABLED:
        from app.core.deps import async_session_factory
        from app.startup.seed import run_seed

        try:
            await run_seed(async_session_factory)
        except Exception:
            logger.exception("种子数据同步失败（不影响服务启动）")
    else:
        logger.info("SEED_DATA_ENABLED=false，跳过种子数据")

    successor_processor = None
    if settings.SUCCESSOR_JOB_ENABLED:
        from app.core.deps import async_session_factory
        from app.services.task_successor_service import SuccessorJobProcessor

        successor_processor = SuccessorJobProcessor(
            async_session_factory,
            settings,
        )
        await successor_processor.start()
        logger.info("后继任务作业处理器已启动")
    else:
        logger.info("SUCCESSOR_JOB_ENABLED=false，后继任务作业处理器保持关闭")
    app.state.successor_job_processor = successor_processor

    try:
        yield
    finally:
        if successor_processor is not None:
            await successor_processor.stop()
        await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(NoCacheAPIMiddleware)
app.add_middleware(AutotaskAccessLogMiddleware)
register_exception_handlers(app)

app.include_router(api_router, prefix="/api/v1/autotask")
app.include_router(worker_api_router, prefix="/api/v1/autotask")
app.include_router(mcp_router, prefix="/api/v1/autotask")


@app.get("/health")
async def root_health():
    return {"status": "ok"}
