# ── Stage 1 : dépendances Python + modèle d'embedding ──
FROM python:3.11-slim AS python-deps

COPY api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Pré-télécharger le modèle pour éviter le download au runtime
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"


# ── Stage 2 : image finale (Python + nginx) ──
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx wget && \
    rm -rf /var/lib/apt/lists/*

# Dépendances Python depuis le stage 1
COPY --from=python-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-deps /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=python-deps /root/.cache /root/.cache

# Config nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default

# Fichiers statiques
COPY index.html search.html fiches.html sources.html /usr/share/nginx/html/
COPY js/  /usr/share/nginx/html/js/
COPY css/ /usr/share/nginx/html/css/
COPY taxonomie-dgccrf.json /usr/share/nginx/html/
COPY corpus/ /usr/share/nginx/html/corpus/

# Source corpora (ancien corpus)
COPY dgccrf-drupal/ /usr/share/nginx/html/sources/dgccrf/
COPY particuliers-drupal/ /usr/share/nginx/html/sources/particuliers/
COPY entreprises-drupal/ /usr/share/nginx/html/sources/entreprises/
COPY inc-conso-md/content/ /usr/share/nginx/html/sources/inc/

# API Python
COPY api/ /app/api/

# Entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD wget -qO- http://127.0.0.1/api/health && wget -qO- http://127.0.0.1/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
