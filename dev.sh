#!/usr/bin/env bash
# Ubuntu 一键安装依赖并启动 service（Task）与 rpa-engine。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="${ROOT}/service"
ENGINE_DIR="${ROOT}/rpa-engine"
LOG_DIR="${ROOT}/logs"
SERVICE_LOG="${LOG_DIR}/service.log"
ENGINE_LOG="${LOG_DIR}/rpa-engine.log"
PIDS=()

die() {
  echo "错误: $*" >&2
  exit 1
}

ensure_ubuntu() {
  [[ -f /etc/os-release ]] || die "仅支持 Ubuntu"
  # shellcheck disable=SC1091
  . /etc/os-release
  [[ "${ID:-}" == "ubuntu" ]] || die "仅支持 Ubuntu，当前系统为 ${ID:-unknown}"
}

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return
  fi
  command -v curl >/dev/null 2>&1 || die "未找到 uv，且系统没有 curl，无法自动安装。请先安装 curl 或手动安装 uv: https://docs.astral.sh/uv/"
  echo "未找到 uv，正在安装到 ~/.local/bin ..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
  command -v uv >/dev/null 2>&1 || die "uv 安装失败"
}

env_get() {
  local file="$1" key="$2" default="${3:-}"
  local line value
  line="$(grep -E "^[[:space:]]*${key}=" "$file" 2>/dev/null | grep -v '^[[:space:]]*#' | tail -n1 || true)"
  if [[ -z "$line" ]]; then
    printf '%s' "$default"
    return
  fi
  value="${line#*=}"
  value="${value%$'\r'}"
  if [[ "$value" == \"*\" ]]; then
    value="${value#\"}"
    value="${value%\"}"
  elif [[ "$value" == \'*\' ]]; then
    value="${value#\'}"
    value="${value%\'}"
  fi
  printf '%s' "${value:-$default}"
}

require_project() {
  local dir="$1" name="$2"
  [[ -d "$dir" ]] || die "找不到 ${name} 目录: ${dir}"
  [[ -f "${dir}/pyproject.toml" ]] || die "${name} 缺少 pyproject.toml"
  [[ -f "${dir}/uv.lock" ]] || die "${name} 缺少 uv.lock"
  [[ -f "${dir}/.env" ]] || die "${name} 缺少 .env，请从 ${dir}/.env.example 复制并填写后重试"
}

sync_venv() {
  local dir="$1" name="$2"
  echo "==> ${name}: uv sync --frozen --python 3.12"
  (
    cd "$dir"
    uv python install 3.12
    uv sync --frozen --python 3.12
  )
  [[ -x "${dir}/.venv/bin/python" ]] || die "${name} 未生成 .venv/bin/python"
}

start_service() {
  local host port
  host="$(env_get "${SERVICE_DIR}/.env" HOST 0.0.0.0)"
  port="$(env_get "${SERVICE_DIR}/.env" PORT 4520)"
  [[ -x "${SERVICE_DIR}/.venv/bin/uvicorn" ]] || die "service 未安装 uvicorn，请检查 uv sync 是否成功"

  echo "==> 启动 service: uvicorn app.main:app --env-file .env --host ${host} --port ${port}"
  (
    cd "$SERVICE_DIR"
    exec .venv/bin/uvicorn app.main:app \
      --env-file .env \
      --host "$host" \
      --port "$port"
  ) >>"$SERVICE_LOG" 2>&1 &
  PIDS+=("$!")
  echo "    pid=${PIDS[-1]}  log=${SERVICE_LOG}  http://${host}:${port}/health"
}

start_engine() {
  echo "==> 启动 rpa-engine: .venv/bin/python -m nodeskclaw_rpa_engine"
  (
    cd "$ENGINE_DIR"
    exec .venv/bin/python -m nodeskclaw_rpa_engine
  ) >>"$ENGINE_LOG" 2>&1 &
  PIDS+=("$!")
  local host port
  host="$(env_get "${ENGINE_DIR}/.env" APP_HOST 127.0.0.1)"
  port="$(env_get "${ENGINE_DIR}/.env" APP_PORT 4610)"
  echo "    pid=${PIDS[-1]}  log=${ENGINE_LOG}  http://${host}:${port}/health/live"
}

cleanup() {
  trap - EXIT INT TERM
  if [[ ${#PIDS[@]} -eq 0 ]]; then
    return
  fi
  echo
  echo "==> 正在停止服务: ${PIDS[*]}"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  sleep 1
  for pid in "${PIDS[@]}"; do
    kill -9 "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}

main() {
  ensure_ubuntu
  require_project "$SERVICE_DIR" "service"
  require_project "$ENGINE_DIR" "rpa-engine"
  ensure_uv
  mkdir -p "$LOG_DIR"
  : >"$SERVICE_LOG"
  : >"$ENGINE_LOG"

  echo "==> 工作区: ${ROOT}"
  sync_venv "$SERVICE_DIR" "service"
  sync_venv "$ENGINE_DIR" "rpa-engine"

  trap cleanup EXIT INT TERM
  start_service
  start_engine

  echo
  echo "两个服务已启动。日志: ${LOG_DIR}/"
  echo "按 Ctrl+C 停止。"
  echo

  tail -F "$SERVICE_LOG" "$ENGINE_LOG" &
  PIDS+=("$!")

  wait -n || true
  echo "有进程已退出，正在收尾。"
}

main "$@"
