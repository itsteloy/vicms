(function() {
    const tabButtons = document.querySelectorAll('.sidebar-nav .tab-button');
    const panels = {
      employeesTab: document.getElementById('employeesTab'),
      attendanceSheetsTab: document.getElementById('attendanceSheetsTab'),
      requestsTab: document.getElementById('requestsTab'),
      documentsTab: document.getElementById('documentsTab'),
      jobOrderTab: document.getElementById('jobOrderTab'),
      idleDaysTab: document.getElementById('idleDaysTab'),
      officialBusinessTab: document.getElementById('officialBusinessTab'),
      travelOrderTab: document.getElementById('travelOrderTab'),
      payrunsTab: document.getElementById('payrunsTab'),
      deductionsTab: document.getElementById('deductionsTab'),
      approvalsTab: document.getElementById('approvalsTab'),
    };
    const defaultTab = 'employeesTab';

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

    const today = new Date().toISOString().slice(0, 10);

    // Force CAPITAL LETTERS while typing on employee name / company fields
    document.querySelectorAll(
      '#employeesTab #company_name, #employeesTab #id_first_name, #employeesTab #id_last_name'
    ).forEach((input) => {
      input.addEventListener('input', function() {
        const start = this.selectionStart;
        const end = this.selectionEnd;
        this.value = this.value.toUpperCase();
        if (typeof start === 'number' && typeof end === 'number') {
          this.setSelectionRange(start, end);
        }
      });
    });

    const attDate = document.getElementById('att_date');
    if (attDate && !attDate.value) attDate.value = today;

    const lrStart = document.getElementById('lr_start_date');
    const lrEnd = document.getElementById('lr_end_date');
    if (lrStart && !lrStart.value) lrStart.value = today;
    if (lrEnd && !lrEnd.value) lrEnd.value = today;
    if (lrStart && lrEnd) {
      lrStart.addEventListener('change', function() {
        if (lrEnd.value < lrStart.value) lrEnd.value = lrStart.value;
        lrEnd.min = lrStart.value;
      });
      lrEnd.min = lrStart.value;
    }

    document.querySelectorAll('.toggle-run-details').forEach((button) => {
      button.addEventListener('click', function() {
        const target = document.getElementById(this.dataset.target);
        if (!target) return;
        const isHidden = target.hasAttribute('hidden');
        if (isHidden) {
          target.removeAttribute('hidden');
          this.textContent = 'Hide';
        } else {
          target.setAttribute('hidden', '');
          this.textContent = 'Details';
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

    (function setupAttendanceSheetPayrunOptions() {
      const useSheets = document.getElementById('use_attendance_sheets');
      const picker = document.getElementById('attendanceSheetPicker');
      const alignField = document.getElementById('alignCutoffField');
      if (!useSheets || !picker) return;

      function sync() {
        const enabled = useSheets.checked;
        picker.style.display = enabled ? '' : 'none';
        if (alignField) alignField.style.display = enabled ? '' : 'none';
        const select = document.getElementById('attendance_sheet_ids');
        if (select) select.disabled = !enabled;
        const align = document.getElementById('align_cutoff_to_sheets');
        if (align) align.disabled = !enabled;
      }

      useSheets.addEventListener('change', sync);
      sync();
    })();

    (function setupAssignDeductionForm() {
      const form = document.getElementById('assignDeductionForm');
      if (!form) return;

      const scopeAll = document.getElementById('deductionScopeAll');
      const scopeSelected = document.getElementById('deductionScopeSelected');
      const employeePicker = document.getElementById('deductionEmployeePicker');
      const selectAllEmployees = document.getElementById('deductionSelectAllEmployees');
      const selectAllConfigs = document.getElementById('deductionSelectAllConfigs');
      const employeeCbs = () => [...form.querySelectorAll('.deduction-employee-cb')];
      const configCbs = () => [...form.querySelectorAll('.deduction-config-cb')];

      function syncScope() {
        const selected = !scopeAll || scopeAll.checked === false;
        if (employeePicker) {
          employeePicker.hidden = !selected;
          employeePicker.style.display = selected ? '' : 'none';
        }
        form.classList.toggle('is-all-employees', !selected);
        employeeCbs().forEach((cb) => {
          cb.disabled = !selected;
          if (!selected) cb.checked = false;
        });
        if (selectAllEmployees && !selected) selectAllEmployees.checked = false;
      }

      if (scopeAll) scopeAll.addEventListener('change', syncScope);
      if (scopeSelected) scopeSelected.addEventListener('change', syncScope);
      syncScope();

      if (selectAllEmployees) {
        selectAllEmployees.addEventListener('change', () => {
          employeeCbs().forEach((cb) => {
            if (!cb.disabled) cb.checked = selectAllEmployees.checked;
          });
        });
      }

      if (selectAllConfigs) {
        selectAllConfigs.addEventListener('change', () => {
          configCbs().forEach((cb) => {
            cb.checked = selectAllConfigs.checked;
          });
        });
      }

      form.addEventListener('submit', (event) => {
        const configsChecked = configCbs().some((cb) => cb.checked);
        if (!configsChecked) {
          event.preventDefault();
          alert('Select at least one deduction.');
          return;
        }
        const applyAll = scopeAll && scopeAll.checked;
        if (!applyAll) {
          const employeesChecked = employeeCbs().some((cb) => cb.checked && !cb.disabled);
          if (!employeesChecked) {
            event.preventDefault();
            alert('Select at least one employee, or choose All employees.');
          }
        }
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

    // Prefill next 10th / 25th semi-monthly pay period
    (function prefillNextPayrollCycle() {
      const startInput = document.getElementById('period_start_date');
      const endInput = document.getElementById('period_end_date');
      const payInput = document.getElementById('period_pay_date');
      if (!startInput || !endInput || !payInput) return;
      if (startInput.value || endInput.value || payInput.value) return;

      function iso(date) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
      }

      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const y = today.getFullYear();
      const m = today.getMonth();
      const day = today.getDate();

      let start;
      let end;
      let pay;
      if (day <= 10) {
        // Next pay: 10th — coverage 26th previous month through 10th
        start = new Date(y, m - 1, 26);
        end = new Date(y, m, 10);
        pay = new Date(y, m, 10);
      } else if (day <= 25) {
        // Next pay: 25th — coverage 11th through 25th
        start = new Date(y, m, 11);
        end = new Date(y, m, 25);
        pay = new Date(y, m, 25);
      } else {
        // Next pay: 10th next month — coverage 26th through 10th next month
        start = new Date(y, m, 26);
        end = new Date(y, m + 1, 10);
        pay = new Date(y, m + 1, 10);
      }

      startInput.value = iso(start);
      endInput.value = iso(end);
      payInput.value = iso(pay);
    })();
  })();
