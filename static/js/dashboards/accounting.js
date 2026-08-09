(function() {
    const tabButtons = document.querySelectorAll('.sidebar-nav .tab-button');
    const panelIds = ['overviewTab', 'arTab', 'apTab', 'bankTab', 'payrollExpenseTab', 'journalTab', 'taxTab', 'reportsTab'];
    const panels = {};
    panelIds.forEach(id => { panels[id] = document.getElementById(id); });
    const defaultTab = 'overviewTab';

    function activateTab(targetId) {
      tabButtons.forEach(btn => {
        const isTarget = btn.dataset.tabTarget === targetId;
        btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
      });
      Object.keys(panels).forEach(id => {
        if (panels[id]) panels[id].classList.toggle('is-active', id === targetId);
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
      activateTab(activeTab && panels[activeTab] ? activeTab : defaultTab);
    });

    // Bank transaction form: toggle contra-account vs transfer-to fields
    const bankTxnType = document.getElementById('bankTxnType');
    const contraField = document.getElementById('bankTxnContraField');
    const toAccountField = document.getElementById('bankTxnToAccountField');
    if (bankTxnType) {
      bankTxnType.addEventListener('change', function() {
        const isTransfer = this.value === 'transfer';
        contraField.style.display = isTransfer ? 'none' : '';
        toAccountField.style.display = isTransfer ? '' : 'none';
      });
    }

    // Manual journal entry: reveal extra line rows
    const addJeLineBtn = document.getElementById('addJeLineBtn');
    if (addJeLineBtn) {
      addJeLineBtn.addEventListener('click', function() {
        const hiddenRow = document.querySelector('#jeLinesContainer [data-je-extra][style*="display: none"], #jeLinesContainer [data-je-extra]:not([data-je-shown])');
        const rows = document.querySelectorAll('#jeLinesContainer .je-line-row');
        for (const row of rows) {
          if (row.style.display === 'none') {
            row.style.display = '';
            row.setAttribute('data-je-shown', '1');
            break;
          }
        }
      });
    }

    // Toggle journal entry line details
    document.querySelectorAll('.toggle-je-lines').forEach(btn => {
      btn.addEventListener('click', function() {
        const target = document.getElementById(this.dataset.target);
        if (!target) return;
        if (target.hasAttribute('hidden')) {
          target.removeAttribute('hidden');
          this.textContent = 'Hide';
        } else {
          target.setAttribute('hidden', '');
          this.textContent = 'View';
        }
      });
    });

    // Reports tab: show account selector only for General Ledger
    const reportTypeSelect = document.getElementById('reportTypeSelect');
    const reportAccountField = document.getElementById('reportAccountField');
    if (reportTypeSelect) {
      reportTypeSelect.addEventListener('change', function() {
        reportAccountField.style.display = this.value === 'general_ledger' ? '' : 'none';
      });
    }
  })();
