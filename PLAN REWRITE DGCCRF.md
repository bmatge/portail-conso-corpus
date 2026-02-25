# Plan complet : Reecriture du corpus DGCCRF

> **Version** : 2.0 — Fevrier 2025
> **Auteur** : MIWEB — Mission Ingenierie du Web, SNUM
> **Taxonomie de reference** : `taxonomie_dgccrf.json` v2.0 (avec mapping SignalConso)

---

## 1. Objectif

Produire **137 fiches pratiques** couvrant l'integralite de la taxonomie DGCCRF, a 3 niveaux de profondeur :

| Niveau | Nombre | Role editorial | Exemple |
|--------|--------|----------------|---------|
| **Domaine** | 8 | Fiche chapeau — vue d'ensemble du domaine, navigation vers les sous-domaines | "Pratiques commerciales deloyales : comprendre et agir" |
| **Sous-domaine** | 34 | Fiche thematique — guide complet sur le sujet, droits, recours, liens vers les situations | "Publicite trompeuse : vos droits et recours" |
| **Situation** | 92 + 3 transversales = 95 | Fiche cas concret — actionnable, specifique, avec sortie vers le bon service | "Le prix reel est superieur au prix annonce" |
| **TOTAL** | **137** | | |

Chaque fiche est generee par un LLM en synthetisant le contenu de 2 corpus sources, structuree selon un modele editorial precis, et articulee autour de l'arbre de decision `taxonomie_dgccrf.json`.

---

## 2. Corpus sources

### 2.1 DGCCRF Drupal (source principale)

- **Origine** : Base MySQL du site economie.gouv.fr, groupe DGCCRF (gid = 113)
- **Contenu** : Fiches existantes (articles, pages), avec body HTML + paragraphes recursifs
- **Extraction** : Via les fonctions existantes du portail-eco-browser :
  - `ContentExplorerService.get_node_full(nid)` → contenu complet avec paragraphes recursifs
  - `search_contents(group_id="113")` → liste paginee des nodes du groupe
  - `strip_html()` de `rag_index_local.py` → nettoyage HTML
- **Volume estime** : quelques centaines de nodes
- **Qualite** : contenu editorial existant, potentiellement redondant entre fiches

### 2.2 INC — Institut National de la Consommation (source complementaire)

- **Origine** : Aspiration du site inc-conso.fr
- **Emplacement** : `/Users/bertrand/Documents/GitHub/portail-conso-corpus/inc-conso-md/`
- **Format** : ~2 487 fichiers Markdown avec frontmatter YAML (title, source, date, tags)
- **Contenu** : Guides pratiques, droits du consommateur, FAQ
- **Volume** : ~15 Mo, articles de 1 a 77 Ko
- **Qualite** : corpus brut non nettoye — bannieres cookies, doublons H1, HTML residuel, images CDN, blocs de navigation scrapes. Nettoyage necessaire (Phase 2).

### 2.3 Taxonomie DGCCRF (structure cible)

- **Fichier** : `taxonomie_dgccrf.json` v2.0
- **Structure** : 8 domaines → 34 sous-domaines → 92 situations + 3 transversales
- **Enrichissement v2** : champ `signalconso` par situation avec category, subcategory_hints, URL de signalement direct, question_pivot
- **16 types de sortie** : SignalConso, mediation, service-public.fr, CNIL, ARCOM, AMF, DGAL, ANSM, ACPR, ARCEP, juridiction, police, 17Cyber, cybermalveillance, RappelConso, liste mediateurs
- **18 categories SignalConso** : mapping vers les formulaires de signalement

---

## 3. Architecture du pipeline

```
Phase 1          Phase 2           Phase 3              Phase 4          Phase 5           Phase 6
Extraction       Nettoyage         Indexation            Inventaire       Generation        Validation
DGCCRF           INC               ChromaDB              couverture       LLM               qualite
                                                                         137 fiches
  Drupal           INC brut
  MySQL            .md files
    |                |
    v                v
  corpus/          corpus/
  dgccrf/          inc/
    |                |
    +-------+--------+
            |
            v
       ChromaDB local
       (E5-small 384D)
            |
            v
      Pour chaque item
      de la taxonomie :
      query semantique
      → top-K sources
            |
            v
      Prompt 3 couches
      + LLM configurable
            |
            v
       fiches/ .md
       par niveau
            |
            v
       Validation
       completude
```

### Scripts

