/**
 * Search page controller — API calls, result rendering, fiche display.
 */
import { stripFrontmatter } from './fiches-renderer.js';

// ── API ──

async function searchAPI(query, topK = 20, minScore = 0.3) {
  const params = new URLSearchParams({ q: query, top_k: topK, min_score: minScore });
  const resp = await fetch(`/api/search?${params}`);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }
  return resp.json();
}

// ── State ──

const ficheCache = {};

// ── UI helpers ──

const $ = (id) => document.getElementById(id);

function setVisible(id, visible) {
  const el = $(id);
  if (el) el.hidden = !visible;
}

function showLoading() {
  setVisible('search-loading', true);
  setVisible('search-error', false);
  setVisible('empty-state', false);
  setVisible('results-header', false);
  closeFicheDrawer();
  $('results-container').innerHTML = '';
}

function showError(msg) {
  setVisible('search-loading', false);
  $('error-message').textContent = msg;
  setVisible('search-error', true);
}

function showEmpty() {
  setVisible('search-loading', false);
  setVisible('empty-state', true);
}

function showResults(query, results, timeMs) {
  setVisible('search-loading', false);
  $('results-count').textContent = results.length;
  $('results-query').textContent = `\u00ab ${query} \u00bb`;
  $('results-time').textContent = `\u2014 ${timeMs} ms`;
  setVisible('results-header', true);
  $('results-container').innerHTML = results.map(buildCard).join('');
}

// ── Card builder ──

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}

function buildCard(r) {
  const snippet = r.text.length > 300 ? r.text.slice(0, 300) + '\u2026' : r.text;
  const pct = Math.round(r.score * 100);
  const src = r.source || 'inc';
  const isFiche = !!r.fiche_path;
  const chunksInfo = r.chunks_matched > 1
    ? `<span class="fr-text--xs fr-text--mention-grey">${r.chunks_matched} passages</span>`
    : '';

  // Title link: fiches → fiches.html, source docs → sources.html, fallback → external URL
  let titleHtml;
  if (isFiche) {
    const taxId = r.taxonomy_id || '';
    titleHtml = `<a href="fiches.html#${escapeHtml(taxId)}">${escapeHtml(r.title)}</a>`;
  } else if (r.source_file) {
    titleHtml = `<a href="sources.html#${escapeHtml(src)}/${escapeHtml(r.source_file)}">${escapeHtml(r.title)}</a>`;
  } else if (r.url) {
    titleHtml = `<a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">${escapeHtml(r.title)}</a>`;
  } else {
    titleHtml = escapeHtml(r.title);
  }

  // Badge
  const badgeHtml = isFiche
    ? `<span class="source-badge source-badge--fiches">fiche</span>`
    : `<span class="source-badge source-badge--${src}">${escapeHtml(src)}</span>`;

  // "Voir la fiche" button for fiches pratiques
  let actionBtn = '';
  if (isFiche) {
    actionBtn = `<button class="fr-btn fr-btn--sm fr-btn--secondary fr-mt-1w fiche-link"
               data-fiche-path="${escapeHtml(r.fiche_path)}">
         Voir la fiche
       </button>`;
  } else if (r.source_file) {
    actionBtn = `<a class="fr-btn fr-btn--sm fr-btn--tertiary fr-mt-1w"
               href="sources.html#${escapeHtml(src)}/${escapeHtml(r.source_file)}">
         Voir le document source
       </a>`;
  }

  return `
    <div class="fr-col-12 fr-col-md-6">
      <div class="fr-card fr-card--sm fr-card--shadow${isFiche ? ' fr-card--fiche' : ''}">
        <div class="fr-card__body">
          <div class="fr-card__content">
            <h3 class="fr-card__title">${titleHtml}</h3>
            <p class="fr-card__desc result-snippet">${escapeHtml(snippet)}</p>
            <div class="result-meta">
              ${badgeHtml}
              <span>Pertinence :</span>
              <span class="score-bar"><span class="score-bar__fill" style="width:${pct}%"></span></span>
              <strong>${pct}\u202f%</strong>
              ${chunksInfo}
            </div>
            ${actionBtn}
          </div>
        </div>
      </div>
    </div>`;
}

// ── Fiche drawer ──

async function openFicheDrawer(fichePath) {
  const drawer = $('fiche-drawer');
  const body = $('fiche-drawer-body');
  if (!drawer || !body) return;

  body.innerHTML = '<div class="search-loading"><div class="fr-spinner"></div></div>';
  drawer.hidden = false;
  drawer.scrollIntoView({ behavior: 'smooth' });

  if (!ficheCache[fichePath]) {
    try {
      const res = await fetch('./corpus/' + fichePath);
      if (!res.ok) { body.innerHTML = '<p>Fiche non disponible.</p>'; return; }
      ficheCache[fichePath] = await res.text();
    } catch {
      body.innerHTML = '<p>Erreur de chargement.</p>';
      return;
    }
  }

  const md = ficheCache[fichePath];
  const content = stripFrontmatter(md);
  body.innerHTML = `<article class="fr-text fiche-article">${window.marked.parse(content)}</article>`;
}

function closeFicheDrawer() {
  const drawer = $('fiche-drawer');
  if (drawer) drawer.hidden = true;
}

// ── Search handler ──

async function performSearch(query) {
  query = (query || '').trim();
  if (query.length < 2) return;

  const url = new URL(window.location);
  url.searchParams.set('q', query);
  history.pushState({}, '', url);

  showLoading();

  try {
    const data = await searchAPI(query);
    if (data.results.length === 0) {
      showEmpty();
    } else {
      showResults(query, data.results, data.execution_time_ms);
    }
  } catch (err) {
    showError(err.message);
  }
}

// ── Init ──

window.addEventListener('DOMContentLoaded', () => {
  const input = $('search-input');
  const btn = $('search-submit');

  btn.addEventListener('click', (e) => { e.preventDefault(); performSearch(input.value); });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); performSearch(input.value); } });

  // Event delegation for fiche links
  $('results-container').addEventListener('click', (e) => {
    const ficheLink = e.target.closest('.fiche-link[data-fiche-path]');
    if (ficheLink) {
      e.preventDefault();
      openFicheDrawer(ficheLink.dataset.fichePath);
    }
  });

  // Close drawer
  $('fiche-drawer-close')?.addEventListener('click', closeFicheDrawer);

  // Support ?q= param
  const q = new URLSearchParams(location.search).get('q');
  if (q) {
    input.value = q;
    performSearch(q);
  } else {
    input.focus();
  }
});

// Handle browser back/forward
window.addEventListener('popstate', () => {
  const q = new URLSearchParams(location.search).get('q');
  if (q) {
    $('search-input').value = q;
    performSearch(q);
  }
});
