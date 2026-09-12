(function () {
  const pageRoot = document.querySelector('.dashboard-wrapper[data-sidebar-key]');
  if (!pageRoot) return;

  const STORAGE_KEY = pageRoot.dataset.sidebarKey || 'dashboardSidebarCollapsed';
  const MOBILE_NAV_MQ = window.matchMedia('(max-width: 768px)');

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

  initSidebarCollapse();
  initSidebarDrawer();
})();
