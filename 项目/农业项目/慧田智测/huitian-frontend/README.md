# 慧田智测 H5 前端

这是连接 `huitian-backend` 的独立 H5 前端，技术栈是 Vite + Vue 3 + TypeScript。

## 启动前提

先启动后端：

```powershell
cd "F:\workspace\智慧农业\huitian-backend"
Set-ExecutionPolicy -Scope Process Bypass
.\start.ps1
```

后端默认地址：

- API: `http://172.20.10.5:8000`
- WebSocket: `ws://172.20.10.5:8000/ws`
- Swagger: `http://172.20.10.5:8000/docs`

## 启动前端

```powershell
cd "F:\workspace\智慧农业\huitian-frontend"
npm install
npm run dev
```

浏览器打开：

```text
http://172.20.10.5:5173
```

## 生产构建

```powershell
npm run build
npm run preview
```

## 可配置项

复制 `.env.example` 为 `.env.local` 后可改后端地址：

```text
VITE_API_BASE_URL=http://172.20.10.5:8000
VITE_WS_URL=ws://172.20.10.5:8000/ws
```

## 当前功能

- 后端健康检查和 MQTT 状态展示
- 农场、地块、设备读取
- 地块传感器汇总和最新数据读取
- 告警列表、确认、解决
- 水泵和补光灯控制命令
- 演示传感器数据上报
- 作物诊断图片上传
- WebSocket 实时事件流
- 手机、平板、桌面自适应布局
