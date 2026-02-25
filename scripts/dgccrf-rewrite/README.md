# Pipeline RAG — Réécriture corpus DGCCRF

Génère **167 fiches pratiques** consommateurs à partir de 4 corpus sources et d'un LLM (Albert DINUM par défaut), structurées selon la `taxonomie-dgccrf.json`.

## Prérequis

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Les 5 phases

### Phase 2 — Nettoyage INC

Corrige les ~3 150 fichiers INC (H1 dupliqués, bannières cookies, JSON résiduel).

```bash
python 02_prepare_inc.py --stats          # aperçu sans écrire
python 02_prepare_inc.py --save-cleaned   # sauvegarde dans output/corpus_inc/cleaned/
```

### Phase 3 — Indexation ChromaDB

Indexe les 4 corpus (dgccrf, particuliers, entreprises, inc) dans une base vectorielle locale.

```bash
python 03_index_chroma.py --reset         # première indexation (~5-10 min)
python 03_index_chroma.py --source inc    # ré-indexer une seule source
python 03_index_chroma.py --dry-run       # compter sans indexer
```

La base est dans `output/chroma_db/` (~200 Mo). Elle est portable : copier le dossier suffit pour la réutiliser ailleurs.

### Phase 4 — Inventaire de couverture

Évalue les sources disponibles pour chaque item de la taxonomie.

```bash
python 04_inventaire.py                    # tous les 167 items
python 04_inventaire.py --verbose          # détails par item
python 04_inventaire.py --situation pub_prix_mensonger  # un seul
```

Produit `output/_inventaire.json` avec couverture good/partial/low/none.

### Phase 5 — Génération LLM

Génère les fiches Markdown via RAG (retrieve → prompt → LLM).

```bash
export LLM_API_KEY=xxx

# Test sur 1 fiche
python 05_generate_fiches.py --dry-run --situation pub_prix_mensonger
python 05_generate_fiches.py --situation pub_prix_mensonger

# Par niveau
python 05_generate_fiches.py --level situation      # 115 fiches
python 05_generate_fiches.py --level sous_domaine   # 44 fiches
python 05_generate_fiches.py --level domaine         # 8 fiches

# Tout générer (bottom-up, reprend après interruption)
python 05_generate_fiches.py --resume
```

Les fiches sont dans `output/fiches/`, log dans `output/_generation_log.jsonl`.

### Phase 6 — Validation

Vérifie structure, URLs, complétude des fiches générées.

```bash
python 06_validate.py --verbose
```

Produit `output/_validation_report.json`.

## Configuration

Tout est dans `config.yaml`. Les secrets passent par variables d'environnement :

| Variable | Usage |
|----------|-------|
| `LLM_API_KEY` | Clé API Albert/OpenAI/Anthropic |
| `LLM_ENDPOINT` | Override endpoint (défaut: Albert DINUM) |
| `LLM_MODEL` | Override modèle (défaut: `openweight-medium`) |

## Structure de sortie

```
output/fiches/
├── domaines/                     # 8 fiches chapeau
│   └── pratiques_commerciales.md
├── pratiques_commerciales/       # sous-domaines + situations
│   └── publicite_trompeuse/
│       ├── _index.md             # fiche sous-domaine
│       ├── pub_prix_mensonger.md # fiche situation
│       └── ...
└── transversales/                # 3 fiches transversales
    └── litige_ue.md
```

## Docker / VPS

La base ChromaDB (`output/chroma_db/`) est portable. Pour la déployer :

```bash
scp -r output/chroma_db/ user@vps:/path/to/app/
```

Seuls `chromadb` et `sentence-transformers` sont nécessaires côté serveur pour les queries. Le modèle e5-small (~470 Mo) est téléchargé au premier lancement.
