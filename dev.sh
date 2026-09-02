#!/usr/bin/env bash
# Ubuntu 一键安装依赖并启动 service（Task）与 rpa-engine。
# 启动前若端口或进程已在运行，先全部停止，确认退出后再启动。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="${ROOT}/service"
ENGINE_DIR="${ROOT}/rpa-engine"
LOG_DIR="${ROOT}/logs"
SERVICE_LOG="${LOG_DIR}/service.log"
ENGINE_LOG="${LOG_DIR}/rpa-engine.log"
DEFAULT_PLAYWRIGHT_BROWSERS_PATH="/var/lib/nodeskclaw-rpa-engine/ms-playwright"
PIDS=()

die() {
  echo "错误: $*" >&2
  exit 1
}

require_sudo() {
  command -v sudo >/dev/null 2>&1 || die "需要 sudo 才能管理 Playwright 浏览器目录"
  sudo -n true 2>/dev/null || sudo -v || die "sudo 不可用，无法创建/授权 ${DEFAULT_PLAYWRIGHT_BROWSERS_PATH}"
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

# 解析 PLAYWRIGHT_BROWSERS_PATH：已配置则沿用，否则使用统一目录。
resolve_playwright_browsers_path() {
  local configured="${PLAYWRIGHT_BROWSERS_PATH:-}"
  if [[ -n "${configured//[[:space:]]/}" ]]; then
    PLAYWRIGHT_BROWSERS_PATH="${configured}"
    echo "==> 已配置 PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH}"
  else
    PLAYWRIGHT_BROWSERS_PATH="${DEFAULT_PLAYWRIGHT_BROWSERS_PATH}"
    echo "==> 未配置 PLAYWRIGHT_BROWSERS_PATH，使用默认: ${PLAYWRIGHT_BROWSERS_PATH}"
  fi
  export PLAYWRIGHT_BROWSERS_PATH
}

# 确保浏览器缓存目录存在，并由当前服务用户/组拥有。
ensure_playwright_browsers_dir() {
  local service_user service_group
  service_user="$(id -un)"
  service_group="$(id -gn)"

  echo "==> Playwright 浏览器目录检查: ${PLAYWRIGHT_BROWSERS_PATH} (user=${service_user} group=${service_group})"

  if [[ -d "${PLAYWRIGHT_BROWSERS_PATH}" ]]; then
    echo "    目录已存在"
    return 0
  fi

  echo "    目录不存在，正在创建并授权..."
  require_sudo
  sudo mkdir -p "${PLAYWRIGHT_BROWSERS_PATH}"
  sudo chown "${service_user}:${service_group}" "${PLAYWRIGHT_BROWSERS_PATH}"
  [[ -d "${PLAYWRIGHT_BROWSERS_PATH}" ]] || die "创建 Playwright 目录失败: ${PLAYWRIGHT_BROWSERS_PATH}"
  echo "    已创建: ${PLAYWRIGHT_BROWSERS_PATH} -> ${service_user}:${service_group}"
}

playwright_chromium_installed() {
  local root="$1"
  local candidate
  shopt -s nullglob
  for candidate in \
    "${root}"/chromium-*/chrome-linux/chrome \
    "${root}"/chromium-*/chrome-linux64/chrome
  do
    if [[ -x "$candidate" ]]; then
      shopt -u nullglob
      return 0
    fi
  done
  shopt -u nullglob
  return 1
}

# 检查并按需安装 Playwright Chromium（安装到 PLAYWRIGHT_BROWSERS_PATH）。
ensure_playwright_chromium() {
  local service_user python_bin
  service_user="$(id -un)"
  python_bin="${ENGINE_DIR}/.venv/bin/python"

  [[ -x "$python_bin" ]] || die "rpa-engine venv 不存在，无法安装 Playwright: ${python_bin}"

  echo "==> 检查 Playwright Chromium (${PLAYWRIGHT_BROWSERS_PATH})"
  if playwright_chromium_installed "${PLAYWRIGHT_BROWSERS_PATH}"; then
    echo "    已检测到 Chromium，跳过安装"
    return 0
  fi

  echo "    未检测到 Chromium，开始安装..."
  require_sudo

  # 系统依赖（Ubuntu）；失败不阻断后续浏览器下载，但会给出提示。
  if ! sudo "$python_bin" -m playwright install-deps chromium; then
    echo "    警告: playwright install-deps 失败，稍后浏览器启动可能缺少系统库" >&2
  fi

  sudo -u "${service_user}" \
    env PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH}" \
    "$python_bin" -m playwright install chromium \
    || die "Playwright Chromium 安装失败"

  playwright_chromium_installed "${PLAYWRIGHT_BROWSERS_PATH}" \
    || die "安装后仍未找到 Chromium 可执行文件，请检查 ${PLAYWRIGHT_BROWSERS_PATH}"
  echo "    Chromium 安装完成"
}

