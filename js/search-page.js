/**
 * Search page controller — API calls, result rendering, URL state.
 */

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

  return `
    <div class="fr-col-12 fr-col-md-6">
      <div class="fr-card fr-card--sm fr-card--shadow">
        <div class="fr-card__body">
          <div class="fr-card__content">
            <h3 class="fr-card__title">
              <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">${escapeHtml(r.title)}</a>
            </h3>
            <p class="fr-card__desc result-snippet">${escapeHtml(snippet)}</p>
            <div class="result-meta">
              <span class="source-badge source-badge--${src}">${escapeHtml(src)}</span>
              <span>Pertinence :</span>
              <span class="score-bar"><span class="score-bar__fill" style="width:${pct}%"></span></span>
              <strong>${pct}\u202f%</strong>
            </div>
          </div>
        </div>
      </div>
    </div>`;
}

// ── Search handler ──

async function performSearch(query) {
  query = (query || '').trim();
  if (query.length < 2) return;

  // Update URL
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

  // Support ?q= param for direct links / header redirect
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