```
scripts/dgccrf-rewrite/
├── config.yaml                  # Configuration unique
├── requirements.txt             # Dependances Python
├── 01_extract_dgccrf.py         # Phase 1
├── 02_prepare_inc.py            # Phase 2
├── 03_index_chroma.py           # Phase 3
├── 04_inventaire.py             # Phase 4
├── 05_generate_fiches.py        # Phase 5
├── 06_validate.py               # Phase 6
├── lib/
│   ├── config.py                # Loader YAML + Pydantic + env vars
│   ├── taxonomy.py              # Parser taxonomie → SituationContext
│   ├── text_utils.py            # HTML→MD, chunking, nettoyage
│   ├── chroma_utils.py          # ChromaDB helpers
│   ├── llm_client.py            # Client LLM OpenAI-compatible
│   └── prompt_builder.py        # Assemblage prompt 3 couches x 3 niveaux
├── prompts/
│   ├── system.md                # Role + ton editorial
│   ├── template_domaine.md      # Structure fiche domaine
│   ├── template_sous_domaine.md # Structure fiche sous-domaine
│   ├── template_situation.md    # Structure fiche situation
│   └── checklist.md             # Checklist de completude
└── output/
    ├── corpus_dgccrf/           # Phase 1
    ├── corpus_inc/              # Phase 2
    ├── chroma_db/               # Phase 3
    ├── _inventaire.json         # Phase 4
    ├── fiches/                  # Phase 5
    │   ├── domaines/            # 8 fiches chapeau
    │   ├── pratiques_commerciales/
    │   │   ├── _index.md        # fiche sous-domaine "publicite_trompeuse"
    │   │   ├── publicite_trompeuse/
    │   │   │   ├── _index.md    # fiche sous-domaine
    │   │   │   ├── pub_caracteristiques_fausses.md
    │   │   │   └── pub_prix_mensonger.md
    │   │   └── ...
    │   └── transversales/
    │       ├── litige_ue.md
    │       └── ...
    ├── _generation_log.jsonl    # Log de generation
    └── _validation_report.json  # Rapport qualite
```

---

## 4. Les 6 phases en detail

### Phase 1 : Extraction DGCCRF (`01_extract_dgccrf.py`)

**Entree** : MySQL Drupal (base `economie`), groupe 113
**Sortie** : `output/corpus_dgccrf/` — un `.md` par node + `_corpus_dgccrf.json` (manifeste)

1. Connexion MySQL directe (meme pattern que `backend/scripts/rag_index_local.py`)
2. Recuperation de tous les NIDs du groupe 113 :
   ```sql
   SELECT DISTINCT entity_id FROM group_relationship_field_data
   WHERE gid = 113 AND plugin_id LIKE 'group_node:%'
   ```
3. Pour chaque node : extraction complete (body + paragraphes recursifs)
   - Resolution recursive des paragraphes (logique de `rag_index_local.py` l.187-306)
   - Conversion HTML → Markdown via `html2text` (preserve la structure)
   - Fallback `strip_html()` pour le texte brut
4. Enrichissement : alias URL (`path_alias`), termes de taxonomie (`taxonomy_index`)
5. Sauvegarde : un `.md` avec frontmatter YAML par node :
   ```yaml
   ---
   nid: 12345
   title: "Publicite mensongere : comment reagir ?"
   type: article_espace
   status: 1
   created: "2023-05-12"
   changed: "2024-11-03"
   alias: "/dgccrf/publicite-mensongere"
   taxonomy: ["Consommation", "Publicite"]
   source: dgccrf
   ---
   # Publicite mensongere : comment reagir ?
   [contenu en markdown...]
   ```
6. Manifeste `_corpus_dgccrf.json` avec metadonnees de tous les nodes extraits

**CLI** : `python 01_extract_dgccrf.py [--dry-run] [--group-id 113]`

**Fonctions existantes reutilisees** :
- `backend/scripts/rag_index_local.py` : pattern MySQL, `chunk_text()`, `strip_html()`, resolution paragraphes
- `backend/app/services/content_explorer.py` : logique `get_node_full()`, `_get_node_paragraphs()` comme reference

---

### Phase 2 : Preparation INC (`02_prepare_inc.py`)

**Entree** : corpus brut INC (`inc-conso-md/content/`)
**Sortie** : `output/corpus_inc/_corpus_inc.json` (manifeste) + optionnel `cleaned/`

**Le corpus INC est brut et non nettoye.** Cette phase doit :

