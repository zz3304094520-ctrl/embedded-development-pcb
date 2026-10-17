# 慧田智测后端 MVP

这是一个面向番茄智慧种植场景的可运行后端，使用 Python、FastAPI、SQLite、REST API、WebSocket 和可选 MQTT。即使没有 MQTT Broker 和真实硬件，也可以通过 HTTP 设备模拟器完整演示数据上报、告警和控制命令。

## 1. 功能

- 农场、地块和设备管理。
- HTTP 与 MQTT 传感器数据接入。
- 最新数据、历史数据和地块汇总查询。
- 阈值告警规则、告警确认和解决。
- 水泵、补光灯控制命令。
- WebSocket 实时消息。
- 图片上传与“演示诊断结果”。
- Swagger 和 ReDoc 文档。
- 独立设备模拟器。
- pytest 自动化测试。

## 2. 架构

```text
UniApp / Postman ──REST──> FastAPI ──> SQLite
       │                    │
       └──WebSocket<────────┤
                            │
设备/边缘网关 ──HTTP/MQTT───┘
       │
RS485/Modbus（后续在独立网关进程中接入）
```

采用模块化单体：路由负责 HTTP 参数和响应，service 负责主要业务逻辑，SQLAlchemy 负责 SQLite，MQTT 在后台线程连接。MQTT 不可用时不会影响 REST API。

## 3. 项目结构

```text
huitian-backend/
├─ app/
│  ├─ main.py                    # FastAPI 入口、路由注册、WebSocket
│  ├─ config.py                  # .env 配置
│  ├─ database.py                # SQLite 和 SQLAlchemy 会话
│  ├─ models.py                  # 数据库模型
│  ├─ schemas.py                 # 请求和响应校验模型
│  ├─ dependencies.py            # 数据库依赖
│  ├─ mqtt_client.py             # 可选 MQTT 后台客户端
│  ├─ websocket_manager.py       # WebSocket 连接和广播
│  ├─ routers/                   # REST API 路由
│  └─ services/                  # 业务逻辑
├─ device_gateway/
│  ├─ config.py                  # 模拟器配置
│  └─ simulator.py               # HTTP/MQTT 设备模拟器
├─ scripts/
│  ├─ init_demo_data.py          # 幂等初始化演示数据
│  └─ demo_flow.py               # 自动端到端演示
├─ tests/                        # 独立测试数据库和自动化测试
├─ postman/                      # 可导入的 Collection 和环境
├─ data/                         # SQLite 数据库目录
├─ uploads/                      # 上传图片目录
├─ .env.example
├─ requirements.txt
├─ start.ps1
├─ run_tests.ps1
└─ README.md
```

## 4. 环境要求

推荐 Python 3.12。

```powershell
python --version
```

如果显示的不是 3.11 或 3.12，可检查常规安装路径或 Codex 自带运行时：

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" --version
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" --version
```

## 5. Windows 一键启动

在 PowerShell 中执行：

```powershell
cd "F:\workspace\智慧农业\huitian-backend"
Set-ExecutionPolicy -Scope Process Bypass
.\start.ps1
```

脚本会创建 `.venv`、安装依赖、复制 `.env`、初始化演示数据并启动服务。

启动后访问：

- Swagger：[http://172.20.10.5:8000/docs](http://172.20.10.5:8000/docs)
- ReDoc：[http://172.20.10.5:8000/redoc](http://172.20.10.5:8000/redoc)
- 健康检查：[http://172.20.10.5:8000/api/v1/health](http://172.20.10.5:8000/api/v1/health)

看到 MQTT 连接失败的日志是正常的，REST API 仍可使用。

## 6. 手动启动

```powershell
cd "F:\workspace\智慧农业\huitian-backend"
$python = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (-not (Test-Path $python)) {
    $python = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
}
& $python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python scripts\init_demo_data.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

SQLite 文件位于 `data/huitian.db`。首次启动会自动建表。

## 7. 运行自动演示

先保持 FastAPI 窗口运行，再打开另一个 PowerShell：

```powershell
cd "F:\workspace\智慧农业\huitian-backend"
.\.venv\Scripts\Activate.ps1
python scripts\demo_flow.py
```

