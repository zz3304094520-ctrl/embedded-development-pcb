#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Intel RealSense D435i + local vision service for Jetson Orin Nano.

The service exposes a real MJPEG stream on /video and uploads structured
tomato-health detections to the Farm Assistant backend. Uploaded crop images
are analyzed by a local open-vocabulary vision model through Ollama.
"""

from __future__ import annotations

import argparse
import base64
import gc
import hmac
import json
import os
import queue
import signal
import socket
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILE = Path(
    os.getenv("EDGE_CAMERA_CONFIG_FILE", SCRIPT_DIR / "edge_camera_config.json")
)
MAX_ANALYZE_IMAGE_BYTES = 10 * 1024 * 1024
ANALYZE_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
VISION_HEALTH_STATUSES = {
    "healthy",
    "suspected_disease",
    "pest_damage",
    "nutrient_or_environmental_stress",
    "unknown",
}
VISION_SEVERITIES = {"healthy", "mild", "moderate", "severe", "unknown"}
VISION_OBSERVATION_SCHEMA = {
    "type": "object",
    "properties": {
        "is_crop": {"type": "boolean"},
        "crop_type": {"type": "string"},
        "plant_organ": {"type": "string"},
        "growth_stage": {"type": "string"},
        "health_status": {"type": "string", "enum": sorted(VISION_HEALTH_STATUSES)},
        "visible_symptoms": {"type": "array", "items": {"type": "string"}},
        "suspected_problem": {"type": "string"},
        "severity": {"type": "string", "enum": sorted(VISION_SEVERITIES)},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "uncertainty": {"type": "string"},
    },
    "required": [
        "is_crop",
        "crop_type",
        "plant_organ",
        "growth_stage",
        "health_status",
        "visible_symptoms",
        "suspected_problem",
        "severity",
        "confidence",
        "uncertainty",
    ],
}
VISION_PROMPT = """你是农业图像观察模块。只根据这张图片中真正可见的内容作答，不使用文件名，不补充图片外事实。
请识别：是否为作物、作物通用中文名称、可见器官、可判断的生长阶段、健康状态、可见症状、疑似问题、可见严重程度、置信度和不确定性。
无法可靠判断时，crop_type 或 suspected_problem 写“未知”，降低 confidence，并说明缺少什么视觉证据。
不要给出施药方案，不要把不确定的病害写成确诊。严格按给定 JSON Schema 返回。"""


class NoSupportedDetectionError(RuntimeError):
    """The uploaded image contains no detection supported by this checkpoint."""


def api_key_matches(expected, provided):
    expected_text = str(expected or "")
    provided_text = str(provided or "")
    return not expected_text or hmac.compare_digest(expected_text, provided_text)


def _positive_int(value, label, minimum=1, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}必须是整数")
    if parsed < minimum or (maximum is not None and parsed > maximum):
        range_text = f"{minimum} 到 {maximum}" if maximum is not None else f"不小于 {minimum}"
        raise ValueError(f"{label}必须在 {range_text} 范围内")
    return parsed


def _bounded_float(value, label, minimum, maximum):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}必须是数字")
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{label}必须在 {minimum} 到 {maximum} 范围内")
    return parsed


def _resolve_path(value, config_dir):
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else (config_dir / path).resolve()


def discover_local_ip(remote_host):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((remote_host, 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def normalize_class_name(value):
    normalized = []
    for char in str(value).strip().lower():
        normalized.append(char if char.isalnum() else "_")
    return "_".join(part for part in "".join(normalized).split("_") if part)


@dataclass(frozen=True)
class EdgeCameraConfig:
    backend_url: str
    api_key: str
    user_id: int
    device_code: str
    device_name: str
    camera_model: str
    model_path: Path
    profiles_path: Path
    stream_host: str
    stream_port: int
    advertise_host: str
    width: int
    height: int
    fps: int
    jpeg_quality: int
    confidence: float
    reported_confidence: float
    inference_every_frames: int
    upload_interval_seconds: float
    heartbeat_interval_seconds: float
    request_timeout_seconds: float
    inference_device: str
    upload_healthy: bool
    strict_camera_model: bool
    vision_api_url: str
    vision_model: str
    vision_timeout_seconds: float
    vision_min_confidence: float
    vision_max_image_side: int
    vision_keep_alive_seconds: int

    @classmethod
    def load(cls, path):
        config_path = Path(path).expanduser().resolve()
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        config_dir = config_path.parent

        backend_url = str(data.get("backend_url") or "").strip().rstrip("/")
        parsed_backend = urlparse(backend_url)
        if parsed_backend.scheme not in {"http", "https"} or not parsed_backend.hostname:
            raise ValueError("backend_url 必须是有效的 HTTP/HTTPS 地址")

        device_code = str(data.get("device_code") or "").strip()
        if not device_code:
            raise ValueError("device_code 不能为空")

        model_path = _resolve_path(data.get("model_path", "best.pt"), config_dir)
        profiles_path = _resolve_path(
            data.get("profiles_path", "tomato_disease_profiles.json"),
            config_dir,
        )
        vision_api_url = str(
            data.get("vision_api_url") or "http://127.0.0.1:11434/api/chat"
        ).strip()
        parsed_vision_api = urlparse(vision_api_url)
        if parsed_vision_api.scheme not in {"http", "https"} or not parsed_vision_api.hostname:
            raise ValueError("vision_api_url 必须是有效的 HTTP/HTTPS 地址")
        vision_model = str(
            data.get("vision_model") or "qwen3-vl:2b-instruct-q4_K_M"
        ).strip()
        if not vision_model:
            raise ValueError("vision_model 不能为空")

        confidence = _bounded_float(data.get("confidence", 0.5), "最低置信度", 0.01, 1.0)
        reported_confidence = _bounded_float(
            data.get("reported_confidence", confidence),
            "上报置信度",
            0.01,
            1.0,
        )

        return cls(
            backend_url=backend_url,
            api_key=str(data.get("api_key") or "").strip(),
            user_id=_positive_int(data.get("user_id", 1), "用户ID"),
            device_code=device_code[:50],
            device_name=str(data.get("device_name") or "Jetson D435i 智能巡检节点").strip()[:100],
            camera_model=str(data.get("camera_model") or "Intel RealSense D435i").strip()[:50],
            model_path=model_path,
            profiles_path=profiles_path,
            stream_host=str(data.get("stream_host") or "0.0.0.0").strip(),
            stream_port=_positive_int(data.get("stream_port", 8081), "视频服务端口", 1, 65535),
            advertise_host=str(data.get("advertise_host") or "").strip(),
            width=_positive_int(data.get("width", 640), "画面宽度", 320, 1920),
            height=_positive_int(data.get("height", 480), "画面高度", 240, 1080),
            fps=_positive_int(data.get("fps", 30), "帧率", 1, 60),
            jpeg_quality=_positive_int(data.get("jpeg_quality", 85), "JPEG质量", 40, 100),
            confidence=confidence,
            reported_confidence=reported_confidence,
            inference_every_frames=_positive_int(
                data.get("inference_every_frames", 3),
                "推理帧间隔",
                1,
                120,
            ),
            upload_interval_seconds=_bounded_float(
                data.get("upload_interval_seconds", 8),
                "结果上传间隔",
                1,
                3600,
            ),
            heartbeat_interval_seconds=_bounded_float(
                data.get("heartbeat_interval_seconds", 10),
                "心跳间隔",
                3,
                300,
            ),
            request_timeout_seconds=_bounded_float(
                data.get("request_timeout_seconds", 5),
                "HTTP超时",
                1,
                60,
            ),
            inference_device=str(data.get("inference_device") or "0").strip(),
            upload_healthy=bool(data.get("upload_healthy", True)),
            strict_camera_model=bool(data.get("strict_camera_model", True)),
            vision_api_url=vision_api_url,
            vision_model=vision_model,
            vision_timeout_seconds=_bounded_float(
                data.get("vision_timeout_seconds", 180),
                "视觉模型超时",
                10,
                600,
            ),
            vision_min_confidence=_bounded_float(
                data.get("vision_min_confidence", 0.45),
                "视觉模型最低置信度",
                0,
                1,
            ),
            vision_max_image_side=_positive_int(
                data.get("vision_max_image_side", 640),
                "视觉图片最大边长",
                384,
                2048,
            ),
            vision_keep_alive_seconds=_positive_int(
                data.get("vision_keep_alive_seconds", 0),
                "视觉模型保活时间",
                0,
                600,
            ),
        )

    def validate_files(self):
        errors = []
        if not self.model_path.is_file():
            errors.append(f"模型文件不存在: {self.model_path}")
        if not self.profiles_path.is_file():
            errors.append(f"病害资料文件不存在: {self.profiles_path}")
        if errors:
            raise ValueError("；".join(errors))

    @property
    def stream_url(self):
        backend_host = urlparse(self.backend_url).hostname or "127.0.0.1"
        host = self.advertise_host or discover_local_ip(backend_host)
        return f"http://{host}:{self.stream_port}/video"


class FrameState:
    def __init__(self):
        self.condition = threading.Condition()
        self.jpeg = None
        self.sequence = 0
        self.last_frame_at = 0.0
        self.frame_count = 0
        self.detection_count = 0
        self.camera_name = ""
        self.model_classes = []
        self.error = "等待 D435i 启动"

    def set_runtime_info(self, camera_name=None, model_classes=None):
        with self.condition:
            if camera_name is not None:
                self.camera_name = str(camera_name)
            if model_classes is not None:
                self.model_classes = list(model_classes)

    def set_error(self, message):
        with self.condition:
            self.error = str(message)
            self.condition.notify_all()

    def set_offline(self, message):
        with self.condition:
            self.error = str(message)
            self.jpeg = None
            self.sequence += 1
            self.last_frame_at = 0.0
            self.detection_count = 0
            self.condition.notify_all()

    def publish(self, jpeg, detection_count=0):
        with self.condition:
            self.jpeg = jpeg
            self.sequence += 1
            self.frame_count += 1
            self.detection_count = int(detection_count)
            self.last_frame_at = time.time()
            self.error = ""
            self.condition.notify_all()

    def wait_for_frame(self, previous_sequence, timeout=5):
        with self.condition:
            self.condition.wait_for(
                lambda: self.sequence != previous_sequence,
                timeout=timeout,
            )
            return self.sequence, self.jpeg

    def health(self):
        age = time.time() - self.last_frame_at if self.last_frame_at else None
        return {
            "status": "online" if age is not None and age < 5 else "offline",
            "camera": self.camera_name,
            "model_classes": self.model_classes,
            "frames": self.frame_count,
            "detections_in_frame": self.detection_count,
            "last_frame_seconds": round(age, 2) if age is not None else None,
            "message": self.error or "D435i 视频流正常",
        }


class CameraHttpServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, state, stop_event, analyzer, api_key):
        super().__init__(address, handler)
        self.state = state
        self.stop_event = stop_event
        self.analyzer = analyzer
        self.api_key = api_key


class CameraRequestHandler(BaseHTTPRequestHandler):
    server_version = "FieldMateD435i/1.0"

    def log_message(self, fmt, *args):
        if self.path != "/video":
            super().log_message(fmt, *args)

    def _common_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")

    def _json_response(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self._common_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Edge-Api-Key")
        self.end_headers()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path != "/analyze":
            self._json_response(
                HTTPStatus.NOT_FOUND,
                {"success": False, "message": "可用 POST 接口: /analyze"},
            )
            return

        if not api_key_matches(self.server.api_key, self.headers.get("X-Edge-Api-Key")):
            self._json_response(
                HTTPStatus.UNAUTHORIZED,
                {"success": False, "message": "边缘推理密钥无效"},
            )
            return

        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type not in ANALYZE_IMAGE_TYPES:
            self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"success": False, "message": "仅支持 JPEG、PNG 或 WebP 图片"},
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        if content_length < 1 or content_length > MAX_ANALYZE_IMAGE_BYTES:
            self._json_response(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"success": False, "message": "图片不能为空且不能超过 10MB"},
            )
            return

        image_bytes = self.rfile.read(content_length)
        try:
            payload = self.server.analyzer.analyze_uploaded_image(image_bytes)
        except NoSupportedDetectionError as exc:
            self._json_response(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"success": False, "message": str(exc)},
            )
            return
        except ValueError as exc:
            self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"success": False, "message": str(exc)},
            )
            return
        except Exception as exc:
            print(f"[图片推理] {exc}", file=sys.stderr)
            self._json_response(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"success": False, "message": "Jetson 图片推理服务暂时不可用"},
            )
            return

        self._json_response(HTTPStatus.OK, payload)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._json_response(HTTPStatus.OK, self.server.state.health())
            return
        if path == "/snapshot.jpg":
            jpeg = self.server.state.jpeg
            if not jpeg:
                self._json_response(HTTPStatus.SERVICE_UNAVAILABLE, self.server.state.health())
                return
            self.send_response(HTTPStatus.OK)
            self._common_headers()
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(jpeg)))
            self.end_headers()
            self.wfile.write(jpeg)
            return
        if path != "/video":
            self._json_response(
                HTTPStatus.NOT_FOUND,
                {"message": "可用接口: /video, /snapshot.jpg, /health, POST /analyze"},
            )
            return

        self.send_response(HTTPStatus.OK)
        self._common_headers()
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        sequence = -1
        try:
            while not self.server.stop_event.is_set():
                sequence, jpeg = self.server.state.wait_for_frame(sequence, timeout=5)
                if not jpeg:
                    continue
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii"))
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


class LocalVisionAnalyzer:
    """Proxy uploaded images to a local Ollama vision model on the Jetson."""

    def __init__(self, config, requests_module, cv2, np, live_runtime=None):
        self.config = config
        self.requests = requests_module
        self.cv2 = cv2
        self.np = np
        self.live_runtime = live_runtime
        self.session = requests_module.Session()
        self.lock = threading.Lock()

    def _unload_model(self):
        parsed = urlparse(self.config.vision_api_url)
        unload_url = parsed._replace(path="/api/generate", params="", query="", fragment="").geturl()
        try:
            self.session.post(
                unload_url,
                json={"model": self.config.vision_model, "keep_alive": 0},
                timeout=15,
            )
        except self.requests.RequestException as exc:
            print(f"[本地视觉] 模型卸载请求失败: {exc}", file=sys.stderr)

    @staticmethod
    def _clean_text(value, fallback="未知", maximum=500):
        text = str(value or "").strip()
        return (text or fallback)[:maximum]

    def _prepare_base64_image(self, image_bytes):
        image_array = self.np.frombuffer(image_bytes, dtype=self.np.uint8)
        frame = self.cv2.imdecode(image_array, self.cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("图片内容损坏或无法解码")

        height, width = frame.shape[:2]
        max_side = max(height, width)
        if max_side > self.config.vision_max_image_side:
            scale = self.config.vision_max_image_side / max_side
            frame = self.cv2.resize(
                frame,
                (max(1, round(width * scale)), max(1, round(height * scale))),
                interpolation=self.cv2.INTER_AREA,
            )

        ok, encoded = self.cv2.imencode(
            ".jpg",
            frame,
            [int(self.cv2.IMWRITE_JPEG_QUALITY), 88],
        )
        if not ok:
            raise ValueError("图片预处理失败")
        return base64.b64encode(encoded.tobytes()).decode("ascii")

    def _normalize_observation(self, raw):
        if not isinstance(raw, dict):
            raise RuntimeError("本地视觉模型没有返回 JSON 对象")

        try:
            confidence = max(0.0, min(1.0, float(raw.get("confidence", 0))))
        except (TypeError, ValueError):
            confidence = 0.0
        health_status = str(raw.get("health_status") or "unknown").strip().lower()
        severity = str(raw.get("severity") or "unknown").strip().lower()
        if health_status not in VISION_HEALTH_STATUSES:
            health_status = "unknown"
        if severity not in VISION_SEVERITIES:
            severity = "unknown"

        symptoms = raw.get("visible_symptoms") or []
        if not isinstance(symptoms, list):
            symptoms = [symptoms]
        symptoms = [self._clean_text(item, "", 160) for item in symptoms]
        symptoms = [item for item in symptoms if item][:8]

        crop_type = self._clean_text(raw.get("crop_type"), "未知", 80)
        suspected_problem = self._clean_text(raw.get("suspected_problem"), "未知", 150)
        neutral_phrases = ("无明显", "未见明显", "未发现", "没有明显")
        abnormal_symptoms = [
            item for item in symptoms
            if not any(phrase in item for phrase in neutral_phrases)
        ]
        problem_is_known = suspected_problem.lower() not in {
            "未知",
            "不确定",
            "unknown",
            "无",
            "未见明确异常",
            "未见明显异常",
        }
        has_abnormal_evidence = (
            severity in {"mild", "moderate", "severe"}
            or bool(abnormal_symptoms)
            or problem_is_known
        )
        if health_status in {"healthy", "unknown"} and has_abnormal_evidence:
            if any(keyword in suspected_problem for keyword in ("虫", "啃食", "蛀食", "虫卵")):
                health_status = "pest_damage"
            elif any(keyword in suspected_problem for keyword in ("缺素", "营养", "水分", "日灼", "冻害", "高温")):
                health_status = "nutrient_or_environmental_stress"
            else:
                health_status = "suspected_disease"
        if health_status == "healthy":
            severity = "healthy"
        elif severity == "healthy":
            severity = "unknown"

        observation = {
            "is_crop": raw.get("is_crop") is True,
            "crop_type": crop_type,
            "plant_organ": self._clean_text(raw.get("plant_organ"), "未知", 80),
            "growth_stage": self._clean_text(raw.get("growth_stage"), "未知", 80),
            "health_status": health_status,
            "visible_symptoms": symptoms,
            "suspected_problem": suspected_problem,
            "severity": severity,
            "confidence": round(confidence, 4),
            "uncertainty": self._clean_text(raw.get("uncertainty"), "仅依据单张图片", 500),
        }
        if not observation["is_crop"]:
            raise NoSupportedDetectionError("图片中未识别到作物，请上传包含清晰叶片、果实或整株的照片")
        if crop_type in {"未知", "不确定", "unknown"}:
            raise NoSupportedDetectionError("无法可靠识别作物种类，请靠近主体并在自然光下重新拍摄")
        if confidence < self.config.vision_min_confidence:
            raise NoSupportedDetectionError(
                f"作物识别置信度仅 {confidence:.0%}，低于 {self.config.vision_min_confidence:.0%} 阈值，请重新拍摄"
            )
        return observation

    def analyze_uploaded_image(self, image_bytes):
        if not image_bytes:
            raise ValueError("图片内容为空")
        encoded_image = self._prepare_base64_image(image_bytes)
        payload = {
            "model": self.config.vision_model,
            "messages": [{
                "role": "user",
                "content": VISION_PROMPT,
                "images": [encoded_image],
            }],
            "format": VISION_OBSERVATION_SCHEMA,
            "stream": False,
            "think": False,
            "keep_alive": self.config.vision_keep_alive_seconds,
            "options": {
                "temperature": 0,
                "num_ctx": 2048,
                "num_predict": 384,
            },
        }

        try:
            with self.lock:
                if self.live_runtime:
                    self.live_runtime.pause_inference_for_static_analysis()
                try:
                    response = self.session.post(
                        self.config.vision_api_url,
                        json=payload,
                        timeout=self.config.vision_timeout_seconds,
                    )
                finally:
                    self._unload_model()
                    if self.live_runtime:
                        self.live_runtime.resume_inference_after_static_analysis()
            response.raise_for_status()
            body = response.json()
            content = body.get("message", {}).get("content", "")
            observation = self._normalize_observation(json.loads(content))
        except NoSupportedDetectionError:
            raise
        except self.requests.RequestException as exc:
            raise RuntimeError(f"本地 Qwen3-VL 服务不可用: {exc}") from exc
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"本地视觉模型返回格式无效: {exc}") from exc

        return {
            "success": True,
            "vision_model": self.config.vision_model,
            "observation": observation,
        }

    def close(self):
        self.session.close()


class BackendClient:
    def __init__(self, config, requests_module, stop_event, state):
        self.config = config
        self.requests = requests_module
        self.stop_event = stop_event
        self.state = state
        self.session = requests_module.Session()
        self.queue = queue.Queue(maxsize=30)
        self.threads = []

    @property
    def headers(self):
        return {"X-Edge-Api-Key": self.config.api_key} if self.config.api_key else {}

    def _registration_payload(self):
        parsed_stream = urlparse(self.config.stream_url)
        health = self.state.health()
        return {
            "user_id": self.config.user_id,
            "device_code": self.config.device_code,
            "device_name": self.config.device_name,
            "camera_model": self.config.camera_model,
            "stream_url": self.config.stream_url,
            "ip_address": parsed_stream.hostname,
            "service_port": self.config.stream_port,
            "camera_online": health["status"] == "online",
            "capabilities": [
                "water_pump",
                "uv_light",
                "realsense_camera",
                "yolo_detection",
                "local_crop_vision",
            ],
            "metadata": {
                "model_path": self.config.model_path.name,
                "model_classes": self.state.model_classes,
                "resolution": f"{self.config.width}x{self.config.height}",
                "fps": self.config.fps,
                "camera_status": health["status"],
                "camera_message": health["message"],
                "last_frame_seconds": health["last_frame_seconds"],
                "vision_model": self.config.vision_model,
            },
        }

    def register(self):
        for attempt in range(2):
            try:
                response = self.requests.post(
                    f"{self.config.backend_url}/camera/edge/register",
                    json=self._registration_payload(),
                    headers={**self.headers, "Connection": "close"},
                    timeout=self.config.request_timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                if not payload.get("success"):
                    raise RuntimeError(payload.get("message", "后端拒绝相机注册"))
                return
            except (self.requests.ConnectionError, self.requests.Timeout):
                if attempt == 0 and not self.stop_event.wait(0.35):
                    continue
                raise

    def _heartbeat_loop(self):
        while not self.stop_event.is_set():
            try:
                self.register()
            except Exception as exc:
                print(f"[相机心跳] {exc}", file=sys.stderr)
            self.stop_event.wait(self.config.heartbeat_interval_seconds)

    def enqueue_detection(self, payload):
        try:
            self.queue.put_nowait(payload)
        except queue.Full:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
            self.queue.put_nowait(payload)

    def _detection_loop(self):
        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                payload = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                response = self.session.post(
                    f"{self.config.backend_url}/camera/edge/detections",
                    json=payload,
                    headers=self.headers,
                    timeout=self.config.request_timeout_seconds,
                )
                response.raise_for_status()
                body = response.json()
                if not body.get("success"):
                    raise RuntimeError(body.get("message", "识别结果被后端拒绝"))
            except Exception as exc:
                print(f"[识别上报] {exc}", file=sys.stderr)
            finally:
                self.queue.task_done()

    def start(self):
        for target, name in (
            (self._heartbeat_loop, "camera-heartbeat"),
            (self._detection_loop, "detection-uploader"),
        ):
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self.threads.append(thread)

    def stop(self):
        for thread in self.threads:
            thread.join(timeout=self.config.request_timeout_seconds + 1)
        self.session.close()


class D435iVisionRuntime:
    def __init__(self, config, state, backend, stop_event, cv2, np, rs, yolo_class):
        self.config = config
        self.state = state
        self.backend = backend
        self.stop_event = stop_event
        self.cv2 = cv2
        self.np = np
        self.rs = rs
        self.yolo_class = yolo_class
        self.profiles = self._load_profiles()
        self.last_upload = {}
        self.model = None
        self.model_lock = threading.RLock()
        self.static_analysis_active = threading.Event()

    def _load_profiles(self):
        with self.config.profiles_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return {normalize_class_name(key): value for key, value in raw.items()}

    def _profile_for(self, class_name):
        key = normalize_class_name(class_name)
        return self.profiles.get(key) or self.profiles.get("default") or {
            "disease_name": str(class_name),
            "cause": "模型没有配置该类别的农艺资料，请由农技人员复核。",
            "severity": "unknown",
            "treatment": ["保留原图和环境数据，交由农技人员确认后再处置。"],
        }

    def _ensure_model(self):
        with self.model_lock:
            if self.model is None:
                self.model = self.yolo_class(str(self.config.model_path))
                model_names = self.model.names
                class_names = (
                    [str(model_names[index]) for index in sorted(model_names)]
                    if isinstance(model_names, dict)
                    else [str(name) for name in model_names]
                )
                self.state.set_runtime_info(model_classes=class_names)
            return self.model

    def _predict(self, source):
        with self.model_lock:
            model = self._ensure_model()
            return model.predict(
                source=source,
                conf=self.config.confidence,
                device=self.config.inference_device,
                verbose=False,
            )

    def pause_inference_for_static_analysis(self):
        self.static_analysis_active.set()
        with self.model_lock:
            self.model = None
            gc.collect()
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
            except (ImportError, RuntimeError):
                pass

    def resume_inference_after_static_analysis(self):
        self.static_analysis_active.clear()

    def _depth_at_box(self, depth_frame, xyxy):
        x1, y1, x2, y2 = [int(round(value)) for value in xyxy]
        center_x = max(0, min(self.config.width - 1, (x1 + x2) // 2))
        center_y = max(0, min(self.config.height - 1, (y1 + y2) // 2))
        samples = []
        for offset_y in (-4, -2, 0, 2, 4):
            for offset_x in (-4, -2, 0, 2, 4):
                x = max(0, min(self.config.width - 1, center_x + offset_x))
                y = max(0, min(self.config.height - 1, center_y + offset_y))
                distance = float(depth_frame.get_distance(x, y))
                if 0.05 <= distance <= 20:
                    samples.append(distance)
        return round(float(self.np.median(samples)), 3) if samples else None

    def _extract_detections(self, result, depth_frame, snapshot_url):
        detections = []
        names = result.names
        for box in result.boxes or []:
            class_id = int(box.cls[0].item())
            class_name = str(names[class_id])
            xyxy = [round(float(value), 1) for value in box.xyxy[0].tolist()]
            profile = self._profile_for(class_name)
            severity = str(profile.get("severity") or "unknown").lower()
            if severity not in {"healthy", "mild", "moderate", "severe", "unknown"}:
                severity = "unknown"
            detections.append({
                "user_id": self.config.user_id,
                "device_code": self.config.device_code,
                "class_name": class_name,
                "disease_name": str(profile.get("disease_name") or class_name),
                "cause": str(profile.get("cause") or ""),
                "severity": severity,
                "treatment": profile.get("treatment") or [],
                "confidence": round(self.config.reported_confidence, 5),
                "distance_m": self._depth_at_box(depth_frame, xyxy) if depth_frame is not None else None,
                "bbox": {"x1": xyxy[0], "y1": xyxy[1], "x2": xyxy[2], "y2": xyxy[3]},
                "image_url": snapshot_url,
                "detected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            })
        return detections

    def _enqueue_due_detections(self, detections):
        now = time.monotonic()
        for detection in detections:
            if detection["severity"] == "healthy" and not self.config.upload_healthy:
                continue
            signature = normalize_class_name(detection["class_name"])
            last = self.last_upload.get(signature, 0)
            if now - last < self.config.upload_interval_seconds:
                continue
            self.backend.enqueue_detection(detection)
            self.last_upload[signature] = now

    def _run_camera_session(self, class_names):
        pipeline = self.rs.pipeline()
        pipeline_config = self.rs.config()
        pipeline_config.enable_stream(
            self.rs.stream.depth,
            self.config.width,
            self.config.height,
            self.rs.format.z16,
            self.config.fps,
        )
        pipeline_config.enable_stream(
            self.rs.stream.color,
            self.config.width,
            self.config.height,
            self.rs.format.bgr8,
            self.config.fps,
        )

        started = False
        try:
            pipeline_profile = pipeline.start(pipeline_config)
            started = True
            camera_name = pipeline_profile.get_device().get_info(self.rs.camera_info.name)
            self.state.set_runtime_info(camera_name=camera_name)
            if self.config.strict_camera_model and "D435I" not in camera_name.upper():
                raise RuntimeError(f"检测到 {camera_name}，配置要求 Intel RealSense D435i")

            align = self.rs.align(self.rs.stream.color)
            frame_index = 0
            detections = []
            snapshot_url = self.config.stream_url.rsplit("/", 1)[0] + "/snapshot.jpg"
            print(f"[相机] 已连接 {camera_name}")
            print(f"[模型] 类别: {', '.join(class_names)}")

            while not self.stop_event.is_set():
                frames = pipeline.wait_for_frames(timeout_ms=2000)
                aligned_frames = align.process(frames)
                color_frame = aligned_frames.get_color_frame()
                depth_frame = aligned_frames.get_depth_frame()
                if not color_frame or not depth_frame:
                    self.state.set_error("D435i 未同时返回彩色帧和深度帧")
                    continue

                frame = self.np.asanyarray(color_frame.get_data())
                frame_index += 1
                output_frame = frame

                if self.static_analysis_active.is_set():
                    detections = []
                elif frame_index % self.config.inference_every_frames == 0:
                    with self.model_lock:
                        results = self._predict(frame)
                        result = results[0]
                        detections = self._extract_detections(result, depth_frame, snapshot_url)
                        output_frame = result.plot()
                        for detection in detections:
                            if detection["distance_m"] is None:
                                continue
                            bbox = detection["bbox"]
                            self.cv2.putText(
                                output_frame,
                                f"{detection['distance_m']:.2f} m",
                                (int(bbox["x1"]), max(24, int(bbox["y1"]) - 8)),
                                self.cv2.FONT_HERSHEY_SIMPLEX,
                                0.65,
                                (223, 246, 166),
                                2,
                                self.cv2.LINE_AA,
                            )
                        self._enqueue_due_detections(detections)
                        del results, result

                ok, encoded = self.cv2.imencode(
                    ".jpg",
                    output_frame,
                    [int(self.cv2.IMWRITE_JPEG_QUALITY), self.config.jpeg_quality],
                )
                if not ok:
                    self.state.set_error("JPEG 视频帧编码失败")
                    continue
                self.state.publish(encoded.tobytes(), len(detections))
        finally:
            if started:
                try:
                    pipeline.stop()
                except Exception:
                    pass

    def run(self):
        model = self._ensure_model()
        model_names = model.names
        class_names = [str(model_names[index]) for index in sorted(model_names)] if isinstance(model_names, dict) else list(model_names)
        self.state.set_runtime_info(model_classes=class_names)
        self.state.set_offline("等待 D435i 接入")

        retry_seconds = 2
        while not self.stop_event.is_set():
            try:
                self._run_camera_session(class_names)
            except Exception as exc:
                message = f"D435i 不在线，{retry_seconds} 秒后自动重试: {exc}"
                self.state.set_offline(message)
                print(f"[相机重连] {message}", file=sys.stderr)
                self.stop_event.wait(retry_seconds)


def load_runtime_dependencies():
    missing = []
    try:
        import cv2
    except ImportError:
        cv2 = None
        missing.append("opencv-python / JetPack OpenCV")
    try:
        import numpy as np
    except ImportError:
        np = None
        missing.append("numpy")
    try:
        import pyrealsense2 as rs
    except ImportError:
        rs = None
        missing.append("pyrealsense2 (librealsense2 Python bindings)")
    try:
        import requests
    except ImportError:
        requests = None
        missing.append("requests")
    try:
        from ultralytics import YOLO
    except ImportError:
        YOLO = None
        missing.append("ultralytics")
    if missing:
        raise RuntimeError("缺少运行依赖: " + ", ".join(missing))
    return cv2, np, rs, requests, YOLO


def build_parser():
    parser = argparse.ArgumentParser(description="D435i 番茄病害实时识别与 MJPEG 推流")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_FILE), help="相机配置 JSON 文件")
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="只检查配置和模型文件，不访问 D435i",
    )
    return parser


def main():
    args = build_parser().parse_args()
    try:
        config = EdgeCameraConfig.load(args.config)
        config.validate_files()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[配置错误] {exc}", file=sys.stderr)
        return 2

    if args.validate_config:
        print("[配置有效]")
        print(f"  后端: {config.backend_url}")
        print(f"  视频: {config.stream_url}")
        print(f"  相机: {config.camera_model}")
        print(f"  模型: {config.model_path}")
        print(f"  本地视觉: {config.vision_model} ({config.vision_api_url})")
        return 0

    try:
        cv2, np, rs, requests, yolo_class = load_runtime_dependencies()
    except RuntimeError as exc:
        print(f"[依赖错误] {exc}", file=sys.stderr)
        return 3

    stop_event = threading.Event()
    state = FrameState()
    backend = BackendClient(config, requests, stop_event, state)
    runtime = D435iVisionRuntime(
        config,
        state,
        backend,
        stop_event,
        cv2,
        np,
        rs,
        yolo_class,
    )
    uploaded_image_analyzer = LocalVisionAnalyzer(
        config,
        requests,
        cv2,
        np,
        live_runtime=runtime,
    )
    server = CameraHttpServer(
        (config.stream_host, config.stream_port),
        CameraRequestHandler,
        state,
        stop_event,
        uploaded_image_analyzer,
        config.api_key,
    )
    server_thread = threading.Thread(target=server.serve_forever, name="mjpeg-server", daemon=True)
    server_thread.start()
    backend.start()

    def stop_handler(_signum, _frame):
        stop_event.set()

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    print(f"[视频服务] {config.stream_url}")
    print(f"[健康检查] {config.stream_url.rsplit('/', 1)[0]}/health")
    print(f"[图片推理] {config.stream_url.rsplit('/', 1)[0]}/analyze")
    exit_code = 0
    try:
        runtime.run()
    except Exception as exc:
        state.set_error(str(exc))
        print(f"[运行错误] {exc}", file=sys.stderr)
        exit_code = 1
    finally:
        stop_event.set()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
        backend.stop()
        uploaded_image_analyzer.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
