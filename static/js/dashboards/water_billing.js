(function () {
  let paymentChromeBound = false;
  let readingChromeBound = false;
  let serviceChromeBound = false;
  let contractChromeBound = false;
  const BATCH_PRINT_MAX = 6;
  const INSTALLATION_FEE = 5900;
  const INSTALLATION_PARTIAL = 3000;
  const RATE_PER_CUM = 20;
  const MIN_CHARGE = 100;
  const MIN_CHARGE_MAX_CUM = 5;
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
    helpTab: document.getElementById('helpTab'),
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
    }
    if (tabId !== 'overviewTab' && tabId !== 'paymentsTab') {
      url.searchParams.delete('revenue_period');
    }
    if (tabId !== 'readingsBillingTab') {
      url.searchParams.delete('reading_zone');
    }
    if (tabId !== 'reportsTab') url.searchParams.delete('report');
    if (extra && extra.page != null) url.searchParams.set('page', String(extra.page));
    else if (!extra || extra.keepPage !== true) url.searchParams.delete('page');
    if (extra) {
      ['customer_q', 'customer_zone', 'customer_status', 'report', 'revenue_period', 'reading_zone'].forEach((key) => {
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
        const readingZone = loc.searchParams.get('reading_zone');
        if (readingZone && tabId === 'readingsBillingTab') url.searchParams.set('reading_zone', readingZone);
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
          updateTabUrl('customersTab', { ...params, page: page || 1 });
        })
        .catch(() => {
          const next = document.getElementById('customerListWrap');
          if (next) next.setAttribute('aria-busy', 'false');
        });
    }
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

  function updateReadingTotals() {
    const prev = Number(previousReading?.value || 0);
    const curr = Number(currentReading?.value || 0);
      const consumption = curr - prev;
    const currentBill = (consumption >= 1 && consumption <= MIN_CHARGE_MAX_CUM)
      ? MIN_CHARGE
      : consumption * RATE_PER_CUM;
    const unpaid = Number(previousBillUnpaid?.value || 0);
    const installment = Number(installmentBalance?.value || 0);
    const total = currentBill + unpaid + installment;
    if (readingConsumption) readingConsumption.value = String(consumption);
    if (readingCurrentBill) readingCurrentBill.value = currentBill.toFixed(2);
    if (readingTotalBill) readingTotalBill.value = total.toFixed(2);
    const stripConsumption = document.getElementById('stripConsumption');
    const stripCurrent = document.getElementById('stripCurrent');
      const stripUnpaid = document.getElementById('stripUnpaid');
      const stripInstallment = document.getElementById('stripInstallment');
    const stripTotal = document.getElementById('stripTotal');
    if (stripConsumption) stripConsumption.textContent = `${consumption} cu.m`;
    if (stripCurrent) stripCurrent.textContent = `₱${currentBill.toFixed(2)}`;
      if (stripUnpaid) stripUnpaid.textContent = `₱${unpaid.toFixed(2)}`;
      if (stripInstallment) stripInstallment.textContent = `₱${installment.toFixed(2)}`;
    if (stripTotal) stripTotal.textContent = `₱${total.toFixed(2)}`;
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
        updateReadingTotals();
        return;
      }
      if (previousReading) previousReading.value = item.dataset.last ?? '0';
      if (previousBillUnpaid) previousBillUnpaid.value = Number(item.dataset.unpaid || 0).toFixed(2);
      if (installmentBalance) installmentBalance.value = Number(item.dataset.installment || 0).toFixed(2);
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
  [previousReading, currentReading, installmentBalance].forEach((el) => {
    if (el) el.addEventListener('input', updateReadingTotals);
  });
  updateReadingTotals();

    const readingZoneFilter = document.getElementById('readingZoneFilter');
    const readingFilterForm = document.getElementById('readingFilterForm');
    function fetchReadingList(page) {
      const wrap = document.getElementById('readingListWrap');
      if (!wrap) return;
      const reading_zone = readingZoneFilter?.value || '';
      const url = new URL(fragmentBase, window.location.origin);
      url.searchParams.set('tab', 'readingsBillingTab');
      url.searchParams.set('fragment', '1');
      url.searchParams.set('list_only', '1');
      url.searchParams.set('page', String(page || 1));
      if (reading_zone) url.searchParams.set('reading_zone', reading_zone);
      wrap.setAttribute('aria-busy', 'true');
      fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then((res) => {
          if (!res.ok) throw new Error('bad status');
          return res.text();
        })
        .then((html) => {
          wrap.outerHTML = html;
          updateTabUrl('readingsBillingTab', { reading_zone, page: page || 1 });
          refreshBatchPrintBars(false);
        })
        .catch(() => {
          const next = document.getElementById('readingListWrap');
          if (next) next.setAttribute('aria-busy', 'false');
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
    const paymentAmount = document.getElementById('paymentAmount');
    const payBalanceDisplay = document.getElementById('payBalanceDisplay');
    const payAmountDisplay = document.getElementById('payAmountDisplay');
    const payRemainingDisplay = document.getElementById('payRemainingDisplay');
    function formatPeso(value) {
      const num = Number(value || 0);
      return `₱${num.toFixed(2)}`;
    }
    function selectedBillBalance() {
      return Number(paymentBill?.dataset?.balance || 0);
    }
    function syncPaymentSummary() {
      const balance = selectedBillBalance();
      const amount = Number(paymentAmount?.value || 0);
      if (payBalanceDisplay) payBalanceDisplay.textContent = formatPeso(balance);
      if (payAmountDisplay) payAmountDisplay.textContent = formatPeso(amount);
      if (payRemainingDisplay) payRemainingDisplay.textContent = formatPeso(Math.max(balance - amount, 0));
    }
    function setPaymentBill(item) {
      if (!paymentBill || !paymentBillSearch) return;
      if (!item) {
        paymentBill.value = '';
        paymentBill.dataset.balance = '';
        paymentBillSearch.setCustomValidity('Please select a bill from the list.');
        syncPaymentSummary();
        return;
      }
      paymentBill.value = item.dataset.id || '';
      paymentBill.dataset.balance = item.dataset.balance || '0';
      paymentBillSearch.value = item.dataset.label || item.textContent.trim();
      paymentBillSearch.setCustomValidity('');
      if (paymentAmount && item.dataset.balance) paymentAmount.value = item.dataset.balance;
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
    function positionPaymentBillList() {
      if (!paymentBillList || !paymentBillSearch) return;
      const rect = paymentBillSearch.getBoundingClientRect();
      paymentBillList.style.left = `${rect.left}px`;
      paymentBillList.style.top = `${rect.bottom + 4}px`;
      paymentBillList.style.width = `${Math.max(rect.width, 280)}px`;
    }
    function openPaymentBillList() {
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
    if (paymentBillSearch && paymentBillList && paymentBill) {
      paymentBillSearch.setCustomValidity('Please select a bill from the list.');
      paymentBillSearch.addEventListener('focus', openPaymentBillList);
      paymentBillSearch.addEventListener('input', () => {
        paymentBill.value = '';
        paymentBill.dataset.balance = '';
        paymentBillSearch.setCustomValidity('Please select a bill from the list.');
        if (paymentAmount) paymentAmount.value = '';
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
      if (!paymentChromeBound) {
        paymentChromeBound = true;
        document.addEventListener('click', (event) => {
          const list = document.getElementById('paymentBillList');
          const combo = document.getElementById('paymentBillCombo');
          if (!list || !list.classList.contains('is-open')) return;
          const inCombo = combo?.contains(event.target);
          const inList = list.contains(event.target);
          if (!inCombo && !inList) {
            list.classList.remove('is-open');
            if (combo && list.parentElement !== combo) combo.appendChild(list);
          }
        });
        window.addEventListener('resize', () => {
          const list = document.getElementById('paymentBillList');
          const search = document.getElementById('paymentBillSearch');
          if (!list || !search || !list.classList.contains('is-open')) return;
          const rect = search.getBoundingClientRect();
          list.style.left = `${rect.left}px`;
          list.style.top = `${rect.bottom + 4}px`;
          list.style.width = `${Math.max(rect.width, 280)}px`;
        });
        window.addEventListener('scroll', () => {
          const list = document.getElementById('paymentBillList');
          const search = document.getElementById('paymentBillSearch');
          if (!list || !search || !list.classList.contains('is-open')) return;
          const rect = search.getBoundingClientRect();
          list.style.left = `${rect.left}px`;
          list.style.top = `${rect.bottom + 4}px`;
          list.style.width = `${Math.max(rect.width, 280)}px`;
        }, true);
      }
      paymentBillSearch.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closePaymentBillList();
      });
      if (paymentAmount) paymentAmount.addEventListener('input', syncPaymentSummary);
      syncPaymentSummary();
    } else if (paymentBill && paymentAmount) {
      paymentBill.addEventListener('change', () => {
        const opt = paymentBill.selectedOptions[0];
        if (opt?.dataset?.balance) paymentAmount.value = opt.dataset.balance;
        syncPaymentSummary();
      });
      paymentAmount.addEventListener('input', syncPaymentSummary);
      syncPaymentSummary();
    }
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
    form?.addEventListener('submit', (event) => {
      event.preventDefault();
      const panel = panels.reportsTab;
      if (!panel) return;
      const url = new URL(fragmentBase, window.location.origin);
      url.searchParams.set('tab', 'reportsTab');
      url.searchParams.set('fragment', '1');
      const report = form.querySelector('[name="report"]')?.value || 'billing';
      url.searchParams.set('report', report);
      url.searchParams.set('page', '1');
      loadTabFragment('reportsTab', panel, url);
      updateTabUrl('reportsTab', { report, page: 1 });
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
            reading_zone: url.searchParams.get('reading_zone') || '',
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
    loadTabFragment(tabId, panel, url);
    updateTabUrl(tabId, {
      page: url.searchParams.get('page') || '1',
      keepPage: true,
      report: url.searchParams.get('report') || undefined,
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
