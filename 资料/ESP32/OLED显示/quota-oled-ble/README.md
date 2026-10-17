# 蓝牙 OLED 额度显示

电脑每 60 秒读取同一 Codex 账户的五小时和周剩余额度，通过 BLE 发送到 ESP32-S3。画面保留 USB 版的四行布局和北京时间重置日期。“重置”标签同步使用加宽字距和专用“置”点阵，此排版已通过 USB 实物显示确认。电脑通过本地已登录的 Codex CLI 读取额度；ESP32 只接收显示像素，没有账户凭据。

当前板内默认是 USB 开机模式：通电后约 1 秒先亮屏，显示四行额度等待画面（数据为 `--`），无需电脑运行。此行为已通过硬件复位及用户实际断电重接确认。BLE 接收代码保留，但当前不会自动开启蓝牙。

## 日常使用（板内已配置 BLE 时）

当前从 USB 开机模式改回 BLE，需要停止电脑的 USB 显示程序，保留数据线连接，再执行 `python deploy_device.py --port COM12 --mode ble`。该设置保存在板内，之后启动蓝牙电脑程序即可。此前蓝牙开启存在欠压复位，尚未验证无线显示；`启动蓝牙显示.cmd` 本身只启动电脑发送程序，不会改写板内模式。

1. ESP32 接 USB 充电器、充电宝或电脑 USB 供电，保留 OLED 的 GPIO7/SDA、GPIO8/SCL、3.3V 和 GND 接线。
2. 电脑开启蓝牙并联网，双击 `启动蓝牙显示.cmd`。程序在后台运行，自动寻找 `CodexOLED-DD48` 并核对设备身份，无需在 Windows 设置中手动配对。
3. 额度每 60 秒刷新。蓝牙断线时每 10 秒重试；实际扫描和连接会增加等待时间。ESP32 重启后先显示等待画面，再启动 BLE，重连后恢复额度画面。
4. 双击 `停止蓝牙显示.cmd` 停止电脑程序。电脑休眠、关机或离开蓝牙范围后，屏幕保留最后数据，超过 150 秒未更新时显示 `OLD`。电脑读取额度失败时，画面在重置时间后显示“旧”。

电脑重启后需要手动启动一次，未设置 Windows 登录时自启动。电脑仍需要运行，蓝牙只替代电脑与 ESP32 之间的数据线。

开发板需要通过自身 USB-C 口获得稳定供电。若启动日志出现 `Brownout detector was triggered`，表示欠压重启，蓝牙广播无法稳定运行；应检查实际供电、USB 线和接触，排除外接串口模块供电或控制线的影响。不能依靠关闭欠压检测解决供电问题。

本次安装状态：官方固件及开机文件均已写入并校验；此前蓝牙开启时发生欠压重启，降到 80 MHz 后情况相同，因此尚未验证无线显示。后续 USB 排查确认 GPIO7、GPIO8 空载可正常上拉。完全断电并重新接线后，USB 额度显示已恢复：额度读取正常，全部 OLED 数据得到应答，用户确认四行文字可见。当前 USB 程序每 60 秒自动刷新。新的开机程序先点亮 OLED，默认 USB 等待模式；用户确认断电重接可自动亮屏。此前 USB 恢复后尚未复测蓝牙；2026-10-12 的后续复测结果见下文。BLE 接收代码仍保留在板内。USB 版本与原始固件备份完整保留。`firmware/install_status.json` 保存各次测试及当前结果。

2026-10-12 蓝牙复测：BLE 模式已写入并校验，但蓝牙初始化触发欠压复位。用户改为开发板 USB-C 供电、断开外接转串口模块后，电脑仍未发现广播；电脑蓝牙能扫描到其他设备。通过已核对身份的 ESP32 串口临时关闭 OLED 显示输出，再单独开启 BLE，仍然复位。目前已恢复 USB 开机模式和 USB 自动额度刷新，待根据当前实物接线进一步确认供电路径。`runtime/enable_ble_boot.log`、`runtime/ble_usb_c_boot.log`、`runtime/ble_oled_off_probe.log` 保存各次启动日志。

同日进一步对照：OLED 显示输出关闭时，单独启动 Wi-Fi（没有执行联网或扫描命令）也直接出现 `Brownout detector was triggered` 并复位。这支持检查无线启动时共用的供电路径；尚未测量电压，不能确定是 USB 线、接口、稳压器、电容还是其他接线问题。该测试没有物理断开 OLED 供电。`runtime/wifi_oled_off_probe.log` 和 `runtime/radio_power_comparison.json` 保存结果。测试后已恢复 USB 自动额度刷新。

## USB 版本与恢复

原 USB 程序完整保留在旁边的 `../quota-oled` 文件夹。`backups/usb_version.zip` 是 USB 程序源文件备份，`backups/original_esp32s3_16MB.bin` 是烧录前的完整 Flash 备份，`backups/manifest.json` 记录芯片 MAC 和校验值。

- 需要回到 USB 数据连接时，把 ESP32 接回电脑，双击 `切回USB显示.cmd`。它先停止蓝牙程序，再启动原 USB 程序；不必重新烧录。原程序会暂时把 ESP32 放入 ROM 模式，蓝牙固件在此期间不执行。
- 回到蓝牙前按上述说明配置一次板内 BLE 模式，再双击 `启动蓝牙显示.cmd`。它先停止 USB 程序、复位开发板，再通过蓝牙连接。
- 若需要恢复烧录前的原始板内固件，在停止两种电脑程序、接好 USB 后，执行 `python flash_tools.py restore --port COM12`。它先核对备份和设备身份，再写回完整原始 Flash。普通 USB/蓝牙切换无需做这一步。

完整 Flash 备份可能包含旧程序保存的数据，请留在本机，不要公开上传。程序没有修改 eFuse。

## 文件

- `firmware/main.py`：ESP32 上电后先显示画面，并根据模式运行 USB 等待或 BLE 接收。
- `firmware/boot_frame.bin`：128×64 开机等待画面，复用已确认清楚的“重置”点阵。
- `firmware/startup_mode.txt`：本次部署模式为 `usb`；`deploy_device.py --mode usb` 可恢复这一模式。
- `firmware/ESP32_GENERIC_S3-SPIRAM_OCT-20260824-v1.29.0.bin`：适用于这块 N16R8 板的官方 MicroPython Octal PSRAM 固件。
- `quota_ble.py`：电脑后台额度读取与发送程序。
- `runtime/status.json`：蓝牙连接、设备确认和最后更新时间；`runtime/preview.png`：最近画面；`runtime/monitor.log`、`runtime/errors.log`：运行日志。

当前电脑使用工作区 `work/ble-runtime` 的 Bleak 和 mpremote，以及 `work/esptool-runtime` 的 esptool。依赖安装在工作区内。移到其他电脑时请同时保留两个显示程序目录，安装 `requirements.txt`，并安装和登录 Codex CLI。

BLE 数据分包含帧编号、偏移和 CRC32。ESP32 只有在完整接收、CRC 校验通过、OLED I²C 写入成功后才返回完成确认。电脑不会仅凭蓝牙写入成功就报告屏幕已更新。

官方资料：[MicroPython ESP32-S3 固件](https://micropython.org/download/ESP32_GENERIC_S3/)、[BLE 接口](https://docs.micropython.org/en/latest/library/bluetooth.html)、[Bleak 客户端](https://bleak.readthedocs.io/en/stable/api/client.html)、[额度读取接口](https://learn.chatgpt.com/docs/app-server)。
