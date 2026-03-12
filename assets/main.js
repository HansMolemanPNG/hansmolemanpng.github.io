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
  const articleHeadings = document.querySelectorAll('.article-content h1, .article-content h2');
  let activeTierCls = null;
  articleHeadings.forEach(el => {
    if (el.tagName === 'H1') {
      activeTierCls = tierMap[el.textContent.trim()] || null;
      if (activeTierCls) el.classList.add(activeTierCls);
    } else if (activeTierCls) {
      el.classList.add(activeTierCls);
    }
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
