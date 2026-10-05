#!/usr/bin/env sh
# Runs docker compose for the staging stack with every staging file and the
# staging env file, so the long command never has to be retyped.
#
#   sh scripts/staging.sh up --build -d
#   sh scripts/staging.sh ps
#   sh scripts/staging.sh logs --tail=100 worker
set -eu
cd "$(dirname "$0")/.."

if [ ! -f .env.staging ]; then
  echo "Missing .env.staging (copy .env.staging.example and fill it in)." >&2
  exit 1
fi

exec docker compose --env-file .env.staging \
  -f docker-compose.yml \
  -f docker-compose.staging.yml \
  -f docker-compose.staging-tuning.yml \
  "$@"
