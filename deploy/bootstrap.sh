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
API_READY_TIMEOUT="${API_READY_TIMEOUT:-120}"   # seconds to wait for /api/health
API_READY_INTERVAL="${API_READY_INTERVAL:-2}"   # seconds between probes

echo ">> Creating service user '${SERVICE_USER}'"
id -u "${SERVICE_USER}" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "${SERVICE_USER}"

echo ">> Installing application to ${APP_DIR}"
mkdir -p "${APP_DIR}"
# Copy the repo (excluding local data and venv) into the app dir.
# NB: '.env' is excluded so re-runs (updates) do not wipe the deployed credentials.
rsync -a --delete \
    --exclude '.git' --exclude '.venv' --exclude 'data' --exclude '.prefect' --exclude '.env' \
    "${REPO_DIR}/" "${APP_DIR}/"

echo ">> Ensuring data root ${DATA_ROOT} exists"
mkdir -p "${DATA_ROOT}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${DATA_ROOT}" "${APP_DIR}"

echo ">> Installing uv for ${SERVICE_USER} (if missing)"
if ! sudo -u "${SERVICE_USER}" bash -lc 'command -v uv' >/dev/null 2>&1; then
    sudo -u "${SERVICE_USER}" bash -lc 'curl -LsSf https://astral.sh/uv/install.sh | sh'
fi
# The systemd units run `/usr/bin/env uv ...` under systemd's minimal PATH, which does not
# include the service user's ~/.local/bin. Symlink uv onto the default system PATH so the
# units can find it (otherwise they crash-loop with exit code 127).
UV_BIN="$(sudo -u "${SERVICE_USER}" bash -lc 'command -v uv')"
ln -sf "${UV_BIN}" /usr/local/bin/uv

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
# 'restart' (not 'enable --now') so a re-run actually reloads new code/deps: a running
# unit is restarted, a stopped one is started. The server restarts first so any Prefect
# database migrations apply before the worker reconnects.
systemctl enable prefect-server.service
systemctl restart prefect-server.service

echo ">> Waiting for the Prefect API to come up (timeout ${API_READY_TIMEOUT}s)"
ready=0
deadline=$(( SECONDS + API_READY_TIMEOUT ))
while (( SECONDS < deadline )); do
    if ! systemctl is-active --quiet prefect-server.service; then
        echo ">> prefect-server.service is not active; aborting wait"
        break
    fi
    if curl -fsS http://127.0.0.1:4200/api/health >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep "${API_READY_INTERVAL}"
done

if [[ "${ready}" -ne 1 ]]; then
    echo ">> ERROR: Prefect API never became ready at http://127.0.0.1:4200/api" >&2
    systemctl status prefect-server.service --no-pager >&2 || true
    journalctl -u prefect-server.service -n 50 --no-pager >&2 || true
    exit 1
fi
echo ">> Prefect API is ready"

echo ">> Creating work pool and deploying the flow"
sudo -u "${SERVICE_USER}" bash -lc "cd '${APP_DIR}' && \
    export PREFECT_API_URL=http://127.0.0.1:4200/api PREFECT_HOME='${APP_DIR}/.prefect' && \
    uv run prefect work-pool create --type process --overwrite aqmesh-pool && \
    uv run prefect --no-prompt deploy --all"

# 'restart' so an update reloads the worker (it holds imported flow code and deps in memory).
systemctl enable prefect-worker.service
systemctl restart prefect-worker.service

# A worker that starts then dies (Restart=on-failure) would still let 'restart' return success,
# so verify it actually stayed up rather than silently printing ">> Done".
sleep "${API_READY_INTERVAL}"
if ! systemctl is-active --quiet prefect-worker.service; then
    echo ">> ERROR: prefect-worker.service failed to start" >&2
    echo "   (On a first run this is expected until ${APP_DIR}/.env has real credentials.)" >&2
    systemctl status prefect-worker.service --no-pager >&2 || true
    journalctl -u prefect-worker.service -n 50 --no-pager >&2 || true
    exit 1
fi

echo ">> Done. Check status with:"
echo "     systemctl status prefect-server prefect-worker"
echo "   Remember to edit ${APP_DIR}/.env with real AQMesh credentials, then:"
echo "     systemctl restart prefect-worker"
