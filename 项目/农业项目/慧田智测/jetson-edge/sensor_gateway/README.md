# Jetson RS485 传感器网关

该服务从 Jetson 本地 USB-RS485 读取真实传感器数据，并上报到现有 FastAPI：

```text
传感器 -> Modbus RTU -> Jetson 172.20.10.4
       -> POST http://172.20.10.2:8000/api/v1/telemetry
```

气象站 `SN-3003-FSXCS-MD1` 使用 `4800bps / 8N1 / slave 1`，上报空气温度、空气湿度、光照和雨量。土壤探头铭牌启用了温度、水分、EC、氮、磷、钾和 RS485；现场已验证驱动按 `9600bps / 8N1 / slave 1` 读取 `0x0000..0x0005`，六个寄存器依次为温度、水分、EC、氮、磷、钾。

同一气象RS485总线还支持两只独立传感器：

- `ZTS-3000-FSJT-N01` 三杯式风速：`4800bps / 8N1 / slave 2`，读取 `0x0000`，数值除以10得到 `m/s`。
- `SN-3000-FXJT-N01` 八方位风向：`4800bps / 8N1 / slave 3`，读取 `0x0000..0x0001`，第二个寄存器为0、45、90……315度。

两只新设备出厂地址通常都是1。并入现有总线前必须逐只单独连接，先把风速地址改为2、风向地址改为3；地址重复时禁止并联。三只设备的棕线接10-30V正极、黑线接电源负极、黄（绿）线接485-A、蓝线接485-B。传感器电源负极与USB-RS485转换器参考地按转换器说明可靠连接。

本地单次验证：

```bash
cd /home/qiongyi/fieldmate-edge
.venv/bin/python -m sensor_gateway --config sensor_gateway/config.json --once --verbose
```

安装 systemd 服务需要管理员权限：

```bash
sudo cp sensor_gateway/huitian-sensor-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl disable --now fieldmate-edge.service 2>/dev/null || true
sudo systemctl enable --now huitian-sensor-agent.service
```

查看状态：

```bash
systemctl status huitian-sensor-agent.service --no-pager
journalctl -u huitian-sensor-agent.service -f
```

两只 CH340 的 USB serial 相同，当前只能按物理 USB 插口形成的 `/dev/serial/by-path/` 区分。更换插口后需要同步更新 `config.json`。
