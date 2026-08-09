(function () {
    const tabButtons = document.querySelectorAll('.sidebar-nav .tab-button');
    const panels = {
      repairTab: document.getElementById('repairTab'),
      borrowMaterialTab: document.getElementById('borrowMaterialTab'),
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
    const hashTab = location.hash === '#repair'
        ? 'repairTab'
        : (location.hash === '#borrow' ? 'borrowMaterialTab' : null);
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
      if (field.name === 'dates_covered') {
        updateJobRepeatablePreview(panel, 'dates_covered', 'input[name="dates_covered"]', true);
        return;
      }
      if (field.name === 'ob_dates') {
        updateJobRepeatablePreview(panel, 'ob_dates', 'input[name="ob_dates"]', true);
        return;
      }
      panel.querySelectorAll(`[data-preview="${field.name}"]`).forEach(target => {
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

    function updateJobRepeatablePreview(panel, previewKey, selector, isDate) {
      const values = [...panel.querySelectorAll(selector)]
        .map((input) => input.value.trim())
        .filter(Boolean)
        .map((value) => {
          if (!isDate) return value;
          const parsed = new Date(value + 'T00:00:00');
          return Number.isNaN(parsed.getTime())
            ? value
            : parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
        });
      const joiner = ', ';
      panel.querySelectorAll(`[data-preview="${previewKey}"]`).forEach((target) => {
        target.textContent = values.length ? values.join(joiner) : '—';
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
          <input type="${inputType}" name="${inputName}" placeholder="${placeholder || ''}">
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

    setupBorrowLines();

    const today = localTodayISO();
    setDefaultDate(document.getElementById('report_date'), today);
    setDefaultDate(document.getElementById('date_borrowed'), today);

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
        });
      });
    });

    syncAllFormPreviews();
  })();
