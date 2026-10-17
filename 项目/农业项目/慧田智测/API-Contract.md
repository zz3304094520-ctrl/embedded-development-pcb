# 慧田智测 API Contract（管理后台使用范围）

Base URL：开发环境同源代理 `/api/v1`；后端直连 `http://172.20.10.2:8000/api/v1`。请求与响应为 JSON，诊断上传除外。

## 运行状态

- `GET /health`：返回 `status`、`database`、`mqtt`、`timestamp`。HTTP-only 下 `mqtt=disabled` 是正常状态。

## 基础资源

- Farms：`GET/POST /farms`，`GET/PUT/DELETE /farms/{id}`。
- Plots：`GET/POST /plots`，`GET/PUT/DELETE /plots/{id}`；列表可传 `farm_id`。
- Devices：`GET/POST /devices`，`GET/PUT/DELETE /devices/{id}`；列表可传 `plot_id`、`is_online`。
- 新建设备 payload：`plot_id`、`device_code`、`name`、`device_type`、`communication_type="http"`。
- `POST /devices/{device_code}/heartbeat`：HTTP 设备心跳；执行器可携带 `{ "actuator_state": "on|off|unknown" }`。
- `DeviceResponse` 对执行器返回 `actuator_state` 和 `state_updated_at`；传感器默认返回 `unknown/null`。

## 数据与告警

- `GET /telemetry?plot_id=&device_id=&limit=`：最近传感器读数。
- `GET /telemetry/summary/{plot_id}`：地块指标摘要。
- `POST /telemetry`：Jetson/HTTP 网关上报，payload 含 `device_code`、带时区的 `recorded_at`、`readings[]`。
- `GET/POST /alerts/rules`，`PUT/DELETE /alerts/rules/{id}`：告警规则。
- `GET /alerts?status_filter=&severity=`：告警列表。
- `POST /alerts/{id}/acknowledge`、`POST /alerts/{id}/resolve`：状态处置。

## 命令与诊断

- `GET/POST /commands`：命令列表与创建；当前交付包支持 `pump_on`、`pump_off`、`light_on`、`light_off`。
- `POST /commands/{id}/ack`：Jetson 回传 `acknowledged|succeeded|failed`，并可携带 `actuator_state` 同步继电器状态。
- `GET /diagnosis?plot_id=`：诊断记录；`POST /diagnosis` 使用 multipart 上传。

### 继电器命令约束

- `pump_on` → CH1 开，必须传 `parameters.duration_seconds`；到时 CH1 关。
- `pump_off` → CH1 关。
- `light_on` → CH2（作物补光灯）开，必须传 `parameters.duration_seconds`；到时 CH2 关。
- `light_off` → CH2 关。
- Jetson 使用 `GET /commands?device_id={id}&status_filter=pending` 获取待执行命令。
- `pump_*` 只能发送给 `device_type=pump`，`light_*` 只能发送给 `device_type=grow_light`；不匹配返回 `409`。
- `pump_on/light_on` 的 `duration_seconds` 必须是 `1..300` 的整数；前端传入 `channel/relay` 等通道参数返回 `422`。
- `pump_off/light_off` 不接受执行参数，并允许作为正在运行任务的紧急停止命令。

## 错误约定

- `404`：资源不存在。
- `409`：重复编码或资源存在关联数据，禁止删除。
- `422`：请求字段校验失败。
- 前端优先展示响应 `detail`；无法解析时展示 HTTP 状态与重试建议。

## D435i 相机边缘接口

以下两个接口保留在根路径，以兼容 Jetson 上已有 `fieldmate-camera.service`：

- `POST /camera/edge/register`：注册/刷新相机在线状态和 MJPEG 地址。请求包含 `device_code`、`device_name`、`camera_model`、`stream_url`、`camera_online`、`capabilities`、`metadata`；返回 `{ "success": true, "device_id": number }`。
- `POST /camera/edge/detections`：接收单条 YOLO 结构化结果。请求包含 `device_code`、`class_name`、`disease_name`、`cause`、`severity`、`treatment[]`、`confidence`、`distance_m`、`bbox`、`image_url`、`detected_at`；不接收图片二进制。
- 当前 Jetson 将上报字段 `confidence` 固定为演示值 `0.905`，后端不再改写；该字段不代表模型真实概率。

H5 查询接口：

- `GET /api/v1/detections?plot_id=&device_id=&limit=`：按检测时间倒序返回病害结果，`limit` 范围 `1..200`。
- `DeviceResponse` 对相机增加可选 `camera_model` 与 `stream_url`；非相机设备返回 `null`。
- 相机热插拔复用同一个 `device_code` 和 `stream_url`：拔出时上报 `camera_online=false`，插入并恢复出帧后上报 `camera_online=true`；两次注册都广播 `camera.status_changed` WebSocket 事件。

## RS485 真实传感器接口

Jetson 继续复用 `http://172.20.10.2:8000/api/v1`，不新增网络监听端口。

### 批量上报采样

`POST /telemetry`

```json
{
  "device_code": "weather-001",
  "recorded_at": "2026-07-23T02:30:00+08:00",
  "readings": [
    { "metric": "air_temperature", "value": 25.2, "unit": "celsius", "quality": "good" },
    { "metric": "air_humidity", "value": 44.0, "unit": "percent", "quality": "good" },
    { "metric": "illumination", "value": 6, "unit": "lux", "quality": "good" },
    { "metric": "rainfall", "value": 0, "unit": "millimeter", "quality": "good" }
  ]
}
```

- `device_code` 必须已存在；当前固定使用 `weather-001` 和 `soil-001`。
- `recorded_at` 必须带时区；Agent 使用现场采样完成时刻。
- `readings` 长度为 `1..100`，`quality` 仅允许 `good | suspect | bad`。
- 一次成功采样的所有已验证指标使用同一个 `recorded_at` 批量上报。
- 当前气象指标为 `air_temperature/celsius`、`air_humidity/percent`、`illumination/lux`、`rainfall/millimeter`。
- 土壤指标仅在协议确认后启用；预留标准名称为 `soil_temperature/celsius`、`soil_moisture/percent`、`soil_ec/microsiemens_per_centimeter`、`soil_ph/ph`、`soil_nitrogen|soil_phosphorus|soil_potassium/milligram_per_kilogram`。
- 未确认的寄存器不得用候选名称上报，也不得以 `0` 代替无数据。

### 报告传感器离线状态

`POST /devices/{device_code}/status`

请求：

```json
{ "is_online": false }
```

响应：

```json
{
  "device_code": "soil-001",
  "is_online": false,
  "last_seen_at": null
}
```

- `false` 不改写最后成功采样时间；设备不存在返回 `404`。
- `true` 可用于设备恢复但尚未产生读数的状态报告，并更新 `last_seen_at`；正常恢复优先由首条 telemetry 自动置在线。
- 状态变化广播 `device.status_changed`；重复上报相同状态仍返回 `200`，但不要求前端显示成新读数。

### H5 查询与实时事件

- `GET /telemetry/latest/{device_code}`：返回该设备每个指标的最新一条读数。
- `GET /telemetry?plot_id=&device_id=&metric=&limit=`：按时间倒序返回读数，H5 以 `device_id + metric` 去重形成当前值。
- `telemetry.created` 事件包含 `device_code`、`metric`、`value`、`unit`。
- `device.status_changed` 事件至少包含 `device_code` 与 `is_online`。
