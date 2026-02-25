import { describe, it, expect, beforeEach, vi } from 'vitest';
import { appendMessage, showThinking, hideThinking, sendMessage, resetConversation } from '../js/conversation-ui.js';
import { MOCK_TAXONOMY, MOCK_LLM_RESPONSE_FOUND, MOCK_LLM_RESPONSE_CLARIFICATION, MOCK_LLM_RESPONSE_HORS } from './setup.js';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="conversation"></div>
    <textarea id="user-input"></textarea>
    <button id="send-btn"></button>
  `;
});

describe('appendMessage', () => {
  it('ajoute un message bot au DOM', () => {
    appendMessage('bot', 'Bonjour');
    const conv = document.getElementById('conversation');
    expect(conv.children.length).toBe(1);
    expect(conv.querySelector('.msg.bot')).toBeTruthy();
    expect(conv.querySelector('.msg-bubble').textContent).toBe('Bonjour');
  });

  it('ajoute un message user au DOM', () => {
    appendMessage('user', 'Mon probleme');
    const conv = document.getElementById('conversation');
    expect(conv.querySelector('.msg.user')).toBeTruthy();
    expect(conv.querySelector('.msg-bubble').textContent).toBe('Mon probleme');
  });

  it('injecte du HTML quand isHtml est true', () => {
    appendMessage('bot', '<strong>important</strong>', true);
    const bubble = document.querySelector('.msg-bubble');
    expect(bubble.innerHTML).toContain('<strong>important</strong>');
  });

  it('echappe le HTML quand isHtml est false', () => {
    appendMessage('bot', '<script>alert("xss")</script>');
    const bubble = document.querySelector('.msg-bubble');
    expect(bubble.innerHTML).not.toContain('<script>');
    expect(bubble.textContent).toContain('<script>');
  });
});

describe('showThinking / hideThinking', () => {
  it('ajoute et retire l\'indicateur de reflexion', () => {
    showThinking(null);
    expect(document.getElementById('thinking')).toBeTruthy();
    expect(document.querySelector('.thinking')).toBeTruthy();

    hideThinking(null);
    expect(document.getElementById('thinking')).toBeNull();
  });

  it('appelle setThinking sur treeViz', () => {
    const mockTree = { setThinking: vi.fn() };
    showThinking(mockTree);
    expect(mockTree.setThinking).toHaveBeenCalledWith(true);
    hideThinking(mockTree);
    expect(mockTree.setThinking).toHaveBeenCalledWith(false);
  });
});

describe('sendMessage', () => {
  it('ne fait rien si l\'input est vide', async () => {
    document.getElementById('user-input').value = '';
    const state = { adapter: {}, conversation: [], treeViz: null, taxonomy: MOCK_TAXONOMY };
    await sendMessage(state);
    expect(document.getElementById('conversation').children.length).toBe(0);
  });

  it('affiche un message d\'erreur si adapter est null', async () => {
    document.getElementById('user-input').value = 'test';
    const state = { adapter: null, conversation: [], treeViz: null, taxonomy: MOCK_TAXONOMY };
    await sendMessage(state);
    const msgs = document.querySelectorAll('.msg.bot .msg-bubble');
    expect(msgs.length).toBe(1);
    expect(msgs[0].textContent).toContain('Configurez');
  });

  it('affiche une result card quand situation_id est trouve', async () => {
    document.getElementById('user-input').value = 'Mon garagiste';
    const mockAdapter = { classify: vi.fn().mockResolvedValue(MOCK_LLM_RESPONSE_FOUND) };
    const state = { adapter: mockAdapter, conversation: [], treeViz: null, taxonomy: MOCK_TAXONOMY };

    await sendMessage(state);

    // user + bot response
    const msgs = document.querySelectorAll('.msg');
    expect(msgs.length).toBe(2);
    // result card present
    const card = document.querySelector('.fr-card');
    expect(card).toBeTruthy();
    expect(card.textContent).toContain('Automobile');
  });

  it('affiche un message de clarification', async () => {
    document.getElementById('user-input').value = 'probleme voiture';
    const mockAdapter = { classify: vi.fn().mockResolvedValue(MOCK_LLM_RESPONSE_CLARIFICATION) };
    const state = { adapter: mockAdapter, conversation: [], treeViz: null, taxonomy: MOCK_TAXONOMY };

    await sendMessage(state);

    const bubbles = document.querySelectorAll('.msg.bot .msg-bubble');
    const lastBubble = bubbles[bubbles.length - 1];
    expect(lastBubble.textContent).toContain('devis ou la facture');
  });

  it('affiche le message hors perimetre', async () => {
    document.getElementById('user-input').value = 'probleme avec mon voisin';
    const mockAdapter = { classify: vi.fn().mockResolvedValue(MOCK_LLM_RESPONSE_HORS) };
    const state = { adapter: mockAdapter, conversation: [], treeViz: null, taxonomy: MOCK_TAXONOMY };

    await sendMessage(state);

    const bubbles = document.querySelectorAll('.msg.bot .msg-bubble');
    const lastBubble = bubbles[bubbles.length - 1];
    expect(lastBubble.textContent).toContain('hors du perimetre');
  });

  it('affiche un message d\'erreur quand le LLM echoue', async () => {
    document.getElementById('user-input').value = 'test';
    const mockAdapter = { classify: vi.fn().mockRejectedValue(new Error('API 500')) };
    const state = { adapter: mockAdapter, conversation: [], treeViz: null, taxonomy: MOCK_TAXONOMY };

    await sendMessage(state);

    const bubbles = document.querySelectorAll('.msg.bot .msg-bubble');
    const lastBubble = bubbles[bubbles.length - 1];
    expect(lastBubble.textContent).toContain('API 500');
  });

  it('met a jour l\'arbre quand situation_id est trouve', async () => {
    document.getElementById('user-input').value = 'garagiste';
    const mockTree = { showResult: vi.fn(), showCandidates: vi.fn(), setThinking: vi.fn() };
    const mockAdapter = { classify: vi.fn().mockResolvedValue(MOCK_LLM_RESPONSE_FOUND) };
    const state = { adapter: mockAdapter, conversation: [], treeViz: mockTree, taxonomy: MOCK_TAXONOMY };

    await sendMessage(state);

    expect(mockTree.showResult).toHaveBeenCalledWith('garage_surfacturation');
  });

  it('met a jour l\'arbre avec les candidats', async () => {
    document.getElementById('user-input').value = 'voiture';
    const mockTree = { showResult: vi.fn(), showCandidates: vi.fn(), setThinking: vi.fn() };
    const mockAdapter = { classify: vi.fn().mockResolvedValue(MOCK_LLM_RESPONSE_CLARIFICATION) };
    const state = { adapter: mockAdapter, conversation: [], treeViz: mockTree, taxonomy: MOCK_TAXONOMY };

    await sendMessage(state);

    expect(mockTree.showCandidates).toHaveBeenCalledWith(['garage_surfacturation', 'compteur_kilometre_truque']);
  });
});

describe('resetConversation', () => {
  it('vide la conversation et le DOM', () => {
    appendMessage('bot', 'test');
    appendMessage('user', 'test2');
    const state = { conversation: [{ role: 'user', content: 'test2' }], treeViz: null };

    resetConversation(state);

    // Le DOM ne contient que le message de reset
    const msgs = document.querySelectorAll('.msg');
    expect(msgs.length).toBe(1);
    expect(state.conversation.length).toBe(0);
  });

  it('reinitialise l\'arbre', () => {
    const mockTree = { reset: vi.fn() };
    const state = { conversation: [], treeViz: mockTree };

    resetConversation(state);

    expect(mockTree.reset).toHaveBeenCalled();
  });
});
