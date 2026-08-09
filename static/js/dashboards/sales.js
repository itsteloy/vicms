(function () {
        // ── Tab switching (now using URL parameter or active_tab) ──
        const tabs = document.querySelectorAll('.sidebar-nav .tab-button');
        const panels = {
            'sales-tab': document.getElementById('sales-tab'),
            'history-tab': document.getElementById('history-tab'),
            'refund-tab': document.getElementById('refund-tab'),
            'analytics-tab': document.getElementById('analytics-tab'),
            'product-quotation-tab': document.getElementById('product-quotation-tab'),
            'service-quotation-tab': document.getElementById('service-quotation-tab'),
            'collection-form-tab': document.getElementById('collection-form-tab'),
            'delivery-receipt-tab': document.getElementById('delivery-receipt-tab'),
            'ageing-accounts-tab': document.getElementById('ageing-accounts-tab'),
            'retention-summary-tab': document.getElementById('retention-summary-tab'),
            'petty-cash-tab': document.getElementById('petty-cash-tab'),
            'saved-documents-tab': document.getElementById('saved-documents-tab'),
        };

        // Function to activate a tab
        function activateTab(targetId) {
            tabs.forEach((btn) => {
                const isTarget = btn.dataset.tabTarget === targetId;
                btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
            });
            Object.keys(panels).forEach((id) => {
                if (panels[id]) {
                    panels[id].classList.toggle('is-active', id === targetId);
                }
            });
        }

        function getCsrfToken() {
            const value = `; ${document.cookie}`;
            const parts = value.split(`; csrftoken=`);
            if (parts.length === 2) return parts.pop().split(';').shift();
            return '';
        }

        async function uploadSalesDocumentPdf({ blob, documentType, title, reference, sourceId, fileName }) {
            if (!blob) throw new Error('PDF blob is missing.');
            const formData = new FormData();
            const safeName = (fileName || title || documentType || 'document')
                .toString()
                .replace(/[^\w.\-]+/g, '_')
                .slice(0, 80) + '.pdf';
            formData.append('pdf', blob, safeName);
            formData.append('document_type', documentType || '');
            formData.append('title', title || '');
            formData.append('reference', reference || '');
            if (sourceId != null && sourceId !== '') {
                formData.append('source_id', String(sourceId));
            }

            const response = await fetch((window.__SALES_CONFIG__ && window.__SALES_CONFIG__.savePdfUrl) || '', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'X-CSRFToken': getCsrfToken() },
                body: formData,
            });

            const contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
                const body = await response.json();
                if (!response.ok) {
                    throw new Error(body?.error || 'Unable to save PDF to the database.');
                }
                return body;
            }

            const text = await response.text();
            throw new Error(text ? text.replace(/\s+/g, ' ').trim().slice(0, 200) : 'Server error while saving PDF.');
        }

        function goToSavedDocuments() {
            window.location.href = ((window.__SALES_CONFIG__ && window.__SALES_CONFIG__.dashboardUrl) || '') + '?tab=saved-documents-tab';
        }

        function printPdfBlob(pdfBlob) {
            const blobUrl = URL.createObjectURL(pdfBlob);
            const printFrame = document.createElement('iframe');
            printFrame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;';
            printFrame.src = blobUrl;
            document.body.appendChild(printFrame);
            const cleanup = () => setTimeout(() => {
                printFrame.remove();
                URL.revokeObjectURL(blobUrl);
            }, 2500);
            printFrame.onload = () => {
                try {
                    printFrame.contentWindow.focus();
                    printFrame.contentWindow.print();
                } catch (err) {
                    console.error(err);
                    window.open(blobUrl, '_blank');
                } finally {
                    cleanup();
                }
            };
        }

        // Shared currency helpers (commas + digits only)
        function parseMoney(val) {
            const n = parseFloat(String(val == null ? '' : val).replace(/[^0-9.-]/g, ''));
            return Number.isFinite(n) ? n : 0;
        }

        function formatMoney(num) {
            const n = Number(num) || 0;
            const neg = n < 0;
            const [intPart, decPart] = Math.abs(n).toFixed(2).split('.');
            return (neg ? '-' : '') + intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + '.' + decPart;
        }

        function formatMoneyTyping(raw) {
            let s = String(raw == null ? '' : raw).replace(/[^0-9.]/g, '');
            if (!s) return '';
            const neg = String(raw).trim().startsWith('-');
            const firstDot = s.indexOf('.');
            let intPart = firstDot === -1 ? s : s.slice(0, firstDot);
            let decPart = firstDot === -1 ? null : s.slice(firstDot + 1).replace(/\./g, '').slice(0, 2);
            intPart = intPart.replace(/^0+(?=\d)/, '') || '0';
            intPart = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
            let out = intPart;
            if (decPart !== null) out += '.' + decPart;
            return (neg ? '-' : '') + out;
        }

        function bindMoneyInputs(root, selector) {
            if (!root) return;
            const applyLive = (el) => {
                const prev = el.value;
                const start = el.selectionStart;
                const formatted = formatMoneyTyping(prev);
                if (formatted !== prev) {
                    el.value = formatted;
                    const delta = formatted.length - prev.length;
                    const pos = Math.max(0, (start || 0) + delta);
                    try { el.setSelectionRange(pos, pos); } catch (_) { /* ignore */ }
                }
            };
            root.addEventListener('input', (e) => {
                if (!e.target.matches || !e.target.matches(selector)) return;
                applyLive(e.target);
            });
            root.addEventListener('blur', (e) => {
                if (!e.target.matches || !e.target.matches(selector)) return;
                if (e.target.readOnly || e.target.disabled) {
                    e.target.value = formatMoney(parseMoney(e.target.value));
                    return;
                }
                e.target.value = formatMoney(parseMoney(e.target.value));
            }, true);
            root.addEventListener('keypress', (e) => {
                if (!e.target.matches || !e.target.matches(selector)) return;
                if (e.ctrlKey || e.metaKey || e.altKey) return;
                const ch = e.key;
                if (ch.length === 1 && !/[0-9.]/.test(ch)) e.preventDefault();
            });
            // Normalize existing values
            root.querySelectorAll(selector).forEach((el) => {
                if ((el.value || '').trim() !== '') el.value = formatMoney(parseMoney(el.value));
            });
        }

        // Set initial active tab based on server-side active_tab (already set in HTML)
        // We'll also ensure the URL has ?tab=... if missing
        const urlParams = new URLSearchParams(window.location.search);
        const tabParam = urlParams.get('tab');
        if (tabParam && panels[tabParam]) {
            activateTab(tabParam);
        } else {
            // If no tab param, use the active_tab from template (which is set by server)
            const activeTab = (window.__SALES_CONFIG__ && window.__SALES_CONFIG__.activeTab) || 'sales-tab';
            if (panels[activeTab]) {
                activateTab(activeTab);
            }
        }

        // Click handlers: update URL with tab parameter
        tabs.forEach((btn) => {
            btn.addEventListener('click', function () {
                const targetId = this.dataset.tabTarget;
                // Update URL without reload
                const url = new URL(window.location);
                url.searchParams.set('tab', targetId);
                window.history.pushState({}, '', url);
                activateTab(targetId);
            });
        });

        // ── Category performance select sync (unchanged) ──
        document.querySelectorAll('.product-code-select').forEach((select) => {
            const card = select.closest('[data-category-card]');
            if (!card) return;
            const revenueEl = card.querySelector('.metric-revenue');
            const quantityEl = card.querySelector('.metric-quantity');
            const ordersEl = card.querySelector('.metric-orders');
            const stockEl = card.querySelector('.perf-stock');

            function sync() {
                const opt = select.options[select.selectedIndex];
                if (!opt || !revenueEl || !quantityEl || !ordersEl || !stockEl) return;
                revenueEl.textContent = '₱' + (opt.dataset.revenue || '0.00');
                quantityEl.textContent = opt.dataset.quantity || '0';
                ordersEl.textContent = opt.dataset.orders || '0';
                const st = Number(opt.dataset.stock || 0);
                stockEl.textContent = st + ' in stock';
                stockEl.classList.toggle('low', st === 0);
            }
            select.addEventListener('change', sync);
            sync();
        });

        // ── Sale preview ──
        const itemSelect = document.getElementById('inventoryItem');
        const quantityInput = document.getElementById('quantity');
        const selectedStock = document.getElementById('selectedStock');
        const selectedPrice = document.getElementById('selectedPrice');
        const selectedTotal = document.getElementById('selectedTotal');

        function fmt(v) {
            const n = Number(v || 0);
            return n.toFixed(2);
        }

        function updatePreview() {
            const opt = itemSelect.options[itemSelect.selectedIndex];
            const stock = Number(opt?.dataset?.stock || 0);
            const price = Number(opt?.dataset?.price || 0);
            const qty = Number(quantityInput.value || 0);

            selectedStock.textContent = itemSelect.value ? stock : '-';
            selectedPrice.textContent = itemSelect.value ? '₱' + fmt(price) : '-';
            selectedTotal.textContent = (itemSelect.value && qty > 0) ? '₱' + fmt(price * qty) : '-';
            if (itemSelect.value) {
                quantityInput.max = stock;
            }
        }

        if (itemSelect) {
            itemSelect.addEventListener('change', updatePreview);
            quantityInput.addEventListener('input', updatePreview);
            updatePreview();
        }

        // ── Mobile scroll ──
        if (window.innerWidth <= 768) {
            tabs.forEach((btn) => {
                btn.addEventListener('click', function () {
                    document.querySelector('.main-content')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                });
            });
        }

        // ── Sales by Category chart toggle ──
        const toggleBtns = document.querySelectorAll('.chart-toggle');
        const chartContainer = document.getElementById('categoryChart');

        function setChartView(view) {
            // Update button styles
            toggleBtns.forEach(btn => {
                btn.style.background = btn.dataset.view === view ? 'var(--brand)' : '#fff';
                btn.style.color = btn.dataset.view === view ? '#fff' : 'var(--brand)';
                btn.style.borderColor = btn.dataset.view === view ? 'var(--brand)' : 'var(--line)';
            });

            // Toggle visibility of revenue vs quantity bars and labels
            const barsRevenue = chartContainer.querySelectorAll('.bar-revenue');
            const barsQuantity = chartContainer.querySelectorAll('.bar-quantity');
            const labelsRevenue = chartContainer.querySelectorAll('.bar-label-revenue');
            const labelsQuantity = chartContainer.querySelectorAll('.bar-label-quantity');

            if (view === 'revenue') {
                barsRevenue.forEach(b => b.style.display = 'block');
                barsQuantity.forEach(b => b.style.display = 'none');
                labelsRevenue.forEach(l => l.style.display = 'block');
                labelsQuantity.forEach(l => l.style.display = 'none');
            } else { // quantity
                barsRevenue.forEach(b => b.style.display = 'none');
                barsQuantity.forEach(b => b.style.display = 'block');
                labelsRevenue.forEach(l => l.style.display = 'none');
                labelsQuantity.forEach(l => l.style.display = 'block');
            }
        }

        // Attach click events
        toggleBtns.forEach(btn => {
            btn.addEventListener('click', function () {
                setChartView(this.dataset.view);
            });
        });

        // Default to revenue (already active)
        setChartView('revenue');

        // ══════════════════════════════════════════════════════════════
        // PRODUCT QUOTATION FORM FUNCTIONALITY
        // ══════════════════════════════════════════════════════════════

        (function initProductQuotation() {
            const itemsBody = document.getElementById('pqItemsBody');
            const subtotalInput = document.getElementById('pqSubtotal');
            const taxInput = document.getElementById('pqTax');
            const discountInput = document.getElementById('pqDiscount');
            const shippingInput = document.getElementById('pqShipping');
            const grandTotalInput = document.getElementById('pqGrandTotal');
            const initialPaymentInput = document.getElementById('pqInitialPayment');
            const balanceDueInput = document.getElementById('pqBalanceDue');
            const addRowBtn = document.getElementById('pqAddRow');
            const saveBtn = document.getElementById('pqSave');
            const printBtn = document.getElementById('pqPrint');
            const resetBtn = document.getElementById('pqReset');
            const currencySelect = document.getElementById('pqCurrency');
            const currencyOther = document.getElementById('pqCurrencyOther');
            const pqDateInput = document.getElementById('pqDate');

            if (!itemsBody) return;

            function money(num) {
                return formatMoney(num);
            }

            function todayISO() {
                const d = new Date();
                const month = String(d.getMonth() + 1).padStart(2, '0');
                const date = String(d.getDate()).padStart(2, '0');
                return `${d.getFullYear()}-${month}-${date}`;
            }

            pqDateInput.value = todayISO();

            function recalcRow(row) {
                const qty = parseMoney(row.querySelector('.pq-qty')?.value) || parseFloat(row.querySelector('.pq-qty')?.value) || 0;
                const cost = parseMoney(row.querySelector('.pq-unit-price')?.value);
                const total = qty * cost;
                const totalInput = row.querySelector('.pq-line-total');
                if (totalInput) totalInput.value = money(total);
            }

            function recalcAll() {
                let subtotal = 0;
                itemsBody.querySelectorAll('tr').forEach(row => {
                    recalcRow(row);
                    subtotal += parseMoney(row.querySelector('.pq-line-total')?.value);
                });
                subtotalInput.value = money(subtotal);
                const tax = parseMoney(taxInput.value);
                const discount = parseMoney(discountInput.value);
                const shipping = parseMoney(shippingInput.value);
                const grand = subtotal + tax + shipping - discount;
                grandTotalInput.value = money(grand);

                const initialPayment = parseMoney(initialPaymentInput.value);
                const balance = grand - initialPayment;
                balanceDueInput.value = money(balance);
            }

            function renumberRows() {
                itemsBody.querySelectorAll('tr').forEach((row, idx) => {
                    const noInput = row.querySelector('.pq-col-no');
                    if (noInput) noInput.value = idx + 1;
                });
            }

            function addRow() {
                const template = itemsBody.querySelector('tr');
                if (!template) return;

                const clone = template.cloneNode(true);
                clone.querySelectorAll('input, textarea').forEach(el => {
                    if (el.classList.contains('pq-qty')) {
                        el.value = 1;
                        return;
                    }
                    if (el.classList.contains('pq-unit-price')) {
                        el.value = '0.00';
                        return;
                    }
                    if (el.classList.contains('pq-line-total')) {
                        el.value = '0.00';
                        return;
                    }
                    el.value = '';
                });

                const rowCount = itemsBody.querySelectorAll('tr').length + 1;
                const noInput = clone.querySelector('.pq-col-no');
                if (noInput) noInput.value = rowCount;

                itemsBody.appendChild(clone);
                renumberRows();
                recalcAll();
            }

            function removeRow(row) {
                const rows = itemsBody.querySelectorAll('tr');
                if (rows.length <= 1) {
                    alert('At least one line item is required.');
                    return;
                }
                row.remove();
                renumberRows();
                recalcAll();
            }

            itemsBody.addEventListener('input', function (e) {
                const row = e.target.closest('tr');
                if (row) recalcRow(row), recalcAll();
            });

            itemsBody.addEventListener('click', function (e) {
                const btn = e.target.closest('.pq-row-remove');
                if (!btn) return;
                removeRow(btn.closest('tr'));
            });

            addRowBtn.addEventListener('click', function (e) {
                e.preventDefault();
                addRow();
            });

            [taxInput, discountInput, shippingInput, initialPaymentInput].forEach(el => {
                el.addEventListener('input', recalcAll);
            });

            bindMoneyInputs(itemsBody, '.pq-unit-price');
            bindMoneyInputs(document.getElementById('product-quotation-tab'), '#pqTax, #pqDiscount, #pqShipping, #pqInitialPayment');
            // Keep computed fields formatted
            [subtotalInput, grandTotalInput, balanceDueInput].forEach((el) => {
                if (!el) return;
                el.addEventListener('input', () => { el.value = formatMoney(parseMoney(el.value)); });
            });

            currencySelect.addEventListener('change', function () {
                const isOther = this.value === 'OTHER';
                currencyOther.hidden = !isOther;
                if (isOther) currencyOther.focus();
            });

            function collectPqPayload() {
                const currency = currencySelect?.value || 'PHP';
                const items = [];
                itemsBody.querySelectorAll('tr').forEach(row => {
                    items.push({
                        no: row.querySelector('.pq-col-no')?.value || '',
                        description: row.querySelector('.pq-col-desc')?.value || '',
                        qty: row.querySelector('.pq-qty')?.value || '0',
                        unit: row.querySelector('.pq-col-unit')?.value || '',
                        unit_price: parseMoney(row.querySelector('.pq-unit-price')?.value).toFixed(2),
                        total: parseMoney(row.querySelector('.pq-line-total')?.value).toFixed(2),
                    });
                });

                return {
                    quotation_number: document.getElementById('pqNumber')?.value || '',
                    currency,
                    currency_other: currencyOther?.value || '',
                    quotation_date: document.getElementById('pqDate')?.value || '',
                    valid_until: document.getElementById('pqValidUntil')?.value || '',
                    customer: {
                        company: document.getElementById('pqCustomerCompany')?.value || '',
                        contact: document.getElementById('pqCustomerContact')?.value || '',
                        address: document.getElementById('pqCustomerAddress')?.value || '',
                        email: document.getElementById('pqCustomerEmail')?.value || '',
                        phone: document.getElementById('pqCustomerPhone')?.value || '',
                    },
                    items,
                    subtotal: parseMoney(subtotalInput?.value).toFixed(2),
                    tax: parseMoney(taxInput?.value).toFixed(2),
                    discount: parseMoney(discountInput?.value).toFixed(2),
                    shipping: parseMoney(shippingInput?.value).toFixed(2),
                    grand_total: parseMoney(grandTotalInput?.value).toFixed(2),
                    initial_payment: parseMoney(initialPaymentInput?.value).toFixed(2),
                    balance_due: parseMoney(balanceDueInput?.value).toFixed(2),
                    payment_terms: document.getElementById('pqPaymentTerms')?.value || '',
                    delivery_terms: document.getElementById('pqDeliveryTerms')?.value || '',
                    warranty: document.getElementById('pqWarranty')?.value || '',
                    other_terms: document.getElementById('pqOtherTerms')?.value || '',
                    prepared_by: {
                        name: document.getElementById('pqPreparedName')?.value || '',
                        title: document.getElementById('pqPreparedPosition')?.value || '',
                        signature: document.getElementById('pqPreparedSignature')?.value || '',
                        date: document.getElementById('pqPreparedDate')?.value || '',
                    },
                    approved_by: {
                        name: 'Engr. Arturo I. Davis, PME',
                        title: 'President / CEO',
                        signature: document.getElementById('pqApprovedSignature')?.value || '',
                        date: document.getElementById('pqApprovedDate')?.value || '',
                    },
                };
            }

            function getCookie(name) {
                const value = `; ${document.cookie}`;
                const parts = value.split(`; ${name}=`);
                if (parts.length === 2) return parts.pop().split(';').shift();
                return '';
            }

            async function savePqPayload() {
                const payload = collectPqPayload();
                const response = await fetch((window.__SALES_CONFIG__ && window.__SALES_CONFIG__.saveQuotationUrl) || '', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify(payload),
                });

                const contentType = response.headers.get('content-type') || '';
                if (contentType.includes('application/json')) {
                    const body = await response.json();
                    if (response.status !== 200) {
                        throw new Error(body?.error || 'Unable to save product quotation.');
                    }
                    if (body.next_quotation_number) {
                        const pqNumber = document.getElementById('pqNumber');
                        pqNumber.value = body.next_quotation_number;
                        pqNumber.setAttribute('data-auto-number', body.next_quotation_number);
                    }
                    return body;
                }

                const text = await response.text();
                throw new Error(text ? text.replace(/\s+/g, ' ').trim().slice(0, 200) : 'Server error');
            }

            async function printPqPdf(downloadUrl) {
                const response = await fetch(downloadUrl, {
                    method: 'GET',
                    credentials: 'same-origin',
                });

                if (!response.ok) {
                    throw new Error('Could not generate the product quotation PDF for printing.');
                }

                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const iframe = document.createElement('iframe');
                iframe.style.position = 'fixed';
                iframe.style.right = '0';
                iframe.style.bottom = '0';
                iframe.style.width = '0';
                iframe.style.height = '0';
                iframe.style.border = '0';
                iframe.src = url;
                document.body.appendChild(iframe);

                const cleanup = () => {
                    setTimeout(() => {
                        iframe.remove();
                        URL.revokeObjectURL(url);
                    }, 1500);
                };

                iframe.onload = function () {
                    try {
                        const win = iframe.contentWindow;
                        if (!win) throw new Error('Print frame unavailable.');
                        win.focus();
                        win.print();
                    } catch (err) {
                        window.open(url, '_blank');
                    } finally {
                        cleanup();
                    }
                };
            }

            if (saveBtn) {
                saveBtn.addEventListener('click', async function (e) {
                    e.preventDefault();
                    const prevLabel = saveBtn.textContent;
                    saveBtn.disabled = true;
                    saveBtn.textContent = 'Saving…';
                    try {
                        const body = await savePqPayload();
                        if (!body.download_url) {
                            throw new Error('Quotation saved, but no PDF URL was returned.');
                        }
                        const pdfRes = await fetch(body.download_url, {
                            method: 'GET',
                            credentials: 'same-origin',
                        });
                        if (!pdfRes.ok) throw new Error('Could not generate the PDF.');
                        const blob = await pdfRes.blob();
                        await uploadSalesDocumentPdf({
                            blob,
                            documentType: 'product_quotation',
                            title: `Product Quotation ${body.quotation_number || ''}`.trim(),
                            reference: body.quotation_number || '',
                            sourceId: body.id,
                            fileName: body.quotation_number || 'product_quotation',
                        });
                        alert('Product quotation PDF saved to the database.');
                        goToSavedDocuments();
                    } catch (error) {
                        alert('Unable to save product quotation PDF: ' + (error.message || error));
                    } finally {
                        saveBtn.disabled = false;
                        saveBtn.textContent = prevLabel;
                    }
                });
            }

            printBtn.addEventListener('click', function (e) {
                e.preventDefault();
                printBtn.disabled = true;

                savePqPayload()
                    .then((body) => {
                        if (!body.download_url) {
                            throw new Error('Product quotation saved, but no PDF URL was returned.');
                        }
                        return printPqPdf(body.download_url);
                    })
                    .catch((error) => {
                        alert('Unable to print product quotation: ' + error.message);
                    })
                    .finally(() => {
                        printBtn.disabled = false;
                    });
            });

            resetBtn.addEventListener('click', function () {
                if (!confirm('Reset the Product Quotation form? All entered data will be cleared.')) return;
                const rows = itemsBody.querySelectorAll('tr');
                rows.forEach((row, idx) => { if (idx > 0) row.remove(); });
                const first = itemsBody.querySelector('tr');
                first.querySelectorAll('input, textarea').forEach(el => {
                    if (el.classList.contains('pq-col-no')) return;
                    if (el.classList.contains('pq-qty')) { el.value = 1; return; }
                    if (el.classList.contains('pq-unit-price')) { el.value = '0.00'; return; }
                    if (el.classList.contains('pq-line-total')) { el.value = '0.00'; return; }
                    el.value = '';
                });
                first.querySelector('.pq-col-no').value = 1;
                taxInput.value = '0.00';
                discountInput.value = '0.00';
                shippingInput.value = '0.00';
                initialPaymentInput.value = '0.00';
                currencySelect.value = 'PHP';
                currencyOther.hidden = true;
                currencyOther.value = '';
                pqDateInput.value = todayISO();
                document.getElementById('pqValidUntil').value = '';
                const pqNumber = document.getElementById('pqNumber');
                pqNumber.value = pqNumber.getAttribute('data-auto-number') || '';
                document.getElementById('pqCustomerCompany').value = '';
                document.getElementById('pqCustomerContact').value = '';
                document.getElementById('pqCustomerAddress').value = '';
                document.getElementById('pqCustomerEmail').value = '';
                document.getElementById('pqCustomerPhone').value = '';
                document.getElementById('pqPaymentTerms').value = '';
                document.getElementById('pqDeliveryTerms').value = '';
                document.getElementById('pqWarranty').value = '';
                document.getElementById('pqOtherTerms').value = '';
                document.getElementById('pqPreparedName').value = '';
                document.getElementById('pqPreparedPosition').value = '';
                document.getElementById('pqPreparedSignature').value = '';
                document.getElementById('pqPreparedDate').value = '';
                document.getElementById('pqApprovedSignature').value = '';
                document.getElementById('pqApprovedDate').value = '';
                recalcAll();
            });

            recalcAll();
        })();

        // ══════════════════════════════════════════════════════════════
        // SERVICE QUOTATION FORM FUNCTIONALITY
        // ══════════════════════════════════════════════════════════════

        (function initServiceQuotation() {
            const itemsBody = document.getElementById('svqItemsBody');
            const subtotalInput = document.getElementById('svqSubtotal');
            const taxInput = document.getElementById('svqTax');
            const discountInput = document.getElementById('svqDiscount');
            const otherFeesInput = document.getElementById('svqOtherFees');
            const grandTotalInput = document.getElementById('svqGrandTotal');
            const initialPaymentInput = document.getElementById('svqInitialPayment');
            const balanceDueInput = document.getElementById('svqBalanceDue');
            const addRowBtn = document.getElementById('svqAddRow');
            const saveBtn = document.getElementById('svqSave');
            const printBtn = document.getElementById('svqPrint');
            const resetBtn = document.getElementById('svqReset');
            const currencySelect = document.getElementById('svqCurrency');
            const currencyOther = document.getElementById('svqCurrencyOther');
            const svqDateInput = document.getElementById('svqDate');

            if (!itemsBody) return;

            function money(num) {
                return formatMoney(num);
            }

            function todayISO() {
                const d = new Date();
                const month = String(d.getMonth() + 1).padStart(2, '0');
                const date = String(d.getDate()).padStart(2, '0');
                return `${d.getFullYear()}-${month}-${date}`;
            }

            svqDateInput.value = todayISO();

            function recalcAll() {
                let subtotal = 0;
                itemsBody.querySelectorAll('tr').forEach(row => {
                    subtotal += parseMoney(row.querySelector('.svq-line-total')?.value);
                });
                subtotalInput.value = money(subtotal);
                const tax = parseMoney(taxInput.value);
                const discount = parseMoney(discountInput.value);
                const otherFees = parseMoney(otherFeesInput.value);
                const grand = subtotal + tax + otherFees - discount;
                grandTotalInput.value = money(grand);

                const initialPayment = parseMoney(initialPaymentInput.value);
                const balance = grand - initialPayment;
                balanceDueInput.value = money(balance);
            }

            function renumberRows() {
                itemsBody.querySelectorAll('tr').forEach((row, idx) => {
                    const noInput = row.querySelector('.svq-col-no');
                    if (noInput) noInput.value = idx + 1;
                });
            }

            function addRow() {
                const template = itemsBody.querySelector('tr');
                if (!template) return;

                const clone = template.cloneNode(true);
                clone.querySelectorAll('input, textarea').forEach(el => {
                    if (el.classList.contains('svq-line-total')) {
                        el.value = '0.00';
                        return;
                    }
                    el.value = '';
                });

                const rowCount = itemsBody.querySelectorAll('tr').length + 1;
                const noInput = clone.querySelector('.svq-col-no');
                if (noInput) noInput.value = rowCount;

                itemsBody.appendChild(clone);
                renumberRows();
                recalcAll();
            }

            function removeRow(row) {
                const rows = itemsBody.querySelectorAll('tr');
                if (rows.length <= 1) {
                    alert('At least one service line item is required.');
                    return;
                }
                row.remove();
                renumberRows();
                recalcAll();
            }

            itemsBody.addEventListener('input', function (e) {
                const row = e.target.closest('tr');
                if (row) recalcAll();
            });

            itemsBody.addEventListener('click', function (e) {
                const btn = e.target.closest('.svq-row-remove');
                if (!btn) return;
                removeRow(btn.closest('tr'));
            });

            addRowBtn.addEventListener('click', function (e) {
                e.preventDefault();
                addRow();
            });

            [taxInput, discountInput, otherFeesInput, initialPaymentInput].forEach(el => {
                el.addEventListener('input', recalcAll);
            });

            bindMoneyInputs(itemsBody, '.svq-line-total');
            bindMoneyInputs(document.getElementById('service-quotation-tab'), '#svqTax, #svqDiscount, #svqOtherFees, #svqInitialPayment');

            currencySelect.addEventListener('change', function () {
                const isOther = this.value === 'OTHER';
                currencyOther.hidden = !isOther;
                if (isOther) currencyOther.focus();
            });

            function collectSvqPayload() {
                const currency = currencySelect?.value || 'PHP';
                const items = [];
                itemsBody.querySelectorAll('tr').forEach(row => {
                    const total = parseMoney(row.querySelector('.svq-line-total')?.value).toFixed(2);
                    items.push({
                        no: row.querySelector('.svq-col-no')?.value || '',
                        description: row.querySelector('.svq-col-desc')?.value || '',
                        qty: '1',
                        unit: '',
                        unit_price: total,
                        total: total,
                    });
                });

                return {
                    quotation_number: document.getElementById('svqNumber')?.value || '',
                    currency,
                    currency_other: currencyOther?.value || '',
                    quotation_date: document.getElementById('svqDate')?.value || '',
                    valid_until: document.getElementById('svqValidUntil')?.value || '',
                    customer: {
                        company: document.getElementById('svqCustomerCompany')?.value || '',
                        contact: document.getElementById('svqCustomerContact')?.value || '',
                        address: document.getElementById('svqCustomerAddress')?.value || '',
                        email: document.getElementById('svqCustomerEmail')?.value || '',
                        phone: document.getElementById('svqCustomerPhone')?.value || '',
                    },
                    items,
                    subtotal: parseMoney(subtotalInput?.value).toFixed(2),
                    tax: parseMoney(taxInput?.value).toFixed(2),
                    discount: parseMoney(discountInput?.value).toFixed(2),
                    other_fees: parseMoney(otherFeesInput?.value).toFixed(2),
                    grand_total: parseMoney(grandTotalInput?.value).toFixed(2),
                    initial_payment: parseMoney(initialPaymentInput?.value).toFixed(2),
                    balance_due: parseMoney(balanceDueInput?.value).toFixed(2),
                    payment_terms: document.getElementById('svqPaymentTerms')?.value || '',
                    service_schedule: document.getElementById('svqServiceSchedule')?.value || '',
                    warranty: document.getElementById('svqWarranty')?.value || '',
                    other_terms: document.getElementById('svqOtherTerms')?.value || '',
                    prepared_by: {
                        name: document.getElementById('svqPreparedName')?.value || '',
                        title: document.getElementById('svqPreparedPosition')?.value || '',
                        signature: document.getElementById('svqPreparedSignature')?.value || '',
                        date: document.getElementById('svqPreparedDate')?.value || '',
                    },
                    approved_by: {
                        name: 'Engr. Arturo I. Davis, PME',
                        title: 'President / CEO',
                        signature: document.getElementById('svqApprovedSignature')?.value || '',
                        date: document.getElementById('svqApprovedDate')?.value || '',
                    },
                };
            }

            function getCookie(name) {
                const value = `; ${document.cookie}`;
                const parts = value.split(`; ${name}=`);
                if (parts.length === 2) return parts.pop().split(';').shift();
                return '';
            }

            async function saveSvqPayload() {
                const payload = collectSvqPayload();
                const response = await fetch((window.__SALES_CONFIG__ && window.__SALES_CONFIG__.saveServiceQuotationUrl) || '', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify(payload),
                });

                const contentType = response.headers.get('content-type') || '';
                if (contentType.includes('application/json')) {
                    const body = await response.json();
                    if (response.status !== 200) {
                        throw new Error(body?.error || 'Unable to save service quotation.');
                    }
                    if (body.next_quotation_number) {
                        const svqNumber = document.getElementById('svqNumber');
                        svqNumber.value = body.next_quotation_number;
                        svqNumber.setAttribute('data-auto-number', body.next_quotation_number);
                    }
                    return body;
                }

                const text = await response.text();
                throw new Error(text ? text.replace(/\s+/g, ' ').trim().slice(0, 200) : 'Server error');
            }

            async function printSvqPdf(downloadUrl) {
                const response = await fetch(downloadUrl, {
                    method: 'GET',
                    credentials: 'same-origin',
                });

                if (!response.ok) {
                    throw new Error('Could not generate the service quotation PDF for printing.');
                }

                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const iframe = document.createElement('iframe');
                iframe.style.position = 'fixed';
                iframe.style.right = '0';
                iframe.style.bottom = '0';
                iframe.style.width = '0';
                iframe.style.height = '0';
                iframe.style.border = '0';
                iframe.src = url;
                document.body.appendChild(iframe);

                const cleanup = () => {
                    setTimeout(() => {
                        iframe.remove();
                        URL.revokeObjectURL(url);
                    }, 1500);
                };

                iframe.onload = function () {
                    try {
                        const win = iframe.contentWindow;
                        if (!win) throw new Error('Print frame unavailable.');
                        win.focus();
                        win.print();
                    } catch (err) {
                        window.open(url, '_blank');
                    } finally {
                        cleanup();
                    }
                };
            }

            if (saveBtn) {
                saveBtn.addEventListener('click', async function (e) {
                    e.preventDefault();
                    const prevLabel = saveBtn.textContent;
                    saveBtn.disabled = true;
                    saveBtn.textContent = 'Saving…';
                    try {
                        const body = await saveSvqPayload();
                        if (!body.download_url) {
                            throw new Error('Quotation saved, but no PDF URL was returned.');
                        }
                        const pdfRes = await fetch(body.download_url, {
                            method: 'GET',
                            credentials: 'same-origin',
                        });
                        if (!pdfRes.ok) throw new Error('Could not generate the PDF.');
                        const blob = await pdfRes.blob();
                        await uploadSalesDocumentPdf({
                            blob,
                            documentType: 'service_quotation',
                            title: `Service Quotation ${body.quotation_number || ''}`.trim(),
                            reference: body.quotation_number || '',
                            sourceId: body.id,
                            fileName: body.quotation_number || 'service_quotation',
                        });
                        alert('Service quotation PDF saved to the database.');
                        goToSavedDocuments();
                    } catch (error) {
                        alert('Unable to save service quotation PDF: ' + (error.message || error));
                    } finally {
                        saveBtn.disabled = false;
                        saveBtn.textContent = prevLabel;
                    }
                });
            }

            printBtn.addEventListener('click', function (e) {
                e.preventDefault();
                printBtn.disabled = true;

                saveSvqPayload()
                    .then((body) => {
                        if (!body.download_url) {
                            throw new Error('Service quotation saved, but no PDF URL was returned.');
                        }
                        return printSvqPdf(body.download_url);
                    })
                    .catch((error) => {
                        alert('Unable to print service quotation: ' + error.message);
                    })
                    .finally(() => {
                        printBtn.disabled = false;
                    });
            });

            resetBtn.addEventListener('click', function () {
                if (!confirm('Reset the Service Quotation form? All entered data will be cleared.')) return;
                const rows = itemsBody.querySelectorAll('tr');
                rows.forEach((row, idx) => { if (idx > 0) row.remove(); });
                const first = itemsBody.querySelector('tr');
                first.querySelectorAll('input, textarea').forEach(el => {
                    if (el.classList.contains('svq-col-no')) return;
                    if (el.classList.contains('svq-line-total')) { el.value = '0.00'; return; }
                    el.value = '';
                });
                first.querySelector('.svq-col-no').value = 1;
                taxInput.value = '0.00';
                discountInput.value = '0.00';
                otherFeesInput.value = '0.00';
                initialPaymentInput.value = '0.00';
                currencySelect.value = 'PHP';
                currencyOther.hidden = true;
                currencyOther.value = '';
                svqDateInput.value = todayISO();
                document.getElementById('svqValidUntil').value = '';
                const svqNumber = document.getElementById('svqNumber');
                svqNumber.value = svqNumber.getAttribute('data-auto-number') || '';
                document.getElementById('svqCustomerCompany').value = '';
                document.getElementById('svqCustomerContact').value = '';
                document.getElementById('svqCustomerAddress').value = '';
                document.getElementById('svqCustomerEmail').value = '';
                document.getElementById('svqCustomerPhone').value = '';
                document.getElementById('svqPaymentTerms').value = '';
                document.getElementById('svqServiceSchedule').value = '';
                document.getElementById('svqWarranty').value = '';
                document.getElementById('svqOtherTerms').value = '';
                document.getElementById('svqPreparedName').value = '';
                document.getElementById('svqPreparedPosition').value = '';
                document.getElementById('svqPreparedSignature').value = '';
                document.getElementById('svqPreparedDate').value = '';
                document.getElementById('svqApprovedSignature').value = '';
                document.getElementById('svqApprovedDate').value = '';
                recalcAll();
            });

            recalcAll();
        })();

        // ══════════════════════════════════════════════════════════════
        // COLLECTION FORM
        // ══════════════════════════════════════════════════════════════

        (function initCollectionForm() {
            const itemsBody = document.getElementById('cfItemsBody');
            if (!itemsBody) return;

            const dateInput = document.getElementById('cfDate');
            const companyInput = document.getElementById('cfCompany');
            const addressInput = document.getElementById('cfAddress');
            const attentionInput = document.getElementById('cfAttention');
            const reInput = document.getElementById('cfRe');
            const officerNameInput = document.getElementById('cfOfficerName');
            const officerTitleInput = document.getElementById('cfOfficerTitle');
            const totalDisplay = document.getElementById('cfTotalDisplay');
            const prevItemsBody = document.getElementById('cfPrevItemsBody');

            function todayISO() {
                const d = new Date();
                const month = String(d.getMonth() + 1).padStart(2, '0');
                const day = String(d.getDate()).padStart(2, '0');
                return `${d.getFullYear()}-${month}-${day}`;
            }

            function formatDisplayDate(iso) {
                if (!iso) return '—';
                const d = new Date(iso + 'T00:00:00');
                if (Number.isNaN(d.getTime())) return iso;
                const months = ['JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE',
                    'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER'];
                return `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
            }

            function formatShortDate(iso) {
                if (!iso) return '';
                const d = new Date(iso + 'T00:00:00');
                if (Number.isNaN(d.getTime())) return iso;
                const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
                return `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
            }

            function parseAmount(val) {
                return parseMoney(val);
            }

            function formatPHP(num) {
                return 'PHP ' + formatMoney(num);
            }

            function formatTableAmount(num) {
                return 'P' + formatMoney(num);
            }

            function numberToWords(num) {
                const ones = ['', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE',
                    'TEN', 'ELEVEN', 'TWELVE', 'THIRTEEN', 'FOURTEEN', 'FIFTEEN', 'SIXTEEN',
                    'SEVENTEEN', 'EIGHTEEN', 'NINETEEN'];
                const tens = ['', '', 'TWENTY', 'THIRTY', 'FORTY', 'FIFTY', 'SIXTY', 'SEVENTY', 'EIGHTY', 'NINETY'];

                function chunkToWords(n) {
                    let s = '';
                    if (n >= 100) {
                        s += ones[Math.floor(n / 100)] + ' HUNDRED';
                        n %= 100;
                        if (n) s += ' ';
                    }
                    if (n >= 20) {
                        s += tens[Math.floor(n / 10)];
                        if (n % 10) s += '-' + ones[n % 10];
                    } else if (n > 0) {
                        s += ones[n];
                    }
                    return s;
                }

                num = Math.round((Number(num) || 0) * 100) / 100;
                if (num === 0) return 'ZERO PESOS ONLY';

                const pesos = Math.floor(num);
                const centavos = Math.round((num - pesos) * 100);

                let words = '';
                if (pesos === 0) {
                    words = 'ZERO';
                } else {
                    const billions = Math.floor(pesos / 1e9);
                    const millions = Math.floor((pesos % 1e9) / 1e6);
                    const thousands = Math.floor((pesos % 1e6) / 1e3);
                    const remainder = pesos % 1e3;
                    const parts = [];
                    if (billions) parts.push(chunkToWords(billions) + ' BILLION');
                    if (millions) parts.push(chunkToWords(millions) + ' MILLION');
                    if (thousands) parts.push(chunkToWords(thousands) + ' THOUSAND');
                    if (remainder) parts.push(chunkToWords(remainder));
                    words = parts.join(' ');
                }

                words += ' PESOS';
                if (centavos > 0) {
                    words += ' AND ' + chunkToWords(centavos) + ' CENTAVOS';
                }
                return words + ' ONLY';
            }

            function createRow() {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><input type="date" class="cf-item-date"></td>
                    <td><input type="text" class="cf-item-drsi" placeholder="DR / SI No."></td>
                    <td><input type="text" class="cf-item-qty" placeholder="1 UNIT"></td>
                    <td><textarea class="cf-item-desc" rows="1" placeholder="Item description"></textarea></td>
                    <td><input type="text" class="cf-item-amount" placeholder="0.00" value="0.00" inputmode="decimal" style="text-align:right;"></td>
                    <td><button type="button" class="cf-row-remove" style="padding:4px 8px;background:#f5f5f5;border:1px solid var(--line);border-radius:4px;cursor:pointer;color:var(--danger);font-weight:600;">✕</button></td>
                `;
                return tr;
            }

            function getRows() {
                return Array.from(itemsBody.querySelectorAll('tr'));
            }

            function refreshPreview() {
                document.getElementById('cfPrevDate').textContent = formatDisplayDate(dateInput.value);
                document.getElementById('cfPrevCompany').textContent = (companyInput.value || '—').toUpperCase();
                document.getElementById('cfPrevAddress').textContent = (addressInput.value || '—').toUpperCase();
                document.getElementById('cfPrevAttention').textContent = (attentionInput.value || '—').toUpperCase();
                document.getElementById('cfPrevRe').textContent = (reInput.value || '—').toUpperCase();
                document.getElementById('cfPrevOfficerName').textContent = (officerNameInput.value || '\u00a0').toUpperCase();
                document.getElementById('cfPrevOfficerTitle').textContent = officerTitleInput.value || 'Collection Officer';

                let total = 0;
                const rows = getRows();
                prevItemsBody.innerHTML = '';

                const usable = rows.filter((row) => {
                    const desc = row.querySelector('.cf-item-desc')?.value.trim();
                    const amount = parseAmount(row.querySelector('.cf-item-amount')?.value);
                    const drsi = row.querySelector('.cf-item-drsi')?.value.trim();
                    const qty = row.querySelector('.cf-item-qty')?.value.trim();
                    return desc || amount || drsi || qty;
                });

                if (!usable.length) {
                    const empty = document.createElement('tr');
                    empty.innerHTML = '<td class="cf-center">&nbsp;</td><td class="cf-center">&nbsp;</td><td class="cf-center">&nbsp;</td><td>&nbsp;</td><td class="cf-amt">&nbsp;</td>';
                    prevItemsBody.appendChild(empty);
                } else {
                    usable.forEach((row) => {
                        const amount = parseAmount(row.querySelector('.cf-item-amount')?.value);
                        total += amount;
                        const tr = document.createElement('tr');
                        const dateVal = row.querySelector('.cf-item-date')?.value || '';
                        tr.innerHTML = `
                            <td class="cf-center">${formatShortDate(dateVal) || '&nbsp;'}</td>
                            <td class="cf-center">${(row.querySelector('.cf-item-drsi')?.value || '').toUpperCase() || '&nbsp;'}</td>
                            <td class="cf-center">${(row.querySelector('.cf-item-qty')?.value || '').toUpperCase() || '&nbsp;'}</td>
                            <td>${(row.querySelector('.cf-item-desc')?.value || '').toUpperCase() || '&nbsp;'}</td>
                            <td class="cf-amt">${formatTableAmount(amount)}</td>
                        `;
                        prevItemsBody.appendChild(tr);
                    });
                }

                // Always sum all row amounts for total (even blank desc)
                total = rows.reduce((sum, row) => sum + parseAmount(row.querySelector('.cf-item-amount')?.value), 0);

                totalDisplay.textContent = formatPHP(total);
                document.getElementById('cfPrevTotal').textContent = formatTableAmount(total);
                document.getElementById('cfPrevAmountFigures').textContent = formatPHP(total);
                document.getElementById('cfPrevAmountWords').textContent = numberToWords(total);
            }

            itemsBody.addEventListener('input', refreshPreview);
            itemsBody.addEventListener('change', refreshPreview);
            [dateInput, companyInput, addressInput, attentionInput, reInput, officerNameInput, officerTitleInput]
                .forEach((el) => {
                    el.addEventListener('input', refreshPreview);
                    el.addEventListener('change', refreshPreview);
                });
            bindMoneyInputs(itemsBody, '.cf-item-amount');

            itemsBody.addEventListener('click', (e) => {
                const btn = e.target.closest('.cf-row-remove');
                if (!btn) return;
                const rows = getRows();
                if (rows.length <= 1) {
                    rows[0].querySelectorAll('input, textarea').forEach((el) => {
                        if (el.classList.contains('cf-item-amount')) el.value = '0.00';
                        else el.value = '';
                    });
                } else {
                    btn.closest('tr').remove();
                }
                refreshPreview();
            });

            document.getElementById('cfAddRow').addEventListener('click', () => {
                itemsBody.appendChild(createRow());
                refreshPreview();
            });

            document.getElementById('cfPrint').addEventListener('click', async () => {
                await runCollectionPdf('print');
            });
            const cfSaveBtn = document.getElementById('cfSave');
            if (cfSaveBtn) {
                cfSaveBtn.addEventListener('click', async () => {
                    await runCollectionPdf('save');
                });
            }

            async function runCollectionPdf(mode) {
                const url = new URL(window.location);
                url.searchParams.set('tab', 'collection-form-tab');
                window.history.pushState({}, '', url);
                activateTab('collection-form-tab');

                const docEl = document.getElementById('cfDocument');
                if (!docEl) {
                    alert('Collection form preview not found.');
                    return;
                }
                if (typeof html2canvas === 'undefined' || !(window.jspdf && window.jspdf.jsPDF)) {
                    alert('PDF libraries failed to load. Please refresh and try again.');
                    return;
                }

                const btn = document.getElementById(mode === 'save' ? 'cfSave' : 'cfPrint');
                const prevLabel = btn ? btn.textContent : '';
                if (btn) {
                    btn.disabled = true;
                    btn.textContent = mode === 'save' ? 'Saving…' : 'Preparing…';
                }

                let holder = null;
                try {
                    // Full A4 content width @ 96dpi (210mm - 20mm margins ≈ 718px)
                    const pageW = 718;
                    const headerImg = docEl.querySelector('.doc-header img');
                    const headerSrc = headerImg ? headerImg.src : '';
                    const bodyNode = docEl.querySelector('.cf-doc-body');

                    holder = document.createElement('div');
                    holder.id = 'cf-print-holder';
                    // Keep in-viewport and visible to layout engine (hidden via visibility)
                    holder.style.cssText = [
                        'position:fixed',
                        'left:0',
                        'top:0',
                        `width:${pageW}px`,
                        'background:#fff',
                        'visibility:hidden',
                        'pointer-events:none',
                        'z-index:-1',
                        'overflow:visible',
                    ].join(';');

                    const styleEl = document.createElement('style');
                    styleEl.textContent = `
                        #cf-print-sheet {
                            width: ${pageW}px !important;
                            max-width: ${pageW}px !important;
                            min-width: ${pageW}px !important;
                            margin: 0 !important;
                            padding: 0 !important;
                            background: #fff !important;
                            color: #111 !important;
                            font-family: "Times New Roman", Times, serif !important;
                            font-size: 13px !important;
                            line-height: 1.45 !important;
                            box-sizing: border-box !important;
                            overflow: visible !important;
                            border: none !important;
                            box-shadow: none !important;
                            border-radius: 0 !important;
                            position: static !important;
                            display: block !important;
                        }
                        #cf-print-sheet * { box-sizing: border-box !important; }
                        #cf-print-sheet .doc-header,
                        #cf-print-sheet .doc-header img {
                            display: block !important;
                            width: 100% !important;
                            max-width: 100% !important;
                            height: auto !important;
                        }
                        #cf-print-sheet .cf-doc-body {
                            padding: 14px 16px 22px !important;
                            width: 100% !important;
                            max-width: 100% !important;
                        }
                        #cf-print-sheet .cf-meta { margin: 0 0 14px !important; }
                        #cf-print-sheet .cf-meta-row {
                            display: grid !important;
                            grid-template-columns: 88px 12px 1fr !important;
                            gap: 4px !important;
                            margin-bottom: 4px !important;
                        }
                        #cf-print-sheet .cf-label,
                        #cf-print-sheet .cf-colon,
                        #cf-print-sheet .cf-value {
                            font-weight: 700 !important;
                            text-transform: uppercase !important;
                            color: #111 !important;
                        }
                        #cf-print-sheet .cf-value { white-space: pre-wrap !important; word-break: break-word !important; }
                        #cf-print-sheet .cf-salutation { margin: 14px 0 8px !important; font-weight: 700 !important; }
                        #cf-print-sheet .cf-intro { margin: 0 0 14px !important; text-align: justify !important; }
                        #cf-print-sheet .cf-amount-words,
                        #cf-print-sheet .cf-amount-figures { font-weight: 700 !important; text-transform: uppercase !important; }
                        #cf-print-sheet table,
                        #cf-print-sheet table.cf-items {
                            width: 100% !important;
                            min-width: 0 !important;
                            max-width: 100% !important;
                            border-collapse: collapse !important;
                            table-layout: fixed !important;
                            margin: 0 0 16px !important;
                            font-size: 12px !important;
                        }
                        #cf-print-sheet .cf-col-date { width: 14% !important; }
                        #cf-print-sheet .cf-col-drsi { width: 16% !important; }
                        #cf-print-sheet .cf-col-qty { width: 12% !important; }
                        #cf-print-sheet .cf-col-desc { width: 35% !important; }
                        #cf-print-sheet .cf-col-amt { width: 23% !important; }
                        #cf-print-sheet .cf-items th,
                        #cf-print-sheet .cf-items td {
                            border: 1px solid #222 !important;
                            padding: 6px 7px !important;
                            vertical-align: top !important;
                            word-break: break-word !important;
                            color: #111 !important;
                        }
                        #cf-print-sheet .cf-items th {
                            background: #f3f4f6 !important;
                            color: #000 !important;
                            font-weight: 700 !important;
                            text-align: center !important;
                            text-transform: uppercase !important;
                            font-size: 10.5px !important;
                        }
                        #cf-print-sheet .cf-amt { text-align: right !important; white-space: nowrap !important; font-size: 11px !important; }
                        #cf-print-sheet .cf-center { text-align: center !important; }
                        #cf-print-sheet .cf-total-row td { font-weight: 700 !important; }
                        #cf-print-sheet .cf-total-label { text-align: right !important; padding-right: 12px !important; }
                        #cf-print-sheet .cf-closing { margin: 0 0 24px !important; text-align: justify !important; }
                        #cf-print-sheet .cf-signs { display: grid !important; grid-template-columns: 1fr 1fr !important; gap: 36px !important; }
                        #cf-print-sheet .cf-officer-name { margin-top: 44px !important; font-weight: 700 !important; text-transform: uppercase !important; }
                        #cf-print-sheet .cf-officer-title { font-size: 12px !important; }
                        #cf-print-sheet .cf-received { font-weight: 700 !important; text-align: left !important; margin-bottom: 40px !important; }
                        #cf-print-sheet .cf-sign-line { border-bottom: 1px solid #222 !important; height: 28px !important; margin: 0 12px 6px !important; }
                        #cf-print-sheet .cf-sign-caption { font-size: 11px !important; font-weight: 700 !important; text-transform: uppercase !important; text-align: center !important; }
                        #cf-print-sheet .cf-sign-right { text-align: center !important; }
                    `;

                    const sheet = document.createElement('div');
                    sheet.id = 'cf-print-sheet';

                    const header = document.createElement('header');
                    header.className = 'doc-header';
                    const img = document.createElement('img');
                    img.crossOrigin = 'anonymous';
                    img.src = headerSrc;
                    img.alt = '';
                    header.appendChild(img);
                    sheet.appendChild(header);

                    const bodyClone = bodyNode ? bodyNode.cloneNode(true) : document.createElement('div');
                    bodyClone.className = 'cf-doc-body';
                    sheet.appendChild(bodyClone);

                    holder.appendChild(styleEl);
                    holder.appendChild(sheet);
                    document.body.appendChild(holder);

                    await new Promise((resolve) => {
                        if (img.complete && img.naturalWidth) resolve();
                        else {
                            img.onload = resolve;
                            img.onerror = resolve;
                            setTimeout(resolve, 2000);
                        }
                    });
                    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

                    const canvas = await html2canvas(sheet, {
                        scale: 2,
                        useCORS: true,
                        allowTaint: true,
                        backgroundColor: '#ffffff',
                        logging: false,
                        scrollX: 0,
                        scrollY: 0,
                        windowWidth: pageW,
                        width: pageW,
                        onclone: (clonedDoc) => {
                            const clonedSheet = clonedDoc.getElementById('cf-print-sheet');
                            if (clonedSheet) {
                                clonedSheet.style.visibility = 'visible';
                                clonedSheet.style.width = pageW + 'px';
                            }
                            const clonedHolder = clonedDoc.getElementById('cf-print-holder');
                            if (clonedHolder) clonedHolder.style.visibility = 'visible';
                        },
                    });

                    const { jsPDF } = window.jspdf;
                    const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
                    const margin = 10;
                    const usableW = 210 - margin * 2;
                    const usableH = 297 - margin * 2;

                    // Stretch image to full printable width so it is not tiny in the corner
                    const imgW = usableW;
                    const imgH = (canvas.height * imgW) / canvas.width;
                    const imgData = canvas.toDataURL('image/jpeg', 0.98);

                    let y = margin;
                    let remaining = imgH;
                    let srcY = 0;
                    const pxPerMm = canvas.height / imgH;

                    // Single page if it fits; otherwise slice across pages
                    if (imgH <= usableH) {
                        pdf.addImage(imgData, 'JPEG', margin, margin, imgW, imgH);
                    } else {
                        let page = 0;
                        while (remaining > 0.5) {
                            if (page > 0) pdf.addPage();
                            const sliceH = Math.min(usableH, remaining);
                            const sliceCanvas = document.createElement('canvas');
                            sliceCanvas.width = canvas.width;
                            sliceCanvas.height = Math.max(1, Math.round(sliceH * pxPerMm));
                            const ctx = sliceCanvas.getContext('2d');
                            ctx.fillStyle = '#fff';
                            ctx.fillRect(0, 0, sliceCanvas.width, sliceCanvas.height);
                            ctx.drawImage(
                                canvas,
                                0, Math.round(srcY * pxPerMm),
                                canvas.width, sliceCanvas.height,
                                0, 0,
                                sliceCanvas.width, sliceCanvas.height
                            );
                            pdf.addImage(sliceCanvas.toDataURL('image/jpeg', 0.98), 'JPEG', margin, margin, imgW, sliceH);
                            srcY += sliceH;
                            remaining -= sliceH;
                            page += 1;
                            if (page > 10) break;
                        }
                    }

                    const pdfBlob = pdf.output('blob');
                    holder.remove();
                    holder = null;

                    if (mode === 'save') {
                        const company = (companyInput.value || '').trim() || 'Collection Form';
                        const dateVal = dateInput.value || todayISO();
                        await uploadSalesDocumentPdf({
                            blob: pdfBlob,
                            documentType: 'collection_form',
                            title: `Collection Form – ${company}`,
                            reference: dateVal,
                            fileName: `collection_form_${dateVal}`,
                        });
                        alert('Collection form PDF saved to the database.');
                        goToSavedDocuments();
                    } else {
                        printPdfBlob(pdfBlob);
                    }
                } catch (error) {
                    if (holder) holder.remove();
                    console.error('Collection form PDF error:', error);
                    alert(error && error.message ? error.message : 'Could not prepare the collection form PDF.');
                } finally {
                    if (btn) {
                        btn.disabled = false;
                        btn.textContent = prevLabel;
                    }
                }
            }
            document.getElementById('cfReset').addEventListener('click', () => {
                dateInput.value = todayISO();
                companyInput.value = '';
                addressInput.value = '';
                attentionInput.value = 'ACCOUNTING DEPARTMENT';
                reInput.value = 'STATEMENT OF ACCOUNT';
                officerNameInput.value = '';
                officerTitleInput.value = 'Collection Officer';
                itemsBody.innerHTML = '';
                itemsBody.appendChild(createRow());
                refreshPreview();
            });

            dateInput.value = todayISO();
            refreshPreview();
        })();

        // ══════════════════════════════════════════════════════════════
        // AGEING OF ACCOUNTS
        // ══════════════════════════════════════════════════════════════

        (function initAgeingAccounts() {
            const itemsBody = document.getElementById('aaItemsBody');
            if (!itemsBody) return;

            const asOfInput = document.getElementById('aaAsOfDate');
            const noteInput = document.getElementById('aaNote');
            const prevBody = document.getElementById('aaPrevItemsBody');

            function todayISO() {
                const d = new Date();
                const m = String(d.getMonth() + 1).padStart(2, '0');
                const day = String(d.getDate()).padStart(2, '0');
                return `${d.getFullYear()}-${m}-${day}`;
            }

            function formatDisplayDate(iso) {
                if (!iso) return '—';
                const d = new Date(iso + 'T00:00:00');
                if (Number.isNaN(d.getTime())) return iso;
                const months = ['JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE',
                    'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER'];
                return `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
            }

            function formatShortDate(iso) {
                if (!iso) return '';
                const d = new Date(iso + 'T00:00:00');
                if (Number.isNaN(d.getTime())) return iso;
                return `${d.getMonth() + 1}/${d.getDate()}/${String(d.getFullYear()).slice(-2)}`;
            }

            function parseAmount(val) {
                return parseMoney(val);
            }

            function formatMoneyLocal(num) {
                return formatMoney(num);
            }

            function formatPHP(num) {
                return 'PHP ' + formatMoney(num);
            }

            function escapeHtml(str) {
                return String(str || '')
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;');
            }

            function createRow() {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><input type="date" class="aa-item-date"></td>
                    <td><input type="text" class="aa-item-customer" placeholder="CUSTOMER NAME"></td>
                    <td><input type="text" class="aa-item-po" placeholder="PO No."></td>
                    <td><input type="text" class="aa-item-agent" placeholder="Agent"></td>
                    <td><input type="text" class="aa-item-bi" placeholder="BI#"></td>
                    <td><input type="text" class="aa-item-si" placeholder="SI#"></td>
                    <td><input type="text" class="aa-item-ci" placeholder="CI#"></td>
                    <td><input type="text" class="aa-item-dr" placeholder="DR No."></td>
                    <td><input type="text" class="aa-item-amount" value="0.00" placeholder="0.00" inputmode="decimal" style="text-align:right;"></td>
                    <td><input type="text" class="aa-item-paid" value="0.00" placeholder="0.00" inputmode="decimal" style="text-align:right;"></td>
                    <td><input type="text" class="aa-item-paid-items" placeholder="Paid items"></td>
                    <td style="text-align:center;">
                        <button type="button" class="aa-row-remove"
                            style="padding:4px 8px; background:#f5f5f5; border:1px solid var(--line); border-radius:4px; cursor:pointer; color:var(--danger); font-weight:600;">✕</button>
                    </td>
                `;
                return tr;
            }

            function refreshPreview() {
                document.getElementById('aaPrevTitle').textContent =
                    'AGEING OF ACCOUNTS AS OF ' + formatDisplayDate(asOfInput.value) + '.';
                const note = (noteInput.value || '').trim();
                document.getElementById('aaPrevNote').textContent = note ? note.toUpperCase() : '';

                const rows = Array.from(itemsBody.querySelectorAll('tr'));
                let totalAmount = 0;
                let totalPaid = 0;
                prevBody.innerHTML = '';

                const usable = rows.filter((row) => {
                    const customer = row.querySelector('.aa-item-customer')?.value.trim();
                    const amount = parseAmount(row.querySelector('.aa-item-amount')?.value);
                    const paid = parseAmount(row.querySelector('.aa-item-paid')?.value);
                    const po = row.querySelector('.aa-item-po')?.value.trim();
                    const agent = row.querySelector('.aa-item-agent')?.value.trim();
                    const dr = row.querySelector('.aa-item-dr')?.value.trim();
                    return customer || amount || paid || po || agent || dr;
                });

                if (!usable.length) {
                    const empty = document.createElement('tr');
                    empty.innerHTML = '<td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td class="aa-num">&nbsp;</td><td class="aa-num">&nbsp;</td><td>&nbsp;</td>';
                    prevBody.appendChild(empty);
                } else {
                    usable.forEach((row) => {
                        const amount = parseAmount(row.querySelector('.aa-item-amount')?.value);
                        const paid = parseAmount(row.querySelector('.aa-item-paid')?.value);
                        totalAmount += amount;
                        totalPaid += paid;
                        const tr = document.createElement('tr');
                        const dateVal = row.querySelector('.aa-item-date')?.value || '';
                        const amountText = formatMoney(amount);
                        const paidText = formatMoney(paid);
                        tr.innerHTML = `
                            <td>${escapeHtml(formatShortDate(dateVal) || (dateVal ? dateVal : '\u00a0'))}</td>
                            <td>${escapeHtml((row.querySelector('.aa-item-customer')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-center">${escapeHtml((row.querySelector('.aa-item-po')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-center">${escapeHtml((row.querySelector('.aa-item-agent')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-center">${escapeHtml((row.querySelector('.aa-item-bi')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-center">${escapeHtml((row.querySelector('.aa-item-si')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-center">${escapeHtml((row.querySelector('.aa-item-ci')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-center">${escapeHtml((row.querySelector('.aa-item-dr')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-num">${escapeHtml(amountText)}</td>
                            <td class="aa-num">${escapeHtml(paidText)}</td>
                            <td>${escapeHtml((row.querySelector('.aa-item-paid-items')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                        `;
                        prevBody.appendChild(tr);
                    });
                }

                totalAmount = rows.reduce((s, row) => s + parseAmount(row.querySelector('.aa-item-amount')?.value), 0);
                totalPaid = rows.reduce((s, row) => s + parseAmount(row.querySelector('.aa-item-paid')?.value), 0);

                document.getElementById('aaTotalAmount').textContent = formatPHP(totalAmount);
                document.getElementById('aaTotalPaid').textContent = formatPHP(totalPaid);
                document.getElementById('aaPrevTotalAmount').textContent = formatMoney(totalAmount);
                document.getElementById('aaPrevTotalPaid').textContent = formatMoney(totalPaid);
            }

            itemsBody.addEventListener('input', refreshPreview);
            itemsBody.addEventListener('change', refreshPreview);
            asOfInput.addEventListener('input', refreshPreview);
            asOfInput.addEventListener('change', refreshPreview);
            noteInput.addEventListener('input', refreshPreview);
            bindMoneyInputs(itemsBody, '.aa-item-amount, .aa-item-paid');

            itemsBody.addEventListener('click', (e) => {
                const btn = e.target.closest('.aa-row-remove');
                if (!btn) return;
                const rows = itemsBody.querySelectorAll('tr');
                if (rows.length <= 1) {
                    rows[0].querySelectorAll('input, textarea').forEach((el) => {
                        if (el.classList.contains('aa-item-amount') || el.classList.contains('aa-item-paid')) el.value = '0.00';
                        else el.value = '';
                    });
                } else {
                    btn.closest('tr').remove();
                }
                refreshPreview();
            });

            document.getElementById('aaAddRow').addEventListener('click', () => {
                itemsBody.appendChild(createRow());
                refreshPreview();
            });

            document.getElementById('aaPrint').addEventListener('click', async () => {
                await runAgeingPdf('print');
            });
            const aaSaveBtn = document.getElementById('aaSave');
            if (aaSaveBtn) {
                aaSaveBtn.addEventListener('click', async () => {
                    await runAgeingPdf('save');
                });
            }

            async function runAgeingPdf(mode) {
                const url = new URL(window.location);
                url.searchParams.set('tab', 'ageing-accounts-tab');
                window.history.pushState({}, '', url);
                activateTab('ageing-accounts-tab');

                const docEl = document.getElementById('aaDocument');
                if (!docEl) {
                    alert('Ageing preview not found.');
                    return;
                }
                if (typeof html2canvas === 'undefined' || !(window.jspdf && window.jspdf.jsPDF)) {
                    alert('PDF libraries failed to load. Please refresh and try again.');
                    return;
                }

                const btn = document.getElementById(mode === 'save' ? 'aaSave' : 'aaPrint');
                const prevLabel = btn ? btn.textContent : '';
                if (btn) {
                    btn.disabled = true;
                    btn.textContent = mode === 'save' ? 'Saving…' : 'Preparing…';
                }

                let holder = null;
                try {
                    // Landscape A4 printable width @ 96dpi ≈ (297-16)mm
                    const pageW = 1060;
                    const bodyNode = docEl.querySelector('.aa-doc-body');

                    holder = document.createElement('div');
                    holder.id = 'aa-print-holder';
                    holder.style.cssText = [
                        'position:fixed', 'left:0', 'top:0', `width:${pageW}px`,
                        'background:#fff', 'visibility:hidden', 'pointer-events:none',
                        'z-index:-1', 'overflow:visible'
                    ].join(';');

                    const styleEl = document.createElement('style');
                    styleEl.textContent = `
                        #aa-print-sheet {
                            width: ${pageW}px !important;
                            min-width: ${pageW}px !important;
                            max-width: ${pageW}px !important;
                            background: #fff !important;
                            color: #111 !important;
                            font-family: Arial, Helvetica, sans-serif !important;
                            font-size: 12px !important;
                            box-sizing: border-box !important;
                            padding: 12px 16px 20px !important;
                        }
                        #aa-print-sheet * { box-sizing: border-box !important; }
                        #aa-print-sheet .aa-letterhead {
                            margin: 0 0 12px !important;
                            color: #1d4ed8 !important;
                            font-weight: 700 !important;
                            text-transform: uppercase !important;
                            letter-spacing: 0.02em !important;
                            line-height: 1.4 !important;
                            font-size: 13px !important;
                        }
                        #aa-print-sheet .aa-letterhead .aa-company {
                            font-size: 15px !important;
                            font-weight: 800 !important;
                        }
                        #aa-print-sheet .aa-title {
                            margin: 0 0 12px !important; font-size: 14px !important; font-weight: 800 !important;
                            letter-spacing: 0.04em !important; text-transform: uppercase !important; color: #1d4ed8 !important;
                        }
                        #aa-print-sheet table.aa-items {
                            width: 100% !important; min-width: 0 !important; border-collapse: collapse !important;
                            table-layout: fixed !important; font-size: 10px !important;
                        }
                        #aa-print-sheet .aa-items th, #aa-print-sheet .aa-items td {
                            border: 1px solid #222 !important; padding: 4px 5px !important; vertical-align: top !important;
                            word-break: break-word !important; color: #111 !important;
                        }
                        #aa-print-sheet .aa-items th {
                            background: #dbeafe !important; color: #000 !important; font-weight: 700 !important;
                            text-align: center !important; text-transform: uppercase !important; font-size: 9px !important;
                        }
                        #aa-print-sheet .aa-num { text-align: right !important; white-space: nowrap !important; }
                        #aa-print-sheet .aa-center { text-align: center !important; }
                        #aa-print-sheet .aa-total-row td { font-weight: 700 !important; background: #f8fafc !important; }
                        #aa-print-sheet .aa-total-label { text-align: right !important; }
                    `;

                    const sheet = document.createElement('div');
                    sheet.id = 'aa-print-sheet';
                    const bodyClone = bodyNode ? bodyNode.cloneNode(true) : document.createElement('div');
                    // Flatten: print sheet IS the body content (no Versatec header)
                    while (bodyClone.firstChild) sheet.appendChild(bodyClone.firstChild);
                    holder.appendChild(styleEl);
                    holder.appendChild(sheet);
                    document.body.appendChild(holder);

                    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

                    const canvas = await html2canvas(sheet, {
                        scale: 2,
                        useCORS: true,
                        allowTaint: true,
                        backgroundColor: '#ffffff',
                        logging: false,
                        scrollX: 0,
                        scrollY: 0,
                        windowWidth: pageW,
                        width: pageW,
                        onclone: (clonedDoc) => {
                            const clonedHolder = clonedDoc.getElementById('aa-print-holder');
                            const clonedSheet = clonedDoc.getElementById('aa-print-sheet');
                            if (clonedHolder) clonedHolder.style.visibility = 'visible';
                            if (clonedSheet) {
                                clonedSheet.style.visibility = 'visible';
                                clonedSheet.style.width = pageW + 'px';
                            }
                        },
                    });

                    const { jsPDF } = window.jspdf;
                    const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
                    const margin = 8;
                    const usableW = 297 - margin * 2;
                    const usableH = 210 - margin * 2;
                    const imgW = usableW;
                    const imgH = (canvas.height * imgW) / canvas.width;
                    const imgData = canvas.toDataURL('image/jpeg', 0.98);

                    if (imgH <= usableH) {
                        pdf.addImage(imgData, 'JPEG', margin, margin, imgW, imgH);
                    } else {
                        let remaining = imgH;
                        let srcY = 0;
                        const pxPerMm = canvas.height / imgH;
                        let page = 0;
                        while (remaining > 0.5 && page < 12) {
                            if (page > 0) pdf.addPage();
                            const sliceH = Math.min(usableH, remaining);
                            const sliceCanvas = document.createElement('canvas');
                            sliceCanvas.width = canvas.width;
                            sliceCanvas.height = Math.max(1, Math.round(sliceH * pxPerMm));
                            const ctx = sliceCanvas.getContext('2d');
                            ctx.fillStyle = '#fff';
                            ctx.fillRect(0, 0, sliceCanvas.width, sliceCanvas.height);
                            ctx.drawImage(
                                canvas,
                                0, Math.round(srcY * pxPerMm),
                                canvas.width, sliceCanvas.height,
                                0, 0, sliceCanvas.width, sliceCanvas.height
                            );
                            pdf.addImage(sliceCanvas.toDataURL('image/jpeg', 0.98), 'JPEG', margin, margin, imgW, sliceH);
                            srcY += sliceH;
                            remaining -= sliceH;
                            page += 1;
                        }
                    }

                    const pdfBlob = pdf.output('blob');
                    holder.remove();
                    holder = null;

                    if (mode === 'save') {
                        const asOf = asOfInput.value || todayISO();
                        await uploadSalesDocumentPdf({
                            blob: pdfBlob,
                            documentType: 'ageing_accounts',
                            title: `Ageing of Accounts as of ${asOf}`,
                            reference: asOf,
                            fileName: `ageing_accounts_${asOf}`,
                        });
                        alert('Ageing of Accounts PDF saved to the database.');
                        goToSavedDocuments();
                    } else {
                        printPdfBlob(pdfBlob);
                    }
                } catch (error) {
                    if (holder) holder.remove();
                    console.error('Ageing PDF error:', error);
                    alert(error && error.message ? error.message : 'Could not prepare ageing PDF.');
                } finally {
                    if (btn) {
                        btn.disabled = false;
                        btn.textContent = prevLabel;
                    }
                }
            }

            document.getElementById('aaReset').addEventListener('click', () => {
                asOfInput.value = todayISO();
                noteInput.value = '';
                itemsBody.innerHTML = '';
                itemsBody.appendChild(createRow());
                refreshPreview();
            });

            asOfInput.value = todayISO();
            refreshPreview();
        })();

        // ══════════════════════════════════════════════════════════════
        // RETENTION SUMMARY
        // ══════════════════════════════════════════════════════════════

        (function initRetentionSummary() {
            const itemsBody = document.getElementById('rsItemsBody');
            if (!itemsBody) return;

            const asOfInput = document.getElementById('rsAsOfDate');
            const noteInput = document.getElementById('rsNote');
            const prevBody = document.getElementById('rsPrevItemsBody');

            function todayISO() {
                const d = new Date();
                const m = String(d.getMonth() + 1).padStart(2, '0');
                const day = String(d.getDate()).padStart(2, '0');
                return `${d.getFullYear()}-${m}-${day}`;
            }

            function formatDisplayDate(iso) {
                if (!iso) return '—';
                const d = new Date(iso + 'T00:00:00');
                if (Number.isNaN(d.getTime())) return iso;
                const months = ['JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE',
                    'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER'];
                return `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
            }

            function formatShortDate(iso) {
                if (!iso) return '';
                const d = new Date(iso + 'T00:00:00');
                if (Number.isNaN(d.getTime())) return iso;
                return `${d.getMonth() + 1}/${d.getDate()}/${d.getFullYear()}`;
            }

            function parseAmount(val) {
                return parseMoney(val);
            }

            function parsePercent(val) {
                const n = parseFloat(String(val == null ? '' : val).replace(/[^0-9.-]/g, ''));
                return Number.isFinite(n) ? n : 0;
            }

            function formatPHP(num) {
                return 'PHP ' + formatMoney(num);
            }

            function formatPercent(val) {
                const n = parsePercent(val);
                if (!n && !String(val || '').trim()) return '';
                return n + '%';
            }

            function escapeHtml(str) {
                return String(str || '')
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;');
            }

            function syncRetentionAmount(row) {
                const amountInput = row.querySelector('.rs-item-amount');
                if (!amountInput || amountInput.dataset.auto !== '1') return;
                const trxn = parseAmount(row.querySelector('.rs-item-trxn')?.value);
                const pct = parsePercent(row.querySelector('.rs-item-percent')?.value);
                amountInput.value = formatMoney(trxn * (pct / 100));
            }

            function createRow() {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><input type="date" class="rs-item-date"></td>
                    <td><input type="text" class="rs-item-client" placeholder="CLIENT NAME"></td>
                    <td><input type="text" class="rs-item-trxn" value="0.00" placeholder="0.00" inputmode="decimal" style="text-align:right;"></td>
                    <td><input type="text" class="rs-item-percent" value="10" placeholder="10%" style="text-align:right;"></td>
                    <td><input type="text" class="rs-item-amount" value="0.00" placeholder="0.00" data-auto="1" inputmode="decimal" style="text-align:right;"></td>
                    <td><textarea class="rs-item-remarks" rows="2" placeholder="Remarks"></textarea></td>
                    <td>
                        <div class="rs-flag">
                            <label><input type="checkbox" class="rs-flag-red"> Red remarks</label>
                            <label><input type="checkbox" class="rs-flag-client"> Yellow client</label>
                            <label><input type="checkbox" class="rs-flag-row"> Pink row</label>
                        </div>
                    </td>
                    <td style="text-align:center;">
                        <button type="button" class="rs-row-remove"
                            style="padding:4px 8px; background:#f5f5f5; border:1px solid var(--line); border-radius:4px; cursor:pointer; color:var(--danger); font-weight:600;">✕</button>
                    </td>
                `;
                return tr;
            }

            function refreshPreview() {
                document.getElementById('rsPrevTitle').textContent =
                    'RETENTION SUMMARY AS OF ' + formatDisplayDate(asOfInput.value) + '.';
                const note = (noteInput.value || '').trim();
                document.getElementById('rsPrevNote').textContent = note ? note.toUpperCase() : '';

                const rows = Array.from(itemsBody.querySelectorAll('tr'));
                prevBody.innerHTML = '';

                const usable = rows.filter((row) => {
                    const client = row.querySelector('.rs-item-client')?.value.trim();
                    const trxn = parseAmount(row.querySelector('.rs-item-trxn')?.value);
                    const amount = parseAmount(row.querySelector('.rs-item-amount')?.value);
                    const remarks = row.querySelector('.rs-item-remarks')?.value.trim();
                    const dateVal = row.querySelector('.rs-item-date')?.value;
                    return client || trxn || amount || remarks || dateVal;
                });

                let totalTrxn = 0;
                let totalAmount = 0;

                if (!usable.length) {
                    const empty = document.createElement('tr');
                    empty.innerHTML = '<td>&nbsp;</td><td>&nbsp;</td><td class="rs-num">&nbsp;</td><td class="rs-center">&nbsp;</td><td class="rs-num">&nbsp;</td><td>&nbsp;</td>';
                    prevBody.appendChild(empty);
                } else {
                    usable.forEach((row) => {
                        const trxn = parseAmount(row.querySelector('.rs-item-trxn')?.value);
                        const amount = parseAmount(row.querySelector('.rs-item-amount')?.value);
                        totalTrxn += trxn;
                        totalAmount += amount;
                        const dateVal = row.querySelector('.rs-item-date')?.value || '';
                        const client = (row.querySelector('.rs-item-client')?.value || '').toUpperCase();
                        const pctText = formatPercent(row.querySelector('.rs-item-percent')?.value);
                        const remarks = row.querySelector('.rs-item-remarks')?.value || '';
                        const red = row.querySelector('.rs-flag-red')?.checked;
                        const clientHl = row.querySelector('.rs-flag-client')?.checked;
                        const rowHl = row.querySelector('.rs-flag-row')?.checked;

                        const tr = document.createElement('tr');
                        if (rowHl) tr.classList.add('rs-row-hl');
                        tr.innerHTML = `
                            <td>${escapeHtml(formatShortDate(dateVal) || '\u00a0')}</td>
                            <td class="${clientHl ? 'rs-client-hl' : ''}">${escapeHtml(client) || '&nbsp;'}</td>
                            <td class="rs-num">${escapeHtml(formatMoney(trxn))}</td>
                            <td class="rs-center">${escapeHtml(pctText) || '&nbsp;'}</td>
                            <td class="rs-num">${escapeHtml(formatMoney(amount))}</td>
                            <td class="${red ? 'rs-remarks-red' : ''}">${escapeHtml(remarks) || '&nbsp;'}</td>
                        `;
                        prevBody.appendChild(tr);
                    });
                }

                totalTrxn = rows.reduce((s, row) => s + parseAmount(row.querySelector('.rs-item-trxn')?.value), 0);
                totalAmount = rows.reduce((s, row) => s + parseAmount(row.querySelector('.rs-item-amount')?.value), 0);

                document.getElementById('rsTotalTrxn').textContent = formatPHP(totalTrxn);
                document.getElementById('rsTotalAmount').textContent = formatPHP(totalAmount);
                document.getElementById('rsPrevTotalTrxn').textContent = formatMoney(totalTrxn);
                document.getElementById('rsPrevTotalAmount').textContent = formatMoney(totalAmount);
            }

            itemsBody.addEventListener('input', (e) => {
                const row = e.target.closest('tr');
                if (!row) return;
                if (e.target.classList.contains('rs-item-trxn') || e.target.classList.contains('rs-item-percent')) {
                    syncRetentionAmount(row);
                }
                if (e.target.classList.contains('rs-item-amount')) {
                    e.target.dataset.auto = '0';
                }
                refreshPreview();
            });
            itemsBody.addEventListener('blur', (e) => {
                if (!e.target.classList.contains('rs-item-trxn')) return;
                const row = e.target.closest('tr');
                if (row) syncRetentionAmount(row);
                refreshPreview();
            }, true);
            itemsBody.addEventListener('change', refreshPreview);
            bindMoneyInputs(itemsBody, '.rs-item-trxn, .rs-item-amount');

            asOfInput.addEventListener('input', refreshPreview);
            asOfInput.addEventListener('change', refreshPreview);
            noteInput.addEventListener('input', refreshPreview);

            itemsBody.addEventListener('click', (e) => {
                const btn = e.target.closest('.rs-row-remove');
                if (!btn) return;
                const rows = itemsBody.querySelectorAll('tr');
                if (rows.length <= 1) {
                    const row = rows[0];
                    row.querySelectorAll('input, textarea').forEach((el) => {
                        if (el.type === 'checkbox') el.checked = false;
                        else if (el.classList.contains('rs-item-trxn') || el.classList.contains('rs-item-amount')) el.value = '0.00';
                        else if (el.classList.contains('rs-item-percent')) el.value = '10';
                        else el.value = '';
                    });
                    const amountEl = row.querySelector('.rs-item-amount');
                    if (amountEl) amountEl.dataset.auto = '1';
                } else {
                    btn.closest('tr').remove();
                }
                refreshPreview();
            });

            document.getElementById('rsAddRow').addEventListener('click', () => {
                itemsBody.appendChild(createRow());
                refreshPreview();
            });

            document.getElementById('rsPrint').addEventListener('click', async () => {
                await runRetentionPdf('print');
            });
            const rsSaveBtn = document.getElementById('rsSave');
            if (rsSaveBtn) {
                rsSaveBtn.addEventListener('click', async () => {
                    await runRetentionPdf('save');
                });
            }

            async function runRetentionPdf(mode) {
                const url = new URL(window.location);
                url.searchParams.set('tab', 'retention-summary-tab');
                window.history.pushState({}, '', url);
                activateTab('retention-summary-tab');

                const docEl = document.getElementById('rsDocument');
                if (!docEl) {
                    alert('Retention preview not found.');
                    return;
                }
                if (typeof html2canvas === 'undefined' || !(window.jspdf && window.jspdf.jsPDF)) {
                    alert('PDF libraries failed to load. Please refresh and try again.');
                    return;
                }

                const btn = document.getElementById(mode === 'save' ? 'rsSave' : 'rsPrint');
                const prevLabel = btn ? btn.textContent : '';
                if (btn) {
                    btn.disabled = true;
                    btn.textContent = mode === 'save' ? 'Saving…' : 'Preparing…';
                }

                let holder = null;
                try {
                    const pageW = 1060;
                    const bodyNode = docEl.querySelector('.rs-doc-body');

                    holder = document.createElement('div');
                    holder.id = 'rs-print-holder';
                    holder.style.cssText = [
                        'position:fixed', 'left:0', 'top:0', `width:${pageW}px`,
                        'background:#fff', 'visibility:hidden', 'pointer-events:none',
                        'z-index:-1', 'overflow:visible'
                    ].join(';');

                    const styleEl = document.createElement('style');
                    styleEl.textContent = `
                        #rs-print-sheet {
                            width: ${pageW}px !important;
                            min-width: ${pageW}px !important;
                            max-width: ${pageW}px !important;
                            background: #fff !important;
                            color: #111 !important;
                            font-family: Arial, Helvetica, sans-serif !important;
                            font-size: 12px !important;
                            box-sizing: border-box !important;
                            padding: 12px 16px 20px !important;
                        }
                        #rs-print-sheet * { box-sizing: border-box !important; }
                        #rs-print-sheet .rs-letterhead {
                            margin: 0 0 12px !important;
                            color: #1d4ed8 !important;
                            font-weight: 700 !important;
                            text-transform: uppercase !important;
                            letter-spacing: 0.02em !important;
                            line-height: 1.4 !important;
                            font-size: 13px !important;
                        }
                        #rs-print-sheet .rs-letterhead .rs-company {
                            font-size: 15px !important;
                            font-weight: 800 !important;
                        }
                        #rs-print-sheet .rs-title {
                            margin: 0 0 12px !important; font-size: 14px !important; font-weight: 800 !important;
                            letter-spacing: 0.04em !important; text-transform: uppercase !important; color: #1d4ed8 !important;
                        }
                        #rs-print-sheet table.rs-items {
                            width: 100% !important; min-width: 0 !important; border-collapse: collapse !important;
                            table-layout: fixed !important; font-size: 10px !important;
                        }
                        #rs-print-sheet .rs-items th, #rs-print-sheet .rs-items td {
                            border: 1px solid #222 !important; padding: 4px 5px !important; vertical-align: top !important;
                            word-break: break-word !important; color: #111 !important;
                        }
                        #rs-print-sheet .rs-items th {
                            background: #dbeafe !important; color: #000 !important; font-weight: 700 !important;
                            text-align: center !important; text-transform: uppercase !important; font-size: 9px !important;
                        }
                        #rs-print-sheet .rs-num { text-align: right !important; white-space: nowrap !important; }
                        #rs-print-sheet .rs-center { text-align: center !important; }
                        #rs-print-sheet .rs-total-row td { font-weight: 700 !important; background: #f8fafc !important; }
                        #rs-print-sheet .rs-total-label { text-align: right !important; }
                        #rs-print-sheet .rs-remarks-red { color: #c00 !important; }
                        #rs-print-sheet .rs-client-hl { background: #ffe566 !important; }
                        #rs-print-sheet tr.rs-row-hl td { background: #f8c8d0 !important; }
                        #rs-print-sheet tr.rs-row-hl td.rs-client-hl { background: #ffe566 !important; }
                    `;

                    const sheet = document.createElement('div');
                    sheet.id = 'rs-print-sheet';
                    const bodyClone = bodyNode ? bodyNode.cloneNode(true) : document.createElement('div');
                    while (bodyClone.firstChild) sheet.appendChild(bodyClone.firstChild);
                    holder.appendChild(styleEl);
                    holder.appendChild(sheet);
                    document.body.appendChild(holder);

                    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

                    const canvas = await html2canvas(sheet, {
                        scale: 2,
                        useCORS: true,
                        allowTaint: true,
                        backgroundColor: '#ffffff',
                        logging: false,
                        scrollX: 0,
                        scrollY: 0,
                        windowWidth: pageW,
                        width: pageW,
                        onclone: (clonedDoc) => {
                            const clonedHolder = clonedDoc.getElementById('rs-print-holder');
                            const clonedSheet = clonedDoc.getElementById('rs-print-sheet');
                            if (clonedHolder) clonedHolder.style.visibility = 'visible';
                            if (clonedSheet) {
                                clonedSheet.style.visibility = 'visible';
                                clonedSheet.style.width = pageW + 'px';
                            }
                        },
                    });

                    const { jsPDF } = window.jspdf;
                    const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
                    const margin = 8;
                    const usableW = 297 - margin * 2;
                    const usableH = 210 - margin * 2;
                    const imgW = usableW;
                    const imgH = (canvas.height * imgW) / canvas.width;
                    const imgData = canvas.toDataURL('image/jpeg', 0.98);

                    if (imgH <= usableH) {
                        pdf.addImage(imgData, 'JPEG', margin, margin, imgW, imgH);
                    } else {
                        let remaining = imgH;
                        let srcY = 0;
                        const pxPerMm = canvas.height / imgH;
                        let page = 0;
                        while (remaining > 0.5 && page < 12) {
                            if (page > 0) pdf.addPage();
                            const sliceH = Math.min(usableH, remaining);
                            const sliceCanvas = document.createElement('canvas');
                            sliceCanvas.width = canvas.width;
                            sliceCanvas.height = Math.max(1, Math.round(sliceH * pxPerMm));
                            const ctx = sliceCanvas.getContext('2d');
                            ctx.fillStyle = '#fff';
                            ctx.fillRect(0, 0, sliceCanvas.width, sliceCanvas.height);
                            ctx.drawImage(
                                canvas,
                                0, Math.round(srcY * pxPerMm),
                                canvas.width, sliceCanvas.height,
                                0, 0, sliceCanvas.width, sliceCanvas.height
                            );
                            pdf.addImage(sliceCanvas.toDataURL('image/jpeg', 0.98), 'JPEG', margin, margin, imgW, sliceH);
                            srcY += sliceH;
                            remaining -= sliceH;
                            page += 1;
                        }
                    }

                    const pdfBlob = pdf.output('blob');
                    holder.remove();
                    holder = null;

                    if (mode === 'save') {
                        const asOf = asOfInput.value || todayISO();
                        await uploadSalesDocumentPdf({
                            blob: pdfBlob,
                            documentType: 'retention_summary',
                            title: `Retention Summary as of ${asOf}`,
                            reference: asOf,
                            fileName: `retention_summary_${asOf}`,
                        });
                        alert('Retention Summary PDF saved to the database.');
                        goToSavedDocuments();
                    } else {
                        printPdfBlob(pdfBlob);
                    }
                } catch (error) {
                    if (holder) holder.remove();
                    console.error('Retention PDF error:', error);
                    alert(error && error.message ? error.message : 'Could not prepare retention summary PDF.');
                } finally {
                    if (btn) {
                        btn.disabled = false;
                        btn.textContent = prevLabel;
                    }
                }
            }

            document.getElementById('rsReset').addEventListener('click', () => {
                asOfInput.value = todayISO();
                noteInput.value = '';
                itemsBody.innerHTML = '';
                itemsBody.appendChild(createRow());
                refreshPreview();
            });

            asOfInput.value = todayISO();
            refreshPreview();
        })();

        // ══════════════════════════════════════════════════════════════
        // PETTY CASH / REVOLVING FUND REPLENISHMENT REPORT
        // ══════════════════════════════════════════════════════════════

        (function initPettyCash() {
            const itemsBody = document.getElementById('pcItemsBody');
            if (!itemsBody) return;

            const reprInput = document.getElementById('pcReprNumber');
            const reportDateInput = document.getElementById('pcReportDate');
            const noteInput = document.getElementById('pcNote');
            const prevBody = document.getElementById('pcPrevItemsBody');

            const CAT_FIELDS = [
                'input-tax', 'fuel', 'fare', 'lodging', 'meal', 'purchases',
                'repair', 'freight', 'meeting', 'office', 'communication',
                'bidding', 'fines', 'misc'
            ];

            function todayISO() {
                const d = new Date();
                const m = String(d.getMonth() + 1).padStart(2, '0');
                const day = String(d.getDate()).padStart(2, '0');
                return `${d.getFullYear()}-${m}-${day}`;
            }

            function formatDisplayDate(iso) {
                if (!iso) return '—';
                const d = new Date(iso + 'T00:00:00');
                if (Number.isNaN(d.getTime())) return iso;
                const months = ['JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE',
                    'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER'];
                return `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
            }

            function formatShortDate(iso) {
                if (!iso) return '';
                const d = new Date(iso + 'T00:00:00');
                if (Number.isNaN(d.getTime())) return iso;
                return `${d.getMonth() + 1}/${d.getDate()}/${d.getFullYear()}`;
            }

            function escapeHtml(str) {
                return String(str || '')
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;');
            }

            function catSum(row) {
                return CAT_FIELDS.reduce((s, key) => s + parseMoney(row.querySelector('.pc-item-' + key)?.value), 0);
            }

            function syncCash(row) {
                const cashInput = row.querySelector('.pc-item-cash');
                if (!cashInput || cashInput.dataset.auto !== '1') return;
                cashInput.value = formatMoney(catSum(row));
            }

            function moneyCellsHtml() {
                return CAT_FIELDS.map((key) =>
                    `<td><input type="text" class="pc-item-${key} pc-money pc-cat" value="0.00" inputmode="decimal" style="text-align:right;"></td>`
                ).join('');
            }

            function createRow() {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><input type="date" class="pc-item-date"></td>
                    <td><input type="text" class="pc-item-particulars" placeholder="Name"></td>
                    <td><input type="text" class="pc-item-explanation" placeholder="Explanation"></td>
                    <td><input type="text" class="pc-item-tin" placeholder="TIN"></td>
                    <td><input type="text" class="pc-item-pcv" placeholder="PCV#"></td>
                    <td><input type="text" class="pc-item-cash pc-money" value="0.00" data-auto="1" inputmode="decimal" style="text-align:right;"></td>
                    ${moneyCellsHtml()}
                    <td style="text-align:center;">
                        <button type="button" class="pc-row-remove"
                            style="padding:4px 8px; background:#f5f5f5; border:1px solid var(--line); border-radius:4px; cursor:pointer; color:var(--danger); font-weight:600;">✕</button>
                    </td>
                `;
                return tr;
            }

            function blankMoney(n) {
                return n ? formatMoney(n) : '&nbsp;';
            }

            function refreshPreview() {
                const repr = (reprInput.value || '').trim() || '—';
                document.getElementById('pcPrevMeta').textContent =
                    `REPR # ${repr}    DATE: ${formatDisplayDate(reportDateInput.value)}`;
                const note = (noteInput.value || '').trim();
                document.getElementById('pcPrevNote').textContent = note ? note.toUpperCase() : '';

                const rows = Array.from(itemsBody.querySelectorAll('tr'));
                const usable = rows.filter((row) => {
                    const particulars = row.querySelector('.pc-item-particulars')?.value.trim();
                    const explanation = row.querySelector('.pc-item-explanation')?.value.trim();
                    const cash = parseMoney(row.querySelector('.pc-item-cash')?.value);
                    const dateVal = row.querySelector('.pc-item-date')?.value;
                    return particulars || explanation || cash || dateVal || catSum(row);
                });

                const totals = { cash: 0 };
                CAT_FIELDS.forEach((k) => { totals[k] = 0; });
                prevBody.innerHTML = '';

                if (!usable.length) {
                    const empty = document.createElement('tr');
                    empty.innerHTML = '<td colspan="20" style="text-align:center;">&nbsp;</td>';
                    prevBody.appendChild(empty);
                } else {
                    usable.forEach((row) => {
                        const cash = parseMoney(row.querySelector('.pc-item-cash')?.value);
                        totals.cash += cash;
                        const vals = {};
                        CAT_FIELDS.forEach((k) => {
                            vals[k] = parseMoney(row.querySelector('.pc-item-' + k)?.value);
                            totals[k] += vals[k];
                        });
                        const dateVal = row.querySelector('.pc-item-date')?.value || '';
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td>${escapeHtml(formatShortDate(dateVal) || '\u00a0')}</td>
                            <td>${escapeHtml((row.querySelector('.pc-item-particulars')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td>${escapeHtml((row.querySelector('.pc-item-explanation')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="pc-center">${escapeHtml(row.querySelector('.pc-item-tin')?.value || '') || '&nbsp;'}</td>
                            <td class="pc-center">${escapeHtml(row.querySelector('.pc-item-pcv')?.value || '') || '&nbsp;'}</td>
                            <td class="pc-num">${blankMoney(cash)}</td>
                            ${CAT_FIELDS.map((k) => `<td class="pc-num">${blankMoney(vals[k])}</td>`).join('')}
                        `;
                        prevBody.appendChild(tr);
                    });
                }

                // Totals from all form rows
                totals.cash = rows.reduce((s, row) => s + parseMoney(row.querySelector('.pc-item-cash')?.value), 0);
                CAT_FIELDS.forEach((k) => {
                    totals[k] = rows.reduce((s, row) => s + parseMoney(row.querySelector('.pc-item-' + k)?.value), 0);
                });

                document.getElementById('pcTotalCash').textContent = 'PHP ' + formatMoney(totals.cash);
                document.getElementById('pcPrevTotalCash').textContent = formatMoney(totals.cash);
                const idMap = {
                    'input-tax': 'pcPrevTotalInputTax',
                    fuel: 'pcPrevTotalFuel',
                    fare: 'pcPrevTotalFare',
                    lodging: 'pcPrevTotalLodging',
                    meal: 'pcPrevTotalMeal',
                    purchases: 'pcPrevTotalPurchases',
                    repair: 'pcPrevTotalRepair',
                    freight: 'pcPrevTotalFreight',
                    meeting: 'pcPrevTotalMeeting',
                    office: 'pcPrevTotalOffice',
                    communication: 'pcPrevTotalCommunication',
                    bidding: 'pcPrevTotalBidding',
                    fines: 'pcPrevTotalFines',
                    misc: 'pcPrevTotalMisc',
                };
                CAT_FIELDS.forEach((k) => {
                    const el = document.getElementById(idMap[k]);
                    if (el) el.textContent = formatMoney(totals[k]);
                });
            }

            itemsBody.addEventListener('input', (e) => {
                const row = e.target.closest('tr');
                if (!row) return;
                if (e.target.classList.contains('pc-cat')) syncCash(row);
                if (e.target.classList.contains('pc-item-cash')) e.target.dataset.auto = '0';
                refreshPreview();
            });
            itemsBody.addEventListener('change', refreshPreview);
            bindMoneyInputs(itemsBody, '.pc-money');

            [reprInput, reportDateInput, noteInput].forEach((el) => {
                el.addEventListener('input', refreshPreview);
                el.addEventListener('change', refreshPreview);
            });

            itemsBody.addEventListener('click', (e) => {
                const btn = e.target.closest('.pc-row-remove');
                if (!btn) return;
                const rows = itemsBody.querySelectorAll('tr');
                if (rows.length <= 1) {
                    const row = rows[0];
                    row.querySelectorAll('input').forEach((el) => {
                        if (el.classList.contains('pc-money')) el.value = '0.00';
                        else el.value = '';
                    });
                    const cash = row.querySelector('.pc-item-cash');
                    if (cash) cash.dataset.auto = '1';
                } else {
                    btn.closest('tr').remove();
                }
                refreshPreview();
            });

            document.getElementById('pcAddRow').addEventListener('click', () => {
                itemsBody.appendChild(createRow());
                refreshPreview();
            });

            async function runPettyCashPdf(mode) {
                const url = new URL(window.location);
                url.searchParams.set('tab', 'petty-cash-tab');
                window.history.pushState({}, '', url);
                activateTab('petty-cash-tab');

                const docEl = document.getElementById('pcDocument');
                if (!docEl) {
                    alert('Petty cash preview not found.');
                    return;
                }
                if (typeof html2canvas === 'undefined' || !(window.jspdf && window.jspdf.jsPDF)) {
                    alert('PDF libraries failed to load. Please refresh and try again.');
                    return;
                }

                const btn = document.getElementById(mode === 'save' ? 'pcSave' : 'pcPrint');
                const prevLabel = btn ? btn.textContent : '';
                if (btn) {
                    btn.disabled = true;
                    btn.textContent = mode === 'save' ? 'Saving…' : 'Preparing…';
                }

                let holder = null;
                try {
                    const pageW = 1500;
                    const bodyNode = docEl.querySelector('.pc-doc-body');

                    holder = document.createElement('div');
                    holder.id = 'pc-print-holder';
                    holder.style.cssText = [
                        'position:fixed', 'left:0', 'top:0', `width:${pageW}px`,
                        'background:#fff', 'visibility:hidden', 'pointer-events:none',
                        'z-index:-1', 'overflow:visible'
                    ].join(';');

                    const styleEl = document.createElement('style');
                    styleEl.textContent = `
                        #pc-print-sheet {
                            width: ${pageW}px !important;
                            background: #fff !important;
                            color: #111 !important;
                            font-family: Arial, Helvetica, sans-serif !important;
                            font-size: 10px !important;
                            box-sizing: border-box !important;
                            padding: 10px 12px 16px !important;
                        }
                        #pc-print-sheet * { box-sizing: border-box !important; }
                        #pc-print-sheet .pc-letterhead {
                            margin: 0 0 8px !important; color: #1d4ed8 !important; font-weight: 700 !important;
                            text-transform: uppercase !important; line-height: 1.35 !important; font-size: 11px !important;
                        }
                        #pc-print-sheet .pc-company { font-size: 13px !important; font-weight: 800 !important; }
                        #pc-print-sheet .pc-title {
                            margin: 0 0 4px !important; font-size: 13px !important; font-weight: 800 !important;
                            text-align: center !important; text-transform: uppercase !important; color: #1d4ed8 !important;
                        }
                        #pc-print-sheet .pc-meta {
                            margin: 0 0 10px !important; font-size: 11px !important; font-weight: 700 !important;
                            text-align: center !important; text-transform: uppercase !important;
                        }
                        #pc-print-sheet table.pc-items {
                            width: 100% !important; min-width: 0 !important; border-collapse: collapse !important;
                            table-layout: fixed !important; font-size: 7.5px !important;
                        }
                        #pc-print-sheet .pc-items th, #pc-print-sheet .pc-items td {
                            border: 1px solid #222 !important; padding: 2px 2px !important; vertical-align: top !important;
                            word-break: break-word !important; color: #111 !important;
                        }
                        #pc-print-sheet .pc-items th {
                            background: #e5e7eb !important; font-weight: 700 !important; text-align: center !important;
                            text-transform: uppercase !important; font-size: 6.5px !important; line-height: 1.15 !important;
                        }
                        #pc-print-sheet .pc-num { text-align: right !important; white-space: nowrap !important; }
                        #pc-print-sheet .pc-center { text-align: center !important; }
                        #pc-print-sheet .pc-total-row td { font-weight: 700 !important; background: #f8fafc !important; }
                        #pc-print-sheet .pc-total-label { text-align: right !important; }
                    `;

                    const sheet = document.createElement('div');
                    sheet.id = 'pc-print-sheet';
                    const bodyClone = bodyNode ? bodyNode.cloneNode(true) : document.createElement('div');
                    while (bodyClone.firstChild) sheet.appendChild(bodyClone.firstChild);
                    holder.appendChild(styleEl);
                    holder.appendChild(sheet);
                    document.body.appendChild(holder);

                    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

                    const canvas = await html2canvas(sheet, {
                        scale: 2,
                        useCORS: true,
                        allowTaint: true,
                        backgroundColor: '#ffffff',
                        logging: false,
                        scrollX: 0,
                        scrollY: 0,
                        windowWidth: pageW,
                        width: pageW,
                        onclone: (clonedDoc) => {
                            const clonedHolder = clonedDoc.getElementById('pc-print-holder');
                            const clonedSheet = clonedDoc.getElementById('pc-print-sheet');
                            if (clonedHolder) clonedHolder.style.visibility = 'visible';
                            if (clonedSheet) {
                                clonedSheet.style.visibility = 'visible';
                                clonedSheet.style.width = pageW + 'px';
                            }
                        },
                    });

                    const { jsPDF } = window.jspdf;
                    const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
                    const margin = 6;
                    const usableW = 297 - margin * 2;
                    const usableH = 210 - margin * 2;
                    const imgW = usableW;
                    const imgH = (canvas.height * imgW) / canvas.width;
                    const imgData = canvas.toDataURL('image/jpeg', 0.96);

                    if (imgH <= usableH) {
                        pdf.addImage(imgData, 'JPEG', margin, margin, imgW, imgH);
                    } else {
                        let remaining = imgH;
                        let srcY = 0;
                        const pxPerMm = canvas.height / imgH;
                        let page = 0;
                        while (remaining > 0.5 && page < 16) {
                            if (page > 0) pdf.addPage();
                            const sliceH = Math.min(usableH, remaining);
                            const sliceCanvas = document.createElement('canvas');
                            sliceCanvas.width = canvas.width;
                            sliceCanvas.height = Math.max(1, Math.round(sliceH * pxPerMm));
                            const ctx = sliceCanvas.getContext('2d');
                            ctx.fillStyle = '#fff';
                            ctx.fillRect(0, 0, sliceCanvas.width, sliceCanvas.height);
                            ctx.drawImage(
                                canvas,
                                0, Math.round(srcY * pxPerMm),
                                canvas.width, sliceCanvas.height,
                                0, 0, sliceCanvas.width, sliceCanvas.height
                            );
                            pdf.addImage(sliceCanvas.toDataURL('image/jpeg', 0.96), 'JPEG', margin, margin, imgW, sliceH);
                            srcY += sliceH;
                            remaining -= sliceH;
                            page += 1;
                        }
                    }

                    const pdfBlob = pdf.output('blob');
                    holder.remove();
                    holder = null;

                    if (mode === 'save') {
                        const repr = (reprInput.value || '').trim() || reportDateInput.value || todayISO();
                        await uploadSalesDocumentPdf({
                            blob: pdfBlob,
                            documentType: 'petty_cash',
                            title: `Revolving Fund Replenishment Report ${repr}`,
                            reference: repr,
                            fileName: `petty_cash_${repr}`,
                        });
                        alert('Petty cash PDF saved to the database.');
                        goToSavedDocuments();
                    } else {
                        printPdfBlob(pdfBlob);
                    }
                } catch (error) {
                    if (holder) holder.remove();
                    console.error('Petty cash PDF error:', error);
                    alert(error && error.message ? error.message : 'Could not prepare petty cash PDF.');
                } finally {
                    if (btn) {
                        btn.disabled = false;
                        btn.textContent = prevLabel;
                    }
                }
            }

            document.getElementById('pcPrint').addEventListener('click', () => runPettyCashPdf('print'));
            const pcSaveBtn = document.getElementById('pcSave');
            if (pcSaveBtn) pcSaveBtn.addEventListener('click', () => runPettyCashPdf('save'));

            document.getElementById('pcReset').addEventListener('click', () => {
                reprInput.value = '';
                reportDateInput.value = todayISO();
                noteInput.value = '';
                itemsBody.innerHTML = '';
                itemsBody.appendChild(createRow());
                refreshPreview();
            });

            reportDateInput.value = todayISO();
            refreshPreview();
        })();

        // ── Delivery Receipt form + live preview ──
        (function setupDeliveryReceiptTab() {
            const panel = document.getElementById('delivery-receipt-tab');
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

            function syncFieldPreview(field) {
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

            function syncPanelPreviews() {
                panel.querySelectorAll('input, textarea, select').forEach(syncFieldPreview);
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
                        syncFieldPreview(field);
                        updateDeliveryReceiptLinesPreview();
                    });
                    field.addEventListener('change', () => {
                        syncFieldPreview(field);
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
                field.addEventListener('input', () => syncFieldPreview(field));
                field.addEventListener('change', () => syncFieldPreview(field));
            });

            const dateInput = document.getElementById('dr_receipt_date');
            if (dateInput && !dateInput.value) {
                const now = new Date();
                dateInput.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
            }

            const form = document.getElementById('deliveryReceiptForm');
            if (form) {
                form.addEventListener('reset', () => {
                    requestAnimationFrame(() => {
                        form.querySelectorAll('input[type="date"]').forEach((input) => {
                            if (!input.value) {
                                const now = new Date();
                                input.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
                            }
                        });
                        form.querySelectorAll('input[data-auto-number]').forEach((input) => {
                            input.value = input.getAttribute('data-auto-number') || '';
                        });
                        syncPanelPreviews();
                        updateDeliveryReceiptLinesPreview();
                    });
                });
            }

            syncPanelPreviews();
            updateDeliveryReceiptLinesPreview();
        })();

    })();

    // Global handler: capture unhandled promise rejections (helps surface extension errors)
    window.addEventListener('unhandledrejection', function (event) {
        try {
            console.error('Unhandled promise rejection:', event.reason);
            // small transient UI notice so users see something happened
            var note = document.createElement('div');
            note.textContent = 'An unexpected error occurred — check the console for details.';
            note.style.position = 'fixed';
            note.style.right = '16px';
            note.style.bottom = '16px';
            note.style.background = 'rgba(17,17,17,0.96)';
            note.style.color = '#fff';
            note.style.padding = '8px 12px';
            note.style.borderRadius = '6px';
            note.style.zIndex = 99999;
            note.style.fontSize = '13px';
            document.body.appendChild(note);
            setTimeout(function () { try { note.remove(); } catch (e) {} }, 8000);
        } catch (err) {
            // swallow errors from the handler itself
            console.error('Error in unhandledrejection handler', err);
        }
    });
