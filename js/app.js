import { DEFAULT_CONFIG } from './constants.js';
import { LLMAdapter } from './llm-adapter.js';
import { TaxonomyTree } from './taxonomy-tree.js';
import { loadSavedConfig, applyPreset, saveConfig, testConfig } from './config-manager.js';
import { appendMessage, showThinking, hideThinking, sendMessage, resetConversation } from './conversation-ui.js';
import { handleKey, autoResize } from './utils.js';
import { showFicheInPanel, hideFicheViewer } from './fiche-panel.js';

// ════════════════════════════════════════════════════════════
// ETAT APPLICATION
// ════════════════════════════════════════════════════════════
const state = {
  taxonomy: null,
  adapter: null,
  treeViz: null,
  conversation: [],
  currentConfig: { ...DEFAULT_CONFIG },
  corpusIndex: null,
  corpusLookup: null,
  ficheCache: {},
};

// ════════════════════════════════════════════════════════════
// CHARGEMENT TAXONOMIE
// ════════════════════════════════════════════════════════════
async function loadTaxonomy() {
  try {
    const res = await fetch('./taxonomie-dgccrf.json');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    state.taxonomy = await res.json();
    const ph = document.getElementById('tree-placeholder');
    if (ph) ph.remove();
    state.treeViz = new TaxonomyTree('tree-svg-wrap', state.taxonomy);
    console.log(`[Taxonomie] ${state.taxonomy.meta?.contenu?.situations} situations`);
  } catch (e) {
    console.warn('[Taxonomie] Chargement echoue :', e.message);
    const ph = document.getElementById('tree-placeholder');
    if (ph) ph.querySelector('div:last-child').textContent = 'Taxonomie non disponible (mode degrade)';
  }
}

// ════════════════════════════════════════════════════════════
// CHARGEMENT CORPUS INDEX
// ════════════════════════════════════════════════════════════
async function loadCorpusIndex() {
  try {
    const res = await fetch('./corpus/index.json');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    state.corpusIndex = await res.json();
    state.corpusLookup = {};
    for (const d of state.corpusIndex.domaines) {
      for (const ss of d.sous_domaines) {
        for (const fiche of ss.fiches) {
          state.corpusLookup[fiche.taxonomy_id] = {
            path: fiche.path,
            title: fiche.title,
            domaine_label: d.label,
            ss_label: ss.label,
          };
        }
      }
    }
    console.log(`[Corpus] ${Object.keys(state.corpusLookup).length} fiches indexees`);
  } catch (e) {
    console.warn('[Corpus] Index non disponible:', e.message);
  }
}

// ════════════════════════════════════════════════════════════
// HELPERS DOM CONFIG
// ════════════════════════════════════════════════════════════
function readFormValues() {
  return {
    endpoint:    document.getElementById('cfg-endpoint').value,
    model:       document.getElementById('cfg-model').value,
    apiKey:      document.getElementById('cfg-key').value,
    format:      document.getElementById('cfg-format').value,
    temperature: document.getElementById('cfg-temp').value,
    maxTokens:   document.getElementById('cfg-maxtokens').value,
  };
}

function writeFormValues(cfg) {
  document.getElementById('cfg-endpoint').value   = cfg.endpoint;
  document.getElementById('cfg-model').value      = cfg.model;
  document.getElementById('cfg-key').value        = cfg.apiKey || '';
  document.getElementById('cfg-format').value     = cfg.format;
  document.getElementById('cfg-temp').value       = cfg.temperature;
  document.getElementById('cfg-maxtokens').value  = cfg.maxTokens;
}

function setStatusUI(type, msg) {
  const el = document.getElementById('config-status');
  el.className = 'config-status ' + (type === 'ok' ? 'ok' : type === 'err' ? 'err' : '');
  el.textContent = msg;
}

function closeConfigPanel() {
  const collapseEl = document.getElementById('accordion-config');
  if (collapseEl && window.dsfr) {
    try { dsfr(collapseEl).collapse.conceal(); } catch { /* fallback */ }
  }
}

