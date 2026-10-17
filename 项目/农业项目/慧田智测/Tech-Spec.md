# 慧田智测管理后台 Tech Spec

## 技术栈

- Vue 3 + Composition API + `<script setup lang="ts">`
- Vite + TypeScript
- Vue Router：管理页面路由与侧边导航
- Element Plus：表单、表格、确认、通知和基础交互组件
- Apache ECharts：传感器趋势图
- FastAPI：复用现有 REST API；开发环境通过 Vite proxy 访问 `/api` 和 `/ws`

## 网络配置唯一来源

- 根目录 `network-config.json` 固定当前 Windows 服务主机 `172.20.10.2`、Jetson `172.20.10.4` 和三个端口。
- `start-all.ps1` 每次启动前根据该文件重建 H5/Admin 的 `.env.local`，避免前后端或文档残留旧 IP。
- `0.0.0.0` 仅用于服务监听；Jetson 和其他局域网客户端始终访问 `172.20.10.2`。

## 目录与模块

`huitian-admin/` 为独立前端包：

- `src/api/`：统一 fetch client、错误转换和业务 API。
- `src/types/`：API DTO 与表单 payload。
- `src/layouts/`：应用外壳、侧栏与顶栏。
- `src/views/`：每个业务页面只负责组合。
- `src/components/`：可复用状态、图表、表单对话框和表格部件。
- `src/composables/`：加载、刷新和选择状态。

## 数据流

页面挂载或筛选变化 → API client 请求 FastAPI → typed state 保存源数据 → `computed` 生成统计与筛选结果 → Element Plus/ECharts 渲染。写操作成功后重新读取相关资源，不在前端猜测数据库最终状态。

## 关键决策

- 管理后台与 H5 独立构建，避免后台依赖增加 H5 体积，也符合独立 `9528` 端口路线。
- 开发环境使用同源 `/api` proxy，避免硬编码 IP 和 CORS 差异；生产环境支持 `VITE_API_BASE_URL`。
- 不引入 Pinia：首版状态按页面隔离，没有跨页面复杂写状态。
- 不修改 FastAPI 数据模型；API 缺少的能力不在前端伪造。
- HTTP 为唯一设备通信模式；已有 MQTT 字段保留兼容，但默认关闭且后台创建表单不提供 MQTT 选项。

## 验证步骤

1. 后端 `pytest -v`。
2. 管理后台 `npm run typecheck`、`npm run build`。
3. 启动 FastAPI `8000`、H5 `5173`、管理后台 `9528`。
4. 浏览器验证总览加载、资源 CRUD、告警状态变更和命令创建。
5. 检查 Console、Network、桌面与平板截图。

## H5 模板视觉重构

### 组件边界

- `App.vue`：继续作为薄组合层，连接 `useFarmDashboard`、WebSocket 和各展示组件，不承载设备控制规则。
- `AppTopBar.vue`：居中品牌标题和通知入口，只负责顶栏呈现。
- `AppHero.vue`：农业实景背景、问候、位置与田间状态；不请求数据、不推断设备状态。
- `OverviewGrid.vue`：农场面积、温度色块、农场/地块选择和三个功能入口；通过原有 models/events 修改选择。
- `BottomNavigation.vue`：四个锚点导航；选中态由滚动位置派生，不创建重复路由。
- 原 `SensorSummaryPanel`、`CameraMonitorPanel`、`DeviceListPanel`、`CommandPanel`、`DiagnosisPanel`、`AlertQueuePanel`：保留公开 props/models/emits，仅统一视觉和页面分组。

### 数据与状态

`useFarmDashboard` 仍是唯一业务数据源；`App.vue` 只用 `computed` 派生首页展示值。农场面积来自 `selectedPlot.area`，实时温度只从 `summaries[metric=air_temperature]` 读取；不存在时显示明确空态，不调用或伪造外部天气接口。

水泵/补光灯链路保持：`CommandPanel emit` → `useFarmDashboard.submitCommand` → FastAPI HTTP → Jetson → `actuator_state`/命令状态 → WebSocket 刷新。设备列表和首页不提供第二个控制入口。

### 视觉实现

- 全局设计 tokens 集中在 `styles.css`：深绿 `#102218`、田野绿 `#1f5138`、天气红 `#bd4332`、嫩芽绿 `#dff49c`、纸白 `#fffef8`、背景 `#edf2e8`。
- Hero 使用独立农业照片资产与纯色半透明遮罩；不使用 CSS 渐变或 CSS 绘画替代图片。
- 图标统一使用 `@phosphor-icons/vue` named imports，选中态使用 `fill`、普通态使用 `regular`/`duotone`，避免全量注册。
- 桌面内容宽度保持流体布局，移动端通过 `900px` 与 `640px` 两级媒体查询折叠；底部导航使用 `position: fixed` 并为主内容预留安全区。
- 动效仅保留轻量进入、hover 和状态反馈；遵守 `prefers-reduced-motion`。

