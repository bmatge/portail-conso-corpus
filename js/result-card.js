import { SORTIE_ICONS, SORTIE_LABELS } from './constants.js';

function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Recherche une situation dans la taxonomie par son id.
 * @param {object} taxonomy
 * @param {string} id
 * @returns {{ sit, ss, domaine } | null}
 */
export function getSituation(taxonomy, id) {
  if (!taxonomy) return null;
  for (const d of taxonomy.domaines) {
    for (const ss of d.sous_domaines) {
      for (const sit of ss.situations) {
        if (sit.id === id) return { sit, ss, domaine: d };
      }
    }
  }
  return null;
}

/**
 * Construit le HTML d'une fiche resultat pour une situation identifiee.
 * @param {object} taxonomy
 * @param {string} situationId
 * @param {object} classifyResult
 * @returns {string} HTML
 */
export function buildResultCard(taxonomy, situationId, classifyResult) {
  const found = getSituation(taxonomy, situationId);
  if (!found) {
    return `<div class="fr-card fr-card--no-arrow">
      <div class="fr-card__body"><div class="fr-card__content">
        <h3 class="fr-card__title">Situation identifiee</h3>
        <p class="fr-card__desc">Code : <code>${situationId}</code></p>
        <a class="fr-btn fr-btn--sm" href="https://signal.conso.gouv.fr" target="_blank" rel="noopener">Acceder a SignalConso</a>
      </div></div></div>`;
  }

  const { sit, ss, domaine } = found;
  const sc = sit.signalconso || {};
  const conf = classifyResult.confiance || 'moyenne';

  const confMap = { haute: 'success', moyenne: 'warning', faible: 'error' };
  const confLabel = { haute: 'Confiance haute', moyenne: 'Confiance moyenne', faible: 'A confirmer' };
  const confBadge = `<p class="fr-badge fr-badge--${confMap[conf]} fr-badge--sm fr-badge--no-icon">${confLabel[conf]}</p>`;

  const urgencyHtml = sc.urgence
    ? `<div class="fr-alert fr-alert--error fr-alert--sm"><p>Situation potentiellement urgente — agir rapidement</p></div>`
    : '';

  const sortiesHtml = (sit.sorties || []).map(s => {
    const icon = SORTIE_ICONS[s.type] || '📌';
    const label = s.label || SORTIE_LABELS[s.type] || s.type;
    const url = s.url || (taxonomy?.types_sortie?.[s.type] || {}).url || '#';
    return `<div class="sortie-item priorite-${s.priorite || 2}">
      <span class="sortie-icon">${icon}</span>
      <div class="sortie-content">
        <div class="sortie-title">${label}</div>
        <div class="sortie-url"><a href="${url}" target="_blank" rel="noopener">${url}</a></div>
        ${s.note ? `<div class="sortie-note">${s.note}</div>` : ''}
      </div></div>`;
  }).join('');

  let pivotHtml = '';
  if (sc.question_pivot && sc.url_signalement_alt) {
    const btns = Object.entries(sc.url_signalement_alt).map(([k, u]) => {
      const lbl = k.replace('url_signalement_', '').replace(/_/g, ' ');
      return `<button class="fr-tag fr-tag--sm pivot-btn" data-url="${u}">${lbl.charAt(0).toUpperCase() + lbl.slice(1)}</button>`;
    }).join('');
    pivotHtml = `<div class="pivot-question"><strong>Precision : ${sc.question_pivot}</strong><div class="pivot-btns">${btns}</div></div>`;
  }

  const scBadge = sc.category
    ? `<p class="fr-tag fr-tag--sm sc-badge">SignalConso · Categorie : ${sc.category}</p>`
    : '';

  const mediateur = ss.mediateur;
  const mediateurHtml = mediateur
    ? `<div class="mediateur-block"><strong>Mediateur sectoriel</strong><a href="${mediateur.url}" target="_blank" rel="noopener">${mediateur.label}</a></div>`
    : '';

  const horsScHtml = sc.canal_principal_si_hors_sc && !sc.category
    ? `<div class="fr-alert fr-alert--warning fr-alert--sm"><p>${sc.note || 'Cette situation ne releve pas directement de SignalConso.'}</p></div>`
    : '';

  return `<div class="fr-card fr-card--no-arrow result-card">
    <div class="fr-card__body"><div class="fr-card__content">
      <div class="fr-card__end">${confBadge}</div>
      <h3 class="fr-card__title">${domaine.label} › ${ss.label}</h3>
      ${urgencyHtml}
      <p class="fr-card__desc result-label">${sit.label}</p>
      ${scBadge}${horsScHtml}${pivotHtml}
      <div style="margin-top:.5rem">${sortiesHtml}</div>
      ${mediateurHtml}
    </div></div></div>`;
}

