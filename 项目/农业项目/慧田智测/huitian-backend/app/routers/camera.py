import hmac
from collections.abc import AsyncIterator
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app import models, schemas
from app.config import settings
from app.dependencies import DbSession
from app.services import camera_service, resource_service
from app.websocket_manager import websocket_manager


edge_router = APIRouter(prefix="/camera/edge", tags=["D435i 边缘相机"])
proxy_router = APIRouter(prefix="/camera", tags=["D435i 视频代理"])
detection_router = APIRouter(prefix="/detections", tags=["病害识别结果"])


def _camera_device(db: DbSession, device_code: str) -> models.Device:
    device = resource_service.get_device_by_code(db, device_code)
    if device.device_type != "camera" or not device.stream_url:
        raise HTTPException(status_code=404, detail="相机视频地址不存在")
    return device


def _edge_url(stream_url: str, path: str) -> str:
    parsed = urlsplit(stream_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=422, detail="相机视频地址无效")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


async def _set_camera_online(
    db: DbSession, device: models.Device, online: bool
) -> None:
    if device.is_online == online:
        return
    device.is_online = online
    if online:
        device.last_seen_at = models.utc_now()
    db.commit()
    await websocket_manager.broadcast(
        "camera.status_changed",
        {
            "device_code": device.device_code,
            "camera_online": online,
            "stream_url": device.stream_url,
        },
    )


@proxy_router.get("/{device_code}/health")
async def proxy_camera_health(device_code: str, db: DbSession):
    device = _camera_device(db, device_code)
    target = _edge_url(device.stream_url or "", "/health")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            upstream = await client.get(target, headers={"Accept": "application/json"})
            upstream.raise_for_status()
            payload = upstream.json()
    except (httpx.HTTPError, ValueError) as exc:
        await _set_camera_online(db, device, False)
        raise HTTPException(status_code=503, detail="Jetson 相机服务暂不可用") from exc

    online = payload.get("status") == "online"
    await _set_camera_online(db, device, online)
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


@proxy_router.get("/{device_code}/snapshot.jpg")
async def proxy_camera_snapshot(device_code: str, db: DbSession) -> Response:
    device = _camera_device(db, device_code)
    target = _edge_url(device.stream_url or "", "/snapshot.jpg")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            upstream = await client.get(target, headers={"Accept": "image/jpeg"})
            upstream.raise_for_status()
    except httpx.HTTPError as exc:
        await _set_camera_online(db, device, False)
        raise HTTPException(status_code=503, detail="Jetson 暂未返回 D435i 视频帧") from exc

    await _set_camera_online(db, device, True)
    return Response(
        content=upstream.content,
        media_type=upstream.headers.get("content-type", "image/jpeg"),
        headers={"Cache-Control": "no-store"},
    )


@proxy_router.get("/{device_code}/video")
async def proxy_camera_video(device_code: str, db: DbSession) -> StreamingResponse:
    device = _camera_device(db, device_code)
    target = _edge_url(device.stream_url or "", "/video")
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=3.0, read=None, write=3.0, pool=3.0)
    )
    try:
        upstream = await client.send(client.build_request("GET", target), stream=True)
        upstream.raise_for_status()
    except httpx.HTTPError as exc:
        await client.aclose()
        await _set_camera_online(db, device, False)
        raise HTTPException(status_code=503, detail="Jetson 视频流连接失败") from exc

    async def stream_frames() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_frames(),
        media_type=upstream.headers.get(
            "content-type", "multipart/x-mixed-replace; boundary=frame"
        ),
        headers={"Cache-Control": "no-store"},
    )


def verify_edge_key(x_edge_api_key: str | None) -> None:
    expected = settings.edge_api_key
    if expected and not hmac.compare_digest(expected, x_edge_api_key or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="边缘设备密钥无效",
        )


@edge_router.post(
    "/register", response_model=schemas.EdgeCameraRegistrationResponse
)
async def register_camera(
    data: schemas.EdgeCameraRegistration,
    db: DbSession,
    x_edge_api_key: str | None = Header(default=None, alias="X-Edge-Api-Key"),
):
    verify_edge_key(x_edge_api_key)
    device = camera_service.register_camera(db, data)
    await websocket_manager.broadcast(
        "camera.status_changed",
        {
            "device_code": device.device_code,
            "camera_online": device.is_online,
            "stream_url": device.stream_url,
        },
    )
    return schemas.EdgeCameraRegistrationResponse(
        device_id=device.id,
        device_code=device.device_code,
    )


@edge_router.post(
    "/detections", response_model=schemas.DiseaseDetectionCreateResponse
)
async def create_detection(
    data: schemas.DiseaseDetectionCreate,
    db: DbSession,
    x_edge_api_key: str | None = Header(default=None, alias="X-Edge-Api-Key"),
):
    verify_edge_key(x_edge_api_key)
    detection = camera_service.create_detection(db, data)
    await websocket_manager.broadcast(
        "camera.detection_created",
        {
            "detection_id": detection.id,
            "device_code": data.device_code,
            "disease_name": detection.disease_name,
            "severity": detection.severity,
            "confidence": detection.confidence,
            "detected_at": detection.detected_at.isoformat(),
        },
    )
    return schemas.DiseaseDetectionCreateResponse(detection_id=detection.id)


@detection_router.get(
    "", response_model=list[schemas.DiseaseDetectionResponse]
)
def list_detections(
    db: DbSession,
    plot_id: int | None = None,
    device_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    return camera_service.list_detections(
        db,
        plot_id=plot_id,
        device_id=device_id,
        limit=limit,
    )