### 验证

1. `npm run typecheck`、`npm run build`。
2. 在局域网实际后端下验证首页加载、锚点导航、农场切换、相机、诊断和设备命令。
3. 分别截取 `1440 × 900` 与 `390 × 844`，与参考图同视口对比。
4. 将对比、问题分级和修复结果记录到 `huitian-frontend/design-qa.md`；只有 `final result: passed` 才交付。

## Jetson HTTP 继电器网关

数据流：H5 创建命令 → FastAPI 校验设备类型并保存 `pending` → Jetson 按两个执行器设备 ID 轮询 → 标记 `acknowledged` → 串口写入固定通道 → HTTP 回报设备 `on/off/unknown` → 到时自动关闭 → 回传 `succeeded` 或 `failed`。

执行器数据模型：

- `Device.actuator_state`：`on | off | unknown`，仅由 Jetson 心跳或命令回执更新。
- `Device.state_updated_at`：最近一次继电器状态回报时间。
- `pump-001 / device_type=pump` 固定为 CH1；`grow-light-001 / device_type=grow_light` 固定为 CH2。
- H5 的 `DeviceListPanel` 只展示后端状态；`CommandPanel` 只产生控制意图；`useFarmDashboard` 负责 API 状态和兼容命令筛选。

安全设计：

- 串口协议帧通过环境变量配置，代码不猜测厂商协议。
- 默认 dry-run，dry-run 只打印动作并回传流程，不写串口。
- 仅接受四种命令：`pump_on/off`、`light_on/off`。
- 开启动作必须带 `1..300` 秒时限；CH1/CH2 映射不可通过前端参数覆盖。
- systemd 服务以普通用户 `qiongyi` 运行；该用户通过 `dialout` 组访问串口。
- 未完成的 `acknowledged` 命令在服务重启时标记为失败，不自动重放，避免重复启动实体设备。
- Agent 启动和退出时都先关闭 CH1/CH2；本地单调时钟负责超时关断，后端短时断网不能延长开启时间。
- 当前部署只允许运行一个 systemd Agent，避免同一继电器命令被多个进程重复执行。

## D435i 相机与 YOLO 边缘识别

数据流：D435i 彩色/深度帧 → Jetson 本地 YOLO → 带框 JPEG 帧进入 Jetson MJPEG 服务 → 浏览器 `<img>` 直连播放；同一次推理生成的结构化结果 → FastAPI → SQLite/MySQL → H5 病害卡片。

推理策略：`inference_every_frames=1` 表示每个成功采集帧都执行 YOLO；Ultralytics `conf=0.900` 仍用模型真实概率完成最低阈值过滤。边缘服务保留兼容字段 `confidence`，但 H5 不展示该字段；右侧“健康状况”由组件每 5 秒生成一次 `60..75` 的随机整数，仅用于界面演示。类别、边界框、距离和时间仍来自实时推理。

组件边界：

- `DeviceListPanel`：显示和选择设备，仅呈现设备在线/离线信息。
- `CameraMonitorPanel`：接收相机设备与识别结果 props，负责 MJPEG 加载状态、手动重连和结果呈现，不修改父级状态。
- `CameraMonitorPanel` 右侧固定展示“小番茄作物概况”，并将最新检测作为“当前识别种类”字段，避免把默认资料文案误当成模型类别。
- `useFarmDashboard`：加载设备与识别结果，使用 `computed` 派生当前地块相机和最近识别结果。
- FastAPI camera compatibility routes：接收现有 Jetson 脚本的注册、心跳与识别 payload。
- Jetson `fieldmate-camera.service`：独占 D435i、执行 YOLO、提供 `/video` 与 `/health`，按类别节流上传 JSON。

热插拔时序：

1. 拔出 D435i 后，采集循环捕获设备异常并将 `camera_online=false`，但 systemd 服务、MJPEG HTTP 服务和后端心跳线程保持运行。
2. 下一次 `POST /camera/edge/register` 将离线状态写入设备并广播 `camera.status_changed`；H5 WebSocket 收到事件后刷新设备数据并卸载 `<img>`。
3. Jetson 每 5 秒重新枚举 D435i；重新插入且成功出帧后将 `camera_online=true`。
4. 下一次注册心跳再次广播状态；H5 在相同 `stream_url` 下也会生成新 nonce、重新挂载 `<img>`，无需用户刷新页面。

关键约束：

- FastAPI 不转发 MJPEG，不接收原始帧；`image_url` 仅保存 Jetson 快照 URL。
- `stream_url` 来自 Jetson 注册信息，用于适配 DHCP/IP 变化。
- `device_code` 是设备、注册信息与检测记录之间的稳定关联键。
- 检测上报同时刷新相机设备 `last_seen_at/is_online`，并广播 `camera.detection_created` WebSocket 事件。
- 当前状态传播上界由 5 秒相机重试和 10 秒后端心跳构成，理论最坏约 15 秒；此延迟换取了较低的 API 轮询压力。

