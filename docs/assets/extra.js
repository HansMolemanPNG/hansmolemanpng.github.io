document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.post-card').forEach(card => {
    const link = card.querySelector('h3 a');
    if (!link) return;
    card.style.cursor = 'pointer';
    card.addEventListener('click', e => {
      if (e.target.closest('a')) return;
      window.location.href = link.href;
    });
  });
});
