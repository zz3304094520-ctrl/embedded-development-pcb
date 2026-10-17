# 慧田智测 Jetson HTTP 继电器 Agent 技术规格

## 目标

在 Jetson Orin Nano 上运行单进程 Agent，通过 HTTP 轮询慧田智测后端，并通过 USB CDC 串口控制双路继电器：

- CH1 固定映射 `pump-001`（水泵）。
- CH2 固定映射 `grow-light-001`（植物补光灯）。
- 后端部署地址只允许通过 `RELAY_API_BASE_URL` 环境变量提供；部署示例为 `http://172.20.10.2:8000`。
- 明确拒绝遗留地址 `192.168.10.77`。

## 硬件协议

- 串口：115200 baud、8 data bits、no parity、1 stop bit、no flow control。
- 默认设备：`/dev/serial/by-id/usb-STMicroelectronics_STM32_Virtual_ComPort_in_FS_Mode_7E7A69E21138-if00`。
- 帧格式：`A0 channel operation checksum`，checksum 为前三个字节之和的低 8 位。
- operation：`00=OFF`、`01=ON`、`02=QUERY`。
- QUERY ALL：`A0 0F 02 B1`，响应必须包含 `CH1:ON|OFF` 和 `CH2:ON|OFF`。

## HTTP API Contract

Agent 不创建后端资源，只调用：

- `GET /api/v1/devices`：解析预先创建的 `pump-001` 与 `grow-light-001`。
- `GET /api/v1/commands?device_id=...&status_filter=...`：读取 `pending` 或遗留 `acknowledged` 命令。
- `POST /api/v1/commands/{id}/ack`：状态只能为 `acknowledged`、`succeeded` 或 `failed`。
- `POST /api/v1/devices/{device_code}/heartbeat`：动作后回报 `actuator_state`。

## 状态机

1. 正常模式启动时先强制两路 OFF，再解析设备并把遗留 `acknowledged` 命令标记为 `failed`。
2. 每条 pending 命令必须先 ACK 为 `acknowledged`，成功后才允许操作硬件。
3. ON 命令建立本地 `time.monotonic()` deadline，不阻塞事件循环；两个通道可同时计时。
4. deadline 到期时执行 OFF、heartbeat=`off`，再把原 ON 命令 ACK 为 `succeeded`。
5. OFF 命令可在 ON 计时期间紧急停止；被停止的 ON 命令与 OFF 命令均结束为 `succeeded`。
6. 已 ACK 的命令执行异常时，Agent 尝试强制两路 OFF，并将相关命令标记为 `failed`。
7. 进程退出时强制两路 OFF；仍在计时的 ON 命令标记为 `failed`。
8. `RELAY_DRY_RUN=true` 时保留完整 HTTP 状态机，但串口 ON/OFF 只记录日志、不写硬件。

## CLI

- 默认：持续轮询并运行状态机。
- `--once`：读取一次 pending 命令；若启动了定时任务，继续轮询紧急 OFF 直到这些任务结束后退出。
- `--probe`：只向串口发送 QUERY ALL，不访问后端、不创建资源、不发送 ON/OFF。

## 验收标准

- 单元测试验证精确串口帧、QUERY 解析、旧 IP 拒绝、双通道并行 deadline、紧急 OFF、异常关断、启动恢复和退出关断。
- 代码与示例配置中不存在 `192.168.10.77`，仅拒绝逻辑和文档说明允许出现该字符串。
- 默认 dry-run，且本地测试不需要真实串口、真实 HTTP 服务或 Jetson。
- systemd 使用 `dialout` 补充组，SIGTERM 能进入清理逻辑。
