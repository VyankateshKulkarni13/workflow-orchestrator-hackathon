"""
api.py
------
Main FastAPI application entry point.

Mounts all 4 routers and configures:
  - Lifespan: Creates DB tables on startup, releases connections on shutdown.
  - CORS: Allows the React frontend to talk to this API.
  - Global Exception Handler: Catches any unhandled errors so the server
    never returns a raw Python traceback to the client.
  - Health Check: GET /health — for Docker/Kubernetes readiness probes.
"""

import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import create_tables
from routers import callbacks, executions, tasks, templates


# Lifespan: Startup & Shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on server startup: ensures all three DB tables exist.
    Runs on server shutdown: (reserved for future cleanup like Redis connection close).
    """
    print("[STARTUP] Creating database tables if they don't exist...")
    await create_tables()
    print("[STARTUP] Database ready. Orchestrator is online.")
    yield
    print("[SHUTDOWN] Orchestrator shutting down cleanly.")


# FastAPI Application
app = FastAPI(
    title="Workflow Orchestrator API",
    description=(
        "A DAG-based workflow orchestration engine using Kahn's Algorithm. "
        "Supports parallel task execution, human approvals, retry logic, "
        "and real-time monitoring via REST APIs."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# CORS Middleware
# Allow the frontend (React/Next.js on localhost:3000) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handler
# Catches any unhandled exception and returns a clean JSON error response.
# Prevents Python tracebacks from leaking to API clients.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    err_detail = traceback.format_exc()
    print(f"[UNHANDLED ERROR] {request.method} {request.url}\n{err_detail}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Check server logs for details.",
        },
    )


# Mount All 4 Routers
app.include_router(templates.router)
app.include_router(executions.router)
app.include_router(tasks.router)
app.include_router(callbacks.router)


# Health Check Endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Readiness probe for Docker/Kubernetes.
    Returns 200 OK if the API server is alive and connected.
    """
    return {"status": "healthy", "service": "workflow-orchestrator", "version": "1.0.0"}


# Root
@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Workflow Orchestrator API is running.",
        "docs": "/docs",
        "health": "/health",
    }
