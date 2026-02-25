import { describe, it, expect, beforeEach } from 'vitest';
import { loadSavedConfig, applyPreset, saveConfig } from '../js/config-manager.js';
import { DEFAULT_CONFIG } from '../js/constants.js';

beforeEach(() => {
  localStorage.clear();
});

describe('loadSavedConfig', () => {
  it('retourne DEFAULT_CONFIG quand localStorage est vide', () => {
    const cfg = loadSavedConfig();
    expect(cfg.endpoint).toBe(DEFAULT_CONFIG.endpoint);
    expect(cfg.model).toBe(DEFAULT_CONFIG.model);
    expect(cfg.format).toBe(DEFAULT_CONFIG.format);
  });

  it('retourne la config sauvegardee fusionnee avec les defaults', () => {
    localStorage.setItem('llm-config', JSON.stringify({
      endpoint: 'https://custom.api/v1',
      model: 'custom-model',
      apiKey: 'sk-test',
    }));
    const cfg = loadSavedConfig();
    expect(cfg.endpoint).toBe('https://custom.api/v1');
    expect(cfg.model).toBe('custom-model');
    expect(cfg.apiKey).toBe('sk-test');
    // defaults preserved
    expect(cfg.format).toBe('openai');
    expect(cfg.temperature).toBe(0.1);
  });

  it('retourne DEFAULT_CONFIG si localStorage contient du JSON invalide', () => {
    localStorage.setItem('llm-config', 'not-json');
    const cfg = loadSavedConfig();
    expect(cfg.endpoint).toBe(DEFAULT_CONFIG.endpoint);
  });
});

describe('applyPreset', () => {
  it('retourne les valeurs correctes pour albert', () => {
    const preset = applyPreset('albert');
    expect(preset).not.toBeNull();
    expect(preset.endpoint).toContain('albert');
    expect(preset.model).toBe('albert-large');
    expect(preset.format).toBe('openai');
  });

  it('retourne les valeurs correctes pour anthropic', () => {
    const preset = applyPreset('anthropic');
    expect(preset).not.toBeNull();
    expect(preset.endpoint).toContain('anthropic');
    expect(preset.format).toBe('anthropic');
  });

  it('retourne null pour un preset inconnu', () => {
    expect(applyPreset('inexistant')).toBeNull();
  });
});

describe('saveConfig', () => {
  it('retourne une erreur quand endpoint est manquant', () => {
    const { error } = saveConfig({ endpoint: '', model: 'x', apiKey: 'sk-x' });
    expect(error).toBeTruthy();
    expect(error).toContain('obligatoires');
  });

  it('retourne une erreur quand apiKey est manquant', () => {
    const { error } = saveConfig({ endpoint: 'https://api.test', model: 'x', apiKey: '' });
    expect(error).toBeTruthy();
  });

  it('retourne une erreur quand model est manquant', () => {
    const { error } = saveConfig({ endpoint: 'https://api.test', model: '', apiKey: 'sk-x' });
    expect(error).toBeTruthy();
  });

  it('retourne un adapter et persiste dans localStorage', () => {
    const { config, adapter, error } = saveConfig({
      endpoint: 'https://api.test/v1',
      model: 'test-model',
      apiKey: 'sk-test',
      format: 'openai',
      temperature: '0.2',
      maxTokens: '256',
    });
    expect(error).toBeNull();
    expect(adapter).toBeTruthy();
    expect(config.endpoint).toBe('https://api.test/v1');
    expect(config.temperature).toBe(0.2);
    expect(config.maxTokens).toBe(256);

    const saved = JSON.parse(localStorage.getItem('llm-config'));
    expect(saved.endpoint).toBe('https://api.test/v1');
  });
});
