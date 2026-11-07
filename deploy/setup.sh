#!/usr/bin/env bash
#
# Proposito: instalar ia_nest_external_home_assistant como servicio local MCP.
# Entrada: --config FICHERO, basado en deploy/ejemplo.setup.conf.
# Efectos: crea usuario, venv, ficheros privados y una unidad systemd.
# Seguridad: no imprime tokens; el servicio solo escucha en localhost por defecto.

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly UNIT_NAME="ianest-external-ha.service"
readonly -a CONFIG_KEYS=(SERVICE_USER INSTALL_ROOT HA_URL HA_TOKEN_SOURCE CORE_TOKEN_SOURCE SCRIPTS_SOURCE HOST PORT TIMEOUT_S)

declare -A VALUES=(
  [SERVICE_USER]=ianest-external-ha
  [INSTALL_ROOT]=/opt/ia_nest/external_home_assistant
  [HA_URL]=http://ha.example:8123
  [HA_TOKEN_SOURCE]=''
  [CORE_TOKEN_SOURCE]=''
  [SCRIPTS_SOURCE]=''
  [HOST]=127.0.0.1
  [PORT]=8770
  [TIMEOUT_S]=8
)

CONFIG_FILE=''

error() {
  echo "error: $1" >&2
  exit 1
}

usage() {
  sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
}

load_config_file() {
  local path="$1" line key value line_number=0
  [[ -r "$path" ]] || error "no se puede leer --config: $path"
  while IFS= read -r line || [[ -n "$line" ]]; do
    line_number=$((line_number + 1))
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    [[ "$line" == *=* ]] || error "$path:$line_number: se esperaba CLAVE=VALOR"
    key="${line%%=*}"
    value="${line#*=}"
    [[ -n "${VALUES[$key]+present}" ]] || error "$path:$line_number: clave desconocida '$key'"
    VALUES["$key"]="$value"
  done < "$path"
}

check_python() {
  local candidate
  for candidate in python3 python3.14 python3.13; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 13))'; then
      PYTHON_BIN="$candidate"
      return
    fi
  done
  error "se requiere Python >=3.13"
}

validate_config() {
  [[ "${EUID}" -eq 0 ]] || error "setup.sh debe ejecutarse como root"
  [[ -n "${VALUES[HA_URL]}" ]] || error "HA_URL no puede estar vacio"
  [[ "${VALUES[HOST]}" == 127.0.0.1 ]] || error "HOST debe ser 127.0.0.1"
  [[ "${VALUES[PORT]}" =~ ^[0-9]+$ ]] || error "PORT debe ser numerico"
  [[ "${VALUES[TIMEOUT_S]}" =~ ^[0-9]+([.][0-9]+)?$ ]] || error "TIMEOUT_S debe ser numerico"
  [[ -r "${VALUES[HA_TOKEN_SOURCE]}" ]] || error "no se puede leer HA_TOKEN_SOURCE"
  [[ -r "${VALUES[CORE_TOKEN_SOURCE]}" ]] || error "no se puede leer CORE_TOKEN_SOURCE"
  [[ -z "${VALUES[SCRIPTS_SOURCE]}" || -r "${VALUES[SCRIPTS_SOURCE]}" ]] || error "no se puede leer SCRIPTS_SOURCE"
}

prepare_user_and_paths() {
  local service_user="${VALUES[SERVICE_USER]}"
  if ! id "$service_user" >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$service_user"
  fi
  CONFIG_DIR="${VALUES[INSTALL_ROOT]}/config"
  VENV_DIR="${VALUES[INSTALL_ROOT]}/venv"
  install -d -o "$service_user" -g "$service_user" -m 750 "${VALUES[INSTALL_ROOT]}" "$CONFIG_DIR"
}

install_package() {
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install --upgrade pip setuptools >/dev/null
  "$VENV_DIR/bin/pip" install "$REPO_DIR"
  chown -R "${VALUES[SERVICE_USER]}:${VALUES[SERVICE_USER]}" "$VENV_DIR"
}