1. **Scanner** tous les `.md` dans `content/` (~2 487 fichiers)
2. **Parser** le frontmatter YAML (title, source, date, description, tags, scraped_at)
3. **Nettoyer** chaque fichier :
   - Supprimer les bannieres cookies/consentement
   - Supprimer les doublons de titre H1
   - Supprimer les lignes images-only (references CDN INC)
   - Supprimer le HTML residuel dans le champ `description` (`[[{"type":"media",...}]]`)
   - Supprimer les blocs de navigation/menu scrapes par erreur
   - Normaliser les sauts de ligne excessifs
4. **Filtrer** :
   - Exclure les fichiers < 200 caracteres apres nettoyage
   - Exclure les repertoires `categories-des-rappels-produits/` et `thematique-des-organismes/` (boilerplate)
   - Exclure les fichiers dont le contenu nettoye est majoritairement du boilerplate
5. **Reporter** : stats (acceptes, rejetes par motif, distribution de taille)
6. **Sauvegarder** optionnellement les versions nettoyees dans `output/corpus_inc/cleaned/`

**CLI** : `python 02_prepare_inc.py [--stats] [--save-cleaned]`

---

### Phase 3 : Indexation ChromaDB (`03_index_chroma.py`)

**Entree** : corpus DGCCRF extrait + corpus INC prepare
**Sortie** : `output/chroma_db/` (base vectorielle persistante)

1. ChromaDB `PersistentClient` + `SentenceTransformerEmbeddingFunction`
2. Modele d'embedding : `intfloat/multilingual-e5-small` (384D)
3. Chunking : 500 caracteres, 100 overlap, coupure aux limites de phrase
4. Chaque chunk est prefixe par le titre du document (meilleur contexte semantique)
5. Metadonnees par chunk :
   | Champ | Valeur |
   |-------|--------|
   | `source` | `dgccrf` ou `inc` |
   | `title` | titre du document source |
   | `nid` | ID Drupal (DGCCRF uniquement) |
   | `url` | URL source (INC) ou alias (DGCCRF) |
   | `content_type` | type Drupal ou vide |
   | `chunk_index` | position dans le document |
6. Insertion par batch de 100

**CLI** : `python 03_index_chroma.py [--reset] [--source dgccrf|inc]`

**Dependances** : `chromadb`, `sentence-transformers`

---

### Phase 4 : Inventaire de couverture (`04_inventaire.py`)

**Entree** : ChromaDB + `taxonomie_dgccrf.json`
**Sortie** : `output/_inventaire.json`

Pour chaque item des 3 niveaux (8 domaines + 34 sous-domaines + 95 situations = 137 items) :

1. Construire une requete semantique :
   - Domaine : `domaine.label + domaine.description`
   - Sous-domaine : `sous_domaine.label + domaine.label`
   - Situation : `situation.label + situation.exemples + sous_domaine.label`
2. Interroger ChromaDB (top_k=20, score minimum 0.3)
3. Evaluer la couverture :
   - `good` : sources DGCCRF + INC pertinentes
   - `partial` : une seule source
   - `low` : < 3 chunks pertinents
   - `none` : aucun chunk pertinent
4. Lister les top-5 sources par item
5. Resume global : combien de fiches sont couvertes, partiellement couvertes, sans source

**Utilite** : identifier les trous de couverture AVANT de lancer le LLM. Permet d'ajuster la taxonomie, chercher des sources complementaires, ou marquer certaines fiches comme `[A COMPLETER]` d'emblee.

**CLI** : `python 04_inventaire.py [--situation ID] [--domaine ID] [--level domaine|sous_domaine|situation]`

---

### Phase 5 : Generation des fiches (`05_generate_fiches.py`)

**Entree** : ChromaDB + taxonomie + prompts + LLM
**Sortie** : 137 fichiers `.md` dans `output/fiches/` + `_generation_log.jsonl`

#### 5.1 Configuration LLM

Configurable dans `config.yaml`, overridable par variables d'environnement :

```yaml
llm:
  endpoint: "https://albert.api.etalab.gouv.fr/v1"   # ou api.anthropic.com, api.openai.com, etc.
  api_key: ""                # LLM_API_KEY env var
  model: "neuronx-llama-3-1-70b-instruct"
  temperature: 0.3
  max_tokens: 4000           # situations : 4000, sous-domaines : 6000, domaines : 5000
  timeout: 120
  rate_limit_rpm: 30
  retry_count: 3
```

