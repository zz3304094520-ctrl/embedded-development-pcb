#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "请使用 sudo 执行：sudo bash relay_gateway/install_jetson.sh" >&2
  exit 1
fi

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELAY_DIR="${PACKAGE_DIR}/relay_gateway"
TARGET_DIR="/home/qiongyi/huitian-relay-gateway"
ENV_FILE="/etc/huitian-relay-agent.env"

if [[ "${PACKAGE_DIR}" != "${TARGET_DIR}" ]]; then
  echo "当前包应部署到 ${TARGET_DIR}，实际为 ${PACKAGE_DIR}" >&2
  exit 1
fi

if [[ ! -x "${TARGET_DIR}/.venv/bin/python" ]]; then
  python3 -m venv "${TARGET_DIR}/.venv"
fi
"${TARGET_DIR}/.venv/bin/pip" install -r "${RELAY_DIR}/requirements.txt"

if [[ ! -f "${ENV_FILE}" ]]; then
  install -m 600 "${RELAY_DIR}/.env.example" "${ENV_FILE}"
  echo "已创建 ${ENV_FILE}；当前保持 RELAY_DRY_RUN=true。"
fi

install -m 644 "${RELAY_DIR}/huitian-relay-agent.service" /etc/systemd/system/
install -m 644 "${RELAY_DIR}/huitian-relay-hotplug.service" /etc/systemd/system/
install -m 644 "${RELAY_DIR}/99-huitian-relay.rules" /etc/udev/rules.d/

systemctl disable --now fieldmate-edge.service 2>/dev/null || true
systemctl daemon-reload
udevadm control --reload-rules
systemctl enable --now huitian-relay-agent.service
udevadm trigger --subsystem-match=tty --action=add

echo
echo "继电器热插拔服务已安装。"
echo "状态：systemctl status huitian-relay-agent.service --no-pager"
echo "日志：journalctl -u huitian-relay-agent.service -f"
echo "实机确认无误后，将 ${ENV_FILE} 中 RELAY_DRY_RUN 改为 false 并重启服务。"
