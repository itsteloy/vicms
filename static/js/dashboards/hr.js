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

    const obName = document.getElementById('ob_name');
    const obDesignation = document.getElementById('ob_designation');
    if (obName && obDesignation) {
      const syncObDesignation = () => {
        const option = obName.options[obName.selectedIndex];
        obDesignation.value = option ? (option.dataset.designation || '') : '';
      };
      obName.addEventListener('change', syncObDesignation);
      syncObDesignation();
    }

    // ── Document forms: live preview + repeatable rows ──
    function formatPreviewDate(value) {
      if (!value) return '—';
      const parsed = new Date(value + 'T00:00:00');
      if (Number.isNaN(parsed.getTime())) return value;
      return parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    }

    function formatPreviewTime(value) {
      if (!value) return '—';
      const [hoursStr, minutesStr] = value.split(':');
      const hours = parseInt(hoursStr, 10);
      if (Number.isNaN(hours)) return value;
      const period = hours >= 12 ? 'PM' : 'AM';
      const displayHour = ((hours + 11) % 12) + 1;
      return `${displayHour}:${minutesStr} ${period}`;
    }

    function updateRepeatablePreview(panel, previewKey, selector, isDate) {
      if (!panel) return;
      const values = [...panel.querySelectorAll(selector)]
        .map((input) => input.value.trim())
        .filter(Boolean)
        .map((value) => (isDate ? formatPreviewDate(value) : value));
      panel.querySelectorAll(`[data-preview="${previewKey}"]`).forEach((target) => {
        const joiner = previewKey === 'travel_with' ? '\n' : ', ';
        target.textContent = values.length ? values.join(joiner) : '—';
      });
    }

    function syncFieldPreview(panel, field) {
      if (!panel || !field || !field.name) return;
      if (field.name === 'assignee_names') {
        updateRepeatablePreview(panel, 'assignee_names', 'input[name="assignee_names"]', false);
        return;
      }
      if (field.name === 'assignee_ids') {
        const selected = [...field.selectedOptions].map((opt) => opt.textContent.trim()).filter(Boolean);
        const freeText = [...panel.querySelectorAll('input[name="assignee_names"]')]
          .map((input) => input.value.trim())
          .filter(Boolean);
        const values = [...selected, ...freeText];
        panel.querySelectorAll('[data-preview="assignee_names"]').forEach((target) => {
          target.textContent = values.length ? values.join(', ') : '—';
        });
        return;
      }
      if (field.name === 'dates_covered' || field.name === 'coverage_start' || field.name === 'coverage_end') {
        const start = panel.querySelector('#coverage_start')?.value;
        const end = panel.querySelector('#coverage_end')?.value;
        let coverageLabel = '—';
        if (start && end) {
          coverageLabel = `${formatPreviewDate(start)} – ${formatPreviewDate(end)}`;
        } else if (start) {
          coverageLabel = formatPreviewDate(start);
        } else if (end) {
          coverageLabel = formatPreviewDate(end);
        } else {
          const values = [...panel.querySelectorAll('input[name="dates_covered"]')]
            .map((input) => input.value.trim())
            .filter(Boolean)
            .map((value) => formatPreviewDate(value));
          coverageLabel = values.length ? values.join(', ') : '—';
        }
        panel.querySelectorAll('[data-preview="dates_covered"]').forEach((target) => {
          target.textContent = coverageLabel;
        });
        return;
      }
      if (field.name === 'ob_dates') {
        updateRepeatablePreview(panel, 'ob_dates', 'input[name="ob_dates"]', true);
        return;
      }
      if (field.name === 'travel_with') {
        updateRepeatablePreview(panel, 'travel_with', 'input[name="travel_with"]', false);
        return;
      }
      let displayValue = field.value || '—';
      if (field.type === 'date' && field.value) {
        displayValue = formatPreviewDate(field.value);
      } else if (field.type === 'time' && field.value) {
        displayValue = formatPreviewTime(field.value);
      }
      panel.querySelectorAll(`[data-preview="${field.name}"]`).forEach((target) => {
        target.textContent = displayValue;
      });
    }

    function setupRepeatableList(listId, addBtnId, inputType, inputName, placeholder, requireFirst = false) {
      const list = document.getElementById(listId);
      const addBtn = document.getElementById(addBtnId);
      if (!list || !addBtn) return;
      const ownerPanel = list.closest('.tab-panel');

      function refreshRemoveButtons() {
        const rows = list.querySelectorAll('.repeatable-row');
        rows.forEach((row, index) => {
          const removeBtn = row.querySelector('[data-remove-row]');
          if (removeBtn) removeBtn.hidden = rows.length === 1;
          const input = row.querySelector('input');
          if (input && index === 0 && inputType === 'text' && requireFirst) {
            input.required = true;
          } else if (input) {
            input.required = false;
          }
        });
      }

      function bindRow(row) {
        row.querySelectorAll('input').forEach((input) => {
          const update = () => updateRepeatablePreview(ownerPanel, inputName, `input[name="${inputName}"]`, inputType === 'date');
          input.addEventListener('input', update);
          input.addEventListener('change', update);
        });
        const removeBtn = row.querySelector('[data-remove-row]');
        if (removeBtn) {
          removeBtn.addEventListener('click', () => {
            if (list.querySelectorAll('.repeatable-row').length === 1) return;
            row.remove();
            refreshRemoveButtons();
            updateRepeatablePreview(ownerPanel, inputName, `input[name="${inputName}"]`, inputType === 'date');
          });
        }
      }

      addBtn.addEventListener('click', () => {
        const row = document.createElement('div');
        row.className = 'repeatable-row';
        row.innerHTML = `
          <input type="${inputType}" name="${inputName}" class="field-input" placeholder="${placeholder || ''}">
          <button type="button" class="action row-remove" data-remove-row aria-label="Remove row">✕</button>
        `;
        list.appendChild(row);
        bindRow(row);
        refreshRemoveButtons();
        row.querySelector('input').focus();
      });

      list.querySelectorAll('.repeatable-row').forEach(bindRow);
      refreshRemoveButtons();
    }

    function setupDocPanel(panel, defaultDateId, formId) {
      if (!panel) return;
      panel.querySelectorAll('input, textarea, select').forEach((field) => {
        if (field.disabled) return;
        const update = () => syncFieldPreview(panel, field);
        field.addEventListener('input', update);
        field.addEventListener('change', update);
        syncFieldPreview(panel, field);
      });

      const defaultDate = defaultDateId ? document.getElementById(defaultDateId) : null;
      if (defaultDate && !defaultDate.value) {
        defaultDate.value = today;
        syncFieldPreview(panel, defaultDate);
      }

      const form = formId ? document.getElementById(formId) : null;
      if (form) {
        form.addEventListener('reset', () => {
          setTimeout(() => {
            if (defaultDate) defaultDate.value = today;
            panel.querySelectorAll('input, textarea, select').forEach((field) => {
              if (!field.disabled) syncFieldPreview(panel, field);
            });
          }, 0);
        });
      }
    }

    setupDocPanel(document.getElementById('jobOrderTab'), 'date_filed', 'jobOrderForm');
    setupDocPanel(document.getElementById('officialBusinessTab'), 'ob_application_date', 'obForm');
    setupDocPanel(document.getElementById('travelOrderTab'), 'to_travel_date', 'travelOrderForm');
    setupRepeatableList('jobNamesList', 'jobAddName', 'text', 'assignee_names', 'Full name (if not selecting employees above)', false);
    setupRepeatableList('jobDatesList', 'jobAddDate', 'date', 'dates_covered', '');
    setupRepeatableList('obDatesList', 'obAddDate', 'date', 'ob_dates', '');
    setupRepeatableList('travelWithList', 'travelAddPassenger', 'text', 'travel_with', 'Passenger name');

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
