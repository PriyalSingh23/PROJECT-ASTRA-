import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db
from app.api import auth, users, devices, messages, endpoints, adapters, diagnostics, audit, experiments, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite tables and seed defaults
    init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Resilient Communications, Offline Messaging, and Approved Radio Interoperability Platform",
    lifespan=lifespan,
)

# CORS middleware for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 Routers
api_v1 = FastAPI()
api_v1.include_router(auth.router)
api_v1.include_router(users.router)
api_v1.include_router(devices.router)
api_v1.include_router(messages.router)
api_v1.include_router(endpoints.router)
api_v1.include_router(adapters.router)
api_v1.include_router(diagnostics.router)
api_v1.include_router(audit.router)
api_v1.include_router(experiments.router)
api_v1.include_router(ws.router)


@api_v1.get("/health")
def api_v1_health():
    return {
        "status": "HEALTHY",
        "service": "SHADOWLINK FIELD Platform Core",
        "version": settings.VERSION,
        "mode": "FIELD_OPERATIONS",
    }


app.mount(settings.API_V1_STR, api_v1)


@app.get("/health")
@app.get("/api/v1/health")
def root_health():
    return {
        "status": "HEALTHY",
        "service": "SHADOWLINK FIELD Platform Core",
        "version": settings.VERSION,
        "mode": "FIELD_OPERATIONS",
    }


dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.exists(dist_path):
    app.mount("/", StaticFiles(directory=dist_path, html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs_url": "/docs",
            "api_v1": settings.API_V1_STR,
        }