/**
 * Construit une carte enrichie avec le resume "En bref" de la fiche.
 * @param {object} taxonomy
 * @param {string} situationId
 * @param {object} classifyResult
 * @param {string} enBref - texte extrait de la section "En bref"
 * @returns {string} HTML
 */
export function buildFicheResultCard(taxonomy, situationId, classifyResult, enBref) {
  const found = getSituation(taxonomy, situationId);
  if (!found) return buildResultCard(taxonomy, situationId, classifyResult);

  const { sit, ss, domaine } = found;
  const sc = sit.signalconso || {};
  const conf = classifyResult.confiance || 'moyenne';

  const confMap = { haute: 'success', moyenne: 'warning', faible: 'error' };
  const confLabel = { haute: 'Confiance haute', moyenne: 'Confiance moyenne', faible: 'A confirmer' };
  const confBadge = `<p class="fr-badge fr-badge--${confMap[conf]} fr-badge--sm fr-badge--no-icon">${confLabel[conf]}</p>`;

  const urgencyHtml = sc.urgence
    ? `<div class="fr-alert fr-alert--error fr-alert--sm"><p>Situation potentiellement urgente — agir rapidement</p></div>`
    : '';

  const sortiesHtml = (sit.sorties || []).map(s => {
    const icon = SORTIE_ICONS[s.type] || '📌';
    const label = s.label || SORTIE_LABELS[s.type] || s.type;
    const url = s.url || (taxonomy?.types_sortie?.[s.type] || {}).url || '#';
    return `<div class="sortie-item priorite-${s.priorite || 2}">
      <span class="sortie-icon">${icon}</span>
      <div class="sortie-content">
        <div class="sortie-title">${label}</div>
        <div class="sortie-url"><a href="${url}" target="_blank" rel="noopener">${url}</a></div>
        ${s.note ? `<div class="sortie-note">${s.note}</div>` : ''}
      </div></div>`;
  }).join('');

  const enBrefHtml = `<div class="fiche-en-bref"><p>${escHtml(enBref)}</p></div>`;

  const voirFicheBtn = `<button class="fr-btn fr-btn--sm fr-btn--secondary voir-fiche-btn" data-taxonomy-id="${situationId}">
    <span class="fr-icon-file-text-line" aria-hidden="true"></span> Voir la fiche compl&egrave;te
  </button>`;

  return `<div class="fr-card fr-card--no-arrow result-card">
    <div class="fr-card__body"><div class="fr-card__content">
      <div class="fr-card__end">${confBadge}</div>
      <h3 class="fr-card__title">${domaine.label} › ${ss.label}</h3>
      ${urgencyHtml}
      <p class="fr-card__desc result-label">${sit.label}</p>
      ${enBrefHtml}
      <div style="margin-top:.5rem">${sortiesHtml}</div>
      <div style="margin-top:.75rem">${voirFicheBtn}</div>
    </div></div></div>`;
}


// ── Agent Phase Cards ───────────────────────────────────


/**
 * Carte de question de clarification (phase CLARIFY).
 * @param {object} data - { question, type?, candidates?, situation_id? }
 * @returns {string} HTML
 */
