(function() {
    const tabButtons = document.querySelectorAll('.sidebar-nav .tab-button');
    const panels = {
      payrunsTab: document.getElementById('payrunsTab'),
      deductionsTab: document.getElementById('deductionsTab'),
      approvalsTab: document.getElementById('approvalsTab'),
    };
    const defaultTab = 'payrunsTab';

    function activateTab(targetId) {
      tabButtons.forEach(btn => {
        const isTarget = btn.dataset.tabTarget === targetId;
        btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
      });

      Object.keys(panels).forEach(id => {
        if (panels[id]) {
          panels[id].classList.toggle('is-active', id === targetId);
        }
      });
    }

    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get('tab');
    const initialTab = tabParam && panels[tabParam] ? tabParam : defaultTab;
    activateTab(initialTab);

    tabButtons.forEach(btn => {
      btn.addEventListener('click', function() {
        const targetId = this.dataset.tabTarget;
        const url = new URL(window.location.href);
        url.searchParams.set('tab', targetId);
        window.history.pushState({}, '', url);
        activateTab(targetId);
      });
    });

    window.addEventListener('popstate', function() {
      const activeTab = new URLSearchParams(window.location.search).get('tab');
      if (activeTab && panels[activeTab]) {
        activateTab(activeTab);
      } else {
        activateTab(defaultTab);
      }
    });

    document.querySelectorAll('.toggle-run-details').forEach((button) => {
      button.addEventListener('click', () => {
        const row = document.getElementById(button.dataset.target);
        if (!row) return;
        const isHidden = row.hasAttribute('hidden');
        if (isHidden) {
          row.removeAttribute('hidden');
          button.textContent = 'Hide';
        } else {
          row.setAttribute('hidden', '');
          button.textContent = 'Details';
        }
      });
    });

    (function setupPayrollRunMenus() {
      function closeOpenMenus(except) {
        document.querySelectorAll('details.payroll-run-menu[open]').forEach((menu) => {
          if (menu !== except) menu.removeAttribute('open');
        });
      }

      document.querySelectorAll('details.payroll-run-menu').forEach((menu) => {
        menu.addEventListener('toggle', () => {
          if (menu.open) closeOpenMenus(menu);
        });
        menu.querySelectorAll('a.payroll-run-menu-item').forEach((link) => {
          link.addEventListener('click', () => menu.removeAttribute('open'));
        });
      });

      document.addEventListener('click', (event) => {
        const openMenu = event.target.closest('details.payroll-run-menu[open]');
        if (!openMenu) closeOpenMenus();
      });
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeOpenMenus();
      });
    })();

    (function setupPayrollOtLiveCalc() {
      const OT_REG_FACTOR = 1.25;
      const OT_SUN_FACTOR = 1.30;

      function money(value) {
        return Math.round((Number(value) || 0) * 100) / 100;
      }

      function formatPeso(value) {
        return '₱' + money(value).toFixed(2);
      }

      function num(value) {
        const n = parseFloat(value);
        return Number.isFinite(n) ? n : 0;
      }

      function recalculateRow(row) {
        if (!row) return;
        const hourly = num(row.dataset.hourly);
        const base = num(row.dataset.base);
        const holiday = num(row.dataset.holiday);
        const undertime = num(row.dataset.undertime);
        const configured = num(row.dataset.configured);
        const reg = Math.max(0, num(row.querySelector('.ot-reg-hours')?.value));
        const sun = Math.max(0, num(row.querySelector('.ot-sun-hours')?.value));
        const otAmount = money(reg * hourly * OT_REG_FACTOR + sun * hourly * OT_SUN_FACTOR);
        const gross = money(base + otAmount + holiday);
        const totalDed = money(undertime + configured);
        const net = money(gross - totalDed);

        const amountEl = row.querySelector('.ot-amount-display');
        const grossEl = row.querySelector('.ot-gross-display');
        const dedEl = row.querySelector('.ot-ded-display');
        const netEl = row.querySelector('.ot-net-display');
        if (amountEl) amountEl.textContent = formatPeso(otAmount);
        if (grossEl) grossEl.textContent = formatPeso(gross);
        if (dedEl) dedEl.textContent = formatPeso(totalDed);
        if (netEl) netEl.textContent = formatPeso(net);
      }

      document.querySelectorAll('.ot-calc-row').forEach((row) => {
        row.querySelectorAll('.ot-hours-input').forEach((input) => {
          input.addEventListener('input', () => recalculateRow(row));
          input.addEventListener('change', () => recalculateRow(row));
        });
        if (row.querySelector('.ot-hours-input')) {
          recalculateRow(row);
        }
      });
    })();
  })();
