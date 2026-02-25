import { SYSTEM_PROMPT } from './constants.js';

/**
 * Adaptateur LLM agnostique fournisseur (OpenAI-compatible / Anthropic).
 */
export class LLMAdapter {
  constructor(config) {
    this.config = { ...config };
  }

  async classify(messages) {
    const { endpoint, apiKey, format, model, temperature, maxTokens } = this.config;
    if (!endpoint) throw new Error('Endpoint non configure');
    if (!apiKey)   throw new Error('Cle API non configuree');
    switch (format) {
      case 'openai':    return this._callOpenAI(endpoint, apiKey, model, messages, temperature, maxTokens);
      case 'anthropic': return this._callAnthropic(endpoint, apiKey, model, messages, temperature, maxTokens);
      default: throw new Error(`Format inconnu : ${format}`);
    }
  }

  async _callOpenAI(endpoint, apiKey, model, messages, temperature, maxTokens) {
    const res = await fetch(this._proxyUrl(endpoint), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
      body: JSON.stringify({
        model, temperature, max_tokens: maxTokens,
        messages: [{ role: 'system', content: SYSTEM_PROMPT }, ...messages],
      }),
    });
    if (!res.ok) { const e = await res.text(); throw new Error(`API ${res.status}: ${e.slice(0, 200)}`); }
    const data = await res.json();
    const text = data?.choices?.[0]?.message?.content;
    if (!text) throw new Error('Reponse vide du modele');
    return LLMAdapter.parseJSON(text);
  }

  async _callAnthropic(endpoint, apiKey, model, messages, temperature, maxTokens) {
    const res = await fetch(this._proxyUrl(endpoint), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json', 'x-api-key': apiKey,
        'anthropic-version': '2023-06-01', 'anthropic-dangerous-direct-browser-access': 'true',
      },
      body: JSON.stringify({ model, temperature, max_tokens: maxTokens, system: SYSTEM_PROMPT, messages }),
    });
    if (!res.ok) { const e = await res.text(); throw new Error(`API ${res.status}: ${e.slice(0, 200)}`); }
    const data = await res.json();
    const text = data?.content?.[0]?.text;
    if (!text) throw new Error('Reponse vide du modele');
    return LLMAdapter.parseJSON(text);
  }

  _proxyUrl(url) {
    // /proxy-https/host/path — avoids :// in URL path (Traefik merges //)
    return url.replace(/^(https?):\/\//, '/proxy-$1/');
  }

  /**
   * Extrait et parse le premier objet JSON d'une reponse brute.
   * Methode statique pour faciliter les tests unitaires.
   */
  static parseJSON(raw) {
    const match = raw.match(/\{[\s\S]*\}/);
    if (!match) throw new Error('Aucun JSON dans la reponse : ' + raw.slice(0, 200));
    try { return JSON.parse(match[0]); }
    catch { throw new Error('JSON invalide : ' + match[0].slice(0, 200)); }
  }
}