list_pids_on_port() {
  local port="$1"
  local pids=""

  if command -v ss >/dev/null 2>&1; then
    pids="$(ss -H -lntp "sport = :${port}" 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2 || true)"
  fi
  if [[ -z "${pids//[$' \t\n']/}" ]] && command -v fuser >/dev/null 2>&1; then
    pids="$(fuser -n tcp "$port" 2>/dev/null || true)"
  fi
  if [[ -z "${pids//[$' \t\n']/}" ]] && command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -t -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  fi

  printf '%s\n' $pids | awk '/^[0-9]+$/' | sort -u
}

list_pids_by_pattern() {
  local pattern="$1"
  pgrep -f -- "$pattern" 2>/dev/null | awk -v self="$$" -v parent="$PPID" '$1 != self && $1 != parent' || true
}

is_workspace_process() {
  local pid="$1" cmdline cwd
  cmdline="$(tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
  cwd="$(readlink "/proc/${pid}/cwd" 2>/dev/null || true)"
  [[ "$cmdline" == *"$SERVICE_DIR"* || "$cmdline" == *"$ENGINE_DIR"* ]] && return 0
  [[ "$cwd" == "$SERVICE_DIR" || "$cwd" == "$SERVICE_DIR/"* ]] && return 0
  [[ "$cwd" == "$ENGINE_DIR" || "$cwd" == "$ENGINE_DIR/"* ]] && return 0
  [[ "$cmdline" == *nodeskclaw_rpa_engine* ]] && return 0
  return 1
}

expand_pid_tree() {
  local pid="$1" child
  printf '%s\n' "$pid"
  while IFS= read -r child; do
    [[ -n "$child" ]] && expand_pid_tree "$child"
  done < <(pgrep -P "$pid" 2>/dev/null || true)
}

unique_pids() {
  printf '%s\n' "$@" | awk '/^[0-9]+$/' | sort -u
}

pid_alive() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

