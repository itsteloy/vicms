(function () {
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
  function syncBillingPeriod() {
    const readingDate = document.getElementById('readingDate');
    const period = document.getElementById('billingPeriod');
    if (!readingDate || !period) return;
    const nextPeriod = periodFromDate(readingDate.value);
    if (nextPeriod) period.value = nextPeriod;
  }

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

  function activateTab(tabId) {
    if (tabId === 'readingsTab' || tabId === 'billingTab') tabId = 'readingsBillingTab';
    Object.entries(panels).forEach(([id, el]) => {
      if (!el) return;
      el.classList.toggle('is-active', id === tabId);
    });
    buttons.forEach((btn) => {
      btn.setAttribute('aria-selected', btn.dataset.tabTarget === tabId ? 'true' : 'false');
    });
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tabId);
    window.history.replaceState({}, '', url);
  }

  buttons.forEach((btn) => btn.addEventListener('click', () => activateTab(btn.dataset.tabTarget)));
  document.querySelectorAll('[data-jump]').forEach((btn) => {
    btn.addEventListener('click', () => activateTab(btn.dataset.jump));
  });

  let initial = new URLSearchParams(window.location.search).get('tab') || 'overviewTab';
  if (initial === 'readingsTab' || initial === 'billingTab') initial = 'readingsBillingTab';
  activateTab(panels[initial] ? initial : 'overviewTab');

  ['custRegDate', 'paymentDate', 'actionDate'].forEach((id) => {
    const el = document.getElementById(id);
    if (el && !el.value) el.value = localTodayISO();
  });

  function forceUppercase(el) {
    if (!el) return;
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
  forceUppercase(document.getElementById('customerFirstName'));
  forceUppercase(document.getElementById('customerLastName'));
  forceUppercase(document.getElementById('customerServiceAddress'));
  forceUppercase(document.getElementById('customerMeterNumber'));

  const INSTALLATION_FEE = 5900;
  const INSTALLATION_PARTIAL = 3000;
  const installationPayment = document.getElementById('installationPayment');
  const installationPaid = document.getElementById('installationPaid');
  const installationBalance = document.getElementById('installationBalance');
  function syncInstallationFee() {
    if (!installationPayment || !installationPaid || !installationBalance) return;
    const paid = installationPayment.value === 'full' ? INSTALLATION_FEE : INSTALLATION_PARTIAL;
    installationPaid.value = paid.toFixed(2);
    installationBalance.value = Math.max(INSTALLATION_FEE - paid, 0).toFixed(2);
  }
  if (installationPayment) {
    installationPayment.addEventListener('change', syncInstallationFee);
    syncInstallationFee();
  }
  const readingDate = document.getElementById('readingDate');
  if (readingDate && !readingDate.value) readingDate.value = readingDateISO();
  if (readingDate) {
    readingDate.addEventListener('change', syncBillingPeriod);
    readingDate.addEventListener('input', syncBillingPeriod);
  }
  syncBillingPeriod();

  const readingCustomer = document.getElementById('readingCustomer');
  const previousReading = document.getElementById('previousReading');
  const currentReading = document.getElementById('currentReading');
  const readingConsumption = document.getElementById('readingConsumption');
  const readingCurrentBill = document.getElementById('readingCurrentBill');
  const previousBillUnpaid = document.getElementById('previousBillUnpaid');
  const installmentBalance = document.getElementById('installmentBalance');
  const readingTotalBill = document.getElementById('readingTotalBill');
  const RATE_PER_CUM = 20;

  function updateReadingTotals() {
    const prev = Number(previousReading?.value || 0);
    const curr = Number(currentReading?.value || 0);
    const consumption = Math.max(curr - prev, 0);
    const currentBill = consumption * RATE_PER_CUM;
    const unpaid = Number(previousBillUnpaid?.value || 0);
    const installment = Number(installmentBalance?.value || 0);
    const total = currentBill + unpaid + installment;
    if (readingConsumption) readingConsumption.value = String(consumption);
    if (readingCurrentBill) readingCurrentBill.value = currentBill.toFixed(2);
    if (readingTotalBill) readingTotalBill.value = total.toFixed(2);
    const stripConsumption = document.getElementById('stripConsumption');
    const stripCurrent = document.getElementById('stripCurrent');
    const stripOther = document.getElementById('stripOther');
    const stripTotal = document.getElementById('stripTotal');
    if (stripConsumption) stripConsumption.textContent = `${consumption} cu.m`;
    if (stripCurrent) stripCurrent.textContent = `₱${currentBill.toFixed(2)}`;
    if (stripOther) stripOther.textContent = `₱${(unpaid + installment).toFixed(2)}`;
    if (stripTotal) stripTotal.textContent = `₱${total.toFixed(2)}`;
  }

  if (readingCustomer && previousReading) {
    const readingCustomerWarning = document.getElementById('readingCustomerWarning');
    const syncReadingCustomerWarning = () => {
      const opt = readingCustomer.selectedOptions[0];
      const status = opt?.dataset?.status || '';
      if (readingCustomerWarning) {
        readingCustomerWarning.hidden = status !== 'disconnected';
      }
    };
    readingCustomer.addEventListener('change', () => {
      const opt = readingCustomer.selectedOptions[0];
      previousReading.value = opt?.dataset?.last ?? '0';
      if (previousBillUnpaid) previousBillUnpaid.value = Number(opt?.dataset?.unpaid || 0).toFixed(2);
      if (installmentBalance) installmentBalance.value = Number(opt?.dataset?.installment || 0).toFixed(2);
      if (currentReading) currentReading.value = '';
      syncReadingCustomerWarning();
      updateReadingTotals();
    });
    syncReadingCustomerWarning();
  }
  [previousReading, currentReading, installmentBalance].forEach((el) => {
    if (el) el.addEventListener('input', updateReadingTotals);
  });
  updateReadingTotals();

  const BATCH_PRINT_MAX = 6;
  const batchPrintUrl = (window.__WATER_CONFIG__ && window.__WATER_CONFIG__.batchPrintUrl) || '';
  const batchChecks = Array.from(document.querySelectorAll('.batch-bill-check'));
  const batchBars = Array.from(document.querySelectorAll('[data-batch-bar]'));

  function selectedBatchIds() {
    const ids = [];
    const seen = new Set();
    batchChecks.forEach((cb) => {
      if (!cb.checked) return;
      if (seen.has(cb.value)) return;
      seen.add(cb.value);
      ids.push(cb.value);
    });
    return ids;
  }

  function syncBatchCheckmates(changed) {
    // Keep same bill id checkboxes in sync across tabs
    if (!changed) return;
    batchChecks.forEach((cb) => {
      if (cb !== changed && cb.value === changed.value) cb.checked = changed.checked;
    });
  }

  function refreshBatchPrintBars(showLimitNote) {
    const ids = selectedBatchIds();
    batchBars.forEach((bar) => {
      const countEl = bar.querySelector('[data-batch-count]');
      const printBtn = bar.querySelector('[data-batch-print]');
      const note = bar.querySelector('[data-batch-note]');
      if (countEl) countEl.textContent = String(ids.length);
      if (printBtn) printBtn.disabled = ids.length === 0;
      bar.classList.toggle('is-visible', ids.length > 0);
      if (note) note.classList.toggle('is-visible', Boolean(showLimitNote));
    });
  }

  batchChecks.forEach((cb) => {
    cb.addEventListener('change', () => {
      let showLimitNote = false;
      const uniqueBeforeSync = selectedBatchIds();
      if (cb.checked && uniqueBeforeSync.length > BATCH_PRINT_MAX) {
        cb.checked = false;
        showLimitNote = true;
      }
      syncBatchCheckmates(cb);
      refreshBatchPrintBars(showLimitNote);
    });
  });

  batchBars.forEach((bar) => {
    const clearBtn = bar.querySelector('[data-batch-clear]');
    const printBtn = bar.querySelector('[data-batch-print]');
    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        batchChecks.forEach((cb) => { cb.checked = false; });
        refreshBatchPrintBars(false);
      });
    }
    if (printBtn) {
      printBtn.addEventListener('click', () => {
        const ids = selectedBatchIds().slice(0, BATCH_PRINT_MAX);
        if (!ids.length) return;
        const params = new URLSearchParams();
        ids.forEach((id) => params.append('bill_ids', id));
        window.location.href = `${batchPrintUrl}?${params.toString()}`;
      });
    }
  });
  refreshBatchPrintBars(false);

  const paymentBill = document.getElementById('paymentBill');
  const paymentAmount = document.getElementById('paymentAmount');
  const payBalanceDisplay = document.getElementById('payBalanceDisplay');
  const payAmountDisplay = document.getElementById('payAmountDisplay');
  const payRemainingDisplay = document.getElementById('payRemainingDisplay');
  function formatPeso(value) {
    const num = Number(value || 0);
    return `₱${num.toFixed(2)}`;
  }
  function syncPaymentSummary() {
    const opt = paymentBill?.selectedOptions?.[0];
    const balance = Number(opt?.dataset?.balance || 0);
    const amount = Number(paymentAmount?.value || 0);
    if (payBalanceDisplay) payBalanceDisplay.textContent = formatPeso(balance);
    if (payAmountDisplay) payAmountDisplay.textContent = formatPeso(amount);
    if (payRemainingDisplay) payRemainingDisplay.textContent = formatPeso(Math.max(balance - amount, 0));
  }
  if (paymentBill && paymentAmount) {
    paymentBill.addEventListener('change', () => {
      const opt = paymentBill.selectedOptions[0];
      if (opt?.dataset?.balance) paymentAmount.value = opt.dataset.balance;
      syncPaymentSummary();
    });
    paymentAmount.addEventListener('input', syncPaymentSummary);
    syncPaymentSummary();
  }
})();
