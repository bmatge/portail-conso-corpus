# Assistant Consommateur DGCCRF

Application web d'orientation des consommateurs, construite sur un pipeline RAG (Retrieval-Augmented Generation) qui transforme les corpus réglementaires de la DGCCRF en fiches pratiques structurées.

## Fonctionnalités

- **Chatbot conversationnel** : le consommateur décrit son problème en langage libre, le LLM identifie la situation dans la taxonomie DGCCRF et propose les recours adaptés (SignalConso, médiation, autorités compétentes…)
- **Arbre de décision interactif** : visualisation D3.js de la taxonomie (12 domaines, 60 sous-domaines, 192 situations) avec navigation par zoom et mise en surbrillance contextuelle
- **267 fiches pratiques** : générées automatiquement par LLM à partir des sources officielles, consultables via une interface de navigation ou la recherche sémantique
- **Recherche sémantique** : interrogation vectorielle (ChromaDB + e5-small) sur l'ensemble du corpus (~23 000 chunks)

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Navigateur                                         │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Chatbot  │  │ Fiches       │  │ Recherche     │  │
│  │ index.html│  │ fiches.html  │  │ search.html   │  │
│  └────┬─────┘  └──────────────┘  └───────┬───────┘  │
│       │                                   │          │
└───────┼───────────────────────────────────┼──────────┘
        │ /api/chat                         │ /api/search
        ▼                                   ▼
┌───────────────────────────────────────────────────────┐
│  FastAPI  (api/search_api.py)                         │
│  ├── /api/search  → ChromaDB (cosine similarity)      │
│  ├── /api/chat    → Albert LLM (DINUM)                │
│  └── /api/health                                      │
├───────────────────────────────────────────────────────┤
│  nginx  (reverse proxy, CORS proxy, assets statiques) │
└───────────────────────────────────────────────────────┘
```

## Taxonomie

Le fichier `taxonomie-dgccrf.json` (v3.0) structure l'ensemble du domaine consommation/concurrence :

| Niveau | Quantité | Exemple |
|--------|----------|---------|
| Domaines | 12 | Pratiques commerciales, Numérique, Logement… |
| Sous-domaines | 60 | Garantie légale, Démarchage, Crédit conso… |
| Situations | 192 | Produit défectueux, Arnaque en ligne, Vice caché… |
| Types de sortie | 17 | SignalConso, médiation, CNIL, ARCOM, AMF… |

Chaque situation référence ses types de sortie (URLs directes vers SignalConso, médiateurs, autorités) et, le cas échéant, sa catégorie SignalConso pour le signalement.

## Pipeline RAG

Le pipeline (`scripts/dgccrf-rewrite/`) transforme les sources brutes en fiches consultables :

```
Corpus sources                  Pipeline                     Sortie
─────────────                  ────────                     ──────
dgccrf-drupal/    (1 754 .md)  02_prepare_inc.py            corpus/
particuliers-drupal/ (361 .md)  ─ Nettoyage INC               ├── alimentaire/
entreprises-drupal/  (271 .md)      │                         │   ├── _index.md
inc-conso-md/     (3 151 .md)  03_index_chroma.py            │   ├── sous_domaine/
                                ─ Indexation ChromaDB          │   │   ├── _index.md
taxonomie-dgccrf.json              │                          │   │   └── situation.md
                               04_inventaire.py               ├── ...
                                ─ Couverture par item          └── transversales/
                                    │
                               05_generate_fiches.py
                                ─ Génération LLM (bottom-up)
                                    │
                               06_validate.py
                                ─ Validation structure + URLs
```

### Étapes

1. **Nettoyage INC** (`02_prepare_inc.py`) — Suppression du boilerplate (cookies, tracking), normalisation des titres dupliqués, nettoyage des descriptions JSON
2. **Indexation ChromaDB** (`03_index_chroma.py`) — Découpage en chunks (500 car., 100 overlap), embedding e5-small (384 dim), indexation des 4 corpus + fiches générées
3. **Inventaire de couverture** (`04_inventaire.py`) — Évaluation des sources disponibles par item de la taxonomie, identification des lacunes
4. **Génération des fiches** (`05_generate_fiches.py`) — Génération bottom-up : situations d'abord, puis sous-domaines (qui résument leurs situations), puis domaines. Chaque fiche est enrichie par le contexte RAG (top-20 chunks). LLM : Albert (DINUM), modèle `openweight-medium`, température 0.3
5. **Validation** (`06_validate.py`) — Vérification du frontmatter, des sections attendues (En bref, Ce que couvre, Vos droits, Que faire, Services, Aller plus loin), des URLs et de la complétude

### Configuration

```yaml
# scripts/dgccrf-rewrite/config.yaml (extrait)
embeddings:
  model_name: "intfloat/multilingual-e5-small"
