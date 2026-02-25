/**
 * Gere Entree pour envoyer (sans Shift).
 * @param {KeyboardEvent} e
 * @param {Function} sendFn
 */
export function handleKey(e, sendFn) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendFn();
  }
}

/**
 * Auto-resize d'un textarea selon son contenu.
 * @param {HTMLTextAreaElement} el
 */
export function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 200) + 'px';
}
