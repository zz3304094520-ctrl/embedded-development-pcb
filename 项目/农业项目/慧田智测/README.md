# 慧田智测

面向番茄智慧种植场景的农业监测项目。现有代码通过FastAPI后端接收边缘端和设备数据，提供H5监测页面、管理后台和实时事件。

## 文件导航

| 目录或文档 | 内容 |
| --- | --- |
| [huitian-frontend](huitian-frontend/README.md) | H5前端 |
| [huitian-admin](huitian-admin/) | 管理后台 |
| [huitian-backend](huitian-backend/README.md) | 后端接口、设备网关与测试 |
| [Jetson传感器网关](jetson-edge/sensor_gateway/README.md) | 传感器采集与数据上报 |
| [Jetson继电器网关](huitian-backend/edge/relay_gateway/README.md) | 继电器控制与边缘端部署说明 |
| [PRD](PRD.md) | 产品需求 |
| [技术方案](Tech-Spec.md) | 系统设计 |
| [接口约定](API-Contract.md) | 前后端接口说明 |
| [产品说明](PRODUCT.md) | 产品定位与设计原则 |
| [版本包](../../../%E5%8E%86%E5%8F%B2/%E5%86%9C%E4%B8%9A%E9%A1%B9%E7%9B%AE/%E6%85%A7%E7%94%B0%E6%99%BA%E6%B5%8B/%E7%89%88%E6%9C%AC%E5%8C%85/) | 2026年7月17日的H5前后端交付包 |

## 本机配置

各模块的环境变量以`.env.example`为模板，使用时另建自己的`.env`。摄像头配置模板为`jetson-edge/edge_camera_config.example.json`，使用时复制为`edge_camera_config.json`并填写自己的接口密钥。归档中的密钥和示例Wi-Fi连接信息已替换为占位值。

启动、安装和部署方法以各模块原有说明及技术方案为准。

[返回农业项目](../README.md)
