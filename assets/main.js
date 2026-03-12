'use strict';

document.addEventListener('DOMContentLoaded', () => {

  /* ── Syntax highlighting ── */
  if (typeof hljs !== 'undefined') {
    hljs.highlightAll();
  }

  /* ── KB technique tier labels ── */
  const tierMap = {
    'Core Techniques':         'tier--core',
    'Intermediate Techniques': 'tier--intermediate',
    'Advanced Techniques':     'tier--advanced',
  };
  document.querySelectorAll('.article-content h1').forEach(h1 => {
    const cls = tierMap[h1.textContent.trim()];
    if (cls) h1.classList.add(cls);
  });

  /* ── Blog post type filter ── */
  const filterBtns = document.querySelectorAll('.filter-btn');
  const postRows   = document.querySelectorAll('.post-row--full');

  if (filterBtns.length && postRows.length) {
    filterBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        filterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const filter = btn.dataset.filter;
        postRows.forEach(row => {
          row.style.display =
            (filter === 'all' || row.dataset.type === filter) ? '' : 'none';
        });
      });
    });
  }

});
