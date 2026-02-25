/**
 * Rendu des fiches markdown et de la page d'accueil.
 */

/**
 * Strip le frontmatter YAML d'un texte markdown.
 * @param {string} md
 * @returns {string} contenu sans frontmatter
 */
export function stripFrontmatter(md) {
  const match = md.match(/^---\n[\s\S]*?\n---\n([\s\S]*)$/);
  return match ? match[1] : md;
}

/**
 * Parse le frontmatter YAML simple (cles: valeurs) d'un texte markdown.
 * @param {string} md
 * @returns {object} metadonnees
 */
export function parseFrontmatter(md) {
  const match = md.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return {};
  const meta = {};
  for (const line of match[1].split('\n')) {
    const m = line.match(/^(\w[\w_]*):\s*(.+)$/);
    if (m) meta[m[1]] = m[2].replace(/^['"]|['"]$/g, '');
  }
  return meta;
}

/**
 * Construit le badge HTML de metadonnees pour une fiche generee.
 * @param {object} meta - frontmatter parse
 * @param {string} body - contenu markdown sans frontmatter
 * @returns {string} HTML
 */
export function buildMetadataBadge(meta, body) {
  const words = body.trim().split(/\s+/).filter(Boolean).length;
  const chars = body.trim().length;

  const date = meta.generated_at
    ? new Date(meta.generated_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })
    : '';

  const rows = [
    meta.model && `<tr><td>Modele</td><td><strong>${esc(meta.model)}</strong></td></tr>`,
    date && `<tr><td>Genere le</td><td>${date}</td></tr>`,
    meta.sources_count && `<tr><td>Sources RAG</td><td>${esc(meta.sources_count)}</td></tr>`,
    meta.tokens && `<tr><td>Tokens</td><td>${Number(meta.tokens).toLocaleString('fr-FR')}</td></tr>`,
    `<tr><td>Mots</td><td>${words.toLocaleString('fr-FR')}</td></tr>`,
    `<tr><td>Caracteres</td><td>${chars.toLocaleString('fr-FR')}</td></tr>`,
  ].filter(Boolean).join('');

  return `<details class="fiche-meta-badge">
    <summary title="Metadonnees de generation">&#9881; Meta</summary>
    <table>${rows}</table>
  </details>`;
}

/**
 * Rend une fiche markdown dans #fiche-content.
 * @param {string} markdownText — le .md brut avec frontmatter
 * @param {{ fiche: object, domaine: object, sous_domaine: object }} info
 */
export function renderFiche(markdownText, info) {
  const content = stripFrontmatter(markdownText);
  const meta = parseFrontmatter(markdownText);
  const html = window.marked.parse(content);
  const metaBadge = buildMetadataBadge(meta, content);
  const container = document.getElementById('fiche-content');

  container.innerHTML =
    `<div style="position:relative">${metaBadge}</div>` +
    `<nav class="fr-breadcrumb" aria-label="vous &ecirc;tes ici">` +
      `<button class="fr-breadcrumb__button" aria-expanded="false" ` +
        `aria-controls="breadcrumb-fiches">Voir le fil d'Ariane</button>` +
      `<div class="fr-collapse" id="breadcrumb-fiches">` +
        `<ol class="fr-breadcrumb__list">` +
          `<li><a class="fr-breadcrumb__link" href="fiches.html">Fiches pratiques</a></li>` +
          `<li><a class="fr-breadcrumb__link" href="fiches.html">${esc(info.domaine.label)}</a></li>` +
          `<li><a class="fr-breadcrumb__link" href="fiches.html">${esc(info.sous_domaine.label)}</a></li>` +
          `<li><a class="fr-breadcrumb__link" aria-current="page">${esc(info.fiche.title)}</a></li>` +
        `</ol>` +
      `</div>` +
    `</nav>` +
    `<article class="fr-text fr-mt-3w">${html}</article>`;

  window.scrollTo(0, 0);

  // Re-init DSFR pour le breadcrumb collapse
  if (typeof window.dsfr === 'function') window.dsfr.start();
}

/**
 * Rend la page d'accueil avec toutes les fiches en cards.
 * @param {{ domaines: Array }} index
 */
export function renderLanding(index) {
  const container = document.getElementById('fiche-content');
  let html = '<div class="fiches-landing">';
  html += '<h1>Fiches pratiques</h1>';
  html += '<p class="fr-text--lead">Retrouvez nos fiches pratiques par domaine pour conna&icirc;tre vos droits et les d&eacute;marches &agrave; suivre.</p>';

  for (const domaine of index.domaines) {
    html += `<h2>${esc(domaine.label)}</h2>`;

    for (const ss of domaine.sous_domaines) {
      html += `<h3>${esc(ss.label)}</h3>`;
      html += '<div class="fr-grid-row fr-grid-row--gutters">';

      for (const fiche of ss.fiches) {
        html +=
          `<div class="fr-col-12 fr-col-md-6 fr-col-lg-4">` +
            `<div class="fr-card fr-card--sm fr-enlarge-link">` +
              `<div class="fr-card__body">` +
                `<div class="fr-card__content">` +
                  `<h4 class="fr-card__title">` +
                    `<a href="#${fiche.taxonomy_id}">${esc(fiche.title)}</a>` +
                  `</h4>` +
                `</div>` +
              `</div>` +
            `</div>` +
          `</div>`;
      }
      html += '</div>';
    }
  }
  html += '</div>';
  container.innerHTML = html;
}

function esc(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