install_private_files() {
  HA_TOKEN_FILE="$CONFIG_DIR/ha.token"
  CORE_TOKEN_FILE="$CONFIG_DIR/core.token"
  ENV_FILE="$CONFIG_DIR/ianest-external-ha.env"
  install -o "${VALUES[SERVICE_USER]}" -g "${VALUES[SERVICE_USER]}" -m 600 "${VALUES[HA_TOKEN_SOURCE]}" "$HA_TOKEN_FILE"
  install -o "${VALUES[SERVICE_USER]}" -g "${VALUES[SERVICE_USER]}" -m 600 "${VALUES[CORE_TOKEN_SOURCE]}" "$CORE_TOKEN_FILE"
  SCRIPTS_FILE="$CONFIG_DIR/scripts.json"
  if [[ -n "${VALUES[SCRIPTS_SOURCE]}" ]]; then
    install -o "${VALUES[SERVICE_USER]}" -g "${VALUES[SERVICE_USER]}" -m 600 "${VALUES[SCRIPTS_SOURCE]}" "$SCRIPTS_FILE"
  else
    rm -f "$SCRIPTS_FILE"
  fi
  umask 077
  {
    printf 'IANEST_EXTERNAL_HA_URL=%s\n' "${VALUES[HA_URL]}"
    printf 'IANEST_EXTERNAL_HA_TOKEN_FILE=%s\n' "$HA_TOKEN_FILE"
    printf 'IANEST_EXTERNAL_HA_CORE_TOKEN_FILE=%s\n' "$CORE_TOKEN_FILE"
    printf 'IANEST_EXTERNAL_HA_TIMEOUT_S=%s\n' "${VALUES[TIMEOUT_S]}"
    [[ -n "${VALUES[SCRIPTS_SOURCE]}" ]] && printf 'IANEST_EXTERNAL_HA_SCRIPTS_FILE=%s\n' "$SCRIPTS_FILE"
  } > "$ENV_FILE"
  chown "${VALUES[SERVICE_USER]}:${VALUES[SERVICE_USER]}" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
}

write_unit() {
  local unit_path="/etc/systemd/system/$UNIT_NAME"
  cat > "$unit_path" <<EOF
[Unit]
Description=IA_NEST closed Home Assistant MCP catalog
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${VALUES[SERVICE_USER]}
Group=${VALUES[SERVICE_USER]}
WorkingDirectory=${VALUES[INSTALL_ROOT]}
EnvironmentFile=$ENV_FILE
ExecStart=$VENV_DIR/bin/ianest-external-ha --host ${VALUES[HOST]} --port ${VALUES[PORT]}
Restart=on-failure
RestartSec=2
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ProtectKernelTunables=true
ProtectControlGroups=true
ReadWritePaths=${VALUES[INSTALL_ROOT]}

[Install]
WantedBy=multi-user.target
EOF
  chmod 644 "$unit_path"
  systemctl daemon-reload
}

wait_for_port() {
  local attempt
  for ((attempt = 1; attempt <= 30; attempt++)); do
    if timeout 2 bash -c "cat < /dev/null > /dev/tcp/${VALUES[HOST]}/${VALUES[PORT]}" 2>/dev/null; then return; fi
    sleep 1
  done
  error "el servicio no escucha tras 30 segundos"
}

monotonic_microseconds() {
  "$VENV_DIR/bin/python" -c 'import time; print(time.clock_gettime_ns(time.CLOCK_MONOTONIC) // 1000)'
}

verify_service_restarted() {
  local before="$1" active_since
  active_since="$(systemctl show --property=ActiveEnterTimestampMonotonic --value "$UNIT_NAME")" || error "no se pudo comprobar el reinicio"
  [[ "$active_since" =~ ^[0-9]+$ && "$active_since" -gt "$before" ]] || error "$UNIT_NAME no se reinicio en esta pasada"
}

verify_tools_list() {
  CORE_TOKEN_FOR_VERIFY="$(<"$CORE_TOKEN_FILE")" "$VENV_DIR/bin/python" - "http://${VALUES[HOST]}:${VALUES[PORT]}/mcp" <<'PY'
import asyncio
import os
import sys

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    headers = {"Authorization": "Bearer " + os.environ["CORE_TOKEN_FOR_VERIFY"]}
    async with httpx.AsyncClient(headers=headers) as http_client:
        async with streamable_http_client(sys.argv[1], http_client=http_client) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                names = [tool.name for tool in (await session.list_tools()).tools]
    if "get_live_context" not in names:
        raise SystemExit("tools/list no publico get_live_context")

asyncio.run(main())
PY
}

verify_unauthenticated() {
  local status
  status="$(curl -sS -o /dev/null -w '%{http_code}' -X POST "http://${VALUES[HOST]}:${VALUES[PORT]}/mcp")"
  [[ "$status" == 401 ]] || error "tools/list sin Bearer debia devolver 401, devolvio $status"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) [[ $# -ge 2 ]] || error "--config requiere una ruta"; CONFIG_FILE="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) error "argumento no reconocido: $1" ;;
  esac
done

[[ -n "$CONFIG_FILE" ]] || error "--config es obligatorio; usa deploy/ejemplo.setup.conf"
load_config_file "$CONFIG_FILE"
check_python
validate_config
prepare_user_and_paths
install_package
install_private_files
write_unit
restart_started="$(monotonic_microseconds)"
systemctl enable "$UNIT_NAME"
systemctl restart "$UNIT_NAME"
wait_for_port
systemctl is-active --quiet "$UNIT_NAME" || error "$UNIT_NAME no quedo activo"
verify_service_restarted "$restart_started"
verify_tools_list
verify_unauthenticated
echo "setup completado: $UNIT_NAME"
