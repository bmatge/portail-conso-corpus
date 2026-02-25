/**
 * Controller for the Corpus Source browsing page.
 * Loads source list from API, builds sidebar, handles hash routing.
 */
import { stripFrontmatter } from './fiches-renderer.js';

const state = {
  sources: [],
  fileCache: {},  // "source:filename" -> markdown
  currentSource: null,
  currentPage: 1,
  searchQuery: '',
};

const PAGE_SIZE = 50;

// URL pattern for serving source .md files
// In Docker: /sources/{source}/{filename}
// In dev: /{dir}/{filename}
const SOURCE_URL_MAP = {
  dgccrf: ['sources/dgccrf', 'dgccrf-drupal'],
  particuliers: ['sources/particuliers', 'particuliers-drupal'],
  entreprises: ['sources/entreprises', 'entreprises-drupal'],
  inc: ['sources/inc', 'inc-conso-md/content'],
};

async function fetchSourceFile(source, filename) {
  const key = `${source}:${filename}`;
  if (state.fileCache[key]) return state.fileCache[key];

  const paths = SOURCE_URL_MAP[source] || [];
  for (const base of paths) {
    try {
      const res = await fetch(`./${base}/${filename}`);
      if (res.ok) {
        const text = await res.text();
        state.fileCache[key] = text;
        return text;
      }
    } catch { /* try next */ }
  }
  return null;
}

// ── API calls ──

async function loadSources() {
  const res = await fetch('/api/sources');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  state.sources = data.sources;
}

async function loadSourceFiles(sourceId, page = 1, q = '') {
  const params = new URLSearchParams({ page, page_size: PAGE_SIZE });
  if (q) params.set('q', q);
  const res = await fetch(`/api/sources/${sourceId}?${params}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Sidebar ──

function buildSidebar() {
  const list = document.getElementById('sidemenu-list');
  if (!list) return;
  list.innerHTML = '';

  for (const src of state.sources) {
    const li = document.createElement('li');
    li.className = 'fr-sidemenu__item';
    li.innerHTML =
      `<a class="fr-sidemenu__link" href="#${src.id}" data-source-id="${src.id}">` +
        `${esc(src.label)} <span class="source-count">(${src.count})</span>` +
      `</a>`;
    list.appendChild(li);
  }
}

function highlightSource(sourceId) {
  document.querySelectorAll('.fr-sidemenu__link[aria-current]')
    .forEach(a => a.removeAttribute('aria-current'));
  if (sourceId) {
    const link = document.querySelector(`.fr-sidemenu__link[data-source-id="${sourceId}"]`);
    if (link) link.setAttribute('aria-current', 'page');
  }
}

// ── Rendering ──

function renderLanding() {
  const container = document.getElementById('source-content');
  let html = '<div class="sources-landing">';
  html += '<h1>Corpus source</h1>';
  html += '<p class="fr-text--lead">Acc&eacute;dez aux documents de r&eacute;f&eacute;rence des 4 sources utilis&eacute;es pour construire les fiches pratiques.</p>';
  html += '<div class="fr-grid-row fr-grid-row--gutters">';

  for (const src of state.sources) {
    html +=
      `<div class="fr-col-12 fr-col-md-6">` +
        `<div class="fr-card fr-card--sm fr-enlarge-link">` +
          `<div class="fr-card__body">` +
            `<div class="fr-card__content">` +
              `<h2 class="fr-card__title">` +
                `<a href="#${src.id}">${esc(src.label)}</a>` +
              `</h2>` +
              `<p class="fr-card__desc">${src.count} documents</p>` +
            `</div>` +
          `</div>` +
        `</div>` +
      `</div>`;
  }
  html += '</div></div>';
  container.innerHTML = html;
}

async function renderSourceList(sourceId, page = 1, q = '') {
  const container = document.getElementById('source-content');
  container.innerHTML = '<div class="fr-alert fr-alert--info fr-alert--sm"><p>Chargement&hellip;</p></div>';

  try {
    const data = await loadSourceFiles(sourceId, page, q);
    state.currentSource = sourceId;
    state.currentPage = page;
    state.searchQuery = q;

    let html = `<h1>${esc(data.label)}</h1>`;
    html += `<p class="fr-text--sm fr-text--mention-grey">${data.total} documents</p>`;

    // Search bar
    html += `<div class="sources-filter">` +
      `<div class="fr-search-bar" role="search">` +
        `<label class="fr-label" for="source-filter-input">Filtrer</label>` +
        `<input class="fr-input" placeholder="Filtrer par titre…" type="search" id="source-filter-input" value="${esc(q)}">` +
        `<button class="fr-btn" title="Filtrer" id="source-filter-btn">Filtrer</button>` +
      `</div></div>`;

    // File list
    html += '<div class="fr-grid-row fr-grid-row--gutters sources-file-list">';
    for (const f of data.files) {
      html +=
        `<div class="fr-col-12 fr-col-md-6 fr-col-lg-4">` +
          `<div class="fr-card fr-card--sm fr-enlarge-link">` +
            `<div class="fr-card__body">` +
              `<div class="fr-card__content">` +
                `<h3 class="fr-card__title">` +
                  `<a href="#${sourceId}/${f.filename}">${esc(f.title)}</a>` +
                `</h3>` +
              `</div>` +
            `</div>` +
          `</div>` +
        `</div>`;
    }
    html += '</div>';

    // Pagination
    const totalPages = Math.ceil(data.total / PAGE_SIZE);
    if (totalPages > 1) {
      html += '<div class="sources-pagination">';
      if (page > 1) {
        html += `<a class="fr-btn fr-btn--sm fr-btn--secondary" href="#${sourceId}?page=${page - 1}${q ? '&q=' + encodeURIComponent(q) : ''}">&larr; Pr&eacute;c&eacute;dent</a>`;
      }
      html += `<span class="fr-text--sm">Page ${page} / ${totalPages}</span>`;
      if (page < totalPages) {
        html += `<a class="fr-btn fr-btn--sm fr-btn--secondary" href="#${sourceId}?page=${page + 1}${q ? '&q=' + encodeURIComponent(q) : ''}">Suivant &rarr;</a>`;
      }
      html += '</div>';
    }

    container.innerHTML = html;

    // Bind filter
    const filterInput = document.getElementById('source-filter-input');
    const filterBtn = document.getElementById('source-filter-btn');
    if (filterBtn && filterInput) {
      const doFilter = () => {
        const val = filterInput.value.trim();
        location.hash = `#${sourceId}${val ? '?q=' + encodeURIComponent(val) : ''}`;
      };
      filterBtn.addEventListener('click', (e) => { e.preventDefault(); doFilter(); });
      filterInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); doFilter(); } });
    }
  } catch (err) {
    container.innerHTML =
      `<div class="fr-alert fr-alert--error fr-alert--sm fr-mt-3w">` +
      `<p>Erreur de chargement : ${esc(err.message)}</p></div>`;
  }
}