wait_pids_gone() {
  local timeout="$1"
  shift
  local deadline=$((SECONDS + timeout)) pid
  local -a remaining
  while (( SECONDS < deadline )); do
    remaining=()
    for pid in "$@"; do
      if pid_alive "$pid"; then
        remaining+=("$pid")
      fi
    done
    if [[ ${#remaining[@]} -eq 0 ]]; then
      return 0
    fi
    sleep 0.2
  done
  return 1
}

port_in_use() {
  local port="$1"
  [[ -n "$(list_pids_on_port "$port")" ]] && return 0
  if command -v ss >/dev/null 2>&1; then
    ss -H -lnt "sport = :${port}" 2>/dev/null | grep -q .
  else
    return 1
  fi
}

wait_port_free() {
  local port="$1" timeout="$2"
  local deadline=$((SECONDS + timeout))
  while (( SECONDS < deadline )); do
    port_in_use "$port" || return 0
    sleep 0.2
  done
  return 1
}

stop_pids() {
  local -a roots=("$@") tree=() unique=() alive=()
  local pid

  [[ ${#roots[@]} -eq 0 ]] && return 0

  while IFS= read -r pid; do
    [[ -n "$pid" ]] && tree+=("$pid")
  done < <(for pid in "${roots[@]}"; do expand_pid_tree "$pid"; done)

  while IFS= read -r pid; do
    [[ -n "$pid" && "$pid" != "$$" && "$pid" != "$PPID" ]] && unique+=("$pid")
  done < <(unique_pids "${tree[@]}")

  alive=()
  for pid in "${unique[@]}"; do
    pid_alive "$pid" && alive+=("$pid")
  done
  [[ ${#alive[@]} -eq 0 ]] && return 0

  echo "    发送 SIGTERM: ${alive[*]}"
  for pid in "${alive[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  if wait_pids_gone 8 "${alive[@]}"; then
    return 0
  fi

  echo "    仍未退出，发送 SIGKILL: ${alive[*]}"
  for pid in "${alive[@]}"; do
    pid_alive "$pid" && kill -9 "$pid" 2>/dev/null || true
  done
  wait_pids_gone 5 "${alive[@]}" || true
}

collect_existing_service_pids() {
  local service_port engine_port pid
  service_port="$(env_get "${SERVICE_DIR}/.env" PORT 4520)"
  engine_port="$(env_get "${ENGINE_DIR}/.env" APP_PORT 4610)"

  {
    list_pids_on_port "$service_port"
    list_pids_on_port "$engine_port"
    {
      list_pids_by_pattern "${SERVICE_DIR}/.venv/bin/uvicorn"
      list_pids_by_pattern "${SERVICE_DIR}/.venv/bin/python .*uvicorn"
      list_pids_by_pattern "uvicorn app.main:app"
      list_pids_by_pattern "${ENGINE_DIR}/.venv/bin/python -m nodeskclaw_rpa_engine"
      list_pids_by_pattern "python -m nodeskclaw_rpa_engine"
    } | while IFS= read -r pid; do
      [[ -n "$pid" ]] && is_workspace_process "$pid" && printf '%s\n' "$pid"
    done
  } | awk '/^[0-9]+$/' | sort -u
}

stop_existing_services() {
  local service_port engine_port
  local -a found=()
  local pid

  service_port="$(env_get "${SERVICE_DIR}/.env" PORT 4520)"
  engine_port="$(env_get "${ENGINE_DIR}/.env" APP_PORT 4610)"

  echo "==> 检查已运行的服务 (service :${service_port}, rpa-engine :${engine_port})"

  while IFS= read -r pid; do
    [[ -n "$pid" && "$pid" != "$$" && "$pid" != "$PPID" ]] && found+=("$pid")
  done < <(collect_existing_service_pids)

  if [[ ${#found[@]} -eq 0 ]]; then
    echo "    未发现已运行的 service / rpa-engine"
    return 0
  fi

  echo "==> 发现已运行进程，先停止: ${found[*]}"
  stop_pids "${found[@]}"

  if ! wait_port_free "$service_port" 8; then
    die "端口 ${service_port} 仍被占用，无法启动 service"
  fi
  if ! wait_port_free "$engine_port" 8; then
    die "端口 ${engine_port} 仍被占用，无法启动 rpa-engine"
  fi

  found=()
  while IFS= read -r pid; do
    [[ -n "$pid" && "$pid" != "$$" && "$pid" != "$PPID" ]] && found+=("$pid")
  done < <(collect_existing_service_pids)
  if [[ ${#found[@]} -ne 0 ]]; then
    die "仍有进程未退出: ${found[*]}"
  fi

  echo "    已全部停止"
}

# curl 探测用：0.0.0.0 / :: 不能作为客户端地址。
probe_host() {
  local host="$1"
  case "$host" in
    ""|"0.0.0.0"|"::"|"*") printf '%s' "127.0.0.1" ;;
    *) printf '%s' "$host" ;;
  esac
}

url_origin() {
  local url="$1"
  printf '%s' "$url" | sed -E 's#^(https?://[^/]+).*#\1#'
}

http_ok() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time 2 "$url" >/dev/null 2>&1
    return
  fi
  python3 - "$url" >/dev/null 2>&1 <<'PY'
import sys, urllib.request
try:
    urllib.request.urlopen(sys.argv[1], timeout=2)
except Exception:
    raise SystemExit(1)
PY
}

# Engine 在 WORKER_ENABLED=true 时，lifespan 会同步向 Task 注册 Worker；
# Task 尚未监听就会立刻退出，随后 wait -n 把 Task 一并停掉。
wait_http_ok() {
  local url="$1" timeout="$2" name="$3"
  local deadline=$((SECONDS + timeout))
  echo "==> 等待 ${name} 就绪: ${url}  (最多 ${timeout}s)"
  while (( SECONDS < deadline )); do
    if http_ok "$url"; then
      echo "    ${name} 已就绪"
      return 0
    fi
    sleep 0.3
  done
  die "${name} 在 ${timeout}s 内未就绪: ${url}。请查看日志后重试。"
}

start_service() {
  local host port probe
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
  probe="http://$(probe_host "$host"):${port}/health"
  echo "    pid=${PIDS[-1]}  log=${SERVICE_LOG}  ${probe}"
}

start_engine() {
  local host port probe
  echo "==> 启动 rpa-engine: .venv/bin/python -m nodeskclaw_rpa_engine"
  echo "    PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH}"
  (
    cd "$ENGINE_DIR"
    export PLAYWRIGHT_BROWSERS_PATH
    exec .venv/bin/python -m nodeskclaw_rpa_engine
  ) >>"$ENGINE_LOG" 2>&1 &
  PIDS+=("$!")
  host="$(env_get "${ENGINE_DIR}/.env" APP_HOST 127.0.0.1)"
  port="$(env_get "${ENGINE_DIR}/.env" APP_PORT 4610)"
  probe="http://$(probe_host "$host"):${port}/health/live"
  echo "    pid=${PIDS[-1]}  log=${ENGINE_LOG}  ${probe}"
}

wait_service_ready() {
  local host port local_health task_api task_origin task_health
  host="$(env_get "${SERVICE_DIR}/.env" HOST 0.0.0.0)"
  port="$(env_get "${SERVICE_DIR}/.env" PORT 4520)"
  local_health="http://$(probe_host "$host"):${port}/health"
  wait_http_ok "$local_health" 60 "service (nodeskclaw-task)"

  task_api="$(env_get "${ENGINE_DIR}/.env" TASK_API_BASE_URL "http://127.0.0.1:4520/api/v1/autotask")"
  task_origin="$(url_origin "$task_api")"
  [[ -n "$task_origin" ]] || die "无法解析 rpa-engine .env 的 TASK_API_BASE_URL"
  task_health="${task_origin}/health"
  echo "    Engine 将连接 ${task_api}"
  if [[ "$task_health" != "$local_health" ]]; then
    wait_http_ok "$task_health" 30 "Engine TASK_API_BASE_URL (${task_origin})"
  fi
}

wait_engine_ready() {
  local host port
  host="$(env_get "${ENGINE_DIR}/.env" APP_HOST 127.0.0.1)"
  port="$(env_get "${ENGINE_DIR}/.env" APP_PORT 4610)"
  wait_http_ok "http://$(probe_host "$host"):${port}/health/live" 60 "rpa-engine"
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

  # 一键环境：先确定 Playwright 浏览器路径与目录，再装依赖/启动服务。
  resolve_playwright_browsers_path
  ensure_playwright_browsers_dir

  require_project "$SERVICE_DIR" "service"
  require_project "$ENGINE_DIR" "rpa-engine"
  ensure_uv
  mkdir -p "$LOG_DIR"
  : >"$SERVICE_LOG"
  : >"$ENGINE_LOG"

  echo "==> 工作区: ${ROOT}"
  sync_venv "$SERVICE_DIR" "service"
  sync_venv "$ENGINE_DIR" "rpa-engine"
  ensure_playwright_chromium

  stop_existing_services

  trap cleanup EXIT INT TERM
  start_service
  wait_service_ready
  start_engine
  wait_engine_ready

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
