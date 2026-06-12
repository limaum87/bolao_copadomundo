#!/bin/bash
# Cron job para sincronizar resultados da Copa 2026
# Executa a cada 15 minutos nos dias de jogo
#
# Instalar: crontab -e
# */15 * * * * /app/backend/sync_cron.sh >> /var/log/bolao_sync.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/.env.sync" 2>/dev/null || true

API_URL="${BOLAO_API_URL:-http://localhost:5000}"
TOKEN="${BOLAO_ADMIN_TOKEN:-}"

cd "$(dirname "$0")"

if [ -n "$TOKEN" ]; then
    python3 sync_results.py --all --api-url "$API_URL" --token "$TOKEN"
else
    # Se tiver credenciais de login
    if [ -n "$ADMIN_USER" ] && [ -n "$ADMIN_PASS" ]; then
        python3 sync_results.py --all --api-url "$API_URL" --login "$ADMIN_USER" "$ADMIN_PASS"
    else
        echo "[$(date)] ERRO: Configure BOLAO_ADMIN_TOKEN ou ADMIN_USER/ADMIN_PASS em .env.sync"
        exit 1
    fi
fi