Tous les endpoints OpenAI-compatible sont supportes (Albert, Claude via adaptateur, OpenAI, Mistral, Ollama local...).

#### 5.2 Prompts — 3 couches x 3 niveaux

**Couche 1 — `system.md`** (commune a tous les niveaux) :
- Redacteur expert DGCCRF, droit de la consommation francais
- Langage clair, phrases courtes (20 mots max), voix active, "vous"
- Pas de jargon dans le corps, references legales en "Pour aller plus loin"
- Synthese des sources (pas de copie verbatim)
- `[A COMPLETER]` si info manquante plutot qu'inventer

**Couche 2 — Templates par niveau** :

##### `template_domaine.md` (8 fiches chapeau)

```
# [Nom du domaine] : comprendre et agir

## En bref
[3-4 phrases. Ce que couvre ce domaine, pourquoi c'est important.]

## Ce que couvre ce domaine
[Liste des sous-domaines avec description courte de chacun.
Liens internes vers les fiches sous-domaines.]

## Vos droits essentiels
[Les grands principes juridiques qui traversent tout le domaine.
En langage simple, sans articles de loi.]

## Que faire en cas de probleme ?
[Les reflexes generaux, communs a toutes les situations du domaine.
Les grandes etapes : contacter le pro, signaler, mediation, recours.]

## Les services a connaitre
[Liste des sorties les plus frequentes pour ce domaine, avec liens.]

## Pour aller plus loin
[Textes de reference du domaine. Codes, directives europeennes.]
```

##### `template_sous_domaine.md` (34 fiches thematiques)

```
# [Sous-domaine] : vos droits et recours

## En bref
[2-3 phrases. De quoi il s'agit, qui est concerne.]

## De quoi s'agit-il ?
[Definition, perimetre, ce qui est couvert et ce qui ne l'est pas.
Distinction avec les sous-domaines proches si pertinent.]

## Quels sont vos droits ?
[Regles legales en langage simple. Obligations du professionnel.
Delais importants. Cas particuliers frequents.]

## Les situations les plus frequentes
[Liste des situations du sous-domaine avec description courte.
Liens internes vers les fiches situation.]

## Que faire concretement ?
[Etapes generales applicables a l'ensemble du sous-domaine.
Modele de courrier si applicable.]

## Ou signaler / a qui s'adresser ?
[Sorties avec liens. Mediateur sectoriel si applicable.]

## Pour aller plus loin
[References legales. Jurisprudence. Textes officiels.]
```

##### `template_situation.md` (95 fiches cas concret)

```
# [Titre clair — question ou probleme concret du consommateur]

## En bref
[2-3 phrases autonomes. Le lecteur presse s'arrete ici.]

## De quoi s'agit-il ?
[Definition, qui est concerne, perimetre.]

## Quels sont vos droits ?
[Loi en langage simple, obligations du pro, delais.]

## Que faire concretement ?
1. [Etape 1 — verbe d'action]
2. [Etape 2]
3. [Recours ultime]

## Exemples / cas concrets
**Situation** : "J'ai achete X et..."
**Ce que vous pouvez faire** : ...
**Resultat attendu** : ...
[2-3 exemples]

## Ou signaler / a qui s'adresser ?
[Sorties avec liens, par ordre de priorite.
URL SignalConso directe si disponible.
Mediateur sectoriel si applicable.]

## Pour aller plus loin
[References legales, jurisprudence, textes officiels.]
```

**Couche 3 — Prompt utilisateur dynamique** (par fiche) :
- Contexte taxonomique complet (domaine, sous-domaine, situation, sorties avec URLs, mediateur, mapping SignalConso)
- Sources retrievees depuis ChromaDB (separees DGCCRF / INC)
- Checklist de completude (12 points de verification)

#### 5.3 Logique de generation

