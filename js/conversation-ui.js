import { buildResultCard, buildFicheResultCard, buildClarifyCard, buildActionCard, buildSourceCitations } from './result-card.js';
import { extractEnBref } from './fiche-panel.js';
import { LLMAdapter } from './llm-adapter.js';

/**
 * Ajoute un message dans le DOM de conversation.
 * @param {string} role - 'bot' | 'user'
 * @param {string} content
 * @param {boolean} isHtml
 * @returns {HTMLElement} la bulle creee
 */
export function appendMessage(role, content, isHtml = false) {
  const conv = document.getElementById('conversation');
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  const avatar = role === 'bot'
    ? '<div class="msg-avatar"><span class="fr-icon-france-line" aria-hidden="true"></span></div>'
    : '<div class="msg-avatar"><span class="fr-icon-user-line" aria-hidden="true"></span></div>';
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  if (isHtml) bubble.innerHTML = content;
  else        bubble.textContent = content;
  div.innerHTML = avatar;
  div.appendChild(bubble);
  conv.appendChild(div);
  if (typeof div.scrollIntoView === 'function') div.scrollIntoView({ behavior: 'smooth', block: 'end' });
  return bubble;
}

/**
 * Affiche l'indicateur de reflexion.
 * @param {object|null} treeViz
 */
export function showThinking(treeViz) {
  const conv = document.getElementById('conversation');
  const div = document.createElement('div');
  div.className = 'msg bot';
  div.id = 'thinking';
  div.innerHTML = `<div class="msg-avatar"><span class="fr-icon-france-line" aria-hidden="true"></span></div>
    <div class="msg-bubble"><div class="thinking"><span></span><span></span><span></span></div></div>`;
  conv.appendChild(div);
  if (typeof div.scrollIntoView === 'function') div.scrollIntoView({ behavior: 'smooth', block: 'end' });
  if (treeViz) treeViz.setThinking(true);
}

/**
 * Masque l'indicateur de reflexion.
 * @param {object|null} treeViz
 */
export function hideThinking(treeViz) {
  document.getElementById('thinking')?.remove();
  if (treeViz) treeViz.setThinking(false);
}

/**
 * Cree une bulle de message streaming (curseur anime).
 * @param {string} role - 'bot' | 'user'
 * @returns {{ bubble: HTMLElement, append(text: string): void, finish(): void }}
 */
export function appendStreamingMessage(role = 'bot') {
  const conv = document.getElementById('conversation');
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  const avatar = role === 'bot'
    ? '<div class="msg-avatar"><span class="fr-icon-france-line" aria-hidden="true"></span></div>'
    : '<div class="msg-avatar"><span class="fr-icon-user-line" aria-hidden="true"></span></div>';
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble streaming';
  div.innerHTML = avatar;
  div.appendChild(bubble);
  conv.appendChild(div);

  let fullText = '';

  return {
    bubble,
    append(text) {
      fullText += text;
      bubble.textContent = fullText;
      if (typeof div.scrollIntoView === 'function') {
        div.scrollIntoView({ behavior: 'smooth', block: 'end' });
      }
    },
    finish() {
      bubble.classList.remove('streaming');
      // Render markdown if marked.js is available
      if (window.marked && fullText) {
        bubble.innerHTML = marked.parse(fullText);
      }
    },
  };
}

/**
 * Envoie un message et traite la reponse LLM.
 * @param {object} state - { adapter, conversation, treeViz, taxonomy, sessionId, ... }
 */
export async function sendMessage(state) {
  const input = document.getElementById('user-input');
  const text = input.value.trim();
  if (!text) return;

  if (!state.adapter) {
    appendMessage('bot', 'Configurez d\'abord le modele LLM dans le panneau ci-dessus.');
    return;
  }

  input.value = '';
  // auto-resize
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 200) + 'px';

  appendMessage('user', text);
  state.conversation.push({ role: 'user', content: text });

  // Agent mode for builtin, classic classify for custom
  if (state.adapter.config.mode === 'builtin') {
    return _sendAgentMessage(state);
  }
  return _sendClassifyMessage(state);
}


/**
 * Agent multi-etapes : classify → clarify → answer → action (builtin mode).
 */