## Jetson RS485 传感器网关

### 数据流与网络边界

气象站/土壤探头 → USB-RS485 → Jetson `172.20.10.4` 本地串口 → `huitian-sensor-agent` 每 5 秒轮询 → HTTP `POST http://172.20.10.2:8000/api/v1/telemetry` → FastAPI/数据库/WebSocket → H5。传感器接入不开放 `8001/8002` 等新 TCP 端口；“端口”分别指 Jetson 的串口设备与既有 FastAPI `8000`。

### 模块边界

- `jetson-edge/sensor_gateway/modbus_rtu.py`：仅负责 Modbus RTU Function 03、CRC16、超时和响应校验，不包含业务指标名称。
- `jetson-edge/sensor_gateway/drivers.py`：按已验证型号解析寄存器和倍率。未知或未确认寄存器直接忽略，不猜测语义。
- `jetson-edge/sensor_gateway/agent.py`：独立轮询两只传感器、维护在线状态、按设备批量上报并隔离单设备故障。
- `jetson-edge/sensor_gateway/config.json`：保存 FastAPI URL、5 秒采样周期、物理 `by-path`、波特率、地址和已启用指标。
- `jetson-edge/sensor_gateway/huitian-sensor-agent.service`：以 `qiongyi` 和 `dialout` 组运行，失败后由 systemd 重启；与 `fieldmate-camera.service`、继电器 Agent 使用不同串口。

### 已验证协议

- 气象站：`SN-3003-FSXCS-MD1`，`4800bps / 8N1 / slave=1 / function=03`。
- `500..515` 连续寄存器中，按厂商 `RS-FSXCS-N01-*` 协议解析：`504 / 10` 为相对湿度 `%`，`505` 按有符号 16 位后 `/ 10` 为温度 `℃`，`(510 << 16) | 511` 为光照 `lux`，`513 / 10` 为累计雨量 `mm`。
- 现场连续采样得到约 `44.0%`、`25.2℃`、`6 lux`、`0 mm`，原始帧 CRC 均通过。
- 标签未选“噪声”，因此虽然标准协议把 `506` 定义为噪声，当前定制设备的 `506=300` 在取得精确型号协议前不进入 telemetry。
- 土壤探头当前仅确认 RS485 物理接口；驱动配置保持 disabled，直到读到合法帧并确认寄存器映射。

### 稳定设备识别与热插拔

- 两只 CH340 的 `ID_SERIAL` 相同，配置必须使用 `/dev/serial/by-path/...2.2.2...`（气象）和 `/dev/serial/by-path/...2.2.4...`（土壤），不能使用冲突的 `by-id` 链接，也不能写死 `/dev/ttyUSB0/1`。
- 每个设备独立打开、采样和关闭串口；一次设备异常不得阻塞另一设备。不存在设备节点、打开失败、连续读失败时上报离线状态并继续低频探测。
- 设备从离线恢复且首次取得合法帧后，由 telemetry 写入自动恢复在线；状态变化才调用离线接口，避免每 5 秒产生冗余状态写入。
- HTTP 使用短超时；后端暂不可达时保留进程并在下一周期重试，不在内存中无限堆积历史样本。

### 后端与 H5 状态模型

- 新增 `POST /api/v1/devices/{device_code}/status`，仅允许 Jetson 报告 `is_online`；离线时保留最后一次 `last_seen_at`，并广播 `device.status_changed`。
- `POST /telemetry` 仍是唯一读数入口，成功写入时自动令设备在线并更新 `last_seen_at`。
- H5 从按时间倒序的 telemetry 中按 `${device_id}:${metric}` 派生最新读数，不以包含历史演示值的全局 summary 作为实时来源。
- `SensorSummaryPanel` 按设备类型分组呈现，显示设备在线状态、采样时间和真实指标；`SensorReadingsPanel` 增加设备名称和中文质量状态。
- WebSocket 传感器事件采用短 debounce 后只执行 `refreshSensorData()`；不增加固定 3 秒定时重连逻辑。

### 验证

1. 用已知请求/响应向量验证 CRC、异常帧、短帧、负温度和 32 位光照解析。
2. 在 Jetson 对气象站连续读取三次，保存原始十六进制帧并与 Agent 输出比对。
3. 启动 Agent 后查询 `/api/v1/telemetry/latest/weather-001`，确认值和时间来自现场采样。
4. 拔出气象适配器，确认 `weather-001` 离线且土壤轮询不受影响；重新插回原物理口后自动恢复。
5. 运行后端 pytest、Jetson 单元测试、前端 typecheck/build，并在桌面和移动视口检查在线、离线、旧值、无数据四种状态。
