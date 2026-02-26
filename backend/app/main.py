"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api.auth import router as auth_router
from app.api.groups import router as groups_router
from app.api.expenses import router as expenses_router
from app.api.ai import router as ai_router
from app.api.analytics import router as analytics_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup — auto-create tables for SQLite dev mode
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")

    from app.core.database import engine, Base
    # Import all models to register them
    from app.models.user import User  # noqa: F401
    from app.models.group import Group, GroupMember  # noqa: F401
    from app.models.expense import Expense, ExpenseSplit, Settlement  # noqa: F401
    from app.models.notification import Notification  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables ready")

    yield
    # Shutdown
    print(f"👋 {settings.APP_NAME} shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router, prefix="/api")
app.include_router(groups_router, prefix="/api")
app.include_router(expenses_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": f"{settings.APP_NAME} API", "version": settings.APP_VERSION}


@app.get("/health")
async def health():
    return {"status": "healthy"}
