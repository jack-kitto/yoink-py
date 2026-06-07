#!/usr/bin/env bash
# example/server.sh — a fake server that requires secrets to start
#
# Run this directly and it will fail. Run it via yoink and it works.
# That's the whole point.
#
# Usage:
#   yoink run dev -- bash example/server.sh

set -euo pipefail

required=(
  DATABASE_URL
  API_KEY
  JWT_SECRET
)

missing=()
for var in "${required[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    missing+=("$var")
  fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
  echo ""
  echo "  ERROR: missing required environment variables:"
  for var in "${missing[@]}"; do
    echo "    - $var"
  done
  echo ""
  echo "  Run with: yoink run dev -- bash example/server.sh"
  echo ""
  exit 1
fi

echo ""
echo "  server starting..."
echo ""
echo "  DATABASE_URL  = ${DATABASE_URL}"
echo "  API_KEY       = ${API_KEY:0:8}... (truncated)"
echo "  JWT_SECRET    = ${JWT_SECRET:0:8}... (truncated)"
echo ""
echo "  all secrets loaded. server would start here."
echo ""
