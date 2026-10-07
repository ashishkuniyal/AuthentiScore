from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.scan import router as scan_router
from app.routes.analytics import router as analytics_router
from app.routes.history import router as history_router
from app.routes.bulk import router as bulk_router
from app.database.mongodb import scans_collection


app = FastAPI(
    title="AuthentiScore API",
    description="AI-Powered Fake Social Media Profile Detection System",
    version="1.0.0"
)


# ==================================================
# CORS
# ==================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================
# Routers
# ==================================================

from app.routes.auth import router as auth_router
from app.routes.users import router as users_router

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(users_router, prefix="/users", tags=["Users"])
app.include_router(scan_router)
app.include_router(analytics_router)
app.include_router(history_router)
app.include_router(bulk_router)
from app.routes.audit import router as audit_router
app.include_router(audit_router)

# ==================================================
# WebSockets (Real-time Notifications)
# ==================================================

from fastapi import WebSocket, WebSocketDisconnect
from typing import List
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect client to send much, but we keep connection open
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)



# ==================================================
# Root
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

    return {
        "status": "healthy",
        "mongodb": mongodb_ok,
        "version": "1.0.0"
    }