脚本会检查服务、上报正常数据、上报告警数据、查询告警并创建水泵命令。

## 8. 设备模拟器

默认 HTTP 模式，不需要 MQTT：

```powershell
cd "F:\workspace\智慧农业\huitian-backend"
.\.venv\Scripts\Activate.ps1
python -m device_gateway.simulator
```

每 5 秒上报一次。按 `Ctrl+C` 停止。设备不存在时，模拟器会自动创建农场、地块和设备。

模拟土壤设备：

```powershell
$env:GATEWAY_DEVICE_CODE="soil-001"
python -m device_gateway.simulator
```

更改间隔：

```powershell
$env:GATEWAY_INTERVAL_SECONDS="2"
python -m device_gateway.simulator
```

## 9. MQTT 可选启用

当前项目固定使用 HTTP 通信，`MQTT_ENABLED=false`；MQTT 配置仅保留交付包兼容字段。

安装并启动任意 MQTT Broker（例如 Mosquitto 或 EMQX）后，在 `.env` 中设置：

```text
MQTT_ENABLED=true
MQTT_HOST=172.20.10.5
MQTT_PORT=1883
```

运行 MQTT 模拟器：

```powershell
$env:GATEWAY_MODE="mqtt"
$env:GATEWAY_DEVICE_CODE="weather-001"
python -m device_gateway.simulator
```

主题：

```text
huitian/{device_code}/telemetry
huitian/{device_code}/status
huitian/{device_code}/command
huitian/{device_code}/command_ack
```

未来接入 RS485/Modbus 时，在 `device_gateway/simulator.py` 的 `read_modbus_registers()` 中使用 `pymodbus` 读取寄存器，再复用 HTTP 或 MQTT 上报代码。串口采集不应放入 FastAPI 主进程。

## 10. WebSocket

地址：

```text
ws://172.20.10.5:8000/ws
```

服务会推送 `telemetry.created`、`alert.created`、`device.status_changed` 和 `command.status_changed`。连接后服务首先发送：

```json
{
  "event": "system.connected",
  "data": {
    "message": "WebSocket 连接成功"
  }
}
```

## 11. 自动测试

测试使用 `tests/test_huitian.db`，不会污染正式数据库。

```powershell
cd "F:\workspace\智慧农业\huitian-backend"
.\run_tests.ps1
```

或：

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

## 12. Postman

导入以下两个文件：

- `postman/Huitian_Backend.postman_collection.json`
- `postman/Local.postman_environment.json`

选择“慧田智测本地环境”，按编号顺序执行。Collection 会自动保存新建的 `farm_id`、`plot_id`、`device_id` 和 `alert_id`。

### 示例 1：创建农场

- Method：`POST`
- URL：`http://172.20.10.5:8000/api/v1/farms`
- Header：`Content-Type: application/json`
- Body：raw JSON

```json
{
  "name": "Postman 番茄农场",
  "location": "上海市金山区",
  "description": "接口测试"
}
```

预期：HTTP 201，返回包含 `id`、`name` 和 `created_at`。

### 示例 2：创建地块

- Method：`POST`
- URL：`http://172.20.10.5:8000/api/v1/plots`
- Header：`Content-Type: application/json`

```json
{
  "farm_id": 1,
  "name": "A1 番茄田",
  "crop_type": "番茄",
  "area": 3.5
}
```

预期：HTTP 201。

### 示例 3：创建设备

- Method：`POST`
- URL：`http://172.20.10.5:8000/api/v1/devices`
- Header：`Content-Type: application/json`

```json
{
  "plot_id": 1,
  "device_code": "postman-weather-001",
  "name": "Postman 气象仪",
  "device_type": "weather_station",
  "communication_type": "http"
}
```

预期：HTTP 201。重复 `device_code` 返回 HTTP 409。

### 示例 4：上报数据

- Method：`POST`
- URL：`http://172.20.10.5:8000/api/v1/telemetry`
- Header：`Content-Type: application/json`

