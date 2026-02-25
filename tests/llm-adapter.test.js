import { describe, it, expect } from 'vitest';
import { LLMAdapter } from '../js/llm-adapter.js';

describe('LLMAdapter.parseJSON', () => {
  it('extrait le JSON d\'une reponse markdown-wrapped', () => {
    const raw = '```json\n{"situation_id":"garage_surfacturation","confiance":"haute"}\n```';
    const result = LLMAdapter.parseJSON(raw);
    expect(result.situation_id).toBe('garage_surfacturation');
    expect(result.confiance).toBe('haute');
  });

  it('extrait le JSON d\'une reponse avec texte prefixe', () => {
    const raw = 'Voici ma reponse:\n{"situation_id":"phishing","confiance":"moyenne","hors_perimetre":false}';
    const result = LLMAdapter.parseJSON(raw);
    expect(result.situation_id).toBe('phishing');
    expect(result.confiance).toBe('moyenne');
  });

  it('throw si aucun JSON dans la reponse', () => {
    expect(() => LLMAdapter.parseJSON('Je ne sais pas repondre'))
      .toThrow(/Aucun JSON/);
  });

  it('throw si JSON malformed', () => {
    expect(() => LLMAdapter.parseJSON('{"situation_id": garage_surfacturation}'))
      .toThrow(/JSON invalide/);
  });

  it('gere les accolades imbriquees', () => {
    const raw = '{"situation_id":"x","nested":{"a":1},"confiance":"haute"}';
    const result = LLMAdapter.parseJSON(raw);
    expect(result.situation_id).toBe('x');
    expect(result.nested).toEqual({ a: 1 });
  });

  it('extrait le JSON meme avec du texte apres', () => {
    const raw = 'Analyse: {"situation_id":"phishing","confiance":"haute"} fin.';
    const result = LLMAdapter.parseJSON(raw);
    expect(result.situation_id).toBe('phishing');
  });

  it('gere une reponse JSON pure', () => {
    const raw = '{"situation_id":null,"question_clarification":"Preciser","candidate_situation_ids":["a","b"],"hors_perimetre":false}';
    const result = LLMAdapter.parseJSON(raw);
    expect(result.situation_id).toBeNull();
    expect(result.candidate_situation_ids).toEqual(['a', 'b']);
  });
});
