(function () {
  const pageRoot = document.querySelector('.dashboard-wrapper[data-sidebar-key]');
  if (!pageRoot) return;

  const STORAGE_KEY = pageRoot.dataset.sidebarKey || 'dashboardSidebarCollapsed';
  const WIDTH_KEY = STORAGE_KEY + ':width';
  const MOBILE_NAV_MQ = window.matchMedia('(max-width: 768px)');

  const MIN_SIDEBAR_WIDTH = 220;
  const MAX_SIDEBAR_WIDTH = 600;
  const SIDEBAR_MIN_CONTENT = 360;

  function isSidebarCollapsed() {
    return pageRoot.classList.contains('sidebar-is-collapsed');
  }

  function syncSidebarToggleUi(collapsed) {
    const toggle = document.getElementById('sidebarToggle');
    if (!toggle) return;
    toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    const label = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
    toggle.title = label;
    const sr = toggle.querySelector('.sr-only');
    if (sr) sr.textContent = label;
  }

  function setSidebarCollapsed(collapsed) {
    pageRoot.classList.toggle('sidebar-is-collapsed', collapsed);
    document.documentElement.classList.toggle('sidebar-pref-collapsed', collapsed);
    try {
      localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0');
    } catch (e) {}
    syncSidebarToggleUi(collapsed);
  }

  function isMobileNav() {
    return MOBILE_NAV_MQ.matches;
  }

  function setSidebarDrawerOpen(open) {
    pageRoot.classList.toggle('sidebar-drawer-open', open);
    document.body.classList.toggle('sidebar-drawer-open', open);
    const backdrop = document.getElementById('sidebarBackdrop');
    if (backdrop) backdrop.hidden = !open;
    const mobileToggle = document.getElementById('mobileNavToggle');
    if (mobileToggle) {
      mobileToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      mobileToggle.title = open ? 'Close menu' : 'Open menu';
      const sr = mobileToggle.querySelector('.sr-only');
      if (sr) sr.textContent = open ? 'Close menu' : 'Open menu';
    }
  }

  function closeSidebarDrawer() {
    setSidebarDrawerOpen(false);
  }

  function clampSidebarWidth(width) {
    const viewportMax = window.innerWidth - SIDEBAR_MIN_CONTENT;
    const max = Math.max(MIN_SIDEBAR_WIDTH, Math.min(MAX_SIDEBAR_WIDTH, viewportMax));
    return Math.max(MIN_SIDEBAR_WIDTH, Math.min(Math.round(width), max));
  }

  function applySidebarWidth(width) {
    if (!Number.isFinite(width)) return;
    document.documentElement.style.setProperty('--sidebar-w', clampSidebarWidth(width) + 'px');
  }

  function currentSidebarWidth() {
    const raw = getComputedStyle(document.documentElement).getPropertyValue('--sidebar-w');
    return parseFloat(raw);
  }

  function loadSidebarWidth() {
    let width = null;
    try {
      width = parseInt(localStorage.getItem(WIDTH_KEY), 10);
    } catch (e) {
      width = null;
    }
    if (Number.isFinite(width)) applySidebarWidth(width);
  }

  function initSidebarResize() {
    const sidebar = pageRoot.querySelector('.sidebar');
    const handle = document.getElementById('sidebarResizer') || pageRoot.querySelector('.sidebar-resizer');
    if (!sidebar || !handle) return;

    let dragging = false;
    let startX = 0;
    let startWidth = 0;

    function onPointerMove(event) {
      if (!dragging) return;
      applySidebarWidth(startWidth + (event.clientX - startX));
    }

    function stopDragging() {
      if (!dragging) return;
      dragging = false;
      handle.classList.remove('is-resizing');
      sidebar.classList.remove('is-resizing');
      document.body.classList.remove('sidebar-resizing');
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', stopDragging);
      window.removeEventListener('pointercancel', stopDragging);
      const width = currentSidebarWidth();
      if (Number.isFinite(width)) {
        try {
          localStorage.setItem(WIDTH_KEY, String(Math.round(width)));
        } catch (e) {}
      }
    }

    handle.addEventListener('pointerdown', (event) => {
      if (isSidebarCollapsed() || isMobileNav()) return;
      event.preventDefault();
      dragging = true;
      startX = event.clientX;
      startWidth = sidebar.getBoundingClientRect().width;
      handle.classList.add('is-resizing');
      sidebar.classList.add('is-resizing');
      document.body.classList.add('sidebar-resizing');
      window.addEventListener('pointermove', onPointerMove);
      window.addEventListener('pointerup', stopDragging);
      window.addEventListener('pointercancel', stopDragging);
    });

    window.addEventListener('resize', () => {
      const width = currentSidebarWidth();
      if (Number.isFinite(width)) applySidebarWidth(width);
    });
  }

  function initSidebarCollapse() {
    let collapsed = false;
    try {
      collapsed = localStorage.getItem(STORAGE_KEY) === '1';
    } catch (e) {
      collapsed = document.documentElement.classList.contains('sidebar-pref-collapsed');
    }
    setSidebarCollapsed(collapsed);
    document.getElementById('sidebarToggle')?.addEventListener('click', () => {
      setSidebarCollapsed(!isSidebarCollapsed());
    });
  }

  function initSidebarDrawer() {
    document.getElementById('mobileNavToggle')?.addEventListener('click', () => {
      setSidebarDrawerOpen(!pageRoot.classList.contains('sidebar-drawer-open'));
    });
    document.getElementById('sidebarBackdrop')?.addEventListener('click', closeSidebarDrawer);
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeSidebarDrawer();
    });
    pageRoot.querySelectorAll('.sidebar-nav .tab-button').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (isMobileNav()) closeSidebarDrawer();
      });
    });
    const onMqChange = () => {
      if (!isMobileNav()) closeSidebarDrawer();
    };
    if (typeof MOBILE_NAV_MQ.addEventListener === 'function') {
      MOBILE_NAV_MQ.addEventListener('change', onMqChange);
    } else if (typeof MOBILE_NAV_MQ.addListener === 'function') {
      MOBILE_NAV_MQ.addListener(onMqChange);
    }
  }

  loadSidebarWidth();
  initSidebarCollapse();
  initSidebarDrawer();
  initSidebarResize();
})();
