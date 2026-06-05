#!/usr/bin/env bash
#
# Provision the AQMesh pipeline on an Ubuntu 24.04 VPS.
#
# Run as root (or with sudo) from a checkout of this repo, e.g.:
#     sudo APP_DIR=/opt/aqmesh DATA_ROOT=/mnt/aqmesh-data bash deploy/bootstrap.sh
#
# It is idempotent: safe to re-run after pulling new code.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/aqmesh}"
DATA_ROOT="${DATA_ROOT:-/mnt/aqmesh-data}"   # the mounted shared storage volume
SERVICE_USER="${SERVICE_USER:-aqmesh}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo ">> Creating service user '${SERVICE_USER}'"
id -u "${SERVICE_USER}" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "${SERVICE_USER}"

echo ">> Installing application to ${APP_DIR}"
mkdir -p "${APP_DIR}"
# Copy the repo (excluding local data and venv) into the app dir.
rsync -a --delete \
    --exclude '.git' --exclude '.venv' --exclude 'data' --exclude '.prefect' \
    "${REPO_DIR}/" "${APP_DIR}/"

echo ">> Ensuring data root ${DATA_ROOT} exists"
mkdir -p "${DATA_ROOT}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${DATA_ROOT}" "${APP_DIR}"

echo ">> Installing uv for ${SERVICE_USER} (if missing)"
if ! sudo -u "${SERVICE_USER}" bash -lc 'command -v uv' >/dev/null 2>&1; then
    sudo -u "${SERVICE_USER}" bash -lc 'curl -LsSf https://astral.sh/uv/install.sh | sh'
fi

echo ">> Installing Python dependencies (uv sync)"
sudo -u "${SERVICE_USER}" bash -lc "cd '${APP_DIR}' && uv sync --no-dev"

if [[ ! -f "${APP_DIR}/.env" ]]; then
    echo ">> Creating ${APP_DIR}/.env from template - EDIT IT with real credentials!"
    cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
    # Point the pipeline at the mounted volume and production API.
    sed -i "s#^AQMESH_DATA_ROOT=.*#AQMESH_DATA_ROOT=${DATA_ROOT}#" "${APP_DIR}/.env"
    sed -i "s#^AQMESH_ENVIRONMENT=.*#AQMESH_ENVIRONMENT=prod#" "${APP_DIR}/.env"
    chown "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}/.env"
    chmod 600 "${APP_DIR}/.env"
fi

echo ">> Installing systemd units"
install -m 0644 "${APP_DIR}/deploy/systemd/prefect-server.service" /etc/systemd/system/
install -m 0644 "${APP_DIR}/deploy/systemd/prefect-worker.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now prefect-server.service

echo ">> Waiting for the Prefect API to come up"
for _ in $(seq 1 30); do
    if sudo -u "${SERVICE_USER}" bash -lc "cd '${APP_DIR}' && PREFECT_API_URL=http://127.0.0.1:4200/api uv run prefect server database --help" >/dev/null 2>&1 \
       && curl -fsS http://127.0.0.1:4200/api/health >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

echo ">> Creating work pool and deploying the flow"
sudo -u "${SERVICE_USER}" bash -lc "cd '${APP_DIR}' && \
    export PREFECT_API_URL=http://127.0.0.1:4200/api PREFECT_HOME='${APP_DIR}/.prefect' && \
    uv run prefect work-pool create --type process aqmesh-pool 2>/dev/null || true && \
    uv run prefect deploy --all"

systemctl enable --now prefect-worker.service

echo ">> Done. Check status with:"
echo "     systemctl status prefect-server prefect-worker"
echo "   Remember to edit ${APP_DIR}/.env with real AQMesh credentials, then:"
echo "     systemctl restart prefect-worker"
