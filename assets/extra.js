document.addEventListener('DOMContentLoaded', () => {

  // ── Make post cards fully clickable ──────────────────────────
  document.querySelectorAll('.post-card').forEach(card => {
    const link = card.querySelector('.post-title a');
    if (!link) return;
    card.addEventListener('click', e => {
      if (e.target.closest('a')) return;
      window.location.href = link.href;
    });
  });

  // ── Blog: combined search + type filter + tag filter ─────────
  const searchInput = document.querySelector('.blog-search-input');
  const filterBtns  = document.querySelectorAll('.filter-btn');
  const tagBtns     = document.querySelectorAll('.tag-btn');
  const cards       = document.querySelectorAll('.post-card');

  let activeType = 'all';
  let activeTag  = null;
  let searchQuery = '';

  function applyFilters() {
    const q = searchQuery.toLowerCase().trim();
    cards.forEach(card => {
      const type     = card.dataset.type || '';
      const tags     = (card.dataset.tags || '').toLowerCase();
      const titleEl  = card.querySelector('.post-title');
      const excerptEl = card.querySelector('.post-excerpt');
      const title    = titleEl  ? titleEl.textContent.toLowerCase()   : '';
      const excerpt  = excerptEl ? excerptEl.textContent.toLowerCase() : '';

      const typeMatch = activeType === 'all' || type === activeType;
      const tagMatch  = !activeTag  || tags.split(',').includes(activeTag);
      const textMatch = !q || title.includes(q) || excerpt.includes(q) || tags.includes(q);

      card.classList.toggle('hidden', !(typeMatch && tagMatch && textMatch));
    });
  }

  if (searchInput) {
    searchInput.addEventListener('input', () => {
      searchQuery = searchInput.value;
      applyFilters();
    });
  }

  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeType = btn.dataset.filter;
      applyFilters();
    });
  });

  tagBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tag = btn.dataset.tag;
      if (activeTag === tag) {
        // deselect
        btn.classList.remove('active');
        activeTag = null;
      } else {
        tagBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeTag = tag;
      }
      applyFilters();
    });
  });

  // ── KB sidebar tree toggle (desktop) ─────────────────────────
  // (kb-nav-cards are always expanded — no toggle needed)

  // ── Mobile KB navigation dropdown ────────────────────────────
  const mobileToggle = document.querySelector('.kb-mobile-toggle');
  const mobileNav    = document.querySelector('.kb-mobile-nav');

  if (mobileToggle && mobileNav) {
    mobileToggle.addEventListener('click', () => {
      const isOpen = mobileToggle.getAttribute('aria-expanded') === 'true';
      mobileToggle.setAttribute('aria-expanded', String(!isOpen));
      mobileNav.classList.toggle('open', !isOpen);
    });
  }

});
