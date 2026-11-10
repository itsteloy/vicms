(function () {
  function getCsrfToken(select) {
    const fromSelect = select && select.dataset ? (select.dataset.csrfToken || '') : '';
    if (fromSelect) return fromSelect;
    const value = `; ${document.cookie}`;
    const parts = value.split('; csrftoken=');
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  }

  function setSheetTheme(color, billId) {
    document.querySelectorAll('[data-statement-sheet]').forEach((sheet) => {
      if (billId && sheet.dataset.billId !== billId) return;
      sheet.classList.toggle('sheet-theme-red', color === 'red');
    });
  }

  function syncSelects(billId, color, changed) {
    document.querySelectorAll('.bill-color-select').forEach((select) => {
      if (select === changed) return;
      if (select.dataset.billId !== billId) return;
      select.value = color;
      select.dataset.savedColor = color;
    });
  }

  function updateBillColor(select) {
    const billId = select.dataset.billId;
    const url = select.dataset.colorUrl;
    if (!billId || !url) return;
    const color = select.value;
    const previous = select.dataset.savedColor || 'default';
    select.disabled = true;
    fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(select),
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify({ color }),
    })
      .then(async (response) => {
        let data = {};
        try {
          data = await response.json();
        } catch (error) {
          data = {};
        }
        if (!response.ok) {
          const message = data.error
            || (response.status === 403 ? 'Session expired. Refresh the page and try again.' : '')
            || `Could not save statement color (${response.status}).`;
          throw new Error(message);
        }
        return data;
      })
      .then(() => {
        select.dataset.savedColor = color;
        syncSelects(billId, color, select);
        setSheetTheme(color, billId);
      })
      .catch((error) => {
        select.value = previous;
        alert(error && error.message ? error.message : 'Could not save statement color.');
      })
      .finally(() => {
        select.disabled = false;
      });
  }

  document.addEventListener('change', (event) => {
    const select = event.target.closest('.bill-color-select');
    if (!select) return;
    updateBillColor(select);
  });
})();
