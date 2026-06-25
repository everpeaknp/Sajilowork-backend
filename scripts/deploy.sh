#!/bin/bash

set -euo pipefail

cd "$(dirname "$0")/.."

docker compose config >/dev/null
docker compose pull || true
docker compose up -d --build --force-recreate --remove-orphans
docker compose ps