```json
{
  "device_code": "postman-weather-001",
  "recorded_at": "2026-06-18T08:00:00Z",
  "readings": [
    {
      "metric": "air_temperature",
      "value": 35.5,
      "unit": "celsius",
      "quality": "good"
    },
    {
      "metric": "air_humidity",
      "value": 72,
      "unit": "percent",
      "quality": "good"
    }
  ]
}
```

预期：

```json
{
  "device_code": "postman-weather-001",
  "saved_count": 2,
  "alert_count": 0,
  "readings": []
}
```

真实响应的 `readings` 会包含两条完整记录。如果已创建高温规则，`alert_count` 会大于 0。

### 示例 5：查询最新数据

- Method：`GET`
- URL：`http://172.20.10.5:8000/api/v1/telemetry/latest/postman-weather-001`
- Body：无

预期：HTTP 200，按指标返回最新值。

### 示例 6：创建告警规则

- Method：`POST`
- URL：`http://172.20.10.5:8000/api/v1/alerts/rules`
- Header：`Content-Type: application/json`

```json
{
  "plot_id": 1,
  "name": "高温规则",
  "metric": "air_temperature",
  "operator": "gt",
  "threshold": 32,
  "severity": "warning",
  "enabled": true,
  "message": "空气温度过高"
}
```

预期：HTTP 201。

### 示例 7：查询告警

- Method：`GET`
- URL：`http://172.20.10.5:8000/api/v1/alerts`
- Body：无

预期：HTTP 200，返回数组。

### 示例 8：创建控制命令

- Method：`POST`
- URL：`http://172.20.10.5:8000/api/v1/commands`
- Header：`Content-Type: application/json`

```json
{
  "device_id": 1,
  "command_type": "pump_on",
  "parameters": {
    "duration_seconds": 30
  }
}
```

MQTT 未连接时仍返回 HTTP 201，状态为 `pending`。

### 示例 9：上传诊断图片

- Method：`POST`
- URL：`http://172.20.10.5:8000/api/v1/diagnosis`
- Body：`form-data`
- 文本字段：`plot_id=1`
- 文件字段：`image`，选择 jpg、jpeg、png 或 webp

预期：HTTP 201。返回结果会明确标记为演示结果，不代表真实 AI 诊断。

## 13. 删除规则

为防止误删历史数据：

- 农场下有地块时不能删除。
- 地块下有设备、规则或诊断记录时不能删除。
- 设备有传感器数据、告警或命令时不能删除。
- 已产生告警的规则不能删除，可将 `enabled` 改为 `false`。

接口会返回 HTTP 409 和中文原因。

## 14. 常见问题

### PowerShell 禁止执行脚本

仅对当前窗口临时放行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### 找不到 Python

安装 Python 3.12，并勾选 Add Python to PATH；在 Codex 环境中也可以使用自带解释器：

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" --version
```

### 8000 端口被占用

查找进程：

```powershell
Get-NetTCPConnection -LocalPort 8000
```

临时改端口：

```powershell
uvicorn app.main:app --reload --port 8001
```

### MQTT Broker 未启动

健康接口中的 MQTT 会显示 `disconnected`，日志会提示后台重试。这不影响 Swagger、SQLite、REST、WebSocket 和 HTTP 模拟器。

如果暂时完全不使用 MQTT，将 `.env` 改为：

```text
MQTT_ENABLED=false
```

### SQLite 数据库被占用

先停止所有 Uvicorn、测试和模拟器进程，再重试。不要在服务运行时手工删除 `data/huitian.db`。

## 15. 当前限制

- SQLite 适合单机演示和早期试点，不适合大量设备高并发写入。
- 告警是基础阈值判断，没有持续时间、迟滞和去重。
- 没有用户登录和权限控制。
- 图片诊断是明确标记的演示结果，不是真实 AI。
- MQTT 开发配置未启用 TLS 和设备级 ACL。

下一阶段建议按实际设备数量和试点数据逐步增加：JWT/RBAC、Alembic 迁移、告警迟滞与冷却、MQTT TLS/ACL、PostgreSQL/TimescaleDB、真实 Modbus 寄存器映射和经过验证的 AI 模型。
