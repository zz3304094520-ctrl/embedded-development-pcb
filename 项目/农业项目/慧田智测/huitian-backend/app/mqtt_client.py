import asyncio
import json
import logging
from typing import Any

import paho.mqtt.client as mqtt
from pydantic import ValidationError
from sqlalchemy import select

from app import models, schemas
from app.config import settings
from app.database import SessionLocal
from app.services import command_service, telemetry_service
from app.websocket_manager import websocket_manager


logger = logging.getLogger(__name__)


class MQTTManager:
    def __init__(self) -> None:
        self.connected = False
        self.started = False
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
        )
        if settings.mqtt_username:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        self.client.on_connect = self._on_connect
        self.client.on_connect_fail = self._on_connect_fail
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(min_delay=2, max_delay=30)

    def start(self, event_loop: asyncio.AbstractEventLoop) -> None:
        self._event_loop = event_loop
        if not settings.mqtt_enabled:
            logger.info("MQTT 已通过配置关闭")
            return
        try:
            self.client.connect_async(settings.mqtt_host, settings.mqtt_port, keepalive=60)
            self.client.loop_start()
            self.started = True
            logger.info("MQTT 后台连接已启动：%s:%s", settings.mqtt_host, settings.mqtt_port)
        except Exception:
            logger.warning("MQTT 启动失败，REST API 仍可使用", exc_info=True)

    def stop(self) -> None:
        if not self.started:
            return
        try:
            self.client.disconnect()
            self.client.loop_stop()
        finally:
            self.connected = False
            self.started = False

    def _on_connect(
        self,
        client: mqtt.Client,
        _userdata: Any,
        _flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            logger.warning("MQTT 连接被拒绝：%s", reason_code)
            self.connected = False
            return
        self.connected = True
        prefix = settings.mqtt_topic_prefix
        client.subscribe(
            [
                (f"{prefix}/+/telemetry", 1),
                (f"{prefix}/+/status", 1),
                (f"{prefix}/+/command_ack", 1),
            ]
        )
        logger.info("MQTT 已连接并完成主题订阅")

    def _on_connect_fail(self, _client: mqtt.Client, _userdata: Any) -> None:
        self.connected = False
        logger.warning("MQTT Broker 暂不可用，后台将继续重试；REST API 不受影响")

    def _on_disconnect(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        _disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        self.connected = False
        if self.started:
            logger.warning("MQTT 连接断开：%s", reason_code)

    def _on_message(
        self, _client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        # Paho 的回调运行在独立线程。这里为每条消息创建独立数据库会话，
        # 并通过 run_coroutine_threadsafe 把 WebSocket 广播提交回 FastAPI 事件循环。
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            parts = message.topic.split("/")
            if len(parts) != 3:
                raise ValueError("MQTT 主题格式错误")
            _, device_code, event_name = parts
            if event_name == "telemetry":
                payload.setdefault("device_code", device_code)
                self._handle_telemetry(payload)
            elif event_name == "status":
                self._handle_status(device_code, payload)
            elif event_name == "command_ack":
                self._handle_command_ack(payload)
        except (ValueError, json.JSONDecodeError, ValidationError):
            logger.warning("忽略无效 MQTT 消息：topic=%s", message.topic, exc_info=True)
        except Exception:
            logger.exception("处理 MQTT 消息失败：topic=%s", message.topic)

    def _handle_telemetry(self, raw_payload: dict[str, Any]) -> None:
        payload = schemas.TelemetryCreate.model_validate(raw_payload)
        with SessionLocal() as db:
            device, readings, alerts = telemetry_service.ingest_telemetry(db, payload)
            for reading in readings:
                self._broadcast(
                    "telemetry.created",
                    {
                        "device_code": device.device_code,
                        "metric": reading.metric,
                        "value": reading.value,
                        "unit": reading.unit,
                    },
                )
            for alert in alerts:
                self._broadcast(
                    "alert.created",
                    {"id": alert.id, "severity": alert.severity, "message": alert.message},
                )

    def _handle_status(self, device_code: str, payload: dict[str, Any]) -> None:
        is_online = bool(payload.get("is_online", True))
        with SessionLocal() as db:
            device = db.scalar(select(models.Device).where(models.Device.device_code == device_code))
            if not device:
                logger.warning("收到未知设备的状态消息：%s", device_code)
                return
            device.is_online = is_online
            device.last_seen_at = models.utc_now()
            db.commit()
        self._broadcast(
            "device.status_changed",
            {"device_code": device_code, "is_online": is_online},
        )

    def _handle_command_ack(self, payload: dict[str, Any]) -> None:
        command_id = int(payload["command_id"])
        ack = schemas.CommandAck.model_validate({"status": payload["status"]})
        with SessionLocal() as db:
            command = command_service.update_command_status(db, command_id, ack.status)
            self._broadcast(
                "command.status_changed",
                {"id": command.id, "status": command.status},
            )

    def _broadcast(self, event: str, data: dict[str, Any]) -> None:
        if self._event_loop and self._event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                websocket_manager.broadcast(event, data), self._event_loop
            )

    def publish_command(self, device_code: str, command: models.DeviceCommand) -> bool:
        if not self.connected:
            return False
        topic = f"{settings.mqtt_topic_prefix}/{device_code}/command"
        payload = json.dumps(
            {
                "command_id": command.id,
                "command_type": command.command_type,
                "parameters": command.parameters_json,
            },
            ensure_ascii=False,
        )
        result = self.client.publish(topic, payload, qos=1)
        return result.rc == mqtt.MQTT_ERR_SUCCESS

    @property
    def status_text(self) -> str:
        if not settings.mqtt_enabled:
            return "disabled"
        return "connected" if self.connected else "disconnected"


mqtt_manager = MQTTManager()

