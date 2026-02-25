#!/usr/bin/env bash
set -euo pipefail

echo "=== Arrêt du conteneur ==="
docker compose down

echo "=== Pull des dernières modifications ==="
git pull

echo "=== Build de l'image (no cache) ==="
docker compose build --no-cache

echo "=== Démarrage ==="
docker compose up -d

echo "=== Déployé ==="
docker compose ps
