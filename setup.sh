#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# setup.sh — Install all dependencies for Zero + WhatsApp bridge
# ─────────────────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   Zero — Setup Dependencies          ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Python dependencies ───────────────────────────────────────────────────────
echo "▶ Installing Python dependencies..."
pip install openai groq requests aiohttp

echo ""

# ── Node.js dependencies ──────────────────────────────────────────────────────
echo "▶ Installing Node.js dependencies (Baileys, no Puppeteer)..."
npm install

echo ""
echo "✅ All dependencies installed!"
echo ""
echo "Next steps:"
echo "  1. Make sure ~/.zero/config.json has your API key set"
echo "  2. Run: bash start.sh"
echo "  3. Scan the QR code with WhatsApp on first run"
echo ""
