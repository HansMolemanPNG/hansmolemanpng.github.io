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

  // ── Blog filter buttons ───────────────────────────────────────
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const filter = btn.dataset.filter;
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.post-card').forEach(card => {
        card.classList.toggle('hidden', filter !== 'all' && card.dataset.type !== filter);
      });
    });
  });

  // ── KB sidebar tree toggle (desktop) ─────────────────────────
  document.querySelectorAll('.kb-tree-cat-hdr').forEach(hdr => {
    hdr.addEventListener('click', e => {
      // Let category name link navigate normally
      if (e.target.closest('.kb-tree-cat-name')) return;

      const cat     = hdr.closest('.kb-tree-cat');
      const items   = cat.querySelector('.kb-tree-items');
      const chevron = hdr.querySelector('.kb-tree-chevron');
      if (!items) return;

      const isOpen = cat.classList.contains('kb-tree-cat--open');
      cat.classList.toggle('kb-tree-cat--open', !isOpen);
      items.classList.toggle('kb-tree-items--hidden', isOpen);
      if (chevron) chevron.textContent = isOpen ? '▸' : '▾';
      hdr.setAttribute('aria-expanded', String(!isOpen));
    });
  });

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
