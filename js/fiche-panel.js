/**
 * Gestion du panneau droit : bascule entre l'arbre D3 et le viewer de fiche.
 */
import { stripFrontmatter } from './fiches-renderer.js';

/**
 * Extrait la section "En bref" d'un markdown brut.
 * @param {string} md - markdown avec frontmatter
 * @returns {string|null}
 */
export function extractEnBref(md) {
  const body = stripFrontmatter(md);
  const match = body.match(/## En bref\n([\s\S]*?)(?=\n## |\n$)/);
  return match ? match[1].trim() : null;
}

/**
 * Affiche la fiche markdown complete dans le panneau droit.
 * @param {string} taxonomyId
 * @param {object} state - { corpusLookup, ficheCache }
 */
export async function showFicheInPanel(taxonomyId, state) {
  const info = state.corpusLookup?.[taxonomyId];
  if (!info) return;

  // Fetch avec cache
  if (!state.ficheCache[taxonomyId]) {
    try {
      const res = await fetch('./corpus/' + info.path);
      if (!res.ok) return;
      state.ficheCache[taxonomyId] = await res.text();
    } catch { return; }
  }

  const md = state.ficheCache[taxonomyId];
  const body = stripFrontmatter(md);
  const html = window.marked.parse(body);

  // Remplir le viewer
  const viewer = document.getElementById('fiche-viewer');
  const content = document.getElementById('fiche-viewer-content');
  content.innerHTML =
    `<nav class="fr-breadcrumb fr-breadcrumb--sm" aria-label="vous etes ici">` +
      `<ol class="fr-breadcrumb__list">` +
        `<li><span class="fr-breadcrumb__link">${esc(info.domaine_label)}</span></li>` +
        `<li><span class="fr-breadcrumb__link">${esc(info.ss_label)}</span></li>` +
        `<li><span class="fr-breadcrumb__link" aria-current="page">${esc(info.title)}</span></li>` +
      `</ol>` +
    `</nav>` +
    `<article class="fr-text fiche-article">${html}</article>`;

  // Basculer la visibilite
  document.getElementById('tree-svg-wrap').hidden = true;
  document.getElementById('tree-footer').hidden = true;
  viewer.hidden = false;
  document.getElementById('tree-back-btn').hidden = false;
  document.getElementById('tree-fit-btn').hidden = true;

  // Mettre a jour le label toolbar
  const label = document.getElementById('tree-state-label');
  if (label) label.textContent = 'Fiche pratique';
}

/**
 * Masque le viewer de fiche, restaure l'arbre D3.
 */
export function hideFicheViewer() {
  const viewer = document.getElementById('fiche-viewer');
  if (!viewer) return;
  viewer.hidden = true;
  document.getElementById('tree-svg-wrap').hidden = false;
  document.getElementById('tree-footer').hidden = false;
  document.getElementById('tree-back-btn').hidden = true;
  document.getElementById('tree-fit-btn').hidden = false;
}

function esc(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
