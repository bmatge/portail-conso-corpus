/**
 * Controller for the About page.
 * Two sub-pages: presentation (PRESENTATION.md) and technique (README.md with mermaid).
 */

const PAGES = {
  presentation: { file: './PRESENTATION.md', title: 'Presentation fonctionnelle' },
  technique:    { file: './README.md',        title: 'Documentation technique' },
};

const cache = {};

// ── Mermaid diagrams to replace ASCII art in README ──

const ARCHITECTURE_MERMAID = `graph TB
  subgraph Browser["&nbsp;Navigateur&nbsp;"]
    direction LR
    Chat["Chatbot<br/><small>index.html</small>"]
    Fiches["Fiches pratiques<br/><small>fiches.html</small>"]
    Search["Recherche<br/><small>search.html</small>"]
    Sources["Corpus source<br/><small>sources.html</small>"]
  end

  Chat -->|"/api/chat"| API
  Search -->|"/api/search"| API

  subgraph Server["&nbsp;Serveur Docker&nbsp;"]
    Nginx["nginx<br/><small>reverse proxy, CORS, assets</small>"]
    API["FastAPI<br/><small>api/search_api.py</small>"]
    Chroma[("ChromaDB<br/><small>~23 000 chunks</small>")]
    Albert["Albert LLM<br/><small>DINUM</small>"]
  end

  Nginx --> API
  API -->|"cosine similarity"| Chroma
  API -->|"chat completions"| Albert`;

const PIPELINE_MERMAID = `graph LR
  subgraph Sources["&nbsp;Corpus sources&nbsp;"]
    D["dgccrf-drupal/<br/><small>1 754 .md</small>"]
    P["particuliers-drupal/<br/><small>361 .md</small>"]
    E["entreprises-drupal/<br/><small>271 .md</small>"]
    I["inc-conso-md/<br/><small>3 151 .md</small>"]
  end

  T["taxonomie-dgccrf.json"]

  Sources --> S2["02_prepare_inc.py<br/><small>Nettoyage INC</small>"]
  S2 --> S3["03_index_chroma.py<br/><small>Indexation ChromaDB</small>"]
  T --> S3
  S3 --> S4["04_inventaire.py<br/><small>Couverture par item</small>"]
  S4 --> S5["05_generate_fiches.py<br/><small>Generation LLM</small>"]
  S5 --> S6["06_validate.py<br/><small>Validation</small>"]
  S6 --> Output["corpus/<br/><small>267 fiches .md</small>"]`;

/**
 * Replace ASCII art code blocks in README with mermaid diagrams.
 * Targets the two known ASCII blocks by detecting their unique content.
 */
function replaceAsciiWithMermaid(md) {
  // Replace architecture diagram (contains "FastAPI" and "nginx" in a code block)
  md = md.replace(
    /```\n┌─────[\s\S]*?nginx[\s\S]*?─+┘\n```/,
    '```mermaid\n' + ARCHITECTURE_MERMAID + '\n```'
  );

  // Replace pipeline diagram (contains "Corpus sources" and "Pipeline" in a code block)
  md = md.replace(
    /```\nCorpus sources[\s\S]*?─ Validation[\s\S]*?```/,
    '```mermaid\n' + PIPELINE_MERMAID + '\n```'
  );

  return md;
}

// ── Rendering ──

function initMermaid() {
  if (window.mermaid) {
    window.mermaid.initialize({
      startOnLoad: false,
      theme: 'default',
      flowchart: { curve: 'basis', htmlLabels: true },
    });
  }
}

async function renderMermaidBlocks() {
  if (!window.mermaid) return;
  const blocks = document.querySelectorAll('#about-content pre code.language-mermaid');
  for (const code of blocks) {
    const pre = code.parentElement;
    const container = document.createElement('div');
    container.className = 'mermaid-diagram';
    const id = 'mermaid-' + Math.random().toString(36).slice(2, 8);
    try {
      const { svg } = await window.mermaid.render(id, code.textContent);
      container.innerHTML = svg;
      pre.replaceWith(container);
    } catch (e) {
      console.warn('Mermaid render failed:', e);
    }
  }
}

async function loadPage(pageId) {
  const el = document.getElementById('about-content');
  const page = PAGES[pageId];
  if (!page) {
    el.innerHTML = '<div class="fr-alert fr-alert--warning fr-alert--sm"><p>Page non trouv\u00e9e.</p></div>';
    return;
  }

  el.innerHTML = '<div class="fr-alert fr-alert--info fr-alert--sm"><p>Chargement\u2026</p></div>';

  if (!cache[pageId]) {
    try {
      const res = await fetch(page.file);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      cache[pageId] = await res.text();
    } catch (e) {
      el.innerHTML = '<div class="fr-alert fr-alert--error fr-alert--sm"><p>Impossible de charger le contenu.</p></div>';
      return;
    }
  }

  let md = cache[pageId];

  // For the technique page, replace ASCII diagrams with mermaid
  if (pageId === 'technique') {
    md = replaceAsciiWithMermaid(md);
  }

  el.innerHTML = window.marked.parse(md);

  // Render mermaid diagrams if any
  if (pageId === 'technique') {
    await renderMermaidBlocks();
  }

  window.scrollTo(0, 0);
}

// ── Sidebar ──

function highlightActive(pageId) {
  document.querySelectorAll('.fr-sidemenu__link[aria-current]')
    .forEach(a => a.removeAttribute('aria-current'));
  const link = document.querySelector(`.fr-sidemenu__link[data-page="${pageId}"]`);
  if (link) link.setAttribute('aria-current', 'page');
}

// ── Routing ──

function getCurrentPage() {
  const hash = location.hash.slice(1);
  return PAGES[hash] ? hash : 'presentation';
}

async function navigate() {
  const pageId = getCurrentPage();
  highlightActive(pageId);
  document.title = PAGES[pageId].title + ' \u2014 DGCCRF';
  await loadPage(pageId);
}

// ── Init ──

window.addEventListener('DOMContentLoaded', () => {
  initMermaid();
  if (typeof window.dsfr === 'function') window.dsfr.start();
  navigate();
});

window.addEventListener('hashchange', navigate);
