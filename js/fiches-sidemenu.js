/**
 * Construction dynamique du sidemenu DSFR 3 niveaux
 * depuis corpus/index.json.
 */

/**
 * Genere le HTML du sidemenu dans #sidemenu-list.
 * Niveau 1 : domaines (collapsible)
 * Niveau 2 : sous-domaines (collapsible)
 * Niveau 3 : fiches (liens hash)
 * @param {{ domaines: Array }} index
 */
export function buildSidemenu(index) {
  const list = document.getElementById('sidemenu-list');
  if (!list) return;
  list.innerHTML = '';

  for (const domaine of index.domaines) {
    const domId = `sm-dom-${domaine.id}`;
    const domLi = document.createElement('li');
    domLi.className = 'fr-sidemenu__item';
    domLi.innerHTML =
      `<button class="fr-sidemenu__btn" aria-expanded="false" aria-controls="${domId}">` +
        escapeHtml(domaine.label) +
      `</button>` +
      `<div class="fr-collapse" id="${domId}"><ul class="fr-sidemenu__list"></ul></div>`;

    const ssUl = domLi.querySelector('ul');

    for (const ss of domaine.sous_domaines) {
      const ssId = `sm-ss-${ss.id}`;
      const ssLi = document.createElement('li');
      ssLi.className = 'fr-sidemenu__item';
      ssLi.innerHTML =
        `<button class="fr-sidemenu__btn" aria-expanded="false" aria-controls="${ssId}">` +
          escapeHtml(ss.label) +
        `</button>` +
        `<div class="fr-collapse" id="${ssId}"><ul class="fr-sidemenu__list"></ul></div>`;

      const ficheUl = ssLi.querySelector('ul');

      for (const fiche of ss.fiches) {
        const ficheLi = document.createElement('li');
        ficheLi.className = 'fr-sidemenu__item';
        ficheLi.innerHTML =
          `<a class="fr-sidemenu__link" href="#${fiche.taxonomy_id}" ` +
          `data-fiche-id="${fiche.taxonomy_id}">` +
            escapeHtml(fiche.title) +
          `</a>`;
        ficheUl.appendChild(ficheLi);
      }
      ssUl.appendChild(ssLi);
    }
    list.appendChild(domLi);
  }
}

/**
 * Met aria-current="page" sur le lien actif et retire des autres.
 * @param {string|null} ficheId
 */
export function highlightActive(ficheId) {
  document.querySelectorAll('.fr-sidemenu__link[aria-current]')
    .forEach(a => a.removeAttribute('aria-current'));

  if (ficheId) {
    const link = document.querySelector(
      `.fr-sidemenu__link[data-fiche-id="${ficheId}"]`
    );
    if (link) link.setAttribute('aria-current', 'page');
  }
}

/**
 * Ouvre programmatiquement les sections parentes d'une fiche.
 * @param {string} ficheId
 */
export function expandToFiche(ficheId) {
  const link = document.querySelector(
    `.fr-sidemenu__link[data-fiche-id="${ficheId}"]`
  );
  if (!link) return;

  // Remonter les fr-collapse parents et les ouvrir via DSFR
  let el = link.closest('.fr-collapse');
  while (el) {
    if (typeof window.dsfr === 'function') {
      window.dsfr(el).collapse.disclose();
    } else {
      // Fallback sans DSFR JS
      el.classList.add('fr-collapse--expanded');
      const btn = document.querySelector(`[aria-controls="${el.id}"]`);
      if (btn) btn.setAttribute('aria-expanded', 'true');
    }
    el = el.parentElement?.closest('.fr-collapse');
  }
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
