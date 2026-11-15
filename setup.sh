#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

if ! command -v curl >/dev/null 2>&1 || ! command -v git >/dev/null 2>&1; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    elif [[ "${EUID}" -eq 0 ]]; then
        SUDO=""
    else
        echo "This script needs sudo to install curl and git." >&2
        exit 1
    fi

    ${SUDO} apt-get update
    ${SUDO} apt-get install -y ca-certificates curl git
fi

if ! command -v uv >/dev/null 2>&1; then
    curl --proto '=https' --tlsv1.2 -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "uv was installed but is not available on PATH." >&2
    exit 1
fi

cd "${BACKEND_DIR}"
uv python install "${PYTHON_VERSION}"
uv sync --locked --python "${PYTHON_VERSION}"

echo "Starting SPHEREx Explorer at http://${HOST}:${PORT}"
exec uv run --python "${PYTHON_VERSION}" uvicorn app.main:app \
    --host "${HOST}" \
    --port "${PORT}"
