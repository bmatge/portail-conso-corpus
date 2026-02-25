/**
 * Header search bar — redirects to search.html with query param.
 */

function initHeaderSearch() {
  const btn = document.getElementById('header-search-submit');
  const input = document.getElementById('header-search-input');
  if (!btn || !input) return;

  function go(e) {
    e.preventDefault();
    const q = input.value.trim();
    if (q.length < 2) return;
    window.location.href = `/search.html?q=${encodeURIComponent(q)}`;
  }

  btn.addEventListener('click', go);
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') go(e); });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initHeaderSearch);
} else {
  initHeaderSearch();
}
