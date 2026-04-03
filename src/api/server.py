import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.core.database import init_db, close_db
from src.core.exceptions import register_exception_handlers
from src.core.logging_config import setup_logging, get_logger
from src.api.v1.research import router as research_router

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting IQinsyt Backend v%s", settings.APP_VERSION)
    await init_db()
    logger.info("Database initialized")
    yield
    await close_db()
    logger.info("Server shutting down")


app = FastAPI(
    title="IQinsyt Backend",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS — allow extension and local dev origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


# Request ID middleware — injects a UUID into request.state for tracing
@app.middleware("http")
async def inject_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


# Routers
app.include_router(research_router, prefix="/v1")


# Health check
@app.get("/health", tags=["health"])
async def health():
    from src.core.database import _mongo_client

    db_status = "ok"
    try:
        if _mongo_client:
            await _mongo_client.admin.command("ping")
        else:
            db_status = "error"
    except Exception as exc:
        db_status = "error"
        logger.warning("Health check: database ping failed — %s", exc)

    status = "ok" if db_status == "ok" else "degraded"
    logger.info("Health check: status=%s, db=%s", status, db_status)

    return {
        "status": status,
        "db": db_status,
        "version": settings.APP_VERSION,
    }