export function buildClarifyCard(data) {
  const question = escHtml(data.question || '');
  const isPivot = data.type === 'pivot';

  let html = `<div class="fr-card fr-card--no-arrow clarify-card">
    <div class="fr-card__body"><div class="fr-card__content">
      <p class="fr-badge fr-badge--info fr-badge--sm fr-badge--no-icon">Question de clarification</p>
      <p class="fr-card__desc" style="margin-top:.5rem;font-weight:600">${question}</p>`;

  if (isPivot) {
    html += `<p class="fr-text--xs" style="margin-top:.5rem;color:var(--text-mention-grey,#666)">
      Repondez en quelques mots pour que je puisse vous orienter plus precisement.</p>`;
  }

  if (data.candidates && data.candidates.length > 0) {
    html += `<p class="fr-text--xs" style="margin-top:.5rem;color:var(--text-mention-grey,#666)">
      Situations possibles : ${data.candidates.length} candidat(s) — consultez l'arbre a droite.</p>`;
  }

  html += `</div></div></div>`;
  return html;
}


/**
 * Carte d'actions concretes (phase ACTION).
 * @param {object} data - { actions[], signalconso?, mediateur? }
 * @returns {string} HTML
 */
export function buildActionCard(data) {
  const actions = data.actions || [];
  const sc = data.signalconso;
  const med = data.mediateur;

  let html = `<div class="fr-card fr-card--no-arrow action-card">
    <div class="fr-card__body"><div class="fr-card__content">
      <p class="fr-badge fr-badge--success fr-badge--sm fr-badge--no-icon">Vos recours</p>`;

  if (sc && sc.url) {
    html += `<div class="action-primary" style="margin-top:.65rem">
      <a class="fr-btn fr-btn--sm" href="${escHtml(sc.url)}" target="_blank" rel="noopener">
        Signaler sur SignalConso
      </a>
      ${sc.urgence ? '<span class="fr-badge fr-badge--error fr-badge--sm" style="margin-left:.5rem">Urgent</span>' : ''}
      ${sc.note ? `<p class="fr-text--xs" style="margin-top:.25rem;color:var(--text-mention-grey,#666)">${escHtml(sc.note)}</p>` : ''}
    </div>`;
  }

  if (actions.length > 0) {
    html += `<div style="margin-top:.65rem">`;
    for (const a of actions) {
      const icon = SORTIE_ICONS[a.type] || '';
      const url = a.url || '#';
      html += `<div class="sortie-item priorite-${a.priorite || 2}">
        <span class="sortie-icon">${icon}</span>
        <div class="sortie-content">
          <div class="sortie-title">${escHtml(a.label)}</div>
          ${url !== '#' ? `<div class="sortie-url"><a href="${escHtml(url)}" target="_blank" rel="noopener">${escHtml(url)}</a></div>` : ''}
          ${a.note ? `<div class="sortie-note">${escHtml(a.note)}</div>` : ''}
          ${a.condition ? `<div class="sortie-note">Condition : ${escHtml(a.condition)}</div>` : ''}
        </div></div>`;
    }
    html += `</div>`;
  }

  if (med && med.url) {
    html += `<div class="mediateur-block" style="margin-top:.65rem">
      <strong>Mediateur sectoriel</strong>
      <a href="${escHtml(med.url)}" target="_blank" rel="noopener">${escHtml(med.label)}</a>
    </div>`;
  }

  html += `</div></div></div>`;
  return html;
}


/**
 * Citations des sources utilisees dans la reponse.
 * @param {Array} sources - [{source, title, score}]
 * @returns {string} HTML
 */
export function buildSourceCitations(sources) {
  if (!sources || sources.length === 0) return '';

  let html = `<details class="source-citations" style="margin-top:.5rem">
    <summary class="fr-text--xs" style="cursor:pointer;color:var(--text-action-high-blue-france,#000091)">
      Sources utilisees (${sources.length})
    </summary>
    <ul class="fr-text--xs" style="margin-top:.25rem;padding-left:1.2rem;color:var(--text-mention-grey,#666)">`;

  for (const [i, s] of sources.entries()) {
    const score = Math.round((s.score || 0) * 100);
    html += `<li>[${i + 1}] ${escHtml(s.source.toUpperCase())} — ${escHtml(s.title)} (${score}%)</li>`;
  }

  html += `</ul></details>`;
  return html;
}
