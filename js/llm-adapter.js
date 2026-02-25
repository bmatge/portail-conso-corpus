import { SYSTEM_PROMPT } from './constants.js';

/**
 * Adaptateur LLM agnostique fournisseur (OpenAI-compatible / Anthropic).
 */
export class LLMAdapter {
  constructor(config) {
    this.config = { ...config };
  }

  async classify(messages) {
    const { mode, endpoint, apiKey, format, model, temperature, maxTokens } = this.config;

    // Builtin mode: call server-side /api/chat (no client API key needed)
    if (mode === 'builtin') {
      return this._callBuiltin(messages, temperature, maxTokens);
    }

    // Custom mode: call proxy with client-side API key
    if (!endpoint) throw new Error('Endpoint non configure');
    if (!apiKey)   throw new Error('Cle API non configuree');
    switch (format) {
      case 'openai':    return this._callOpenAI(endpoint, apiKey, model, messages, temperature, maxTokens);
      case 'anthropic': return this._callAnthropic(endpoint, apiKey, model, messages, temperature, maxTokens);
      default: throw new Error(`Format inconnu : ${format}`);
    }
  }

  /**
   * Streaming classification via SSE (builtin mode only).
   * @param {Array} messages
   * @param {Object} callbacks - { onChunk(text), onDone(fullText), onRagSources(sources) }
   * @returns {Promise<string>} full text response
   */
  async classifyStream(messages, { onChunk, onDone, onRagSources } = {}) {
    const { temperature, maxTokens } = this.config;
    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, temperature, max_tokens: maxTokens }),
    });
    if (!res.ok) {
      const e = await res.text();
      throw new Error(`API ${res.status}: ${e.slice(0, 200)}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullText = '';
    let currentEvent = 'chunk';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop(); // keep incomplete line

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          const data = line.slice(6);
          if (currentEvent === 'chunk') {
            try {
              const { text } = JSON.parse(data);
              fullText += text;
              onChunk?.(text);
            } catch { /* skip malformed chunk */ }
          } else if (currentEvent === 'done') {
            onDone?.(fullText);
          } else if (currentEvent === 'rag_sources') {
            try {
              onRagSources?.(JSON.parse(data));
            } catch { /* skip */ }
          } else if (currentEvent === 'error') {
            throw new Error(data.slice(0, 200));
          }
          currentEvent = 'chunk'; // reset
        }
      }
    }

    return fullText;
  }

  async _callBuiltin(messages, temperature, maxTokens) {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, temperature, max_tokens: maxTokens }),
    });
    if (!res.ok) { const e = await res.text(); throw new Error(`API ${res.status}: ${e.slice(0, 200)}`); }
    const data = await res.json();
    const text = data?.choices?.[0]?.message?.content;
    if (!text) throw new Error('Reponse vide du modele');
    return LLMAdapter.parseJSON(text);
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

  /**
   * Multi-step agent chat via SSE (builtin mode only).
   * @param {Array} messages
   * @param {string|null} sessionId
   * @param {Object} callbacks - { onPhase, onChunk, onSources, onDone }
   * @returns {Promise<{sessionId: string}>}
   */
  async agentChat(messages, sessionId, { onPhase, onChunk, onSources, onDone } = {}) {
    const { temperature, maxTokens } = this.config;
    const res = await fetch('/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages,
        session_id: sessionId,
        temperature,
        max_tokens: maxTokens,
      }),
    });
    if (!res.ok) {
      const e = await res.text();
      throw new Error(`API ${res.status}: ${e.slice(0, 200)}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let currentEvent = 'chunk';
    let result = { sessionId: null };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            switch (currentEvent) {
              case 'phase':
                onPhase?.(data.phase, data);
                break;
              case 'chunk':
                onChunk?.(data.text);
                break;
              case 'sources':
                onSources?.(data.sources);
                break;
              case 'done':
                result.sessionId = data.session_id;
                onDone?.(data);
                break;
              case 'error':
                throw new Error(data.error || 'Agent error');
            }
          } catch (e) {
            if (e.message?.includes('Agent error') || e.message?.includes('API ')) throw e;
            /* skip malformed data */
          }
          currentEvent = 'chunk';
        }
      }
    }

    return result;
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