async function renderDocument(sourceId, filename) {
  const container = document.getElementById('source-content');
  container.innerHTML = '<div class="fr-alert fr-alert--info fr-alert--sm"><p>Chargement du document&hellip;</p></div>';

  const md = await fetchSourceFile(sourceId, filename);
  if (!md) {
    container.innerHTML =
      '<div class="fr-alert fr-alert--warning fr-alert--sm fr-mt-3w">' +
      '<p>Document non disponible.</p></div>';
    return;
  }

  const content = stripFrontmatter(md);
  const srcInfo = state.sources.find(s => s.id === sourceId);
  const label = srcInfo ? srcInfo.label : sourceId;

  container.innerHTML =
    `<nav class="fr-breadcrumb" aria-label="vous &ecirc;tes ici">` +
      `<button class="fr-breadcrumb__button" aria-expanded="false" ` +
        `aria-controls="breadcrumb-source">Voir le fil d'Ariane</button>` +
      `<div class="fr-collapse" id="breadcrumb-source">` +
        `<ol class="fr-breadcrumb__list">` +
          `<li><a class="fr-breadcrumb__link" href="sources.html">Corpus source</a></li>` +
          `<li><a class="fr-breadcrumb__link" href="#${sourceId}">${esc(label)}</a></li>` +
          `<li><a class="fr-breadcrumb__link" aria-current="page">${esc(filename)}</a></li>` +
        `</ol>` +
      `</div>` +
    `</nav>` +
    `<article class="fr-text fr-mt-3w">${window.marked.parse(content)}</article>`;

  window.scrollTo(0, 0);
  if (typeof window.dsfr === 'function') window.dsfr.start();
}

// ── Routing ──

function parseHash() {
  const hash = location.hash.slice(1);
  if (!hash) return { type: 'landing' };

  // #sourceId/filename.md
  const slashIdx = hash.indexOf('/');
  if (slashIdx > 0) {
    const sourceId = hash.slice(0, slashIdx);
    const filename = hash.slice(slashIdx + 1);
    return { type: 'document', sourceId, filename };
  }

  // #sourceId or #sourceId?page=2&q=test
  const [sourceId, qs] = hash.split('?');
  const params = new URLSearchParams(qs || '');
  const page = parseInt(params.get('page') || '1', 10);
  const q = params.get('q') || '';
  return { type: 'list', sourceId, page, q };
}

async function navigate() {
  const route = parseHash();

  if (route.type === 'landing') {
    renderLanding();
    highlightSource(null);
    document.title = 'Corpus source — DGCCRF';
    return;
  }

  if (route.type === 'list') {
    highlightSource(route.sourceId);
    const srcInfo = state.sources.find(s => s.id === route.sourceId);
    document.title = (srcInfo ? srcInfo.label : route.sourceId) + ' — Corpus source';
    await renderSourceList(route.sourceId, route.page, route.q);
    return;
  }

  if (route.type === 'document') {
    highlightSource(route.sourceId);
    document.title = route.filename + ' — Corpus source';
    await renderDocument(route.sourceId, route.filename);
    return;
  }
}

// ── Init ──

window.addEventListener('DOMContentLoaded', async () => {
  try {
    await loadSources();
    buildSidebar();
    if (typeof window.dsfr === 'function') window.dsfr.start();
    await navigate();
  } catch (err) {
    console.error(err);
    document.getElementById('source-content').innerHTML =
      '<div class="fr-alert fr-alert--error fr-alert--sm">' +
      `<p>Erreur d'initialisation : ${esc(err.message)}</p></div>`;
  }
});

window.addEventListener('hashchange', navigate);

function esc(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
