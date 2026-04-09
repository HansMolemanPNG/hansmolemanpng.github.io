'use strict';

/* ── Scroll position save/restore (survives DOM rewrites) ── */
history.scrollRestoration = 'manual';
window.addEventListener('beforeunload', () => {
  sessionStorage.setItem('scrollY:' + location.pathname, window.scrollY);
});

document.addEventListener('DOMContentLoaded', () => {

  /* ── Syntax highlighting ── */
  if (typeof hljs !== 'undefined') {
    hljs.highlightAll();
  }

  /* ── KB technique tier sections + vertical markers ── */
  const tierMap = {
    'Core Techniques':         'tier--core',
    'Intermediate Techniques': 'tier--intermediate',
    'Advanced Techniques':     'tier--advanced',
  };
  const article = document.querySelector('.article-content');
  if (article) {
    const nodes = Array.from(article.childNodes);
    const frag  = document.createDocumentFragment();
    let tierWrap = null;
    let techWrap = null;
    let activeTierCls = null;

    nodes.forEach(node => {
      if (node.nodeType !== 1) {
        (techWrap || tierWrap || frag).appendChild(node);
        return;
      }
      const tag     = node.tagName;
      const tierCls = tag === 'H1' ? tierMap[node.textContent.trim()] : null;

      if (tierCls) {
        activeTierCls = tierCls;
        tierWrap = document.createElement('div');
        tierWrap.className = 'tier-section ' + tierCls.replace('tier--', 'tier-section--');
        techWrap = null;
        node.classList.add(tierCls);
        tierWrap.appendChild(node);
        frag.appendChild(tierWrap);
      } else if (tag === 'H1') {
        activeTierCls = null;
        tierWrap = null;
        techWrap = null;
        frag.appendChild(node);
      } else if (tag === 'H2' && tierWrap) {
        techWrap = document.createElement('div');
        techWrap.className = 'technique-block';
        node.classList.add(activeTierCls);
        techWrap.appendChild(node);
        tierWrap.appendChild(techWrap);
      } else {
        (techWrap || tierWrap || frag).appendChild(node);
      }
    });

    while (article.firstChild) article.removeChild(article.firstChild);
    article.appendChild(frag);
  }

  /* ── Scroll restore (after all DOM work) ── */
  const savedY = sessionStorage.getItem('scrollY:' + location.pathname);
  if (savedY !== null) {
    requestAnimationFrame(() => window.scrollTo(0, parseInt(savedY, 10)));
  }

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
        const active = link.getAttribute('href') === '#' + id;
        link.classList.toggle('is-active', active);
        if (active && window.innerWidth > 920) {
          link.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
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

  /* ── Code block copy button ── */
  document.querySelectorAll('.article-content pre').forEach(pre => {
    // Wrap pre in a relative container so the button stays at viewport-right
    const wrap = document.createElement('div');
    wrap.className = 'code-wrap';
    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(pre);

    const btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.textContent = 'Copy';
    btn.setAttribute('aria-label', 'Copy code');
    wrap.appendChild(btn);

    btn.addEventListener('click', () => {
      const code = pre.querySelector('code');
      const text = code ? code.innerText : pre.innerText;
      navigator.clipboard.writeText(text).then(() => {
        btn.textContent = 'Copied ✓';
        btn.classList.add('is-copied');
        setTimeout(() => {
          btn.textContent = 'Copy';
          btn.classList.remove('is-copied');
        }, 2000);
      }).catch(() => {});
    });
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
