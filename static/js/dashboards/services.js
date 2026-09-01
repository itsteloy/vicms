(function () {
    const tabButtons = document.querySelectorAll('.sidebar-nav .tab-button');
    const panels = {
      repairTab: document.getElementById('repairTab'),
      borrowMaterialTab: document.getElementById('borrowMaterialTab'),
      jobOrderTab: document.getElementById('jobOrderTab'),
      travelOrderTab: document.getElementById('travelOrderTab'),
      officialBusinessTab: document.getElementById('officialBusinessTab'),
      deliveryReceiptTab: document.getElementById('deliveryReceiptTab'),
      withdrawalSlipTab: document.getElementById('withdrawalSlipTab'),
      idleDaysTab: document.getElementById('idleDaysTab'),
    };
    const defaultTab = 'repairTab';

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
    const hashTabMap = {
      '#repair': 'repairTab',
      '#borrow': 'borrowMaterialTab',
      '#job': 'jobOrderTab',
      '#travel': 'travelOrderTab',
      '#ob': 'officialBusinessTab',
      '#dr': 'deliveryReceiptTab',
      '#ws': 'withdrawalSlipTab',
      '#idle': 'idleDaysTab',
    };
    const hashTab = hashTabMap[location.hash] || null;
    const initialTab = (tabParam && panels[tabParam]) ? tabParam : (hashTab || defaultTab);
    activateTab(initialTab);

    tabButtons.forEach(btn => {
      btn.addEventListener('click', function () {
        const targetId = this.dataset.tabTarget;
        const url = new URL(window.location.href);
        url.searchParams.set('tab', targetId);
        window.history.pushState({}, '', url);
        activateTab(targetId);
      });
    });

    window.addEventListener('popstate', function () {
      const activeTab = new URLSearchParams(window.location.search).get('tab');
      if (activeTab && panels[activeTab]) {
        activateTab(activeTab);
      } else {
        activateTab(defaultTab);
      }
    });

    document.querySelectorAll('.tab-panel').forEach(panel => {
      panel.querySelectorAll('input, textarea, select').forEach(field => {
        const update = () => syncFieldPreview(panel, field);
        field.addEventListener('input', update);
        field.addEventListener('change', update);
      });
    });

    function syncFieldPreview(panel, field) {
      if (!panel || !field || !field.name) return;
      if (field.name === 'assignee_names') {
        updateJobRepeatablePreview(panel, 'assignee_names', 'input[name="assignee_names"]');
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
        updateJobRepeatablePreview(panel, 'ob_dates', 'input[name="ob_dates"]', true);
        return;
      }
      if (field.name === 'travel_with') {
        updateJobRepeatablePreview(panel, 'travel_with', 'input[name="travel_with"]', false, '\n');
        return;
      }
      panel.querySelectorAll(`[data-preview="${field.name}"]`).forEach(target => {
        if (field.tagName === 'SELECT') {
          const optionText = field.options[field.selectedIndex] ? field.options[field.selectedIndex].text : '';
          target.textContent = (field.name === 'name' ? field.value : optionText) || '—';
          return;
        }
        let displayValue = field.value || '—';
        if (field.type === 'date' && field.value) {
          const parsed = new Date(`${field.value}T00:00:00`);
          if (!Number.isNaN(parsed.getTime())) {
            displayValue = parsed.toLocaleDateString(undefined, {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
            });
          }
        } else if (field.type === 'time' && field.value) {
          const [hoursStr, minutesStr] = field.value.split(':');
          const hours = parseInt(hoursStr, 10);
          if (!Number.isNaN(hours)) {
            const period = hours >= 12 ? 'PM' : 'AM';
            const displayHour = ((hours + 11) % 12) + 1;
            displayValue = `${displayHour}:${minutesStr} ${period}`;
          }
        }
        target.textContent = displayValue;
      });
    }

    function syncPanelPreviews(panel) {
      if (!panel) return;
      panel.querySelectorAll('input, textarea, select').forEach((field) => {
        syncFieldPreview(panel, field);
      });
    }

    function syncAllFormPreviews() {
      document.querySelectorAll('.tab-panel').forEach(syncPanelPreviews);
    }

    function localTodayISO() {
      const now = new Date();
      const year = now.getFullYear();
      const month = String(now.getMonth() + 1).padStart(2, '0');
      const day = String(now.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    }

    function setDefaultDate(input, value) {
      if (!input) return;
      if (!input.value) input.value = value;
      // Always refresh the live preview so today's date shows immediately.
      const panel = input.closest('.tab-panel');
      if (panel) syncFieldPreview(panel, input);
    }

    function formatPreviewDate(value) {
      if (!value) return '—';
      const parsed = new Date(`${value}T00:00:00`);
      if (Number.isNaN(parsed.getTime())) return value;
      return parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    }

    function updateJobRepeatablePreview(panel, previewKey, selector, isDate, joiner) {
      const values = [...panel.querySelectorAll(selector)]
        .map((input) => input.value.trim())
        .filter(Boolean)
        .map((value) => {
          if (!isDate) return value;
          return formatPreviewDate(value);
        });
      const separator = joiner || (previewKey === 'travel_with' ? '\n' : ', ');
      panel.querySelectorAll(`[data-preview="${previewKey}"]`).forEach((target) => {
        target.textContent = values.length ? values.join(separator) : '—';
      });
    }

    function setupRepeatableList(listId, addBtnId, inputType, inputName, placeholder) {
      const list = document.getElementById(listId);
      const addBtn = document.getElementById(addBtnId);
      if (!list || !addBtn) return;

      function refreshRemoveButtons() {
        const rows = list.querySelectorAll('.repeatable-row');
        rows.forEach((row, index) => {
          const removeBtn = row.querySelector('[data-remove-row]');
          if (removeBtn) {
            removeBtn.hidden = rows.length === 1;
          }
          const input = row.querySelector('input');
          if (input && index === 0 && inputType === 'text') {
            input.required = true;
          } else if (input) {
            input.required = false;
          }
        });
      }

      function bindRow(row) {
        const ownerPanel = list.closest('.tab-panel');
        row.querySelectorAll('input').forEach((input) => {
          input.addEventListener('input', () => {
            updateJobRepeatablePreview(
              ownerPanel,
              inputName,
              `input[name="${inputName}"]`,
              inputType === 'date'
            );
          });
          input.addEventListener('change', () => {
            updateJobRepeatablePreview(
              ownerPanel,
              inputName,
              `input[name="${inputName}"]`,
              inputType === 'date'
            );
          });
        });
        const removeBtn = row.querySelector('[data-remove-row]');
        if (removeBtn) {
          removeBtn.addEventListener('click', () => {
            if (list.querySelectorAll('.repeatable-row').length === 1) return;
            row.remove();
            refreshRemoveButtons();
            updateJobRepeatablePreview(
              ownerPanel,
              inputName,
              `input[name="${inputName}"]`,
              inputType === 'date'
            );
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

    function updateBorrowLinesPreview() {
      const panel = document.getElementById('borrowMaterialTab');
      const tbody = panel?.querySelector('[data-preview="borrow_lines"]');
      if (!panel || !tbody) return;

      const rows = [...panel.querySelectorAll('.borrow-line-row')];
      const lines = rows.map((row) => {
        const description = row.querySelector('[data-borrow-description]')?.value.trim() || '';
        const quantity = row.querySelector('[data-borrow-quantity]')?.value.trim() || '1';
        const unit = row.querySelector('[data-borrow-unit]')?.value.trim() || 'pcs';
        const remarks = row.querySelector('[data-borrow-remarks]')?.value.trim() || '—';
        return { description, quantity, unit, remarks };
      }).filter((line) => line.description);

      if (!lines.length) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="5">No items added yet.</td></tr>';
        return;
      }

      tbody.innerHTML = lines.map((line, index) => `
        <tr>
          <td>${index + 1}</td>
          <td>${escapeHtml(line.description)}</td>
          <td>${escapeHtml(line.quantity)}</td>
          <td>${escapeHtml(line.unit)}</td>
          <td>${escapeHtml(line.remarks)}</td>
        </tr>
      `).join('');
    }

    function escapeHtml(value) {
      return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
    }

    function setupBorrowLines() {
      const list = document.getElementById('borrowLinesList');
      const addBtn = document.getElementById('borrowAddLine');
      if (!list || !addBtn) return;

      const inventoryTemplate = list.querySelector('[data-borrow-inventory]')?.innerHTML || '';

      function refreshRemoveButtons() {
        const rows = list.querySelectorAll('.borrow-line-row');
        rows.forEach((row) => {
          const removeBtn = row.querySelector('[data-remove-row]');
          if (removeBtn) {
            removeBtn.hidden = rows.length === 1;
          }
          const description = row.querySelector('[data-borrow-description]');
          if (description) {
            description.required = rows.length >= 1 && row === rows[0];
          }
        });
      }

      function bindInventorySelect(select) {
        if (!select) return;
        select.addEventListener('change', () => {
          const option = select.options[select.selectedIndex];
          const description = select.closest('.borrow-line-row')?.querySelector('[data-borrow-description]');
          if (description && option?.dataset.name) {
            description.value = option.dataset.name;
          }
          updateBorrowLinesPreview();
        });
      }

      function bindRow(row) {
        row.querySelectorAll('input, select').forEach((field) => {
          field.addEventListener('input', updateBorrowLinesPreview);
          field.addEventListener('change', updateBorrowLinesPreview);
        });
        bindInventorySelect(row.querySelector('[data-borrow-inventory]'));

        const removeBtn = row.querySelector('[data-remove-row]');
        if (removeBtn) {
          removeBtn.addEventListener('click', () => {
            if (list.querySelectorAll('.borrow-line-row').length === 1) return;
            row.remove();
            refreshRemoveButtons();
            updateBorrowLinesPreview();
          });
        }
      }

      addBtn.addEventListener('click', () => {
        const row = document.createElement('div');
        row.className = 'repeatable-row borrow-line-row';
        row.innerHTML = `
          <select name="borrow_item_inventory" data-borrow-inventory aria-label="Inventory item">${inventoryTemplate}</select>
          <input type="text" name="borrow_item_description" placeholder="Item description" data-borrow-description>
          <input type="number" name="borrow_item_quantity" value="1" min="1" step="1" data-borrow-quantity aria-label="Quantity">
          <input type="text" name="borrow_item_unit" value="pcs" placeholder="Unit" data-borrow-unit aria-label="Unit">
          <input type="text" name="borrow_item_remarks" placeholder="Remarks" data-borrow-remarks aria-label="Remarks">
          <button type="button" class="action row-remove" data-remove-row aria-label="Remove item">✕</button>
        `;
        list.appendChild(row);
        bindRow(row);
        refreshRemoveButtons();
        row.querySelector('[data-borrow-description]')?.focus();
        updateBorrowLinesPreview();
      });

      list.querySelectorAll('.borrow-line-row').forEach(bindRow);
      refreshRemoveButtons();
      updateBorrowLinesPreview();
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
        setDefaultDate(defaultDate, localTodayISO());
      }

      const form = formId ? document.getElementById(formId) : null;
      if (form) {
        form.addEventListener('reset', () => {
          requestAnimationFrame(() => {
            if (defaultDate) defaultDate.value = localTodayISO();
            const jobNumber = form.querySelector('#job_order_number');
            if (jobNumber && jobNumber.hasAttribute('data-auto-number')) {
              jobNumber.value = jobNumber.getAttribute('data-auto-number') || '';
            }
            syncPanelPreviews(panel);
          });
        });
      }
    }

    setupBorrowLines();
    setupRepeatableList('obDatesList', 'obAddDate', 'date', 'ob_dates', '');
    setupRepeatableList('jobNamesList', 'jobAddName', 'text', 'assignee_names', 'Full name (if not selecting employees above)');
    setupRepeatableList('jobDatesList', 'jobAddDate', 'date', 'dates_covered', '');
    setupRepeatableList('travelWithList', 'travelAddPassenger', 'text', 'travel_with', 'Passenger name');
    setupDocPanel(document.getElementById('jobOrderTab'), 'date_filed', 'jobOrderForm');
    setupDocPanel(document.getElementById('travelOrderTab'), 'to_travel_date', 'travelOrderForm');

    const obName = document.getElementById('ob_name');
    const obDesignation = document.getElementById('ob_designation');
    if (obName && obDesignation) {
      const syncObDesignation = () => {
        const option = obName.options[obName.selectedIndex];
        obDesignation.value = option ? (option.dataset.designation || '') : '';
        const panel = obName.closest('.tab-panel');
        if (panel) syncFieldPreview(panel, obDesignation);
      };
      obName.addEventListener('change', syncObDesignation);
      syncObDesignation();
    }

    const today = localTodayISO();
    setDefaultDate(document.getElementById('report_date'), today);
    setDefaultDate(document.getElementById('date_borrowed'), today);
    setDefaultDate(document.getElementById('ob_application_date'), today);
    setDefaultDate(document.getElementById('date_filed'), today);
    setDefaultDate(document.getElementById('to_travel_date'), today);
    setDefaultDate(document.getElementById('dr_receipt_date'), today);
    setDefaultDate(document.getElementById('ws_slip_date'), today);

    const jobOrderNumber = document.getElementById('job_order_number');
    if (jobOrderNumber && jobOrderNumber.value) {
      jobOrderNumber.setAttribute('data-auto-number', jobOrderNumber.value);
      const panel = jobOrderNumber.closest('.tab-panel');
      if (panel) syncFieldPreview(panel, jobOrderNumber);
    }

    // After Clear/reset, restore today's date, auto numbers, and refresh the preview.
    document.querySelectorAll('.tab-panel form').forEach((form) => {
      form.addEventListener('reset', () => {
        requestAnimationFrame(() => {
          const panel = form.closest('.tab-panel');
          form.querySelectorAll('input[type="date"]').forEach((input) => {
            if (!input.value) input.value = localTodayISO();
          });
          form.querySelectorAll('input[data-auto-number]').forEach((input) => {
            input.value = input.getAttribute('data-auto-number') || '';
          });
          syncPanelPreviews(panel);
          if (panel?.id === 'borrowMaterialTab' && typeof updateBorrowLinesPreview === 'function') {
            updateBorrowLinesPreview();
          }
          if (panel?.id === 'withdrawalSlipTab') {
            const wsTbody = panel.querySelector('[data-preview="ws_lines"]');
            if (wsTbody) {
              wsTbody.innerHTML = '<tr class="empty-row"><td colspan="3">No items added yet.</td></tr>';
            }
          }
        });
      });
    });

    syncAllFormPreviews();

    (function setupDeliveryReceiptTab() {
      const panel = document.getElementById('deliveryReceiptTab');
      if (!panel) return;

      function escapeHtml(value) {
        return String(value ?? '')
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;');
      }

      function formatCurrency(value) {
        return `₱${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      }

      function syncDrFieldPreview(field) {
        if (!field?.name) return;
        panel.querySelectorAll(`[data-preview="${field.name}"]`).forEach((target) => {
          if (field.tagName === 'SELECT') {
            target.textContent = field.options[field.selectedIndex].text;
            return;
          }
          let displayValue = field.value || '—';
          if (field.type === 'date' && field.value) {
            const parsed = new Date(`${field.value}T00:00:00`);
            if (!Number.isNaN(parsed.getTime())) {
              displayValue = parsed.toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
              });
            }
          }
          target.textContent = displayValue;
        });
      }

      function syncDrPanelPreviews() {
        panel.querySelectorAll('input, textarea, select').forEach(syncDrFieldPreview);
      }

      function updateDeliveryReceiptLinesPreview() {
        const tbody = panel.querySelector('[data-preview="dr_lines"]');
        const totalCell = panel.querySelector('[data-preview="dr_total"]');
        if (!tbody) return;

        const rows = [...panel.querySelectorAll('.dr-line-row')];
        const lines = rows.map((row) => {
          const description = row.querySelector('[data-dr-description]')?.value.trim() || '';
          const quantity = parseFloat(row.querySelector('[data-dr-quantity]')?.value) || 0;
          const unit = row.querySelector('[data-dr-unit]')?.value.trim() || 'pcs';
          const unitPrice = parseFloat(row.querySelector('[data-dr-unit-price]')?.value) || 0;
          const amount = quantity * unitPrice;
          return { description, quantity, unit, unitPrice, amount };
        }).filter((line) => line.description || line.quantity || line.unitPrice);

        if (!lines.length) {
          tbody.innerHTML = '<tr class="empty-row"><td colspan="5">No articles added yet.</td></tr>';
          if (totalCell) totalCell.textContent = formatCurrency(0);
          return;
        }

        tbody.innerHTML = lines.map((line) => `
          <tr>
            <td>${escapeHtml(line.quantity)}</td>
            <td>${escapeHtml(line.unit)}</td>
            <td>${escapeHtml(line.description || '—')}</td>
            <td>${formatCurrency(line.unitPrice)}</td>
            <td>${formatCurrency(line.amount)}</td>
          </tr>
        `).join('');

        const total = lines.reduce((sum, line) => sum + (line.quantity * line.unitPrice), 0);
        if (totalCell) totalCell.textContent = formatCurrency(total);
      }

      const list = document.getElementById('drLinesList');
      const addBtn = document.getElementById('drAddLine');
      const inventoryTemplate = list?.querySelector('[data-dr-inventory]')?.innerHTML || '';

      function refreshRemoveButtons() {
        if (!list) return;
        const rows = list.querySelectorAll('.dr-line-row');
        rows.forEach((row) => {
          const removeBtn = row.querySelector('[data-remove-row]');
          if (removeBtn) removeBtn.hidden = rows.length === 1;
          const description = row.querySelector('[data-dr-description]');
          if (description) description.required = rows.length >= 1 && row === rows[0];
        });
      }

      function bindInventorySelect(select) {
        if (!select) return;
        select.addEventListener('change', () => {
          const option = select.options[select.selectedIndex];
          const row = select.closest('.dr-line-row');
          const description = row?.querySelector('[data-dr-description]');
          const unitPrice = row?.querySelector('[data-dr-unit-price]');
          if (description && option?.dataset.name) description.value = option.dataset.name;
          if (unitPrice && option?.dataset.price) unitPrice.value = option.dataset.price;
          updateDeliveryReceiptLinesPreview();
        });
      }

      function bindRow(row) {
        row.querySelectorAll('input, select').forEach((field) => {
          field.addEventListener('input', () => {
            syncDrFieldPreview(field);
            updateDeliveryReceiptLinesPreview();
          });
          field.addEventListener('change', () => {
            syncDrFieldPreview(field);
            updateDeliveryReceiptLinesPreview();
          });
        });
        bindInventorySelect(row.querySelector('[data-dr-inventory]'));
        const removeBtn = row.querySelector('[data-remove-row]');
        if (removeBtn) {
          removeBtn.addEventListener('click', () => {
            if (!list || list.querySelectorAll('.dr-line-row').length === 1) return;
            row.remove();
            refreshRemoveButtons();
            updateDeliveryReceiptLinesPreview();
          });
        }
      }

      if (list && addBtn) {
        addBtn.addEventListener('click', () => {
          const row = document.createElement('div');
          row.className = 'repeatable-row dr-line-row';
          row.innerHTML = `
            <select name="dr_item_inventory" data-dr-inventory aria-label="Inventory item">${inventoryTemplate}</select>
            <input type="number" name="dr_item_quantity" value="1" min="0" step="0.01" data-dr-quantity aria-label="Quantity">
            <input type="text" name="dr_item_unit" value="pcs" placeholder="Unit" data-dr-unit aria-label="Unit">
            <input type="text" name="dr_item_description" placeholder="Item / article description" data-dr-description>
            <input type="number" name="dr_item_unit_price" value="0" min="0" step="0.01" data-dr-unit-price aria-label="Unit amount">
            <button type="button" class="action row-remove" data-remove-row aria-label="Remove item">✕</button>
          `;
          list.appendChild(row);
          bindRow(row);
          refreshRemoveButtons();
          row.querySelector('[data-dr-description]')?.focus();
          updateDeliveryReceiptLinesPreview();
        });
        list.querySelectorAll('.dr-line-row').forEach(bindRow);
        refreshRemoveButtons();
      }

      panel.querySelectorAll('input, textarea, select').forEach((field) => {
        field.addEventListener('input', () => syncDrFieldPreview(field));
        field.addEventListener('change', () => syncDrFieldPreview(field));
      });

      const form = document.getElementById('deliveryReceiptForm');
      if (form) {
        form.addEventListener('reset', () => {
          requestAnimationFrame(() => {
            form.querySelectorAll('input[type="date"]').forEach((input) => {
              if (!input.value) input.value = localTodayISO();
            });
            form.querySelectorAll('input[data-auto-number]').forEach((input) => {
              input.value = input.getAttribute('data-auto-number') || '';
            });
            syncDrPanelPreviews();
            updateDeliveryReceiptLinesPreview();
          });
        });
      }

      syncDrPanelPreviews();
      updateDeliveryReceiptLinesPreview();
    })();

    (function setupWithdrawalSlipTab() {
      const panel = document.getElementById('withdrawalSlipTab');
      if (!panel) return;

      function escapeHtml(value) {
        return String(value ?? '')
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;');
      }

      function syncWsFieldPreview(field) {
        if (!field?.name) return;
        panel.querySelectorAll(`[data-preview="${field.name}"]`).forEach((target) => {
          if (field.tagName === 'SELECT') {
            target.textContent = field.options[field.selectedIndex].text;
            return;
          }
          let displayValue = field.value || '—';
          if (field.type === 'date' && field.value) {
            const parsed = new Date(`${field.value}T00:00:00`);
            if (!Number.isNaN(parsed.getTime())) {
              displayValue = parsed.toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
              });
            }
          }
          target.textContent = displayValue;
        });
      }

      function syncWsPanelPreviews() {
        panel.querySelectorAll('input, textarea, select').forEach(syncWsFieldPreview);
      }

      function updateWithdrawalSlipLinesPreview() {
        const tbody = panel.querySelector('[data-preview="ws_lines"]');
        if (!tbody) return;

        const rows = [...panel.querySelectorAll('.ws-line-row')];
        const lines = rows.map((row) => {
          const description = row.querySelector('[data-ws-description]')?.value.trim() || '';
          const quantity = row.querySelector('[data-ws-quantity]')?.value.trim() || '';
          const unit = row.querySelector('[data-ws-unit]')?.value.trim() || 'pcs';
          return { description, quantity, unit };
        }).filter((line) => line.description || line.quantity);

        if (!lines.length) {
          tbody.innerHTML = '<tr class="empty-row"><td colspan="3">No items added yet.</td></tr>';
          return;
        }

        tbody.innerHTML = lines.map((line) => `
          <tr>
            <td>${escapeHtml(line.quantity || '—')}</td>
            <td>${escapeHtml(line.unit)}</td>
            <td>${escapeHtml(line.description || '—')}</td>
          </tr>
        `).join('');
      }

      const list = document.getElementById('wsLinesList');
      const addBtn = document.getElementById('wsAddLine');
      const inventoryTemplate = list?.querySelector('[data-ws-inventory]')?.innerHTML || '';

      function refreshRemoveButtons() {
        if (!list) return;
        const rows = list.querySelectorAll('.ws-line-row');
        rows.forEach((row) => {
          const removeBtn = row.querySelector('[data-remove-row]');
          if (removeBtn) removeBtn.hidden = rows.length === 1;
          const description = row.querySelector('[data-ws-description]');
          if (description) description.required = rows.length >= 1 && row === rows[0];
        });
      }

      function bindInventorySelect(select) {
        if (!select) return;
        select.addEventListener('change', () => {
          const option = select.options[select.selectedIndex];
          const row = select.closest('.ws-line-row');
          const description = row?.querySelector('[data-ws-description]');
          if (description && option?.dataset.name) description.value = option.dataset.name;
          updateWithdrawalSlipLinesPreview();
        });
      }

      function bindRow(row) {
        row.querySelectorAll('input, select').forEach((field) => {
          field.addEventListener('input', () => {
            syncWsFieldPreview(field);
            updateWithdrawalSlipLinesPreview();
          });
          field.addEventListener('change', () => {
            syncWsFieldPreview(field);
            updateWithdrawalSlipLinesPreview();
          });
        });
        bindInventorySelect(row.querySelector('[data-ws-inventory]'));
        const removeBtn = row.querySelector('[data-remove-row]');
        if (removeBtn) {
          removeBtn.addEventListener('click', () => {
            if (!list || list.querySelectorAll('.ws-line-row').length === 1) return;
            row.remove();
            refreshRemoveButtons();
            updateWithdrawalSlipLinesPreview();
          });
        }
      }

      if (list && addBtn) {
        addBtn.addEventListener('click', () => {
          const row = document.createElement('div');
          row.className = 'repeatable-row ws-line-row';
          row.innerHTML = `
            <select name="ws_item_inventory" data-ws-inventory aria-label="Inventory item">${inventoryTemplate}</select>
            <input type="number" name="ws_item_quantity" value="1" min="0" step="0.01" data-ws-quantity aria-label="Quantity">
            <input type="text" name="ws_item_unit" value="pcs" placeholder="Unit" data-ws-unit aria-label="Unit">
            <input type="text" name="ws_item_description" placeholder="Item description" data-ws-description>
            <button type="button" class="action row-remove" data-remove-row aria-label="Remove item">✕</button>
          `;
          list.appendChild(row);
          bindRow(row);
          refreshRemoveButtons();
          row.querySelector('[data-ws-description]')?.focus();
          updateWithdrawalSlipLinesPreview();
        });
        list.querySelectorAll('.ws-line-row').forEach(bindRow);
        refreshRemoveButtons();
      }

      panel.querySelectorAll('input, textarea, select').forEach((field) => {
        field.addEventListener('input', () => syncWsFieldPreview(field));
        field.addEventListener('change', () => syncWsFieldPreview(field));
      });

      const form = document.getElementById('withdrawalSlipForm');
      if (form) {
        form.addEventListener('reset', () => {
          requestAnimationFrame(() => {
            form.querySelectorAll('input[type="date"]').forEach((input) => {
              if (!input.value) input.value = localTodayISO();
            });
            form.querySelectorAll('input[data-auto-number]').forEach((input) => {
              input.value = input.getAttribute('data-auto-number') || '';
            });
            syncWsPanelPreviews();
            updateWithdrawalSlipLinesPreview();
          });
        });
      }

      syncWsPanelPreviews();
      updateWithdrawalSlipLinesPreview();
    })();
  })();
