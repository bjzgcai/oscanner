#!/usr/bin/env bash
set -euo pipefail

# Minimal backend smoke test for CI only.
# Requires: docker, jq, curl

IMAGE="${1:-ink-backend:ci}"
PORT="${PORT:-18765}"
CONTAINER_NAME="ink-backend-smoke"
DB_DIR="$(mktemp -d)"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  rm -rf "${DB_DIR}"
}
trap cleanup EXIT

echo "🚀 Starting container ${IMAGE} on port ${PORT} with db at ${DB_DIR}"
docker run -d --rm --name "${CONTAINER_NAME}" -p "${PORT}:8765" -v "${DB_DIR}:/app/data" "${IMAGE}" >/dev/null

echo "⏳ Waiting for server..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/docs" >/dev/null; then
    break
  fi
  sleep 1
done

# Initialize database tables + seed system decks
docker exec "${CONTAINER_NAME}" python database.py >/dev/null

API="http://127.0.0.1:${PORT}/api"

echo "👤 Registering user..."
REGISTER_RES=$(curl -s -X POST -H "Content-Type: application/json" \
  -d '{"email":"ci-smoke@example.com","password":"test123","display_name":"CI Smoke"}' \
  "${API}/register")
TOKEN=$(echo "${REGISTER_RES}" | jq -r '.token')
if [[ -z "${TOKEN}" || "${TOKEN}" == "null" ]]; then
  echo "Register failed: ${REGISTER_RES}"
  exit 1
fi

echo "🃏 Creating deck..."
CREATE_RES=$(curl -s -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"name":"Smoke Deck","description":"CI deck"}' \
  "${API}/decks")
DECK_ID=$(echo "${CREATE_RES}" | jq -r '.deck_id')
if [[ -z "${DECK_ID}" || "${DECK_ID}" == "null" ]]; then
  echo "Deck creation failed: ${CREATE_RES}"
  exit 1
fi

echo "📋 Verifying deck exists..."
LIST_RES=$(curl -s -H "Authorization: Bearer ${TOKEN}" "${API}/decks")
echo "${LIST_RES}" | jq -e --arg id "${DECK_ID}" '.decks | map(.id == $id) | any' >/dev/null

echo "✅ Smoke test passed"