// ════════════════════════════════════════════════════════════
// EVENT HANDLERS
// ════════════════════════════════════════════════════════════
function onPresetClick(e) {
  const name = e.currentTarget.dataset.preset;
  const preset = applyPreset(name);
  if (!preset) return;
  document.getElementById('cfg-endpoint').value = preset.endpoint;
  document.getElementById('cfg-model').value    = preset.model;
  document.getElementById('cfg-format').value   = preset.format;
  setStatusUI('info', `Preset "${name}" applique — ajoutez votre cle API puis Enregistrer.`);
}

function onSaveConfig() {
  const { config, adapter, error } = saveConfig(readFormValues());
  if (error) {
    setStatusUI('err', error);
    return;
  }
  state.currentConfig = config;
  state.adapter = adapter;
  if (config.mode === 'builtin') {
    setStatusUI('ok', `✓ Mode integre — Albert (${config.model})`);
  } else {
    setStatusUI('ok', `✓ ${config.model} sur ${new URL(config.endpoint).hostname}`);
  }
  closeConfigPanel();
}

async function onTestConfig() {
  const { config } = saveConfig(readFormValues());
  setStatusUI('info', 'Test en cours…');
  const result = await testConfig(config);
  setStatusUI(result.ok ? 'ok' : 'err', (result.ok ? '✓ ' : '✗ ') + result.message);
}

function onSend() {
  sendMessage(state);
}

function onReset() {
  resetConversation(state);
}

function onTreeFit() {
  if (state.treeViz) state.treeViz.fitAll();
}

// ════════════════════════════════════════════════════════════
// INIT
// ════════════════════════════════════════════════════════════
window.addEventListener('DOMContentLoaded', async () => {
  await loadTaxonomy();
  await loadCorpusIndex();

  appendMessage('bot',
    'Bonjour, je suis l\'assistant consommateur de la DGCCRF.\n\n' +
    'Decrivez votre probleme en langage libre — livraison non recue, demarchage abusif, ' +
    'probleme d\'hygiene, arnaque en ligne… — et je vous oriente vers le bon recours.\n\n' +
    'L\'arbre a droite suit votre conversation en temps reel.');

  // Restaurer config
  state.currentConfig = loadSavedConfig();
  // Always create adapter — builtin mode works without a client API key
  state.adapter = new LLMAdapter(state.currentConfig);
  writeFormValues(state.currentConfig);
  if (state.currentConfig.mode === 'builtin') {
    setStatusUI('ok', `✓ Mode integre — Albert (${state.currentConfig.model})`);
  } else if (state.currentConfig.apiKey) {
    setStatusUI('ok', `✓ Config restauree — ${state.currentConfig.model} sur ${new URL(state.currentConfig.endpoint).hostname}`);
  }

  // Bind events
  const userInput = document.getElementById('user-input');
  userInput.addEventListener('keydown', e => handleKey(e, onSend));
  userInput.addEventListener('input', () => autoResize(userInput));

  document.getElementById('send-btn').addEventListener('click', onSend);
  document.getElementById('reset-btn').addEventListener('click', onReset);
  document.getElementById('save-config-btn').addEventListener('click', onSaveConfig);
  document.getElementById('test-config-btn').addEventListener('click', onTestConfig);
  document.getElementById('tree-fit-btn')?.addEventListener('click', onTreeFit);

  document.querySelectorAll('[data-preset]').forEach(btn => {
    btn.addEventListener('click', onPresetClick);
  });

  // Delegation pour les boutons dans les result cards
  document.getElementById('conversation').addEventListener('click', e => {
    const pivotBtn = e.target.closest('.pivot-btn[data-url]');
    if (pivotBtn) {
      window.open(pivotBtn.dataset.url, '_blank');
      return;
    }
    const ficheBtn = e.target.closest('.voir-fiche-btn[data-taxonomy-id]');
    if (ficheBtn) {
      showFicheInPanel(ficheBtn.dataset.taxonomyId, state);
    }
  });

  // Bouton retour a l'arbre
  document.getElementById('tree-back-btn')?.addEventListener('click', hideFicheViewer);

  // Resize observer pour l'arbre
  if (state.treeViz && window.ResizeObserver) {
    new ResizeObserver(() => {
      const r = state.treeViz.wrap.getBoundingClientRect();
      state.treeViz.W = r.width;
      state.treeViz.H = r.height;
    }).observe(document.getElementById('tree-svg-wrap'));
  }
});