chunking:
  chunk_size: 500
  chunk_overlap: 100
retrieval:
  collection_name: "dgccrf_corpus"
  top_k: 20
  max_source_chars: 25000
llm:
  endpoint: "https://albert.api.etalab.gouv.fr/v1"
  model: "openweight-medium"
  temperature: 0.3
```

La clé API est lue depuis la variable d'environnement `LLM_API_KEY`.

## Stack technique

| Composant | Technologie |
|-----------|------------|
| Frontend | HTML/JS vanilla, DSFR 1.12.1 (Design System de l'État) |
| Visualisation | D3.js v7 (arbre de décision), Marked.js (rendu Markdown) |
| Backend API | FastAPI + Uvicorn |
| Recherche vectorielle | ChromaDB, sentence-transformers (e5-small) |
| LLM | Albert API (DINUM) — compatible OpenAI, configurable |
| Pipeline | Python 3.11, Pydantic, python-frontmatter, tqdm |
| Tests | Vitest + jsdom |
| Déploiement | Docker (multi-stage), nginx, Traefik |

## Installation

### Prérequis

- Python 3.11+
- Node.js 18+ (pour les tests)
- Docker & Docker Compose (pour le déploiement)

### Développement local

```bash
# Dépendances Python (pipeline)
pip install -r scripts/dgccrf-rewrite/requirements.txt

# Dépendances Python (API)
pip install -r api/requirements.txt

# Dépendances JS (tests)
npm install

# Lancer le pipeline complet
cd scripts/dgccrf-rewrite
export LLM_API_KEY="votre-clé-albert"
python 03_index_chroma.py --reset
python 05_generate_fiches.py --resume
python 06_validate.py

# Construire l'index du corpus (nécessaire pour le frontend)
python scripts/build_corpus_index.py

# Lancer l'API
uvicorn api.search_api:app --reload --port 8000

# Lancer le serveur de dev (port 8888, avec proxy CORS)
python serve.py
```

L'application est alors accessible sur `http://localhost:8888`.

### Docker

```bash
export LLM_API_KEY="votre-clé-albert"
docker compose up --build -d
```

Le conteneur expose le port 80 (nginx) avec :
- Assets statiques (HTML, JS, CSS, corpus)
- API FastAPI sur `/api/`
- Proxy CORS sur `/proxy-https/` pour les appels LLM depuis le navigateur

## Tests

```bash
npm test            # exécution unique
npm run test:watch  # mode watch
```

Les tests couvrent : gestion de la configuration, rendu de l'interface chat, adaptateurs LLM, composants de résultats de recherche.

## Structure des fichiers

```
├── index.html                   # Chatbot + arbre de décision
├── fiches.html                  # Navigation fiches pratiques
├── search.html                  # Recherche sémantique
├── css/                         # Styles (DSFR overrides)
├── js/                          # Modules frontend
│   ├── app.js                   # Chatbot principal
│   ├── taxonomy-tree.js         # Visualisation D3
│   ├── fiches-app.js            # Navigateur de fiches
│   ├── search-page.js           # Page de recherche
│   ├── llm-adapter.js           # Abstraction API LLM
│   └── header-search.js         # Barre de recherche header
├── api/
│   └── search_api.py            # FastAPI (search + chat)
├── corpus/                      # 267 fiches générées (.md)
├── taxonomie-dgccrf.json        # Taxonomie v3.0 (187 KB)
├── scripts/
│   ├── dgccrf-rewrite/          # Pipeline RAG
│   │   ├── config.yaml
│   │   ├── 02_prepare_inc.py
│   │   ├── 03_index_chroma.py
│   │   ├── 04_inventaire.py
│   │   ├── 05_generate_fiches.py
│   │   ├── 06_validate.py
│   │   └── lib/                 # Modules partagés
│   └── build_corpus_index.py    # Génère corpus/index.json
├── dgccrf-drupal/               # Corpus DGCCRF (1 754 fiches)
├── particuliers-drupal/         # Corpus service-public.fr (361)
├── entreprises-drupal/          # Corpus entreprises (271)
├── inc-conso-md/                # Corpus INC (3 151)
├── tests/                       # Tests Vitest
├── Dockerfile                   # Build multi-stage
├── docker-compose.yml           # Déploiement avec Traefik
└── serve.py                     # Serveur de dev (port 8888)
```

## Licence

Projet interne DGCCRF — SNUM / MIWEB.
