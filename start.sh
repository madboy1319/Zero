#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# start.sh — Launch Zero gateway + WhatsApp bridge
# ─────────────────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   Zero + WhatsApp — Starting Up      ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. Start Zero API server in background ───────────────────────────────────
echo "▶ Starting Zero API server (port 18790)..."
python -m zero serve --port 18790 &
ZERO_PID=$!
echo "  Zero PID: $ZERO_PID"

# ── 2. Wait for Zero to boot ──────────────────────────────────────────────────
echo "  Waiting for Zero to be ready..."
for i in $(seq 1 15); do
  if curl -sf http://localhost:18790/v1/models > /dev/null 2>&1; then
    echo "  ✅ Zero is ready!"
    break
  fi
  sleep 1
done

echo ""

# ── 3. Start WhatsApp bridge ──────────────────────────────────────────────────
echo "▶ Starting WhatsApp bridge..."
echo "  (Scan QR code if this is your first time)"
echo ""
node whatsapp_bridge.js

# ── Cleanup on exit ───────────────────────────────────────────────────────────
trap "echo ''; echo 'Shutting down Zero...'; kill $ZERO_PID 2>/dev/null; exit 0" SIGINT SIGTERM
