'use strict';

document.addEventListener('DOMContentLoaded', () => {

  /* ── Syntax highlighting ── */
  if (typeof hljs !== 'undefined') {
    hljs.highlightAll();
  }

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
