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

  /* ── KB sheet: sidebar TOC ── */
  (function () {
    const toc = document.getElementById('kb-toc');
    if (!toc) return;

    // Mobile toggle
    const toggle = toc.querySelector('.kb-toc-toggle');
    if (toggle) {
      toggle.addEventListener('click', () => {
        const open = toc.classList.toggle('is-open');
        toggle.setAttribute('aria-expanded', open);
      });
    }

    // Close sidebar when a TOC link is clicked on mobile
    toc.querySelectorAll('.kb-toc-h1, .kb-toc-h2').forEach(link => {
      link.addEventListener('click', () => {
        if (window.innerWidth <= 920) {
          toc.classList.remove('is-open');
          if (toggle) toggle.setAttribute('aria-expanded', 'false');
        }
      });
    });

    // Search filter
    const search = toc.querySelector('.kb-toc-search');
    if (search) {
      search.addEventListener('input', () => {
        const q = search.value.trim().toLowerCase();
        toc.querySelectorAll('.kb-toc-section').forEach(section => {
          if (!q) {
            section.classList.remove('is-hidden');
            section.querySelectorAll('.kb-toc-child-item').forEach(li => li.classList.remove('is-hidden'));
            return;
          }
          const h1Match = section.dataset.h1.includes(q);
          let anyChild = false;
          section.querySelectorAll('.kb-toc-child-item').forEach(li => {
            const match = h1Match || li.dataset.h2.includes(q);
            li.classList.toggle('is-hidden', !match);
            if (match) anyChild = true;
          });
          section.classList.toggle('is-hidden', !h1Match && !anyChild);
        });
      });
    }

    // Active section on scroll
    const headings = Array.from(
      document.querySelectorAll('.article-content h1[id], .article-content h2[id]')
    );
    if (!headings.length) return;

    const tocLinks = toc.querySelectorAll('.kb-toc-h1, .kb-toc-h2');

    function setActive(id) {
      tocLinks.forEach(link => {
        link.classList.toggle('is-active', link.getAttribute('href') === '#' + id);
      });
    }

    function findActive() {
      const offset = 120;
      let active = headings[0];
      for (const h of headings) {
        if (h.getBoundingClientRect().top <= offset) active = h;
        else break;
      }
      return active ? active.id : null;
    }

    window.addEventListener('scroll', () => {
      const id = findActive();
      if (id) setActive(id);
    }, { passive: true });

    // Run once on load
    const id = findActive();
    if (id) setActive(id);
  })();

  /* ── KB category: equal-height sheet rows ── */
  document.querySelectorAll('.sheet-list').forEach(list => {
    const rows = Array.from(list.querySelectorAll('.sheet-row'));
    if (rows.length < 2) return;
    rows.forEach(r => r.style.minHeight = '');
    const max = rows.reduce((m, r) => Math.max(m, r.offsetHeight), 0);
    if (max > 0) rows.forEach(r => r.style.minHeight = max + 'px');
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
