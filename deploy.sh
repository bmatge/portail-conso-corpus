#!/usr/bin/env bash
set -euo pipefail

echo "=== Arrêt du conteneur ==="
docker compose down

echo "=== Pull des dernières modifications ==="
git checkout -- corpus/index.json 2>/dev/null || true
git pull
git lfs pull

echo "=== Rebuild corpus index ==="
pip install -q pyyaml 2>/dev/null || true
python3 scripts/build_corpus_index.py

echo "=== Build de l'image (no cache) ==="
docker compose build

echo "=== Démarrage ==="
docker compose up -d

echo "=== Déployé ==="
docker compose ps
