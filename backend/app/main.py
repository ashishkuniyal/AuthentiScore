import os
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database.mongodb import setup_indexes, scans_collection
from app.core.ws import manager
from app.services.model_store import is_loaded, get_model, get_metrics
from app.routes.auth import verify_token_string, router as auth_router
from app.routes.users import router as users_router
from app.routes.scan import router as scan_router
from app.routes.analytics import router as analytics_router
from app.routes.history import router as history_router
from app.routes.bulk import router as bulk_router
from app.routes.audit import router as audit_router

logger = logging.getLogger(__name__)


# ==================================================
# Lifespan Management (B3, C1)
# ==================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Capture event loop for thread-safe WebSocket dispatch
    manager.capture_loop()

    # 2. Setup MongoDB indexes
    try:
        setup_indexes()
        logger.info("MongoDB indexes configured successfully.")
    except Exception as exc:
        logger.warning("Could not setup MongoDB indexes at startup: %s", exc)

    # 3. Model warm-up
    try:
        get_model()
    except Exception as exc:
        logger.warning("Model warm-up skipped: %s", exc)

    yield


# ==================================================
# Application
# ==================================================

app = FastAPI(
    title="AuthentiScore API",
    description="AI-Powered Fake Social Media Profile Detection System",
    version="1.0.0",
    lifespan=lifespan
)


# ==================================================
# CORS (S12)
# ==================================================

cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env.strip():
    allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
else:
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================
# Routers
# ==================================================

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(users_router, prefix="/users", tags=["Users"])
app.include_router(scan_router)
app.include_router(analytics_router)
app.include_router(history_router)
app.include_router(bulk_router)
app.include_router(audit_router)


# ==================================================
# WebSockets — Authenticated per-user stream (S5, C1, C3)
# ==================================================

@app.websocket("/ws/notifications")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(default=None)
):
    user_id = None
    if token:
        try:
            user_doc = verify_token_string(token)
            user_id = str(user_doc["_id"])
            await manager.connect(websocket, user_id)
        except Exception:
            await websocket.close(code=4401)
            return
    else:
        # Handshake via first message if token not in query param
        await websocket.accept()
        try:
            first_msg = await websocket.receive_text()
            data = json.loads(first_msg)
            token_val = data.get("token")
            if not token_val:
                await websocket.close(code=4401)
                return
            user_doc = verify_token_string(token_val)
            user_id = str(user_doc["_id"])
            # Register in active connections
            manager._connections.setdefault(user_id, set()).add(websocket)
        except Exception:
            await websocket.close(code=4401)
            return

    try:
        while True:
            # Keep socket alive; ignore incoming pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        if user_id:
            manager.disconnect(websocket, user_id)


# ==================================================
# Root & Health (B2, C31)
# ==================================================

@app.get("/")
def root():
    return {
        "project": "AuthentiScore",
        "message": "API is running",
        "version": "1.0.0"
    }


@app.get("/health")
def health_check():
    mongodb_ok = False
    try:
        scans_collection.database.client.admin.command("ping")
        mongodb_ok = True
    except Exception:
        pass

    model_loaded = is_loaded()
    status_str = "healthy" if mongodb_ok else "degraded"
    response_data = {
        "status": status_str,
        "mongodb": mongodb_ok,
        "model_loaded": model_loaded,
        "version": "1.0.0"
    }
    if not mongodb_ok:
        return JSONResponse(status_code=503, content=response_data)
    return response_data


@app.get("/model/metrics")
def get_metrics_endpoint():
    """Return trained model evaluation metrics (F6)."""
    return get_metrics()