import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_database
from app.routers import alerts, camera, commands, devices, diagnosis, farms, health, plots, telemetry
from app.websocket_manager import websocket_manager


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_database()
    yield


app = FastAPI(
    title=settings.app_name,
    description="番茄智慧种植后端 MVP：HTTP REST、WebSocket、SQLite。",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = "/api/v1"
app.include_router(health.router, prefix=api_prefix)
app.include_router(farms.router, prefix=api_prefix)
app.include_router(plots.router, prefix=api_prefix)
app.include_router(devices.router, prefix=api_prefix)
app.include_router(telemetry.router, prefix=api_prefix)
app.include_router(alerts.router, prefix=api_prefix)
app.include_router(commands.router, prefix=api_prefix)
app.include_router(diagnosis.router, prefix=api_prefix)
app.include_router(camera.detection_router, prefix=api_prefix)
app.include_router(camera.proxy_router, prefix=api_prefix)
app.include_router(camera.edge_router)


@app.get("/", tags=["入口"])
def root() -> dict[str, str]:
    return {
        "message": "慧田智测后端运行中",
        "swagger": "/docs",
        "health": "/api/v1/health",
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket_manager.connect(websocket)
    await websocket.send_json(
        {"event": "system.connected", "data": {"message": "WebSocket 连接成功"}}
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket)
    except Exception:
        await websocket_manager.disconnect(websocket)
