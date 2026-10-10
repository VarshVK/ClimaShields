#!/bin/bash
set -e

PORT="${PORT:-8080}"
HOST="${HOST:-127.0.0.1}"

echo "=========================================================="
echo "🛡️  ClimaShield Unified Platform"
echo "   - 🌤️  AI Weather Forecast Reliability Detector"
echo "   - 🚨  Flood Evacuation Route Planner"
echo "=========================================================="
echo "Server starting at: http://${HOST}:${PORT}"
echo "=========================================================="

cd "$(dirname "$0")"

python3 -m uvicorn backend.app:app --host "${HOST}" --port "${PORT}" --reload