Pour chaque item (137 au total, dans l'ordre domaine → sous-domaine → situation) :

1. Charger le contexte taxonomique
2. Choisir le template adapte au niveau
3. Retriever les sources ChromaDB :
   - Domaine : top-K avec query large (label + description)
   - Sous-domaine : top-K + sources des situations enfants
   - Situation : top-K avec boost DGCCRF x1.5, cap a 15 000 caracteres
4. Assembler system_prompt + user_prompt
5. Appeler le LLM (OpenAI-compatible API)
6. Sauvegarder la fiche `.md`
7. Logger : item_id, level, model, tokens, sources utilisees, duree

#### 5.4 Fonctionnalites CLI

```bash
# Preview sans appeler le LLM
python 05_generate_fiches.py --dry-run

# Generer une seule fiche
python 05_generate_fiches.py --situation pub_caracteristiques_fausses
python 05_generate_fiches.py --sous-domaine publicite_trompeuse
python 05_generate_fiches.py --domaine pratiques_commerciales

# Generer un seul niveau
python 05_generate_fiches.py --level domaine        # 8 fiches
python 05_generate_fiches.py --level sous_domaine   # 34 fiches
python 05_generate_fiches.py --level situation       # 95 fiches

# Reprendre apres interruption (saute les fiches existantes)
python 05_generate_fiches.py --resume

# Tout generer
LLM_API_KEY=xxx python 05_generate_fiches.py
```

---

### Phase 6 : Validation (`06_validate.py`)

**Entree** : `output/fiches/` + taxonomie
**Sortie** : `output/_validation_report.json`

Verifications par fiche, adaptees au niveau :

| Verification | Domaine | Sous-domaine | Situation |
|-------------|---------|-------------|-----------|
| Sections attendues presentes | 6 sections | 7 sections | 7 sections |
| URLs de sortie integrees | — | Sorties du SD | Toutes les sorties |
| Mediateur sectoriel mentionne | — | Si applicable | Si applicable |
| URL SignalConso directe | — | — | Si champ `signalconso` present |
| Liens vers fiches enfants | Vers 34 SD | Vers N situations | — |
| Markdown pur (pas de HTML) | Oui | Oui | Oui |
| Longueur minimale | > 200 mots | > 300 mots | > 200 mots |
| Marqueurs `[A COMPLETER]` | Comptes | Comptes | Comptes |

Resume global : OK / erreurs / manquantes / warnings, par niveau.

**CLI** : `python 06_validate.py [--verbose] [--level domaine|sous_domaine|situation]`

---

## 5. Modele editorial

### Ton et style

| Regle | Description |
|-------|-------------|
| Langue | Francais, langage clair |
| Phrases | 20 mots max, voix active |
| Personne | 2e personne du pluriel ("vous") |
| Jargon | Interdit dans le corps, autorise dans "Pour aller plus loin" |
| Ton | Informatif, rassurant, oriente action |
| Inventions | Interdites — `[A COMPLETER]` si l'info manque |
| Format | Markdown pur, pas de HTML |
| Liens | Format `[texte](url)` |

### Checklist de completude (couche 3 du prompt)

1. Le titre est une question ou un probleme concret du consommateur
2. La section "En bref" est autonome (comprehensible seule)
3. Le perimetre est precise (ce qui est couvert ET ce qui ne l'est pas)
4. "Que faire concretement" contient des etapes numerotees avec verbes d'action
5. Au moins 2 exemples concrets (niveau situation)
6. TOUTES les URLs de sortie de la taxonomie sont integrees
7. Le mediateur sectoriel est mentionne avec son URL (si fourni)
8. L'URL SignalConso directe est integree (si champ `signalconso` present)
9. Pas de jargon juridique non explique dans le corps
10. References legales uniquement dans "Pour aller plus loin"
11. Markdown pur (pas de HTML)
12. Sections manquant d'info marquees `[A COMPLETER]`

---

## 6. Stack technique

### Dependances

```
pyyaml, pydantic, python-dotenv, tqdm
html2text                    # HTML → Markdown structure
chromadb                     # Base vectorielle locale
sentence-transformers        # Embeddings E5-small
openai                       # Client LLM (OpenAI-compatible)
mysql-connector-python       # Extraction Drupal
python-frontmatter           # Parsing frontmatter YAML
```

### Configuration (`config.yaml`)

```yaml
paths:
  taxonomy_file: "../../taxonomie_dgccrf.json"
  inc_corpus_dir: "/path/to/portail-conso-corpus/inc-conso-md/content"
  output_dir: "./output"
  chroma_db_path: "./output/chroma_db"
  prompts_dir: "./prompts"

mysql:
  host: "127.0.0.1"
  port: 3307
  user: "root"
  password: ""              # MYSQL_PASSWORD env var
  database: "economie"
  dgccrf_group_id: 113

embeddings:
  model_name: "intfloat/multilingual-e5-small"   # 384D

chunking:
  chunk_size: 500
  chunk_overlap: 100
  min_chunk_length: 50

retrieval:
  top_k: 20
  min_score: 0.3
  max_source_chars: 15000
  dgccrf_weight: 1.5       # boost sources DGCCRF vs INC

llm:
  endpoint: "https://albert.api.etalab.gouv.fr/v1"
  api_key: ""               # LLM_API_KEY env var
  model: "neuronx-llama-3-1-70b-instruct"
  temperature: 0.3
  max_tokens: 4000
  rate_limit_rpm: 30

inc_filter:
  min_content_length: 200
  skip_directories:
    - "categories-des-rappels-produits"
    - "thematique-des-organismes"
```

Les secrets (mots de passe, cles API) sont surchargeables par variables d'environnement : `MYSQL_PASSWORD`, `LLM_API_KEY`, `LLM_ENDPOINT`, `LLM_MODEL`, `LLM_TEMPERATURE`.

---

## 7. Execution

```bash
cd scripts/dgccrf-rewrite
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Phase 1 : Extraction DGCCRF (~2 min)
python 01_extract_dgccrf.py

# Phase 2 : Nettoyage INC (~30 sec)
python 02_prepare_inc.py --stats          # verifier d'abord
python 02_prepare_inc.py --save-cleaned   # puis nettoyer

# Phase 3 : Indexation ChromaDB (~5-10 min)
python 03_index_chroma.py --reset

# Phase 4 : Inventaire (~1 min, a lire avant de generer)
python 04_inventaire.py

# Phase 5 : Generation LLM (~30-60 min pour 137 fiches)
python 05_generate_fiches.py --dry-run                     # preview
python 05_generate_fiches.py --situation pub_prix_mensonger # test 1 fiche
python 05_generate_fiches.py --level domaine               # 8 fiches chapeau
python 05_generate_fiches.py --resume                      # tout, reprise auto

# Phase 6 : Validation (~10 sec)
python 06_validate.py --verbose
```

Les phases 1 et 2 sont independantes (parallelisables).
La phase 4 est informative (la phase 5 n'en depend pas).

---

## 8. Sortie finale

```
output/fiches/
├── domaines/
│   ├── pratiques_commerciales.md              # 1 des 8 fiches chapeau
│   ├── contrats_garanties.md
│   ├── prix_etiquetage.md
│   ├── alimentaire.md
│   ├── numerique_cyber.md
│   ├── secteurs_reglementes.md
│   ├── securite_produits.md
│   └── concurrence.md
├── pratiques_commerciales/
│   ├── publicite_trompeuse/
│   │   ├── _index.md                          # fiche sous-domaine
│   │   ├── pub_caracteristiques_fausses.md    # fiche situation
│   │   ├── pub_prix_mensonger.md
│   │   ├── pub_influenceur_dissimule.md
│   │   └── pub_greenwashing.md
│   ├── demarchage/
│   │   ├── _index.md
│   │   ├── demarchage_telephonique.md
│   │   ├── demarchage_domicile.md
│   │   └── abus_faiblesse.md
│   └── ...
├── contrats_garanties/
│   └── ...
├── ...
└── transversales/
    ├── litige_ue.md
    ├── litige_hors_ue.md
    └── urgence_securite.md
```

**Volumes estimes** :
- 137 fiches × ~800 mots en moyenne = ~110 000 mots
- ~137 appels LLM, ~550 000 tokens au total (estimation)
- Cout API : variable selon le modele (Albert = gratuit, Claude Sonnet ~2-3€, GPT-4o ~5€)

---

## 9. Points d'attention

1. **L'extraction DGCCRF (Phase 1) est la seule phase qui interagit avec le portail-eco-browser** — elle peut etre executee ici ou dans le projet cible
2. **Le corpus INC est brut** : la Phase 2 de nettoyage est critique. Prevoir un mode `--stats` pour inspecter avant de valider
3. **Les fiches domaine et sous-domaine doivent lier vers leurs enfants** : le prompt doit inclure la liste des sous-domaines/situations pour generer les liens internes
4. **Le mapping SignalConso (v2.0)** ajoute des URLs de signalement direct par situation — le prompt doit les integrer dans "Ou signaler"
5. **Le parser de taxonomie est dynamique** : si des situations sont ajoutees a `taxonomie_dgccrf.json`, le pipeline les prendra en compte sans modification de code
6. **Strategie de generation recommandee** : commencer par les situations (bottom-up), puis sous-domaines (qui referent les situations), puis domaines (qui referent les sous-domaines)
7. **Le `--dry-run` est essentiel** : toujours previsualiser les prompts avant de lancer une generation massive