async function _sendAgentMessage(state) {
  showThinking(state.treeViz);

  let streamBubble = null;

  try {
    const response = await state.adapter.agentChat(
      state.conversation, state.sessionId,
      {
        onPhase(phase, data) {
          if (phase === 'classify') {
            hideThinking(state.treeViz);
            // Update tree
            if (state.treeViz) {
              if (data.situation_id) state.treeViz.showResult(data.situation_id);
              else if (data.candidate_situation_ids?.length) state.treeViz.showCandidates(data.candidate_situation_ids);
            }
            // Hors perimetre
            if (data.hors_perimetre) {
              appendMessage('bot',
                'Ce probleme semble hors du perimetre DGCCRF. Quelques pistes :\n\n' +
                '- Litige entre particuliers \u2192 tribunal judiciaire\n' +
                '- Probleme avec une administration \u2192 Defenseur des droits (defenseurdesdroits.fr)\n' +
                '- Probleme international \u2192 Centre Europeen des Consommateurs (europe-consommateurs.eu)\n\n' +
                'Si vous pensez que je me suis trompe, reformulez votre situation.');
            }
          }
          else if (phase === 'clarify') {
            hideThinking(state.treeViz);
            appendMessage('bot', buildClarifyCard(data), true);
          }
          else if (phase === 'answer') {
            hideThinking(state.treeViz);
            streamBubble = appendStreamingMessage('bot');
          }
          else if (phase === 'action') {
            if (streamBubble) { streamBubble.finish(); streamBubble = null; }
            appendMessage('bot', buildActionCard(data), true);
          }
        },
        onChunk(text) {
          if (streamBubble) streamBubble.append(text);
        },
        onSources(sources) {
          if (sources?.length) {
            appendMessage('bot', buildSourceCitations(sources), true);
          }
        },
        onDone() {
          if (streamBubble) { streamBubble.finish(); streamBubble = null; }
        },
      }
    );

    state.sessionId = response.sessionId;
    state.conversation.push({ role: 'assistant', content: '[agent_response]' });

  } catch (err) {
    hideThinking(state.treeViz);
    if (streamBubble) streamBubble.finish();
    appendMessage('bot', `Erreur : ${err.message}\n\nVerifiez la configuration LLM.`);
    console.error('[Agent]', err);
  }
}


/**
 * Classification simple (mode custom avec cle API client).
 */
async function _sendClassifyMessage(state) {
  showThinking(state.treeViz);

  try {
    const result = await state.adapter.classify(state.conversation);
    hideThinking(state.treeViz);
    state.conversation.push({ role: 'assistant', content: JSON.stringify(result) });

    // Mise a jour de l'arbre
    if (state.treeViz) {
      if (result.situation_id) {
        state.treeViz.showResult(result.situation_id);
      } else if (result.candidate_situation_ids && result.candidate_situation_ids.length > 0) {
        state.treeViz.showCandidates(result.candidate_situation_ids);
      }
    }

    // Reponse chat
    if (result.hors_perimetre) {
      appendMessage('bot',
        'Ce probleme semble hors du perimetre DGCCRF. Quelques pistes :\n\n' +
        '- Litige entre particuliers \u2192 tribunal judiciaire\n' +
        '- Probleme avec une administration \u2192 Defenseur des droits (defenseurdesdroits.fr)\n' +
        '- Probleme international \u2192 Centre Europeen des Consommateurs (europe-consommateurs.eu)\n\n' +
        'Si vous pensez que je me suis trompe, reformulez votre situation.');
      return;
    }

    if (result.question_clarification) {
      appendMessage('bot',
        result.question_clarification +
        '\n\n(Repondez en quelques mots pour affiner l\'identification — j\'affiche les candidats dans l\'arbre a droite.)');
      return;
    }

    if (result.situation_id) {
      let usedFicheCard = false;
      const ficheInfo = state.corpusLookup?.[result.situation_id];
      if (ficheInfo) {
        try {
          if (!state.ficheCache[result.situation_id]) {
            const res = await fetch('./corpus/' + ficheInfo.path);
            if (res.ok) state.ficheCache[result.situation_id] = await res.text();
          }
          const md = state.ficheCache[result.situation_id];
          const enBref = md ? extractEnBref(md) : null;
          if (enBref) {
            appendMessage('bot', buildFicheResultCard(state.taxonomy, result.situation_id, result, enBref), true);
            usedFicheCard = true;
          }
        } catch { /* fallback ci-dessous */ }
      }
      if (!usedFicheCard) {
        appendMessage('bot', buildResultCard(state.taxonomy, result.situation_id, result), true);
      }
    } else {
      appendMessage('bot', 'Je n\'ai pas pu identifier clairement votre situation. Pouvez-vous preciser le type de professionnel et ce qui s\'est passe exactement ?');
    }

  } catch (err) {
    hideThinking(state.treeViz);
    appendMessage('bot', `Erreur : ${err.message}\n\nVerifiez la configuration LLM.`);
    console.error('[LLM]', err);
  }
}


/**
 * Reinitialise la conversation.
 * @param {object} state - { conversation, treeViz, sessionId }
 */
export function resetConversation(state) {
  state.conversation.length = 0;
  state.sessionId = null;
  document.getElementById('conversation').innerHTML = '';
  appendMessage('bot', 'Conversation reinitialisee. Decrivez votre probleme de consommation.');
  if (state.treeViz) state.treeViz.reset();
}
