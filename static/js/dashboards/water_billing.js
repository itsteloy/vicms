(function () {
  let paymentChromeBound = false;
  let readingChromeBound = false;
  let serviceChromeBound = false;
  let contractChromeBound = false;
  const BATCH_PRINT_MAX = 6;
  const INSTALLATION_FEE = 5900;
  const INSTALLATION_PARTIAL = 3000;
  const DEFAULT_RATE_PER_CUM = 20;
  const MIN_CHARGE = 100;
  const MIN_CHARGE_MAX_CUM = 5;
  let activeReadingRate = DEFAULT_RATE_PER_CUM;
  let activeEditReadingRate = DEFAULT_RATE_PER_CUM;
  function fmtMoney(value) {
    return Number(value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function fmtPeso(value) {
    return '\u20b1' + fmtMoney(value);
  }
  const batchPrintUrl = (window.__WATER_CONFIG__ && window.__WATER_CONFIG__.batchPrintUrl) || '';
  const pageRoot = document.querySelector('.water-billing-page');
  const fragmentBase = (pageRoot && pageRoot.dataset.fragmentUrl) || window.location.pathname;

  const panels = {
    overviewTab: document.getElementById('overviewTab'),
    customersTab: document.getElementById('customersTab'),
    readingsBillingTab: document.getElementById('readingsBillingTab'),
    paymentsTab: document.getElementById('paymentsTab'),
    arTab: document.getElementById('arTab'),
    disconnectTab: document.getElementById('disconnectTab'),
    reportsTab: document.getElementById('reportsTab'),
    auditTab: document.getElementById('auditTab'),
  };
  const buttons = Array.from(document.querySelectorAll('.tab-button[data-tab-target]'));

  function localTodayISO() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }
  function readingDateISO() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    return `${y}-${m}-28`;
  }
  function periodFromDate(value) {
    if (!value || value.length < 7) return '';
    return value.slice(0, 7);
  }
  function normalizeTab(tabId) {
    if (tabId === 'readingsTab' || tabId === 'billingTab') return 'readingsBillingTab';
    return panels[tabId] ? tabId : 'overviewTab';
  }
  function setDateIfEmpty(id, value) {
    const el = document.getElementById(id);
    if (el && !el.value) el.value = value;
  }

  function updateTabUrl(tabId, extra) {
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tabId);
    url.searchParams.delete('fragment');
    url.searchParams.delete('list_only');
    if (tabId !== 'customersTab') {
      url.searchParams.delete('customer_q');
      url.searchParams.delete('customer_zone');
      url.searchParams.delete('customer_type');
      url.searchParams.delete('customer_status');
      url.searchParams.delete('customer_view');
    }
    if (tabId !== 'overviewTab' && tabId !== 'paymentsTab') {
      url.searchParams.delete('revenue_period');
    }
    if (tabId !== 'paymentsTab') {
      url.searchParams.delete('payment_q');
      url.searchParams.delete('payment_view');
    }
    if (tabId !== 'readingsBillingTab') {
      url.searchParams.delete('reading_zone');
      url.searchParams.delete('reading_q');
      url.searchParams.delete('reading_view');
    }
    if (tabId !== 'reportsTab') {
      url.searchParams.delete('report');
      url.searchParams.delete('week_start');
      url.searchParams.delete('week_end');
    }
    if (extra && extra.page != null) url.searchParams.set('page', String(extra.page));
    else if (!extra || extra.keepPage !== true) url.searchParams.delete('page');
    if (extra) {
      ['customer_q', 'customer_zone', 'customer_status', 'customer_view', 'report', 'revenue_period', 'reading_zone', 'reading_q', 'reading_view', 'payment_q', 'payment_view', 'week_start', 'week_end'].forEach((key) => {
        if (extra[key] == null) return;
        if (extra[key] === '') url.searchParams.delete(key);
        else url.searchParams.set(key, extra[key]);
      });
    }
    window.history.replaceState({}, '', url);
  }

  function showTab(tabId) {
    Object.entries(panels).forEach(([id, el]) => {
      if (!el) return;
      el.classList.toggle('is-active', id === tabId);
    });
    buttons.forEach((btn) => {
      btn.setAttribute('aria-selected', btn.dataset.tabTarget === tabId ? 'true' : 'false');
    });
  }

  function activateTab(tabId, opts) {
    tabId = normalizeTab(tabId);
    const panel = panels[tabId];
    if (!panel) return;
    showTab(tabId);
    if (!opts || !opts.preserveSearch) updateTabUrl(tabId);
    if (syncRevenueTabIfNeeded(tabId)) return;
    if (panel.dataset.fragmentTab && panel.dataset.loaded !== '1') {
      loadTabFragment(tabId, panel);
      return;
    }
    initWaterTab(tabId);
  }

  async function loadTabFragment(tabId, panel, requestUrl) {
    panel.innerHTML = '<p class="tab-panel-loading">Loading…</p>';
    try {
      const url = requestUrl || new URL(fragmentBase, window.location.origin);
      if (!requestUrl) {
        url.searchParams.set('tab', tabId);
        url.searchParams.set('fragment', '1');
        const loc = new URL(window.location.href);
        const period = loc.searchParams.get('revenue_period');
        if (period) url.searchParams.set('revenue_period', period);
        if (tabId === 'reportsTab') {
          const report = loc.searchParams.get('report');
          const weekStart = loc.searchParams.get('week_start');
          const weekEnd = loc.searchParams.get('week_end');
          if (report) url.searchParams.set('report', report);
          if (weekStart) url.searchParams.set('week_start', weekStart);
          if (weekEnd) url.searchParams.set('week_end', weekEnd);
        }
        if (tabId === 'readingsBillingTab') {
          const readingZone = loc.searchParams.get('reading_zone');
          const readingQ = loc.searchParams.get('reading_q');
          const readingView = loc.searchParams.get('reading_view');
          if (readingZone) url.searchParams.set('reading_zone', readingZone);
          if (readingQ) url.searchParams.set('reading_q', readingQ);
          if (readingView) url.searchParams.set('reading_view', readingView);
        }
        if (tabId === 'paymentsTab') {
          const paymentQ = loc.searchParams.get('payment_q');
          const paymentView = loc.searchParams.get('payment_view');
          if (paymentQ) url.searchParams.set('payment_q', paymentQ);
          if (paymentView) url.searchParams.set('payment_view', paymentView);
        }
      } else {
        url.searchParams.set('fragment', '1');
      }
      const res = await fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      if (!res.ok) throw new Error('bad status');
      panel.dataset.inited = '';
      panel.innerHTML = await res.text();
      panel.dataset.loaded = '1';
      initWaterTab(tabId);
    } catch (err) {
      panel.dataset.loaded = '';
      panel.innerHTML = '<p class="tab-panel-error">Could not load this section. <button type="button" class="action" data-tab-retry>Retry</button></p>';
      panel.querySelector('[data-tab-retry]')?.addEventListener('click', () => {
        loadTabFragment(tabId, panel, requestUrl);
      });
    }
  }

  function currentRevenuePeriod() {
    return new URL(window.location.href).searchParams.get('revenue_period') || 'month';
  }

  function bindRevenuePeriod(tabId) {
    const panel = panels[tabId];
    if (!panel) return;
    panel.querySelectorAll('.revenue-period[data-period]').forEach((btn) => {
      if (btn.dataset.revenueBound === '1') return;
      btn.dataset.revenueBound = '1';
      btn.addEventListener('click', () => {
        const period = btn.dataset.period || 'month';
        const url = new URL(fragmentBase, window.location.origin);
        url.searchParams.set('tab', tabId);
        url.searchParams.set('fragment', '1');
        url.searchParams.set('revenue_period', period);
        loadTabFragment(tabId, panel, url);
        updateTabUrl(tabId, { revenue_period: period });
      });
    });
  }

  function syncRevenueTabIfNeeded(tabId) {
    if (tabId !== 'overviewTab' && tabId !== 'paymentsTab') return false;
    const panel = panels[tabId];
    if (!panel) return false;
    const shown = panel.querySelector('[data-revenue-period]')?.getAttribute('data-revenue-period');
    const wanted = currentRevenuePeriod();
    if (!shown || shown === wanted) return false;
    const url = new URL(fragmentBase, window.location.origin);
    url.searchParams.set('tab', tabId);
    url.searchParams.set('fragment', '1');
    url.searchParams.set('revenue_period', wanted);
    loadTabFragment(tabId, panel, url);
    return true;
  }

  function initOverviewTab() {
    bindRevenuePeriod('overviewTab');
  }

  function forceUppercase(el) {
    if (!el || el.dataset.upperBound === '1') return;
    el.dataset.upperBound = '1';
    const toUpper = () => {
      const start = el.selectionStart;
      const end = el.selectionEnd;
      const upper = el.value.toUpperCase();
      if (el.value !== upper) {
        el.value = upper;
        if (typeof start === 'number' && typeof end === 'number' && el.setSelectionRange) {
          try { el.setSelectionRange(start, end); } catch (e) {}
        }
      }
    };
    el.addEventListener('input', toUpper);
    el.addEventListener('blur', toUpper);
  }

  function initCustomersTab() {
    setDateIfEmpty('custRegDate', localTodayISO());
  forceUppercase(document.getElementById('customerFirstName'));
  forceUppercase(document.getElementById('customerLastName'));
  forceUppercase(document.getElementById('customerServiceAddress'));
  forceUppercase(document.getElementById('customerMeterNumber'));

  const installationPayment = document.getElementById('installationPayment');
  const installationPaid = document.getElementById('installationPaid');
  const installationBalance = document.getElementById('installationBalance');
    function syncInstallationBalance() {
      if (!installationPaid || !installationBalance) return;
      const paid = Math.min(Math.max(Number(installationPaid.value || 0), 0), INSTALLATION_FEE);
      installationBalance.value = Math.max(INSTALLATION_FEE - paid, 0).toFixed(2);
    }
    function normalizeInstallationPaid() {
      if (!installationPaid) return;
      const paid = Math.min(Math.max(Number(installationPaid.value || 0), 0), INSTALLATION_FEE);
      installationPaid.value = paid.toFixed(2);
      syncInstallationBalance();
    }
  function syncInstallationFee() {
    if (!installationPayment || !installationPaid || !installationBalance) return;
      const choice = installationPayment.value;
      const isCustom = choice === 'custom';
      installationPaid.readOnly = !isCustom;
      if (choice === 'full') {
        installationPaid.value = INSTALLATION_FEE.toFixed(2);
      } else if (choice === 'partial') {
        installationPaid.value = INSTALLATION_PARTIAL.toFixed(2);
      }
      syncInstallationBalance();
      if (isCustom) installationPaid.focus();
  }
  if (installationPayment) {
    installationPayment.addEventListener('change', syncInstallationFee);
    syncInstallationFee();
  }
    if (installationPaid) {
      installationPaid.addEventListener('input', syncInstallationBalance);
      installationPaid.addEventListener('change', normalizeInstallationPaid);
    }

    const zoneSelect = document.getElementById('zoneSelect');
    const zoneNewField = document.getElementById('zoneNewField');
    const zoneNewInput = document.getElementById('zoneNewInput');
    function syncZoneNewField() {
      if (!zoneSelect || !zoneNewField || !zoneNewInput) return;
      const isNew = zoneSelect.value === '__new__';
      zoneNewField.hidden = !isNew;
      zoneNewInput.required = isNew;
      if (!isNew) zoneNewInput.value = '';
    }
    if (zoneSelect) {
      zoneSelect.addEventListener('change', syncZoneNewField);
      syncZoneNewField();
    }
    forceUppercase(zoneNewInput);

    function setCustomerView(view) {
      const next = view === 'list' ? 'list' : 'register';
      const registerPanel = document.getElementById('customerRegisterPanel');
      const listPanel = document.getElementById('customerListPanel');
      document.querySelectorAll('.customer-subnav-btn').forEach((btn) => {
        const selected = btn.dataset.customerPanel === next;
        btn.setAttribute('aria-selected', selected ? 'true' : 'false');
      });
      if (registerPanel) {
        registerPanel.classList.toggle('is-active', next === 'register');
        registerPanel.hidden = next !== 'register';
      }
      if (listPanel) {
        listPanel.classList.toggle('is-active', next === 'list');
        listPanel.hidden = next !== 'list';
      }
      const params = currentCustomerParams();
      updateTabUrl('customersTab', {
        ...params,
        customer_view: next,
        keepPage: next === 'list',
      });
    }

    const customerSearch = document.getElementById('customerSearch');
    const zoneFilter = document.getElementById('customerZoneFilter');
    const statusFilter = document.getElementById('customerStatusFilter');
    const filterForm = document.getElementById('customerFilterForm');
    let searchTimer = null;
    function currentCustomerParams() {
      return {
        customer_q: customerSearch?.value.trim() || '',
        customer_zone: zoneFilter?.value || '',
        customer_status: statusFilter?.value || '',
      };
    }
    function fetchCustomerList(page) {
      const wrap = document.getElementById('customerListWrap');
      if (!wrap) return;
      const params = currentCustomerParams();
      const url = new URL(fragmentBase, window.location.origin);
      url.searchParams.set('tab', 'customersTab');
      url.searchParams.set('fragment', '1');
      url.searchParams.set('list_only', '1');
      url.searchParams.set('customer_view', 'list');
      url.searchParams.set('page', String(page || 1));
      if (params.customer_q) url.searchParams.set('customer_q', params.customer_q);
      if (params.customer_zone) url.searchParams.set('customer_zone', params.customer_zone);
      if (params.customer_status) url.searchParams.set('customer_status', params.customer_status);
      wrap.setAttribute('aria-busy', 'true');
      fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then((res) => {
          if (!res.ok) throw new Error('bad status');
          return res.text();
        })
        .then((html) => {
          wrap.outerHTML = html;
          updateTabUrl('customersTab', { ...params, customer_view: 'list', page: page || 1 });
        })
        .catch(() => {
          const next = document.getElementById('customerListWrap');
          if (next) next.setAttribute('aria-busy', 'false');
        });
    }
    document.querySelectorAll('.customer-subnav-btn').forEach((btn) => {
      btn.addEventListener('click', () => setCustomerView(btn.dataset.customerPanel));
    });
    const loc = new URL(window.location.href);
    const viewParam = loc.searchParams.get('customer_view');
    const pageParam = loc.searchParams.get('page');
    const openList = viewParam === 'list'
      || Boolean(loc.searchParams.get('customer_q'))
      || Boolean(loc.searchParams.get('customer_zone'))
      || Boolean(loc.searchParams.get('customer_status'))
      || (pageParam && pageParam !== '1');
    setCustomerView(openList ? 'list' : 'register');
    if (customerSearch) {
      customerSearch.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => fetchCustomerList(1), 300);
      });
    }
    zoneFilter?.addEventListener('change', () => fetchCustomerList(1));
    statusFilter?.addEventListener('change', () => fetchCustomerList(1));
    filterForm?.addEventListener('submit', (event) => {
      event.preventDefault();
      fetchCustomerList(1);
    });
  }

  function syncBillingPeriod(force) {
    const readingDate = document.getElementById('readingDate');
    const period = document.getElementById('billingPeriod');
    if (!readingDate || !period) return;
    if (!force && period.dataset.userSet === '1') return;
    const nextPeriod = periodFromDate(readingDate.value);
    if (nextPeriod) period.value = nextPeriod;
  }

  function initReadingsTab() {
  const readingDate = document.getElementById('readingDate');
  if (readingDate && !readingDate.value) readingDate.value = readingDateISO();
  if (readingDate) {
    readingDate.addEventListener('change', () => syncBillingPeriod(false));
    readingDate.addEventListener('input', () => syncBillingPeriod(false));
  }
  const billingPeriod = document.getElementById('billingPeriod');
  if (billingPeriod) {
    billingPeriod.addEventListener('change', () => {
      billingPeriod.dataset.userSet = billingPeriod.value ? '1' : '';
    });
  }
  syncBillingPeriod(true);

    const orphanCustomerList = document.getElementById('readingCustomerList');
    const readingsTab = document.getElementById('readingsBillingTab');
    if (orphanCustomerList && readingsTab && !readingsTab.contains(orphanCustomerList) && !orphanCustomerList.classList.contains('is-open')) {
      orphanCustomerList.remove();
    }

  const readingCustomer = document.getElementById('readingCustomer');
    const readingCustomerSearch = document.getElementById('readingCustomerSearch');
    const readingCustomerList = document.getElementById('readingCustomerList');
    const readingCustomerCombo = document.getElementById('readingCustomerCombo');
  const previousReading = document.getElementById('previousReading');
  const currentReading = document.getElementById('currentReading');
  const readingConsumption = document.getElementById('readingConsumption');
  const readingCurrentBill = document.getElementById('readingCurrentBill');
  const previousBillUnpaid = document.getElementById('previousBillUnpaid');
  const installmentBalance = document.getElementById('installmentBalance');
  const readingTotalBill = document.getElementById('readingTotalBill');
    const readingCustomerWarning = document.getElementById('readingCustomerWarning');
    const editModal = document.getElementById('editReadingModal');
    const editReadingId = document.getElementById('editReadingId');
    const editReadingCustomerId = document.getElementById('editReadingCustomerId');
    const editReadingCustomerLabel = document.getElementById('editReadingCustomerLabel');
    const editReadingDate = document.getElementById('editReadingDate');
    const editBillingPeriod = document.getElementById('editBillingPeriod');
    const editReaderName = document.getElementById('editReaderName');
    const editIsEstimated = document.getElementById('editIsEstimated');
    const editPreviousReading = document.getElementById('editPreviousReading');
    const editCurrentReading = document.getElementById('editCurrentReading');
    const editReadingConsumption = document.getElementById('editReadingConsumption');
    const editReadingRemarks = document.getElementById('editReadingRemarks');
    const editReadingCurrentBill = document.getElementById('editReadingCurrentBill');
    const editPreviousBillUnpaid = document.getElementById('editPreviousBillUnpaid');
    const editInstallmentBalance = document.getElementById('editInstallmentBalance');
    const editReadingTotalBill = document.getElementById('editReadingTotalBill');

  function updateReadingTotals() {
    const prev = Number(previousReading?.value || 0);
    const curr = Number(currentReading?.value || 0);
      const consumption = curr - prev;
    const rate = Number(activeReadingRate) || DEFAULT_RATE_PER_CUM;
    const currentBill = (consumption >= 0 && consumption <= MIN_CHARGE_MAX_CUM)
      ? MIN_CHARGE
      : consumption * rate;
    const unpaid = Number(previousBillUnpaid?.value || 0);
    const installment = Number(installmentBalance?.value || 0);
    const total = currentBill + unpaid + installment;
    if (readingConsumption) readingConsumption.value = String(consumption);
    if (readingCurrentBill) readingCurrentBill.value = fmtMoney(currentBill);
    if (readingTotalBill) readingTotalBill.value = fmtMoney(total);
    const stripConsumption = document.getElementById('stripConsumption');
    const stripCurrent = document.getElementById('stripCurrent');
      const stripUnpaid = document.getElementById('stripUnpaid');
      const stripInstallment = document.getElementById('stripInstallment');
    const stripTotal = document.getElementById('stripTotal');
    if (stripConsumption) stripConsumption.textContent = `${consumption} cu.m`;
    if (stripCurrent) stripCurrent.textContent = fmtPeso(currentBill);
      if (stripUnpaid) stripUnpaid.textContent = fmtPeso(unpaid);
      if (stripInstallment) stripInstallment.textContent = fmtPeso(installment);
    if (stripTotal) stripTotal.textContent = fmtPeso(total);
  }

    function updateEditReadingTotals() {
      const prev = Number(editPreviousReading?.value || 0);
      const curr = Number(editCurrentReading?.value || 0);
      const consumption = curr - prev;
      const rate = Number(activeEditReadingRate) || DEFAULT_RATE_PER_CUM;
      const currentBill = (consumption >= 0 && consumption <= MIN_CHARGE_MAX_CUM)
        ? MIN_CHARGE
        : consumption * rate;
      const unpaid = Number(editPreviousBillUnpaid?.value || 0);
      const installment = Number(editInstallmentBalance?.value || 0);
      const total = currentBill + unpaid + installment;
      if (editReadingConsumption) editReadingConsumption.value = String(consumption);
      if (editReadingCurrentBill) editReadingCurrentBill.value = fmtMoney(currentBill);
      if (editReadingTotalBill) editReadingTotalBill.value = fmtMoney(total);
      const stripConsumption = document.getElementById('editStripConsumption');
      const stripCurrent = document.getElementById('editStripCurrent');
      const stripUnpaid = document.getElementById('editStripUnpaid');
      const stripInstallment = document.getElementById('editStripInstallment');
      const stripTotal = document.getElementById('editStripTotal');
      if (stripConsumption) stripConsumption.textContent = `${consumption} cu.m`;
      if (stripCurrent) stripCurrent.textContent = fmtPeso(currentBill);
      if (stripUnpaid) stripUnpaid.textContent = fmtPeso(unpaid);
      if (stripInstallment) stripInstallment.textContent = fmtPeso(installment);
      if (stripTotal) stripTotal.textContent = fmtPeso(total);
    }

    function closeEditReadingModal() {
      if (!editModal) return;
      editModal.hidden = true;
      editModal.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('wb-modal-open');
    }

    function openEditReadingModal(btn) {
      if (!editModal || !btn) return;
      if (editReadingId) editReadingId.value = btn.dataset.id || '';
      if (editReadingCustomerId) editReadingCustomerId.value = btn.dataset.customerId || '';
      if (editReadingCustomerLabel) {
        editReadingCustomerLabel.textContent = btn.dataset.customerLabel || '';
      }
      if (editReadingDate) editReadingDate.value = btn.dataset.readingDate || '';
      if (editBillingPeriod) editBillingPeriod.value = btn.dataset.billingPeriod || '';
      if (editPreviousReading) editPreviousReading.value = btn.dataset.previous ?? '0';
      if (editCurrentReading) editCurrentReading.value = btn.dataset.current ?? '';
      if (editPreviousBillUnpaid) editPreviousBillUnpaid.value = Number(btn.dataset.unpaid || 0).toFixed(2);
      if (editInstallmentBalance) editInstallmentBalance.value = Number(btn.dataset.installment || 0).toFixed(2);
      activeEditReadingRate = Number(btn.dataset.rate || DEFAULT_RATE_PER_CUM) || DEFAULT_RATE_PER_CUM;
      if (editReaderName) editReaderName.value = btn.dataset.reader || 'James Pahilagao';
      if (editIsEstimated) editIsEstimated.value = btn.dataset.estimated === '1' ? '1' : '';
      if (editReadingRemarks) editReadingRemarks.value = btn.dataset.remarks || '';
      updateEditReadingTotals();
      editModal.hidden = false;
      editModal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('wb-modal-open');
      editCurrentReading?.focus();
    }

    function applyReadingCustomer(item) {
      const status = item?.dataset?.status || readingCustomer?.dataset?.status || '';
      if (readingCustomerWarning) {
        readingCustomerWarning.hidden = status !== 'disconnected';
      }
      if (!item) {
        if (previousReading) previousReading.value = '0';
        if (previousBillUnpaid) previousBillUnpaid.value = '0.00';
        if (installmentBalance) installmentBalance.value = '0.00';
        if (currentReading) currentReading.value = '';
        activeReadingRate = DEFAULT_RATE_PER_CUM;
        updateReadingTotals();
        return;
      }
      if (previousReading) previousReading.value = item.dataset.last ?? '0';
      if (previousBillUnpaid) {
        const unpaidVal = Number(item.dataset.unpaid);
        previousBillUnpaid.value = Number.isFinite(unpaidVal) ? unpaidVal.toFixed(2) : '0.00';
      }
      if (installmentBalance) installmentBalance.value = Number(item.dataset.installment || 0).toFixed(2);
      activeReadingRate = Number(item.dataset.rate || DEFAULT_RATE_PER_CUM) || DEFAULT_RATE_PER_CUM;
      if (currentReading) currentReading.value = '';
      updateReadingTotals();
    }

    function setReadingCustomer(item) {
      if (!readingCustomer || !readingCustomerSearch) return;
      if (!item) {
        readingCustomer.value = '';
        readingCustomer.dataset.status = '';
        readingCustomerSearch.setCustomValidity('Please select a customer from the list.');
        applyReadingCustomer(null);
        return;
      }
      readingCustomer.value = item.dataset.id || '';
      readingCustomer.dataset.status = item.dataset.status || '';
      readingCustomerSearch.value = item.dataset.label || item.textContent.trim();
      readingCustomerSearch.setCustomValidity('');
      applyReadingCustomer(item);
    }

    function filterReadingCustomers() {
      if (!readingCustomerList || !readingCustomerSearch) return;
      const query = readingCustomerSearch.value.trim().toLowerCase();
      let visible = 0;
      readingCustomerList.querySelectorAll('.bill-combobox-item').forEach((item) => {
        const name = (item.dataset.name || '').toLowerCase();
        const match = !query || name.includes(query);
        item.hidden = !match;
        if (match) visible += 1;
      });
      const noMatch = document.getElementById('readingCustomerNoMatch');
      if (noMatch) noMatch.hidden = visible > 0;
    }

    function positionReadingCustomerList() {
      if (!readingCustomerList || !readingCustomerSearch) return;
      const rect = readingCustomerSearch.getBoundingClientRect();
      readingCustomerList.style.left = `${rect.left}px`;
      readingCustomerList.style.top = `${rect.bottom + 4}px`;
      readingCustomerList.style.width = `${Math.max(rect.width, 280)}px`;
    }

    function openReadingCustomerList() {
      filterReadingCustomers();
      positionReadingCustomerList();
      if (readingCustomerList.parentElement !== document.body) {
        document.body.appendChild(readingCustomerList);
      }
      readingCustomerList.classList.add('is-open');
    }

    function closeReadingCustomerList() {
      readingCustomerList?.classList.remove('is-open');
      if (readingCustomerCombo && readingCustomerList && readingCustomerList.parentElement !== readingCustomerCombo) {
        readingCustomerCombo.appendChild(readingCustomerList);
      }
    }

    if (readingCustomerSearch && readingCustomerList && readingCustomer) {
      readingCustomerSearch.setCustomValidity('Please select a customer from the list.');
      readingCustomerSearch.addEventListener('focus', openReadingCustomerList);
      readingCustomerSearch.addEventListener('input', () => {
        setReadingCustomer(null);
        openReadingCustomerList();
      });
      readingCustomerList.addEventListener('mousedown', (event) => {
        const item = event.target.closest('.bill-combobox-item');
        if (!item || item.hidden) return;
        event.preventDefault();
        setReadingCustomer(item);
        closeReadingCustomerList();
      });
      if (!readingChromeBound) {
        readingChromeBound = true;
        document.addEventListener('click', (event) => {
          const list = document.getElementById('readingCustomerList');
          const combo = document.getElementById('readingCustomerCombo');
          if (!list || !list.classList.contains('is-open')) return;
          const inCombo = combo?.contains(event.target);
          const inList = list.contains(event.target);
          if (!inCombo && !inList) {
            list.classList.remove('is-open');
            if (combo && list.parentElement !== combo) combo.appendChild(list);
          }
        });
        window.addEventListener('resize', () => {
          const list = document.getElementById('readingCustomerList');
          const search = document.getElementById('readingCustomerSearch');
          if (!list || !search || !list.classList.contains('is-open')) return;
          const rect = search.getBoundingClientRect();
          list.style.left = `${rect.left}px`;
          list.style.top = `${rect.bottom + 4}px`;
          list.style.width = `${Math.max(rect.width, 280)}px`;
        });
        window.addEventListener('scroll', () => {
          const list = document.getElementById('readingCustomerList');
          const search = document.getElementById('readingCustomerSearch');
          if (!list || !search || !list.classList.contains('is-open')) return;
          const rect = search.getBoundingClientRect();
          list.style.left = `${rect.left}px`;
          list.style.top = `${rect.bottom + 4}px`;
          list.style.width = `${Math.max(rect.width, 280)}px`;
        }, true);
      }
      readingCustomerSearch.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeReadingCustomerList();
      });
      applyReadingCustomer(null);
  }
  [previousReading, currentReading, previousBillUnpaid, installmentBalance].forEach((el) => {
    if (el) el.addEventListener('input', updateReadingTotals);
  });
  updateReadingTotals();
  [editPreviousReading, editCurrentReading, editPreviousBillUnpaid, editInstallmentBalance].forEach((el) => {
    if (el) el.addEventListener('input', updateEditReadingTotals);
  });
  document.getElementById('editReadingClose')?.addEventListener('click', closeEditReadingModal);
  document.getElementById('editReadingCancel')?.addEventListener('click', closeEditReadingModal);
  editModal?.addEventListener('click', (event) => {
    if (event.target === editModal) closeEditReadingModal();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && editModal && !editModal.hidden) {
      closeEditReadingModal();
    }
  });

    const readingZoneFilter = document.getElementById('readingZoneFilter');
    const readingSearch = document.getElementById('readingSearch');
    const readingFilterForm = document.getElementById('readingFilterForm');
    let readingSearchTimer = null;
    function currentReadingParams() {
      return {
        reading_q: readingSearch?.value.trim() || '',
        reading_zone: readingZoneFilter?.value || '',
      };
    }
    function setReadingView(view) {
      const next = view === 'history' ? 'history' : 'new';
      const newPanel = document.getElementById('readingNewPanel');
      const historyPanel = document.getElementById('readingHistoryPanel');
      document.querySelectorAll('.reading-subnav-btn').forEach((btn) => {
        const selected = btn.dataset.readingPanel === next;
        btn.setAttribute('aria-selected', selected ? 'true' : 'false');
      });
      if (newPanel) {
        newPanel.classList.toggle('is-active', next === 'new');
        newPanel.hidden = next !== 'new';
      }
      if (historyPanel) {
        historyPanel.classList.toggle('is-active', next === 'history');
        historyPanel.hidden = next !== 'history';
      }
      const params = currentReadingParams();
      updateTabUrl('readingsBillingTab', {
        ...params,
        reading_view: next,
        keepPage: next === 'history',
      });
    }
    function fetchReadingList(page) {
      const wrap = document.getElementById('readingListWrap');
      if (!wrap) return;
      const params = currentReadingParams();
      const url = new URL(fragmentBase, window.location.origin);
      url.searchParams.set('tab', 'readingsBillingTab');
      url.searchParams.set('fragment', '1');
      url.searchParams.set('list_only', '1');
      url.searchParams.set('reading_view', 'history');
      url.searchParams.set('page', String(page || 1));
      if (params.reading_q) url.searchParams.set('reading_q', params.reading_q);
      if (params.reading_zone) url.searchParams.set('reading_zone', params.reading_zone);
      wrap.setAttribute('aria-busy', 'true');
      fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then((res) => {
          if (!res.ok) throw new Error('bad status');
          return res.text();
        })
        .then((html) => {
          wrap.outerHTML = html;
          updateTabUrl('readingsBillingTab', { ...params, reading_view: 'history', page: page || 1 });
          refreshBatchPrintBars(false);
        })
        .catch(() => {
          const next = document.getElementById('readingListWrap');
          if (next) next.setAttribute('aria-busy', 'false');
        });
    }
    document.querySelectorAll('.reading-subnav-btn').forEach((btn) => {
      btn.addEventListener('click', () => setReadingView(btn.dataset.readingPanel));
    });
    readingsTab?.addEventListener('click', (event) => {
      const editBtn = event.target.closest('.reading-edit-btn');
      if (!editBtn || !readingsTab.contains(editBtn)) return;
      event.preventDefault();
      openEditReadingModal(editBtn);
    });
    const readingLoc = new URL(window.location.href);
    const readingViewParam = readingLoc.searchParams.get('reading_view');
    const readingPageParam = readingLoc.searchParams.get('page');
    const openHistory = readingViewParam === 'history'
      || Boolean(readingLoc.searchParams.get('reading_q'))
      || Boolean(readingLoc.searchParams.get('reading_zone'))
      || (readingPageParam && readingPageParam !== '1');
    setReadingView(openHistory ? 'history' : 'new');
    if (readingSearch) {
      readingSearch.addEventListener('input', () => {
        clearTimeout(readingSearchTimer);
        readingSearchTimer = setTimeout(() => fetchReadingList(1), 300);
      });
    }
    readingZoneFilter?.addEventListener('change', () => fetchReadingList(1));
    readingFilterForm?.addEventListener('submit', (event) => {
      event.preventDefault();
      fetchReadingList(1);
    });
    refreshBatchPrintBars(false);
  }

  function initPaymentsTab() {
    bindRevenuePeriod('paymentsTab');
    setDateIfEmpty('paymentDate', localTodayISO());
    const orphanList = document.getElementById('paymentBillList');
    const paymentsTab = document.getElementById('paymentsTab');
    if (orphanList && paymentsTab && !paymentsTab.contains(orphanList) && !orphanList.classList.contains('is-open')) {
      orphanList.remove();
    }

    const paymentBill = document.getElementById('paymentBill');
    const paymentBillSearch = document.getElementById('paymentBillSearch');
    const paymentBillList = document.getElementById('paymentBillList');
    const paymentBillCombo = document.getElementById('paymentBillCombo');
    const paymentBillField = document.getElementById('paymentBillField');
    const paymentInstallField = document.getElementById('paymentInstallField');
    const paymentInstallCustomer = document.getElementById('paymentInstallCustomer');
    const paymentInstallSearch = document.getElementById('paymentInstallSearch');
    const paymentInstallList = document.getElementById('paymentInstallList');
    const paymentInstallCombo = document.getElementById('paymentInstallCombo');
    const paymentPurposeBill = document.getElementById('paymentPurposeBill');
    const paymentPurposeInstall = document.getElementById('paymentPurposeInstall');
    const paymentPurposeCombined = document.getElementById('paymentPurposeCombined');
    const paymentPurposeOther = document.getElementById('paymentPurposeOther');
    const payBalanceLabel = document.getElementById('payBalanceLabel');
    const paymentAmount = document.getElementById('paymentAmount');
    const paymentAmountField = document.getElementById('paymentAmountField');
    const paymentBillAmount = document.getElementById('paymentBillAmount');
    const paymentInstallAmount = document.getElementById('paymentInstallAmount');
    const paymentBillAmountField = document.getElementById('paymentBillAmountField');
    const paymentInstallAmountField = document.getElementById('paymentInstallAmountField');
    const paymentRemarks = document.getElementById('paymentRemarks');
    const paymentReceiptField = document.getElementById('paymentReceiptField');
    const paymentReceiptHint = document.getElementById('paymentReceiptHint');
    const paymentMethodField = document.getElementById('paymentMethodField');
    const paymentReferenceField = document.getElementById('paymentReferenceField');
    const paymentReceivedByField = document.getElementById('paymentReceivedByField');
    const paymentOtherReceivedFromField = document.getElementById('paymentOtherReceivedFromField');
    const paymentOtherAddressField = document.getElementById('paymentOtherAddressField');
    const paymentOtherPaymentOfField = document.getElementById('paymentOtherPaymentOfField');
    const paymentAmountReceivedStatus = document.getElementById('paymentAmountReceivedStatus');
    const paymentReceivedFrom = document.getElementById('paymentReceivedFrom');
    const paymentAddress = document.getElementById('paymentAddress');
    const paymentOf = document.getElementById('paymentOf');
    const paymentCombinedInstallWarning = document.getElementById('paymentCombinedInstallWarning');
    const paymentSummarySingle = document.getElementById('paymentSummarySingle');
    const paymentSummaryCombined = document.getElementById('paymentSummaryCombined');
    const payBalanceDisplay = document.getElementById('payBalanceDisplay');
    const payAmountDisplay = document.getElementById('payAmountDisplay');
    const payRemainingDisplay = document.getElementById('payRemainingDisplay');
    const paymentRecordForm = document.getElementById('paymentRecordForm');

    function paymentPurpose() {
      if (paymentPurposeOther?.checked) return 'other';
      if (paymentPurposeCombined?.checked) return 'combined';
      if (paymentPurposeInstall?.checked) return 'installation';
      return 'bill';
    }
    function isInstallPurpose() {
      return paymentPurpose() === 'installation';
    }
    function isCombinedPurpose() {
      return paymentPurpose() === 'combined';
    }
    function isOtherPurpose() {
      return paymentPurpose() === 'other';
    }
    function formatPeso(value) {
      return fmtPeso(value);
    }
    function selectedBalance() {
      if (isInstallPurpose()) {
        return Number(paymentInstallCustomer?.dataset?.balance || 0);
      }
      return Number(paymentBill?.dataset?.balance || 0);
    }
    function syncPaymentSummary() {
      if (isCombinedPurpose()) {
        const billBal = Number(paymentBill?.dataset?.balance || 0);
        const installBal = Number(paymentInstallCustomer?.dataset?.balance || 0);
        const billAmt = Number(paymentBillAmount?.value || 0);
        const installAmt = Number(paymentInstallAmount?.value || 0);
        const billRemaining = billBal - billAmt;
        const installRemaining = installBal - installAmt;
        const billBalEl = document.getElementById('payCombinedBillBal');
        const billAmtEl = document.getElementById('payCombinedBillAmt');
        const installBalEl = document.getElementById('payCombinedInstallBal');
        const installAmtEl = document.getElementById('payCombinedInstallAmt');
        const totalEl = document.getElementById('payCombinedTotal');
        const remainEl = document.getElementById('payCombinedRemain');
        const remainLabel = document.getElementById('payCombinedRemainLabel');
        const installRemainEl = document.getElementById('payCombinedInstallRemain');
        const installRemainLabel = document.getElementById('payCombinedInstallRemainLabel');
        if (billBalEl) billBalEl.textContent = formatPeso(billBal);
        if (billAmtEl) billAmtEl.textContent = formatPeso(billAmt);
        if (installBalEl) installBalEl.textContent = formatPeso(installBal);
        if (installAmtEl) installAmtEl.textContent = formatPeso(installAmt);
        if (totalEl) totalEl.textContent = formatPeso(billAmt + installAmt);
        if (remainEl) remainEl.textContent = formatPeso(billRemaining);
        if (remainLabel) {
          remainLabel.textContent = billRemaining < 0 ? 'Bill advance credit' : 'Bill remaining';
        }
        if (installRemainEl) installRemainEl.textContent = formatPeso(Math.max(installRemaining, 0));
        if (installRemainLabel) {
          installRemainLabel.textContent = 'Install remaining';
        }
        return;
      }
      const balance = selectedBalance();
      const amount = Number(paymentAmount?.value || 0);
      const remaining = balance - amount;
      if (payBalanceDisplay) payBalanceDisplay.textContent = formatPeso(balance);
      if (payAmountDisplay) payAmountDisplay.textContent = formatPeso(amount);
      if (payRemainingDisplay) payRemainingDisplay.textContent = formatPeso(remaining);
      const remainingLabel = document.getElementById('payRemainingLabel');
      if (remainingLabel) {
        remainingLabel.textContent = remaining < 0 ? 'Advance credit' : 'Remaining after pay';
      }
    }
    function clearPaymentBill() {
      if (paymentBill) {
        paymentBill.value = '';
        paymentBill.dataset.balance = '';
        paymentBill.dataset.customerId = '';
        paymentBill.dataset.installment = '';
      }
      if (paymentBillSearch) {
        paymentBillSearch.value = '';
        paymentBillSearch.setCustomValidity('Please select a bill from the list.');
      }
    }
    function clearPaymentInstall() {
      if (paymentInstallCustomer) {
        paymentInstallCustomer.value = '';
        paymentInstallCustomer.dataset.balance = '';
      }
      if (paymentInstallSearch) {
        paymentInstallSearch.value = '';
        if (isInstallPurpose() || isCombinedPurpose()) {
          paymentInstallSearch.setCustomValidity('Please select a customer from the list.');
        } else {
          paymentInstallSearch.setCustomValidity('');
        }
      }
    }
    function findInstallItemByCustomerId(customerId) {
      if (!paymentInstallList || !customerId) return null;
      return paymentInstallList.querySelector(`.bill-combobox-item[data-id="${customerId}"]`);
    }
    function syncCombinedInstallFromBill(item) {
      if (!isCombinedPurpose()) return;
      const warning = paymentCombinedInstallWarning;
      const customerId = item?.dataset?.customerId || '';
      const installment = Number(item?.dataset?.installment || 0);
      if (!customerId || installment <= 0) {
        clearPaymentInstall();
        if (paymentInstallAmount) paymentInstallAmount.value = '';
        if (warning) warning.hidden = false;
        if (paymentInstallSearch) {
          paymentInstallSearch.setCustomValidity(
            'Selected bill customer has no installation balance. Choose another bill or use Water bill only.'
          );
        }
        syncPaymentSummary();
        return;
      }
      if (warning) warning.hidden = true;
      const installItem = findInstallItemByCustomerId(customerId);
      if (installItem) {
        setPaymentInstallCustomer(installItem, { fromCombined: true });
      } else {
        // Customer has installment on the bill row but may not be in the install list cache.
        if (paymentInstallCustomer) {
          paymentInstallCustomer.value = customerId;
          paymentInstallCustomer.dataset.balance = String(installment);
        }
        if (paymentInstallSearch) {
          paymentInstallSearch.value = `${item.dataset.label || ''} · installment ` + fmtPeso(installment);
          paymentInstallSearch.setCustomValidity('');
        }
      }
      syncPaymentSummary();
    }
    function syncPaymentPurpose() {
      const purpose = paymentPurpose();
      const install = purpose === 'installation';
      const combined = purpose === 'combined';
      const other = purpose === 'other';
      const showBill = !install && !other;
      const showInstall = install || combined;

      if (paymentReceiptField) paymentReceiptField.hidden = other;
      if (paymentMethodField) paymentMethodField.hidden = other;
      if (paymentReferenceField) paymentReferenceField.hidden = other;
      if (paymentReceivedByField) paymentReceivedByField.hidden = other;
      if (paymentOtherReceivedFromField) paymentOtherReceivedFromField.hidden = !other;
      if (paymentOtherAddressField) paymentOtherAddressField.hidden = !other;
      if (paymentOtherPaymentOfField) paymentOtherPaymentOfField.hidden = !other;
      if (paymentAmountReceivedStatus) {
        paymentAmountReceivedStatus.hidden = !other;
        paymentAmountReceivedStatus.disabled = !other;
        if (!other) paymentAmountReceivedStatus.value = 'not_received';
      }

      if (paymentBillField) paymentBillField.hidden = !showBill;
      if (paymentInstallField) paymentInstallField.hidden = !showInstall;
      if (paymentAmountField) paymentAmountField.hidden = combined;
      if (paymentBillAmountField) paymentBillAmountField.hidden = !combined;
      if (paymentInstallAmountField) paymentInstallAmountField.hidden = !combined;
      if (paymentSummarySingle) {
        paymentSummarySingle.hidden = combined || other;
        paymentSummarySingle.setAttribute('aria-hidden', (combined || other) ? 'true' : 'false');
      }
      if (paymentSummaryCombined) {
        paymentSummaryCombined.hidden = !combined;
        paymentSummaryCombined.setAttribute('aria-hidden', combined ? 'false' : 'true');
      }
      if (paymentReceiptHint) paymentReceiptHint.hidden = !combined;
      if (paymentCombinedInstallWarning && !combined) paymentCombinedInstallWarning.hidden = true;

      if (payBalanceLabel) {
        payBalanceLabel.textContent = install ? 'Installment balance' : 'Bill balance';
      }

      if (paymentBill) paymentBill.disabled = install || other;
      if (paymentBillSearch) {
        paymentBillSearch.disabled = install || other;
        paymentBillSearch.required = showBill;
        if (install || other) paymentBillSearch.setCustomValidity('');
        else if (!paymentBill.value) {
          paymentBillSearch.setCustomValidity('Please select a bill from the list.');
        }
      }
      if (paymentAmount) {
        paymentAmount.disabled = combined;
        paymentAmount.required = !combined;
        if (combined) paymentAmount.value = '';
      }
      if (paymentBillAmount) {
        paymentBillAmount.disabled = !combined;
        paymentBillAmount.required = combined;
        if (!combined) paymentBillAmount.value = '';
      }
      if (paymentInstallAmount) {
        paymentInstallAmount.disabled = !combined;
        paymentInstallAmount.required = combined;
        if (!combined) paymentInstallAmount.value = '';
      }
      if (paymentReceivedFrom) {
        paymentReceivedFrom.disabled = !other;
        paymentReceivedFrom.required = other;
        if (!other) paymentReceivedFrom.value = '';
      }
      if (paymentAddress) {
        paymentAddress.disabled = !other;
        if (!other) paymentAddress.value = '';
      }
      if (paymentOf) {
        paymentOf.disabled = !other;
        paymentOf.required = other;
        if (!other) paymentOf.value = '';
      }

      // Installation picker: interactive only in install-only mode; locked in combined.
      if (paymentInstallCustomer) paymentInstallCustomer.disabled = !showInstall;
      if (paymentInstallSearch) {
        paymentInstallSearch.disabled = !install;
        paymentInstallSearch.readOnly = combined;
        paymentInstallSearch.required = showInstall;
        if (!showInstall) paymentInstallSearch.setCustomValidity('');
        else if (!paymentInstallCustomer.value) {
          paymentInstallSearch.setCustomValidity('Please select a customer from the list.');
        }
      }

      if (other) {
        closePaymentBillList();
        closePaymentInstallList();
        clearPaymentBill();
        clearPaymentInstall();
        if (paymentRemarks) paymentRemarks.placeholder = 'Optional';
      } else if (install) {
        closePaymentBillList();
        clearPaymentBill();
        if (paymentRemarks && !paymentRemarks.value.trim()) {
          paymentRemarks.placeholder = 'Installation fee';
        }
      } else if (combined) {
        closePaymentInstallList();
        if (paymentRemarks) paymentRemarks.placeholder = 'Optional (applies to both lines)';
        if (paymentBill?.value) {
          const selected = paymentBillList?.querySelector(`.bill-combobox-item[data-id="${paymentBill.value}"]`);
          if (selected) syncCombinedInstallFromBill(selected);
        } else {
          clearPaymentInstall();
        }
      } else {
        closePaymentInstallList();
        clearPaymentInstall();
        if (paymentRemarks) paymentRemarks.placeholder = 'Optional';
      }
      if (!combined && paymentAmount && (install || purpose === 'bill')) paymentAmount.value = '';
      syncPaymentSummary();
    }
    function setPaymentBill(item) {
      if (!paymentBill || !paymentBillSearch) return;
      if (!item) {
        clearPaymentBill();
        if (isCombinedPurpose()) {
          clearPaymentInstall();
          if (paymentBillAmount) paymentBillAmount.value = '';
          if (paymentInstallAmount) paymentInstallAmount.value = '';
          if (paymentCombinedInstallWarning) paymentCombinedInstallWarning.hidden = true;
        }
        syncPaymentSummary();
        return;
      }
      paymentBill.value = item.dataset.id || '';
      paymentBill.dataset.balance = item.dataset.balance || '0';
      paymentBill.dataset.customerId = item.dataset.customerId || '';
      paymentBill.dataset.installment = item.dataset.installment || '0';
      paymentBillSearch.value = item.dataset.label || item.textContent.trim();
      paymentBillSearch.setCustomValidity('');
      if (isCombinedPurpose()) {
        syncCombinedInstallFromBill(item);
      }
      syncPaymentSummary();
    }
    function setPaymentInstallCustomer(item, opts) {
      if (!paymentInstallCustomer || !paymentInstallSearch) return;
      const fromCombined = Boolean(opts && opts.fromCombined);
      if (!item) {
        clearPaymentInstall();
        syncPaymentSummary();
        return;
      }
      paymentInstallCustomer.value = item.dataset.id || '';
      paymentInstallCustomer.dataset.balance = item.dataset.balance || '0';
      paymentInstallSearch.value = item.dataset.label || item.textContent.trim();
      paymentInstallSearch.setCustomValidity('');
      if (!fromCombined && paymentRemarks && !paymentRemarks.value.trim()) {
        paymentRemarks.value = 'Installation fee';
      }
      syncPaymentSummary();
    }
    function filterPaymentBills() {
      if (!paymentBillList || !paymentBillSearch) return;
      const query = paymentBillSearch.value.trim().toLowerCase();
      let visible = 0;
      paymentBillList.querySelectorAll('.bill-combobox-item').forEach((item) => {
        const name = (item.dataset.name || '').toLowerCase();
        const match = !query || name.includes(query);
        item.hidden = !match;
        if (match) visible += 1;
      });
      const noMatch = document.getElementById('paymentBillNoMatch');
      if (noMatch) noMatch.hidden = visible > 0;
    }
    function filterPaymentInstallCustomers() {
      if (!paymentInstallList || !paymentInstallSearch) return;
      const query = paymentInstallSearch.value.trim().toLowerCase();
      let visible = 0;
      paymentInstallList.querySelectorAll('.bill-combobox-item').forEach((item) => {
        const name = (item.dataset.name || '').toLowerCase();
        const match = !query || name.includes(query);
        item.hidden = !match;
        if (match) visible += 1;
      });
      const noMatch = document.getElementById('paymentInstallNoMatch');
      if (noMatch) noMatch.hidden = visible > 0;
    }
    function positionPaymentBillList() {
      if (!paymentBillList || !paymentBillSearch) return;
      const rect = paymentBillSearch.getBoundingClientRect();
      paymentBillList.style.left = `${rect.left}px`;
      paymentBillList.style.top = `${rect.bottom + 4}px`;
      paymentBillList.style.width = `${Math.max(rect.width, 280)}px`;
    }
    function positionPaymentInstallList() {
      if (!paymentInstallList || !paymentInstallSearch) return;
      const rect = paymentInstallSearch.getBoundingClientRect();
      paymentInstallList.style.left = `${rect.left}px`;
      paymentInstallList.style.top = `${rect.bottom + 4}px`;
      paymentInstallList.style.width = `${Math.max(rect.width, 280)}px`;
    }
    function openPaymentBillList() {
      if (isInstallPurpose() || isOtherPurpose()) return;
      filterPaymentBills();
      positionPaymentBillList();
      if (paymentBillList.parentElement !== document.body) {
        document.body.appendChild(paymentBillList);
      }
      paymentBillList.classList.add('is-open');
    }
    function closePaymentBillList() {
      paymentBillList?.classList.remove('is-open');
      if (paymentBillCombo && paymentBillList && paymentBillList.parentElement !== paymentBillCombo) {
        paymentBillCombo.appendChild(paymentBillList);
      }
    }
    function openPaymentInstallList() {
      if (!isInstallPurpose()) return;
      filterPaymentInstallCustomers();
      positionPaymentInstallList();
      if (paymentInstallList.parentElement !== document.body) {
        document.body.appendChild(paymentInstallList);
      }
      paymentInstallList.classList.add('is-open');
    }
    function closePaymentInstallList() {
      paymentInstallList?.classList.remove('is-open');
      if (paymentInstallCombo && paymentInstallList && paymentInstallList.parentElement !== paymentInstallCombo) {
        paymentInstallCombo.appendChild(paymentInstallList);
      }
    }
    paymentPurposeBill?.addEventListener('change', syncPaymentPurpose);
    paymentPurposeInstall?.addEventListener('change', syncPaymentPurpose);
    paymentPurposeCombined?.addEventListener('change', syncPaymentPurpose);
    paymentPurposeOther?.addEventListener('change', syncPaymentPurpose);
    if (paymentBillSearch && paymentBillList && paymentBill) {
      paymentBillSearch.setCustomValidity('Please select a bill from the list.');
      paymentBillSearch.addEventListener('focus', openPaymentBillList);
      paymentBillSearch.addEventListener('input', () => {
        paymentBill.value = '';
        paymentBill.dataset.balance = '';
        paymentBill.dataset.customerId = '';
        paymentBill.dataset.installment = '';
        paymentBillSearch.setCustomValidity('Please select a bill from the list.');
        if (paymentAmount) paymentAmount.value = '';
        if (paymentBillAmount) paymentBillAmount.value = '';
        if (isCombinedPurpose()) {
          clearPaymentInstall();
          if (paymentInstallAmount) paymentInstallAmount.value = '';
          if (paymentCombinedInstallWarning) paymentCombinedInstallWarning.hidden = true;
        }
        syncPaymentSummary();
        openPaymentBillList();
      });
      paymentBillList.addEventListener('mousedown', (event) => {
        const item = event.target.closest('.bill-combobox-item');
        if (!item || item.hidden) return;
        event.preventDefault();
        setPaymentBill(item);
        closePaymentBillList();
      });
      paymentBillSearch.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closePaymentBillList();
      });
    }
    if (paymentInstallSearch && paymentInstallList && paymentInstallCustomer) {
      paymentInstallSearch.addEventListener('focus', openPaymentInstallList);
      paymentInstallSearch.addEventListener('input', () => {
        if (isCombinedPurpose()) return;
        paymentInstallCustomer.value = '';
        paymentInstallCustomer.dataset.balance = '';
        paymentInstallSearch.setCustomValidity('Please select a customer from the list.');
        if (paymentAmount) paymentAmount.value = '';
        syncPaymentSummary();
        openPaymentInstallList();
      });
      paymentInstallList.addEventListener('mousedown', (event) => {
        const item = event.target.closest('.bill-combobox-item');
        if (!item || item.hidden) return;
        event.preventDefault();
        setPaymentInstallCustomer(item);
        closePaymentInstallList();
      });
      paymentInstallSearch.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closePaymentInstallList();
      });
    }
    if (!paymentChromeBound) {
      paymentChromeBound = true;
      document.addEventListener('click', (event) => {
        const billList = document.getElementById('paymentBillList');
        const billCombo = document.getElementById('paymentBillCombo');
        if (billList?.classList.contains('is-open')) {
          const inCombo = billCombo?.contains(event.target);
          const inList = billList.contains(event.target);
          if (!inCombo && !inList) {
            billList.classList.remove('is-open');
            if (billCombo && billList.parentElement !== billCombo) billCombo.appendChild(billList);
          }
        }
        const installList = document.getElementById('paymentInstallList');
        const installCombo = document.getElementById('paymentInstallCombo');
        if (installList?.classList.contains('is-open')) {
          const inCombo = installCombo?.contains(event.target);
          const inList = installList.contains(event.target);
          if (!inCombo && !inList) {
            installList.classList.remove('is-open');
            if (installCombo && installList.parentElement !== installCombo) {
              installCombo.appendChild(installList);
            }
          }
        }
      });
      window.addEventListener('resize', () => {
        const billList = document.getElementById('paymentBillList');
        const billSearch = document.getElementById('paymentBillSearch');
        if (billList?.classList.contains('is-open') && billSearch) {
          const rect = billSearch.getBoundingClientRect();
          billList.style.left = `${rect.left}px`;
          billList.style.top = `${rect.bottom + 4}px`;
          billList.style.width = `${Math.max(rect.width, 280)}px`;
        }
        const installList = document.getElementById('paymentInstallList');
        const installSearch = document.getElementById('paymentInstallSearch');
        if (installList?.classList.contains('is-open') && installSearch) {
          const rect = installSearch.getBoundingClientRect();
          installList.style.left = `${rect.left}px`;
          installList.style.top = `${rect.bottom + 4}px`;
          installList.style.width = `${Math.max(rect.width, 280)}px`;
        }
      });
      window.addEventListener('scroll', () => {
        const billList = document.getElementById('paymentBillList');
        const billSearch = document.getElementById('paymentBillSearch');
        if (billList?.classList.contains('is-open') && billSearch) {
          const rect = billSearch.getBoundingClientRect();
          billList.style.left = `${rect.left}px`;
          billList.style.top = `${rect.bottom + 4}px`;
          billList.style.width = `${Math.max(rect.width, 280)}px`;
        }
        const installList = document.getElementById('paymentInstallList');
        const installSearch = document.getElementById('paymentInstallSearch');
        if (installList?.classList.contains('is-open') && installSearch) {
          const rect = installSearch.getBoundingClientRect();
          installList.style.left = `${rect.left}px`;
          installList.style.top = `${rect.bottom + 4}px`;
          installList.style.width = `${Math.max(rect.width, 280)}px`;
        }
      }, true);
    }
    if (paymentAmount) paymentAmount.addEventListener('input', syncPaymentSummary);
    if (paymentBillAmount) paymentBillAmount.addEventListener('input', syncPaymentSummary);
    if (paymentInstallAmount) paymentInstallAmount.addEventListener('input', syncPaymentSummary);
    paymentRecordForm?.addEventListener('submit', (event) => {
      if (!isCombinedPurpose()) return;
      const billAmt = Number(paymentBillAmount?.value || 0);
      const installAmt = Number(paymentInstallAmount?.value || 0);
      if (!paymentBill?.value) {
        event.preventDefault();
        paymentBillSearch?.setCustomValidity('Please select a bill from the list.');
        paymentBillSearch?.reportValidity();
        return;
      }
      if (!paymentInstallCustomer?.value) {
        event.preventDefault();
        paymentInstallSearch?.setCustomValidity(
          'Selected bill customer has no installation balance. Choose another bill or use Water bill only.'
        );
        paymentInstallSearch?.reportValidity();
        return;
      }
      if (!(billAmt > 0) || !(installAmt > 0)) {
        event.preventDefault();
        const target = !(billAmt > 0) ? paymentBillAmount : paymentInstallAmount;
        target?.setCustomValidity('Enter an amount greater than zero for both bill and installation.');
        target?.reportValidity();
        return;
      }
      paymentBillAmount?.setCustomValidity('');
      paymentInstallAmount?.setCustomValidity('');
      // Ensure customer_id posts even though the control is not interactively edited.
      if (paymentInstallCustomer) paymentInstallCustomer.disabled = false;
    });
    syncPaymentPurpose();
    syncPaymentSummary();

    const paymentSearch = document.getElementById('paymentSearch');
    const paymentFilterForm = document.getElementById('paymentFilterForm');
    let paymentSearchTimer = null;
    function setPaymentView(view) {
      const next = view === 'history' ? 'history' : 'record';
      const recordPanel = document.getElementById('paymentRecordPanel');
      const historyPanel = document.getElementById('paymentHistoryPanel');
      document.querySelectorAll('.payment-subnav-btn').forEach((btn) => {
        const selected = btn.dataset.paymentPanel === next;
        btn.setAttribute('aria-selected', selected ? 'true' : 'false');
      });
      if (recordPanel) {
        recordPanel.classList.toggle('is-active', next === 'record');
        recordPanel.hidden = next !== 'record';
      }
      if (historyPanel) {
        historyPanel.classList.toggle('is-active', next === 'history');
        historyPanel.hidden = next !== 'history';
      }
      const paymentQ = paymentSearch?.value.trim() || '';
      updateTabUrl('paymentsTab', {
        payment_q: paymentQ,
        payment_view: next,
        keepPage: next === 'history',
      });
    }
    function fetchPaymentList(page) {
      const wrap = document.getElementById('paymentListWrap');
      if (!wrap) return;
      const paymentQ = paymentSearch?.value.trim() || '';
      const url = new URL(fragmentBase, window.location.origin);
      url.searchParams.set('tab', 'paymentsTab');
      url.searchParams.set('fragment', '1');
      url.searchParams.set('list_only', '1');
      url.searchParams.set('payment_view', 'history');
      url.searchParams.set('page', String(page || 1));
      if (paymentQ) url.searchParams.set('payment_q', paymentQ);
      wrap.setAttribute('aria-busy', 'true');
      fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then((res) => {
          if (!res.ok) throw new Error('bad status');
          return res.text();
        })
        .then((html) => {
          wrap.outerHTML = html;
          updateTabUrl('paymentsTab', { payment_q: paymentQ, payment_view: 'history', page: page || 1 });
        })
        .catch(() => {
          const next = document.getElementById('paymentListWrap');
          if (next) next.setAttribute('aria-busy', 'false');
        });
    }
    document.querySelectorAll('.payment-subnav-btn').forEach((btn) => {
      btn.addEventListener('click', () => setPaymentView(btn.dataset.paymentPanel));
    });
    const paymentLoc = new URL(window.location.href);
    const paymentViewParam = paymentLoc.searchParams.get('payment_view');
    const paymentPageParam = paymentLoc.searchParams.get('page');
    const openHistory = paymentViewParam === 'history'
      || Boolean(paymentLoc.searchParams.get('payment_q'))
      || (paymentPageParam && paymentPageParam !== '1');
    setPaymentView(openHistory ? 'history' : 'record');
    paymentSearch?.addEventListener('input', () => {
      clearTimeout(paymentSearchTimer);
      paymentSearchTimer = setTimeout(() => fetchPaymentList(1), 300);
    });
    paymentFilterForm?.addEventListener('submit', (event) => {
      event.preventDefault();
      fetchPaymentList(1);
    });
  }

  function initServiceTab() {
    setDateIfEmpty('actionDate', localTodayISO());

    const orphanCustomerList = document.getElementById('serviceCustomerList');
    const serviceTab = document.getElementById('disconnectTab');
    if (orphanCustomerList && serviceTab && !serviceTab.contains(orphanCustomerList) && !orphanCustomerList.classList.contains('is-open')) {
      orphanCustomerList.remove();
    }

    const serviceCustomer = document.getElementById('serviceCustomer');
    const serviceCustomerSearch = document.getElementById('serviceCustomerSearch');
    const serviceCustomerList = document.getElementById('serviceCustomerList');
    const serviceCustomerCombo = document.getElementById('serviceCustomerCombo');

    function setServiceCustomer(item) {
      if (!serviceCustomer || !serviceCustomerSearch) return;
      if (!item) {
        serviceCustomer.value = '';
        serviceCustomerSearch.setCustomValidity('Please select a customer from the list.');
        return;
      }
      serviceCustomer.value = item.dataset.id || '';
      serviceCustomerSearch.value = item.dataset.label || item.textContent.trim();
      serviceCustomerSearch.setCustomValidity('');
    }

    function filterServiceCustomers() {
      if (!serviceCustomerList || !serviceCustomerSearch) return;
      const query = serviceCustomerSearch.value.trim().toLowerCase();
      let visible = 0;
      serviceCustomerList.querySelectorAll('.bill-combobox-item').forEach((item) => {
        const name = (item.dataset.name || '').toLowerCase();
        const match = !query || name.includes(query);
        item.hidden = !match;
        if (match) visible += 1;
      });
      const noMatch = document.getElementById('serviceCustomerNoMatch');
      if (noMatch) noMatch.hidden = visible > 0;
    }

    function positionServiceCustomerList() {
      if (!serviceCustomerList || !serviceCustomerSearch) return;
      const rect = serviceCustomerSearch.getBoundingClientRect();
      serviceCustomerList.style.left = `${rect.left}px`;
      serviceCustomerList.style.top = `${rect.bottom + 4}px`;
      serviceCustomerList.style.width = `${Math.max(rect.width, 280)}px`;
    }

    function openServiceCustomerList() {
      filterServiceCustomers();
      positionServiceCustomerList();
      if (serviceCustomerList.parentElement !== document.body) {
        document.body.appendChild(serviceCustomerList);
      }
      serviceCustomerList.classList.add('is-open');
    }

    function closeServiceCustomerList() {
      serviceCustomerList?.classList.remove('is-open');
      if (serviceCustomerCombo && serviceCustomerList && serviceCustomerList.parentElement !== serviceCustomerCombo) {
        serviceCustomerCombo.appendChild(serviceCustomerList);
      }
    }

    if (serviceCustomerSearch && serviceCustomerList && serviceCustomer) {
      serviceCustomerSearch.setCustomValidity('Please select a customer from the list.');
      serviceCustomerSearch.addEventListener('focus', openServiceCustomerList);
      serviceCustomerSearch.addEventListener('input', () => {
        setServiceCustomer(null);
        openServiceCustomerList();
      });
      serviceCustomerList.addEventListener('mousedown', (event) => {
        const item = event.target.closest('.bill-combobox-item');
        if (!item || item.hidden) return;
        event.preventDefault();
        setServiceCustomer(item);
        closeServiceCustomerList();
      });
      if (!serviceChromeBound) {
        serviceChromeBound = true;
        document.addEventListener('click', (event) => {
          const list = document.getElementById('serviceCustomerList');
          const combo = document.getElementById('serviceCustomerCombo');
          if (!list || !list.classList.contains('is-open')) return;
          const inCombo = combo?.contains(event.target);
          const inList = list.contains(event.target);
          if (!inCombo && !inList) {
            list.classList.remove('is-open');
            if (combo && list.parentElement !== combo) combo.appendChild(list);
          }
        });
        window.addEventListener('resize', () => {
          const list = document.getElementById('serviceCustomerList');
          const search = document.getElementById('serviceCustomerSearch');
          if (!list || !search || !list.classList.contains('is-open')) return;
          const rect = search.getBoundingClientRect();
          list.style.left = `${rect.left}px`;
          list.style.top = `${rect.bottom + 4}px`;
          list.style.width = `${Math.max(rect.width, 280)}px`;
        });
        window.addEventListener('scroll', () => {
          const list = document.getElementById('serviceCustomerList');
          const search = document.getElementById('serviceCustomerSearch');
          if (!list || !search || !list.classList.contains('is-open')) return;
          const rect = search.getBoundingClientRect();
          list.style.left = `${rect.left}px`;
          list.style.top = `${rect.bottom + 4}px`;
          list.style.width = `${Math.max(rect.width, 280)}px`;
        }, true);
      }
      serviceCustomerSearch.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeServiceCustomerList();
      });
    }

    const orphanContractList = document.getElementById('contractCustomerList');
    if (orphanContractList && serviceTab && !serviceTab.contains(orphanContractList) && !orphanContractList.classList.contains('is-open')) {
      orphanContractList.remove();
    }

    const contractForm = document.getElementById('waterContractForm');
    if (!contractForm) return;

    const contractCustomerId = document.getElementById('contractCustomerId');
    const contractCustomerSearch = document.getElementById('contractCustomerSearch');
    const contractCustomerList = document.getElementById('contractCustomerList');
    const contractCustomerCombo = document.getElementById('contractCustomerCombo');
    const contractApplicationStatus = document.getElementById('contractApplicationStatus');
    const contractTransferField = document.getElementById('contractTransferField');

    function contractAddressFrom(zone, address) {
      const z = (zone || '').trim();
      const a = (address || '').trim();
      if (!a) return z;
      if (z && !a.toLowerCase().includes(z.toLowerCase())) return `${z}, ${a}`.replace(/^,\s*/, '');
      return a;
    }

    function setContractField(id, value) {
      const el = document.getElementById(id);
      if (el) el.value = value || '';
    }

    function shouldPrefillContract() {
      if (!contractApplicationStatus) return false;
      const status = contractApplicationStatus.value;
      return status === 'reconnection' || status === 'transfer';
    }

    function prefillContractFromCustomer(item) {
      if (!item || !shouldPrefillContract()) return;
      setContractField('contractLastName', item.dataset.lastName);
      setContractField('contractFirstName', item.dataset.firstName);
      setContractField('contractZonePurok', item.dataset.zone);
      setContractField('contractConnectionLocation', item.dataset.address);
      setContractField('contractAddress', contractAddressFrom(item.dataset.zone, item.dataset.address));
      setContractField('contractContactNumber', item.dataset.contact);
      setContractField('contractMeterSize', item.dataset.meter);
      setContractField('contractAckPayee', item.dataset.displayName);
      const classification = document.getElementById('contractClassification');
      if (classification && item.dataset.classification) {
        classification.value = item.dataset.classification;
      }
    }

    function syncContractTransferField() {
      if (!contractApplicationStatus || !contractTransferField) return;
      contractTransferField.hidden = contractApplicationStatus.value !== 'transfer';
    }

    function setContractCustomer(item) {
      if (!contractCustomerId || !contractCustomerSearch) return;
      if (!item) {
        contractCustomerId.value = '';
        return;
      }
      contractCustomerId.value = item.dataset.id || '';
      contractCustomerSearch.value = item.dataset.label || item.textContent.trim();
      prefillContractFromCustomer(item);
    }

    function filterContractCustomers() {
      if (!contractCustomerList || !contractCustomerSearch) return;
      const query = contractCustomerSearch.value.trim().toLowerCase();
      let visible = 0;
      contractCustomerList.querySelectorAll('.bill-combobox-item').forEach((item) => {
        const name = (item.dataset.name || '').toLowerCase();
        const match = !query || name.includes(query);
        item.hidden = !match;
        if (match) visible += 1;
      });
      const noMatch = document.getElementById('contractCustomerNoMatch');
      if (noMatch) noMatch.hidden = visible > 0;
    }

    function positionContractCustomerList() {
      if (!contractCustomerList || !contractCustomerSearch) return;
      const rect = contractCustomerSearch.getBoundingClientRect();
      contractCustomerList.style.left = `${rect.left}px`;
      contractCustomerList.style.top = `${rect.bottom + 4}px`;
      contractCustomerList.style.width = `${Math.max(rect.width, 280)}px`;
    }

    function openContractCustomerList() {
      filterContractCustomers();
      positionContractCustomerList();
      if (contractCustomerList.parentElement !== document.body) {
        document.body.appendChild(contractCustomerList);
      }
      contractCustomerList.classList.add('is-open');
    }

    function closeContractCustomerList() {
      contractCustomerList?.classList.remove('is-open');
      if (contractCustomerCombo && contractCustomerList && contractCustomerList.parentElement !== contractCustomerCombo) {
        contractCustomerCombo.appendChild(contractCustomerList);
      }
    }

    syncContractTransferField();
    contractApplicationStatus?.addEventListener('change', () => {
      syncContractTransferField();
      if (shouldPrefillContract() && contractCustomerId?.value) {
        const selected = contractCustomerList?.querySelector(`.bill-combobox-item[data-id="${contractCustomerId.value}"]`);
        if (selected) prefillContractFromCustomer(selected);
      }
    });

    if (contractCustomerSearch && contractCustomerList && contractCustomerId) {
      contractCustomerSearch.addEventListener('focus', openContractCustomerList);
      contractCustomerSearch.addEventListener('input', () => {
        setContractCustomer(null);
        openContractCustomerList();
      });
      contractCustomerList.addEventListener('mousedown', (event) => {
        const item = event.target.closest('.bill-combobox-item');
        if (!item || item.hidden) return;
        event.preventDefault();
        setContractCustomer(item);
        closeContractCustomerList();
      });
      contractCustomerSearch.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeContractCustomerList();
      });
      if (!contractChromeBound) {
        contractChromeBound = true;
        document.addEventListener('click', (event) => {
          const list = document.getElementById('contractCustomerList');
          const combo = document.getElementById('contractCustomerCombo');
          if (!list || !list.classList.contains('is-open')) return;
          const inCombo = combo?.contains(event.target);
          const inList = list.contains(event.target);
          if (!inCombo && !inList) {
            list.classList.remove('is-open');
            if (combo && list.parentElement !== combo) combo.appendChild(list);
          }
        });
        window.addEventListener('resize', () => {
          const list = document.getElementById('contractCustomerList');
          const search = document.getElementById('contractCustomerSearch');
          if (!list || !search || !list.classList.contains('is-open')) return;
          const rect = search.getBoundingClientRect();
          list.style.left = `${rect.left}px`;
          list.style.top = `${rect.bottom + 4}px`;
          list.style.width = `${Math.max(rect.width, 280)}px`;
        });
        window.addEventListener('scroll', () => {
          const list = document.getElementById('contractCustomerList');
          const search = document.getElementById('contractCustomerSearch');
          if (!list || !search || !list.classList.contains('is-open')) return;
          const rect = search.getBoundingClientRect();
          list.style.left = `${rect.left}px`;
          list.style.top = `${rect.bottom + 4}px`;
          list.style.width = `${Math.max(rect.width, 280)}px`;
        }, true);
      }
    }
  }

  function selectedBatchIds() {
    const ids = [];
    const seen = new Set();
    document.querySelectorAll('.batch-bill-check').forEach((cb) => {
      if (!cb.checked) return;
      if (seen.has(cb.value)) return;
      seen.add(cb.value);
      ids.push(cb.value);
    });
    return ids;
  }

  function syncBatchCheckmates(changed) {
    if (!changed) return;
    document.querySelectorAll('.batch-bill-check').forEach((cb) => {
      if (cb !== changed && cb.value === changed.value) cb.checked = changed.checked;
    });
  }

  function refreshBatchPrintBars(showLimitNote) {
    const ids = selectedBatchIds();
    document.querySelectorAll('[data-batch-bar]').forEach((bar) => {
      const countEl = bar.querySelector('[data-batch-count]');
      const printBtn = bar.querySelector('[data-batch-print]');
      const note = bar.querySelector('[data-batch-note]');
      if (countEl) countEl.textContent = String(ids.length);
      if (printBtn) printBtn.disabled = ids.length === 0;
      bar.classList.toggle('is-visible', ids.length > 0);
      if (note) note.classList.toggle('is-visible', Boolean(showLimitNote));
    });
  }

  function initReportsTab() {
    const form = document.getElementById('reportFilterForm');
    const reportSelect = document.getElementById('reportTypeSelect');
    const weekStart = document.getElementById('weekStart');
    const weekEnd = document.getElementById('weekEnd');
    const rangeStart = document.getElementById('weeklyRangeFields');
    const rangeEnd = document.getElementById('weeklyRangeEndFields');
    function syncWeeklyFields() {
      const isWeekly = reportSelect?.value === 'weekly';
      if (rangeStart) rangeStart.hidden = !isWeekly;
      if (rangeEnd) rangeEnd.hidden = !isWeekly;
    }
    reportSelect?.addEventListener('change', syncWeeklyFields);
    syncWeeklyFields();
    form?.addEventListener('submit', (event) => {
      event.preventDefault();
      const panel = panels.reportsTab;
      if (!panel) return;
      const url = new URL(fragmentBase, window.location.origin);
      url.searchParams.set('tab', 'reportsTab');
      url.searchParams.set('fragment', '1');
      const report = reportSelect?.value || 'billing';
      url.searchParams.set('report', report);
      url.searchParams.set('page', '1');
      const extra = { report, page: 1 };
      if (report === 'weekly') {
        extra.week_start = weekStart?.value || '';
        extra.week_end = weekEnd?.value || '';
        if (extra.week_start) url.searchParams.set('week_start', extra.week_start);
        if (extra.week_end) url.searchParams.set('week_end', extra.week_end);
      }
      loadTabFragment('reportsTab', panel, url);
      updateTabUrl('reportsTab', extra);
    });
    initWeeklyRefillForm();
    initWeeklyOtherReceived();
    initWeeklyDenominationTables();
    updateWeeklyCashRemittance();
  }

  function parseWeeklyPesoText(text) {
    return Number(String(text || '').replace(/[₱,\s]/g, '')) || 0;
  }

  function updateWeeklyCashRemittance() {
    const block = document.getElementById('weeklyCashRemittanceBlock');
    const grossEl = document.getElementById('weeklyGrossSalesTotal');
    const gcashEl = document.getElementById('weeklyGcashCollectionTotal');
    const aidEl = document.getElementById('weeklyAidReceivedTotal');
    const parcelEl = document.getElementById('weeklyParcelPaymentTotal');
    const valueEl = document.getElementById('weeklyCashRemittanceTotal');
    if (!block || !valueEl) return;

    const gcashTotal = parseWeeklyPesoText(
      document.getElementById('weeklyCollectionGcashTotal')?.textContent
    ) || Number(block.dataset.gcashTotal || 0);
    const refillCashTotal = parseWeeklyPesoText(
      document.getElementById('weeklyRefillCashTotal')?.textContent
    ) || Number(block.dataset.refillCashTotal || 0);

    let cashTotal = 0;
    let aidReceived = 0;
    let parcelPayment = 0;

    document.querySelectorAll('#weeklyBillingBody .weekly-billing-row').forEach((row) => {
      const paymentOf = String(row.dataset.paymentOf || '').toLowerCase();
      const isParcel = paymentOf.includes('parcel');
      const otherId = row.dataset.otherId;
      if (otherId) {
        const amount = Number(row.dataset.amount || 0);
        const raw = (row.querySelector('.weekly-other-received')?.value || '').trim();
        if (raw === '') {
          cashTotal += amount;
          if (isParcel) parcelPayment += amount;
        } else {
          const received = Number(raw || 0);
          aidReceived += received;
          if (isParcel) parcelPayment += received;
        }
      } else {
        cashTotal += parseWeeklyPesoText(row.querySelector('.weekly-row-cash')?.textContent);
      }
    });

    // Include non-other cash already in footer if body empty of billing cash cells —
    // cashTotal from rows is authoritative when rows exist.
    const grossSales = cashTotal + gcashTotal + aidReceived + refillCashTotal;
    const remittance = grossSales - gcashTotal - aidReceived - parcelPayment;

    if (grossEl) grossEl.textContent = fmtPeso(grossSales);
    if (gcashEl) gcashEl.textContent = fmtPeso(gcashTotal);
    if (aidEl) aidEl.textContent = fmtPeso(aidReceived);
    if (parcelEl) parcelEl.textContent = fmtPeso(parcelPayment);
    valueEl.textContent = fmtPeso(remittance);

    const cashLine = document.getElementById('weeklyBillingCashLine');
    const aidLine = document.getElementById('weeklyBillingAidLine');
    const collectionTotal = document.getElementById('weeklyBillingCollectionTotal');
    const cashFooter = document.getElementById('weeklyCollectionCashTotal');
    const aidFooter = document.getElementById('weeklyCollectionAidTotal');
    if (cashLine) cashLine.textContent = fmtPeso(cashTotal);
    if (aidLine) aidLine.textContent = fmtPeso(aidReceived);
    if (cashFooter) cashFooter.textContent = fmtPeso(cashTotal);
    if (aidFooter) aidFooter.textContent = fmtPeso(aidReceived);
    if (collectionTotal) collectionTotal.textContent = fmtPeso((cashTotal + gcashTotal + aidReceived));
    if (block) block.dataset.cashTotal = String(cashTotal);
  }

  function initWeeklyDenominationTables() {
    const wrap = document.querySelector('.weekly-denom-grid');
    if (!wrap) return;
    function formatPeso(value) {
      return fmtPeso(Number(value || 0));
    }
    function sumTable(table, totalId) {
      if (!table) return;
      let total = 0;
      table.querySelectorAll('.weekly-denom-row').forEach((row) => {
        const money = Number(row.dataset.money || 0);
        const qtyRaw = (row.querySelector('.weekly-denom-qty')?.value || '').trim();
        const qty = qtyRaw === '' ? 0 : Number(qtyRaw);
        const lineTotal = Number.isFinite(qty) ? money * qty : 0;
        total += lineTotal;
        const cell = row.querySelector('.weekly-denom-line-total');
        if (cell) cell.textContent = qtyRaw === '' || !qty ? '' : formatPeso(lineTotal);
      });
      const totalEl = document.getElementById(totalId);
      if (totalEl) totalEl.textContent = formatPeso(total);
    }
    function refreshAll() {
      sumTable(document.getElementById('weeklyDenomBillingTable'), 'weeklyDenomBillingTotal');
    }
    wrap.addEventListener('input', (event) => {
      if (!event.target.classList.contains('weekly-denom-qty')) return;
      refreshAll();
    });
  }

  function initWeeklyOtherReceived() {
    const body = document.getElementById('weeklyBillingBody');
    if (!body) return;
    function formatPeso(value) {
      return fmtPeso(Number(value || 0));
    }
    function syncOtherRowCash(row) {
      if (!row?.dataset.otherId) return;
      const amount = Number(row.dataset.amount || 0);
      const input = row.querySelector('.weekly-other-received');
      const cashCell = row.querySelector('.weekly-row-cash');
      const raw = (input?.value || '').trim();
      if (!cashCell) return;
      if (raw === '') {
        cashCell.textContent = amount ? formatPeso(amount) : '';
      } else {
        cashCell.textContent = '';
      }
    }
    function refreshMergedOther() {
      body.querySelectorAll('.weekly-other-row').forEach(syncOtherRowCash);
      updateWeeklyCashRemittance();
    }
    body.addEventListener('input', (event) => {
      if (!event.target.classList.contains('weekly-other-received')) return;
      syncOtherRowCash(event.target.closest('.weekly-other-row'));
      updateWeeklyCashRemittance();
    });
    refreshMergedOther();
  }

  function initWeeklyRefillForm() {
    const body = document.getElementById('weeklyRefillBody');
    const countInput = document.getElementById('weeklyRefillCount');
    const addBtn = document.getElementById('addWeeklyRefillRow');
    if (!body) return;
    function reindex() {
      const rows = [...body.querySelectorAll('.weekly-refill-row')];
      rows.forEach((row, index) => {
        row.querySelectorAll('input[name^="weekly_refill-"]').forEach((input) => {
          input.name = input.name.replace(/weekly_refill-\d+-/, `weekly_refill-${index}-`);
        });
        const lineNo = row.querySelector('.weekly-line-no');
        if (lineNo) lineNo.value = String(index + 1);
      });
      if (countInput) countInput.value = String(rows.length);
      sumRefill();
    }
    function sumRefill() {
      let cash = 0;
      let amount = 0;
      let hasInputs = false;
      body.querySelectorAll('.weekly-refill-row').forEach((row) => {
        const cashEl = row.querySelector('[name$="-cash_in_bank"]');
        const amtEl = row.querySelector('.weekly-refill-amount');
        if (cashEl || amtEl) hasInputs = true;
        cash += Number(cashEl?.value || 0);
        amount += Number(amtEl?.value || 0);
      });
      if (!hasInputs) {
        cash = parseWeeklyPesoText(document.getElementById('weeklyRefillCashTotal')?.textContent);
        amount = parseWeeklyPesoText(document.getElementById('weeklyRefillAmountTotal')?.textContent);
      }
      const cashTotal = document.getElementById('weeklyRefillCashTotal');
      const amtTotal = document.getElementById('weeklyRefillAmountTotal');
      const cashLine = document.getElementById('weeklyRefillCashLine');
      const amountLine = document.getElementById('weeklyRefillAmountLine');
      const collectionTotal = document.getElementById('weeklyRefillCollectionTotal');
      const peso = (value) => fmtPeso(Number(value || 0));
      if (cashTotal) cashTotal.textContent = peso(cash);
      if (amtTotal) amtTotal.textContent = peso(amount);
      if (cashLine) cashLine.textContent = peso(cash);
      if (amountLine) amountLine.textContent = peso(amount);
      if (collectionTotal) collectionTotal.textContent = peso(cash + amount);
      updateWeeklyCashRemittance();
    }
    sumRefill();
    addBtn?.addEventListener('click', () => {
      const index = body.querySelectorAll('.weekly-refill-row').length;
      const tr = document.createElement('tr');
      tr.className = 'weekly-refill-row';
      tr.innerHTML = `
        <td><input name="weekly_refill-${index}-line_no" value="${index + 1}" class="weekly-line-no"></td>
        <td><input name="weekly_refill-${index}-line_date" placeholder="Date"></td>
        <td><input name="weekly_refill-${index}-name" placeholder="Name"></td>
        <td><input name="weekly_refill-${index}-explanation" placeholder="Explanation"></td>
        <td><input name="weekly_refill-${index}-ref_number" placeholder="Ref #"></td>
        <td class="col-cash-bank"><input name="weekly_refill-${index}-cash_in_bank" class="weekly-money" inputmode="decimal"></td>
        <td><input name="weekly_refill-${index}-amount" class="weekly-money weekly-refill-amount" inputmode="decimal"></td>
        <td class="no-print"><button type="button" class="action danger" data-remove-refill>Remove</button></td>`;
      body.appendChild(tr);
      reindex();
    });
    body.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-remove-refill]');
      if (!btn) return;
      btn.closest('.weekly-refill-row')?.remove();
      if (!body.querySelector('.weekly-refill-row')) addBtn?.click();
      reindex();
    });
    body.addEventListener('input', (event) => {
      if (event.target.classList.contains('weekly-money')) sumRefill();
    });
  }

  function initWaterTab(tabId) {
    const panel = panels[tabId];
    if (!panel || panel.dataset.inited === '1') return;
    panel.dataset.inited = '1';
    if (tabId === 'overviewTab') initOverviewTab();
    if (tabId === 'customersTab') initCustomersTab();
    if (tabId === 'readingsBillingTab') initReadingsTab();
    if (tabId === 'paymentsTab') initPaymentsTab();
    if (tabId === 'arTab') refreshBatchPrintBars(false);
    if (tabId === 'disconnectTab') initServiceTab();
    if (tabId === 'reportsTab') initReportsTab();
  }

  buttons.forEach((btn) => btn.addEventListener('click', () => activateTab(btn.dataset.tabTarget)));
  document.addEventListener('click', (event) => {
    const jump = event.target.closest('[data-jump]');
    if (jump) {
      activateTab(jump.dataset.jump);
      return;
    }
    const pager = event.target.closest('[data-pager-link]');
    if (!pager) return;
    const panel = pager.closest('.tab-panel');
    if (!panel) return;
    event.preventDefault();
    const url = new URL(pager.href, window.location.origin);
    url.searchParams.set('fragment', '1');
    const customerWrap = pager.closest('#customerListWrap');
    const readingWrap = pager.closest('#readingListWrap');
    const paymentWrap = pager.closest('#paymentListWrap');
    const tabId = panel.id;
    if (customerWrap && tabId === 'customersTab') {
      url.searchParams.set('list_only', '1');
      customerWrap.setAttribute('aria-busy', 'true');
      fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then((res) => {
          if (!res.ok) throw new Error('bad status');
          return res.text();
        })
        .then((html) => {
          customerWrap.outerHTML = html;
          const page = url.searchParams.get('page') || '1';
          updateTabUrl('customersTab', {
            customer_q: url.searchParams.get('customer_q') || '',
            customer_zone: url.searchParams.get('customer_zone') || '',
            customer_status: url.searchParams.get('customer_status') || '',
            customer_view: 'list',
            page,
          });
        })
        .catch(() => {
          const next = document.getElementById('customerListWrap');
          if (next) next.setAttribute('aria-busy', 'false');
        });
      return;
    }
    if (readingWrap && tabId === 'readingsBillingTab') {
      url.searchParams.set('list_only', '1');
      readingWrap.setAttribute('aria-busy', 'true');
      fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then((res) => {
          if (!res.ok) throw new Error('bad status');
          return res.text();
        })
        .then((html) => {
          readingWrap.outerHTML = html;
          const page = url.searchParams.get('page') || '1';
          updateTabUrl('readingsBillingTab', {
            reading_q: url.searchParams.get('reading_q') || '',
            reading_zone: url.searchParams.get('reading_zone') || '',
            reading_view: 'history',
            page,
          });
          refreshBatchPrintBars(false);
        })
        .catch(() => {
          const next = document.getElementById('readingListWrap');
          if (next) next.setAttribute('aria-busy', 'false');
        });
      return;
    }
    if (paymentWrap && tabId === 'paymentsTab') {
      url.searchParams.set('list_only', '1');
      paymentWrap.setAttribute('aria-busy', 'true');
      fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then((res) => {
          if (!res.ok) throw new Error('bad status');
          return res.text();
        })
        .then((html) => {
          paymentWrap.outerHTML = html;
          updateTabUrl('paymentsTab', {
            payment_q: url.searchParams.get('payment_q') || '',
            payment_view: 'history',
            page: url.searchParams.get('page') || '1',
          });
        })
        .catch(() => {
          const next = document.getElementById('paymentListWrap');
          if (next) next.setAttribute('aria-busy', 'false');
        });
      return;
    }
    loadTabFragment(tabId, panel, url);
    updateTabUrl(tabId, {
      page: url.searchParams.get('page') || '1',
      keepPage: true,
      report: url.searchParams.get('report') || undefined,
      week_start: url.searchParams.get('week_start') || undefined,
      week_end: url.searchParams.get('week_end') || undefined,
    });
  });

  document.addEventListener('change', (event) => {
    const cb = event.target.closest('.batch-bill-check');
    if (!cb) return;
      let showLimitNote = false;
    if (cb.checked && selectedBatchIds().length > BATCH_PRINT_MAX) {
        cb.checked = false;
        showLimitNote = true;
      }
      syncBatchCheckmates(cb);
      refreshBatchPrintBars(showLimitNote);
  });

  document.addEventListener('click', (event) => {
    const bar = event.target.closest('[data-batch-bar]');
    if (!bar) return;
    if (event.target.closest('[data-batch-clear]')) {
      document.querySelectorAll('.batch-bill-check').forEach((cb) => { cb.checked = false; });
        refreshBatchPrintBars(false);
      return;
    }
    if (event.target.closest('[data-batch-print]')) {
        const ids = selectedBatchIds().slice(0, BATCH_PRINT_MAX);
        if (!ids.length) return;
        const params = new URLSearchParams();
        ids.forEach((id) => params.append('bill_ids', id));
        window.location.href = `${batchPrintUrl}?${params.toString()}`;
    }
  });

  let initial = normalizeTab(new URLSearchParams(window.location.search).get('tab') || 'overviewTab');
  activateTab(initial, { preserveSearch: true });
})();
