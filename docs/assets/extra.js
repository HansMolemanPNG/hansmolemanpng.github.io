document.addEventListener('DOMContentLoaded', () => {
  // Make entire post card clickable
  document.querySelectorAll('.post-card').forEach(card => {
    const link = card.querySelector('.post-title a');
    if (!link) return;
    card.style.cursor = 'pointer';
    card.addEventListener('click', e => {
      if (e.target.closest('a')) return;
      window.location.href = link.href;
    });
  });

  // Filter buttons
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const filter = btn.dataset.filter;

      // Toggle active state
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      // Show/hide cards
      document.querySelectorAll('.post-card').forEach(card => {
        if (filter === 'all' || card.dataset.type === filter) {
          card.classList.remove('hidden');
        } else {
          card.classList.add('hidden');
        }
      });
    });
  });
});
