# OLED Codex 额度显示

显示当前 Codex 账户的五小时剩余额度、周剩余额度及各自重置日期和时间，全部使用北京时间（UTC+8）。这是 Codex 额度，不代表 ChatGPT 中每一个模型的聊天次数或 API 余额。

屏幕采用四行布局：上方显示“5小时”和剩余百分比，下方显示“周额度”和剩余百分比，每组下方显示各自的重置时间。时间均为北京时间；去掉了标题和更新时间，增大字体与两组之间的间距。“重置”标签使用更大字形并增加字距，其中“置”采用专用点阵，避免密集横线粘连；此版已在实物屏幕上确认清楚可读。

默认每 60 秒向已登录的本地 Codex 读取一次最新数据。没有模型推理调用。读取失败时保留最近数据，并在重置时间后标记“旧”；数据缺失显示 `--`。不会按本地时钟猜测额度已经恢复，也不会使用账户的额度重置券。

## 当前设备

- ESP32-S3，MAC `28:84:85:60:dd:48`。
- SDA：GPIO7，SCL：GPIO8，供电：3.3V，与 ESP32 共地。
- OLED 地址：`0x3C`，128×64，列起始偏移：2。
- 当前串口：COM12；若串口编号变化，只有一个兼容 USB 串口时可自动重新选择，并再次核对芯片 MAC。

## 使用

ESP32 已保存开机显示程序：接通电源后约 1 秒自行点亮屏幕，先显示“5小时”“周额度”和 `--`，不需要电脑程序先运行。当前默认以 USB 模式启动。收到电脑发送的实时额度后，等待画面会被替换；开机不会把上次额度当作最新数据。

1. 保持 ESP32 的 USB 数据线连接电脑，电脑联网，Codex CLI 登录同一个 ChatGPT 账户。
2. 双击 `启动额度显示.cmd`。程序在后台运行，不需让本次聊天持续生成回复。
3. 双击 `停止额度显示.cmd` 可以停止；停止后将恢复寄存器并复位到 ESP32 原有固件。

本方案由电脑通过 ESP32 ROM 驱动屏幕。运行期间 ESP32 专用于额度显示，板内开机程序暂时停止执行。USB 额度刷新程序不改写 Flash 或 eFuse，也没有把登录信息写入 ESP32；独立的开机显示程序已保存到开发板 Flash。电脑休眠、关机或断开 USB 时停止刷新，屏幕可能保留最近的画面。恢复连接后程序会重试。程序未设置 Windows 登录时自启动；电脑重新开机后需启动一次，开发板亮屏不依赖这个步骤。

本电脑已经有 Python、Pillow、pyserial 和 Codex CLI；程序会使用当前工作区 `work/esptool-runtime` 中经过验证的 esptool。若移动到其他电脑，需安装 Codex CLI 并登录，再运行 `python -m pip install -r requirements.txt`。

`runtime/usage.json` 是最近一次成功读取的额度，`runtime/status.json` 是运行状态，`runtime/preview.png` 是最近的显示画面。失败原因可以查看 `runtime/monitor.log` 和 `runtime/errors.log`。

额度读数使用官方 `account/rateLimits/read` 接口，按 `windowDurationMins` 识别 300 分钟和 10080 分钟窗口；剩余额度为 `100 - usedPercent`。优先选择 `rateLimitsByLimitId.codex`，避免混淆其他额度池。程序会核对当前桌面账户 ID；若日后切换账户，需要同步调整 `quota_oled.py` 中的 `EXPECTED_ACCOUNT`。

接口说明：[OpenAI App Server 文档](https://learn.chatgpt.com/docs/app-server)。GPIO/I²C 寄存器与时序采用 [ESP-IDF v5.3 ESP32-S3 定义](https://github.com/espressif/esp-idf/tree/v5.3/components/hal/esp32s3)。
