/* =============================================================
   DASHBOARD.JS — HeartGuard Admin Dashboard
   ============================================================= */
(function () {
  'use strict';

  const sidebar  = document.getElementById('dash-sidebar');
  const overlay  = document.getElementById('sb-overlay');
  const toggle   = document.getElementById('sb-toggle');

  /* ---- Sidebar toggle -------------------------------------- */
  function isMobile() { return window.innerWidth <= 768; }

  toggle?.addEventListener('click', () => {
    if (isMobile()) {
      sidebar.classList.toggle('mob-open');
      overlay.classList.toggle('on');
    } else {
      sidebar.classList.toggle('collapsed');
      localStorage.setItem('sb-collapsed', sidebar.classList.contains('collapsed') ? '1' : '0');
    }
  });

  overlay?.addEventListener('click', () => {
    sidebar.classList.remove('mob-open');
    overlay.classList.remove('on');
  });

  /* Restore on desktop */
  if (!isMobile() && localStorage.getItem('sb-collapsed') === '1') {
    sidebar.classList.add('collapsed');
  }

  window.addEventListener('resize', () => {
    if (isMobile()) {
      sidebar.classList.remove('collapsed');
      overlay.classList.remove('on');
    }
  });

  /* ---- Accordion submenus ---------------------------------- */
  document.querySelectorAll('.nav-group-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const grp = btn.closest('.nav-group');
      const open = grp.classList.contains('open');
      /* Close others */
      document.querySelectorAll('.nav-group.open').forEach(g => {
        if (g !== grp) g.classList.remove('open');
      });
      grp.classList.toggle('open', !open);
    });
  });

  /* Open group if current path matches a subitem */
  const path = window.location.pathname;
  document.querySelectorAll('.sb-subitem').forEach(link => {
    if (link.getAttribute('href') === path) {
      const grp = link.closest('.nav-group');
      if (grp) {
        grp.classList.add('open');
        grp.querySelector('.nav-group-btn')?.classList.add('grp-active');
      }
    }
  });

  /* ---- Date display in welcome banner ---------------------- */
  const dateEl = document.getElementById('today-date');
  if (dateEl) {
    const d = new Date();
    dateEl.textContent = d.toLocaleDateString('en-US', {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });
  }

  /* ---- Confirm before delete ------------------------------- */
  document.querySelectorAll('[data-confirm]').forEach(btn => {
    btn.addEventListener('click', e => {
      if (!confirm(btn.dataset.confirm)) {
        e.preventDefault();
        e.stopImmediatePropagation();
      }
    });
  });

  /* ---- Table search (client-side filter) ------------------- */
  const tableSearch = document.getElementById('table-search');
  if (tableSearch) {
    tableSearch.addEventListener('input', () => {
      const q = tableSearch.value.toLowerCase().trim();
      document.querySelectorAll('.dash-tbl tbody tr').forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    });
  }


})();
