import { DEFAULT_CONFIG, PRESETS } from './constants.js';
import { LLMAdapter } from './llm-adapter.js';

const STORAGE_KEY = 'llm-config';

/**
 * Charge la config sauvegardee dans localStorage.
 * @returns {object} config fusionnee avec les defaults
 */
export function loadSavedConfig() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return { ...DEFAULT_CONFIG, ...JSON.parse(saved) };
  } catch { /* ignore */ }
  return { ...DEFAULT_CONFIG };
}

/**
 * Retourne les valeurs d'un preset, ou null si inconnu.
 * @param {string} name
 * @returns {object|null}
 */
export function applyPreset(name) {
  return PRESETS[name] || null;
}

/**
 * Valide et sauvegarde la config. Retourne l'adaptateur ou une erreur.
 * @param {object} formValues - { endpoint, model, apiKey, format, temperature, maxTokens }
 * @returns {{ config, adapter, error }}
 */
export function saveConfig(formValues) {
  const config = {
    endpoint:    formValues.endpoint?.trim() || '',
    model:       formValues.model?.trim() || '',
    apiKey:      formValues.apiKey?.trim() || '',
    format:      formValues.format || 'openai',
    temperature: parseFloat(formValues.temperature) || 0.1,
    maxTokens:   parseInt(formValues.maxTokens) || 320,
  };

  if (!config.endpoint || !config.apiKey || !config.model) {
    return { config, adapter: null, error: 'Endpoint, modele et cle API sont obligatoires.' };
  }

  const adapter = new LLMAdapter(config);
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(config)); } catch { /* ignore */ }

  return { config, adapter, error: null };
}

/**
 * Teste une config en envoyant une requete de classification.
 * @param {object} config
 * @returns {Promise<{ok: boolean, message: string}>}
 */
export async function testConfig(config) {
  if (!config.apiKey || !config.endpoint) {
    return { ok: false, message: 'Sauvegardez d\'abord.' };
  }
  try {
    const r = await new LLMAdapter(config).classify([{
      role: 'user',
      content: 'Mon garagiste m\'a facture une reparation qu\'il n\'a pas effectuee.',
    }]);
    return { ok: true, message: `OK — ${r.situation_id}, confiance: ${r.confiance}` };
  } catch (e) {
    return { ok: false, message: e.message };
  }
}
