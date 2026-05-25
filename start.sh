#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Check for .env
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "⚠️  Created .env from .env.example"
    echo "➡️  Please open .env and add your OpenAI API key, then run this script again."
    open .env 2>/dev/null || nano .env
    exit 1
  fi
fi

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "❌ Python 3 not found. Install from https://python.org"
  exit 1
fi

# Create venv if needed
if [ ! -d venv ]; then
  echo "🔧 Creating Python virtual environment..."
  python3 -m venv venv
fi

# Activate and install
source venv/bin/activate
pip install -q -r requirements.txt

echo ""
PORT="${PORT:-8001}"

echo "✨ ============================================ ✨"
echo "   Sparkle's Magic Game Maker is starting!"
echo "✨ ============================================ ✨"
echo ""
echo "👉 Open your browser to: http://localhost:${PORT}"
echo "   (It will open automatically in a moment)"
echo ""
echo "   Press Ctrl+C to stop the server."
echo ""

# Open browser after short delay
sleep 2 && open "http://localhost:${PORT}" &

# Start server
PORT="${PORT}" uvicorn server:app --host 0.0.0.0 --port "${PORT}" --reload
