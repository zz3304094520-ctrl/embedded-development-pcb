# Jetson HTTP 双路继电器 Agent

该 Agent 只使用 HTTP 与慧田智测后端通信，并独占 USB CDC 继电器：CH1=`pump-001`，CH2=`grow-light-001`。串口固定为 115200 8N1，默认使用设备序列号生成的 `/dev/serial/by-id/...` 路径。

## 安全约束

- 默认 `RELAY_DRY_RUN=true`：完整执行 HTTP 命令状态机，但 ON/OFF 仅记录日志，不写串口。它会消费并 ACK 后端命令，不能把 dry-run 当只读模式。
- `--probe` 才是硬件只读诊断：仅发送 `A0 0F 02 B1` QUERY，不访问后端、不创建资源、不发送 ON/OFF。
- Agent 不会创建 farm、plot 或 device；后端必须预先存在 `pump-001`（`device_type=pump`）与 `grow-light-001`（`device_type=grow_light`）。
- 启动本服务前必须停用旧 `fieldmate-edge.service`。unit 也声明了 `Conflicts=fieldmate-edge.service`，防止两个服务同时占用串口。
- 实机首次测试时，先物理断开水泵、灯具和全部负载线，只保留 USB 继电器。

## 部署

将本目录复制成 Jetson 上的 package：

```bash
mkdir -p /home/qiongyi/huitian-relay-gateway
cp -r relay_gateway /home/qiongyi/huitian-relay-gateway/
cd /home/qiongyi/huitian-relay-gateway
python3 -m venv .venv
.venv/bin/pip install -r relay_gateway/requirements.txt
sudo cp relay_gateway/.env.example /etc/huitian-relay-agent.env
sudo chmod 600 /etc/huitian-relay-agent.env
```

先保持 `/etc/huitian-relay-agent.env` 中 `RELAY_DRY_RUN=true`，确认新后端为 `http://172.20.10.2:8000`。不要从旧服务复制后端地址。

也可以在包已复制到 `/home/qiongyi/huitian-relay-gateway` 后，一次性安装
Python 依赖、systemd 服务和 udev 热插拔规则：

```bash
cd /home/qiongyi/huitian-relay-gateway
sudo bash relay_gateway/install_jetson.sh
```

只查询继电器状态：

```bash
cd /home/qiongyi/huitian-relay-gateway
sudo -u qiongyi -g qiongyi env \
  RELAY_PORT=/dev/serial/by-id/usb-STMicroelectronics_STM32_Virtual_ComPort_in_FS_Mode_7E7A69E21138-if00 \
  RELAY_BAUD_RATE=115200 \
  .venv/bin/python -m relay_gateway --probe
```

期望输出同时包含 `CH1` 和 `CH2`。确认负载仍未连接后，再安装服务：

```bash
sudo systemctl disable --now fieldmate-edge.service
sudo cp relay_gateway/huitian-relay-agent.service /etc/systemd/system/
sudo cp relay_gateway/huitian-relay-hotplug.service /etc/systemd/system/
sudo cp relay_gateway/99-huitian-relay.rules /etc/udev/rules.d/
sudo systemctl daemon-reload
sudo udevadm control --reload-rules
sudo systemctl enable --now huitian-relay-agent.service
sudo journalctl -u huitian-relay-agent.service -f
```

`99-huitian-relay.rules` 只匹配序列号为 `7E7A69E21138` 的 STM32
继电器。继电器插入或重新插入时，systemd 会自动启动或重启 Agent，
无需手动执行重启命令。Agent 运行期间还会定期发送只读 QUERY，
拔出后主动上报水泵和补光灯离线；服务每 3 秒持续重试，重新插入后
自动强制两路 OFF、恢复心跳并继续接收新命令。

验证 HTTP 流程后，停止服务，把 `RELAY_DRY_RUN` 改为 `false`，仍在无负载状态下分别做短时 CH1/CH2 命令测试。确认 COM-NO 行为正确后才能接入独立供电的实际负载。

## 命令生命周期

Agent 先把 pending 命令 ACK 为 `acknowledged`，之后才操作继电器。ON 使用本地 monotonic deadline，因此两路可同时计时，并可随时处理 OFF。deadline 到期或收到 OFF 后，先关继电器并 heartbeat=`off`，再 ACK `succeeded`。任何异常都会尝试强制两路 OFF 并 ACK `failed`；进程退出也执行同样的失效保护。
