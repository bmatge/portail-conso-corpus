/**
 * Orchestrateur de la page Fiches pratiques.
 * Charge l'index, construit le sidemenu, gere le routing hash.
 */

import { buildSidemenu, highlightActive, expandToFiche } from './fiches-sidemenu.js';
import { renderFiche, renderLanding } from './fiches-renderer.js';

const state = {
  index: null,
  cache: {},   // taxonomy_id -> markdown brut
};

/* ── Index loading ── */

async function loadIndex() {
  const res = await fetch('./corpus/index.json');
  if (!res.ok) throw new Error(`Erreur chargement index: HTTP ${res.status}`);
  state.index = await res.json();
}

/* ── Fiche lookup ── */

/**
 * Trouve une fiche par taxonomy_id, retourne aussi le domaine et sous-domaine parents.
 * @returns {{ fiche, domaine, sous_domaine }|null}
 */
function findFiche(index, id) {
  for (const domaine of index.domaines) {
    for (const ss of domaine.sous_domaines) {
      for (const fiche of ss.fiches) {
        if (fiche.taxonomy_id === id) {
          return { fiche, domaine, sous_domaine: ss };
        }
      }
    }
  }
  return null;
}

/* ── Routing ── */

function getCurrentFicheId() {
  return location.hash.slice(1) || null;
}

async function navigate() {
  const ficheId = getCurrentFicheId();

  if (!ficheId) {
    renderLanding(state.index);
    highlightActive(null);
    document.title = 'Fiches pratiques — DGCCRF';
    return;
  }

  const info = findFiche(state.index, ficheId);
  if (!info) {
    document.getElementById('fiche-content').innerHTML =
      '<div class="fr-alert fr-alert--warning fr-alert--sm fr-mt-3w">' +
      `<p>Fiche <strong>${ficheId}</strong> non trouv&eacute;e.</p>` +
      '</div>';
    highlightActive(null);
    return;
  }

  // Fetch markdown (with cache)
  if (!state.cache[ficheId]) {
    const res = await fetch('./corpus/' + info.fiche.path);
    if (!res.ok) {
      document.getElementById('fiche-content').innerHTML =
        '<div class="fr-alert fr-alert--error fr-alert--sm fr-mt-3w">' +
        `<p>Erreur de chargement de la fiche (HTTP ${res.status}).</p>` +
        '</div>';
      return;
    }
    state.cache[ficheId] = await res.text();
  }

  renderFiche(state.cache[ficheId], info);
  highlightActive(ficheId);
  expandToFiche(ficheId);
  document.title = info.fiche.title + ' — DGCCRF';
}

/* ── Init ── */

window.addEventListener('DOMContentLoaded', async () => {
  try {
    await loadIndex();
    buildSidemenu(state.index);

    // Reinit DSFR pour les collapses dynamiques du sidemenu
    if (typeof window.dsfr === 'function') window.dsfr.start();

    await navigate();
  } catch (err) {
    console.error(err);
    document.getElementById('fiche-content').innerHTML =
      '<div class="fr-alert fr-alert--error fr-alert--sm">' +
      `<p>Erreur d'initialisation : ${err.message}</p>` +
      '</div>';
  }
});

window.addEventListener('hashchange', navigate);
