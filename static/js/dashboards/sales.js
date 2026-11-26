(function () {
        // Tab switching (DOM-driven so new tabs/panels stay in sync)
        const tabs = Array.from(document.querySelectorAll('.sidebar-nav .tab-button[data-tab-target]'));
        const panels = {};
        tabs.forEach((btn) => {
            const id = btn.dataset.tabTarget;
            if (!id) return;
            const panel = document.getElementById(id);
            if (panel) panels[id] = panel;
        });
        Object.keys(panels).forEach((id) => {
            const linkedBtn = tabs.find((btn) => btn.dataset.tabTarget === id);
            if (linkedBtn) linkedBtn.setAttribute('aria-selected', panels[id].classList.contains('is-active') ? 'true' : 'false');
        });

        function resolveActiveTab(preferredId) {
            if (preferredId && panels[preferredId]) return preferredId;
            const serverTab = window.__SALES_CONFIG__ && window.__SALES_CONFIG__.activeTab;
            if (serverTab && panels[serverTab]) return serverTab;
            const domActive = Object.keys(panels).find((id) => panels[id].classList.contains('is-active'));
            if (domActive) return domActive;
            if (panels['sales-tab']) return 'sales-tab';
            return Object.keys(panels)[0] || null;
        }

        // Function to activate a tab
        function activateTab(targetId) {
            const activeId = resolveActiveTab(targetId);
            if (!activeId) return;
            tabs.forEach((btn) => {
                const isTarget = btn.dataset.tabTarget === activeId;
                btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
            });
            Object.keys(panels).forEach((id) => {
                panels[id].classList.toggle('is-active', id === activeId);
            });
            const landscapePrint = ['ageing-accounts-tab', 'retention-summary-tab', 'petty-cash-tab', 'check-voucher-tab'].includes(activeId);
            document.body.classList.toggle('sales-print-landscape', landscapePrint);
            let pageStyle = document.getElementById('sales-print-page-style');
            if (!pageStyle) {
                pageStyle = document.createElement('style');
                pageStyle.id = 'sales-print-page-style';
                document.head.appendChild(pageStyle);
            }
            pageStyle.textContent = landscapePrint
                ? '@media print { @page { size: A4 landscape; margin: 6mm; } }'
                : '';
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
            printFrame.setAttribute('title', 'Print document');
            printFrame.style.cssText = 'position:fixed;left:0;top:0;width:100vw;height:100vh;border:0;opacity:0;pointer-events:none;z-index:-1;';
            printFrame.src = blobUrl;
            document.body.appendChild(printFrame);
            let cleaned = false;
            const cleanup = () => {
                if (cleaned) return;
                cleaned = true;
                printFrame.remove();
                URL.revokeObjectURL(blobUrl);
            };
            printFrame.onload = () => {
                try {
                    const win = printFrame.contentWindow;
                    win.focus();
                    win.addEventListener('afterprint', cleanup);
                    win.print();
                } catch (err) {
                    console.error(err);
                    window.open(blobUrl, '_blank');
                    cleanup();
                }
            };
        }

        async function landscapePdfFromSheet(sheet, { width, margin = 6, maxPages = 16, jpegQuality = 0.96 } = {}) {
            const captureW = Math.max(
                width || 0,
                Math.ceil(sheet.scrollWidth || 0),
                Math.ceil(sheet.offsetWidth || 0)
            );
            sheet.style.width = captureW + 'px';
            sheet.style.minWidth = captureW + 'px';
            sheet.style.maxWidth = 'none';
            sheet.style.overflow = 'visible';

            await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

            const canvas = await html2canvas(sheet, {
                scale: 2,
                useCORS: true,
                allowTaint: true,
                backgroundColor: '#ffffff',
                logging: false,
                scrollX: 0,
                scrollY: 0,
                windowWidth: captureW,
                width: captureW,
                height: Math.ceil(sheet.scrollHeight || sheet.offsetHeight || 0),
                onclone: (clonedDoc) => {
                    const clonedSheet = clonedDoc.getElementById(sheet.id);
                    if (clonedSheet) {
                        clonedSheet.style.visibility = 'visible';
                        clonedSheet.style.width = captureW + 'px';
                        clonedSheet.style.minWidth = captureW + 'px';
                        clonedSheet.style.maxWidth = 'none';
                        clonedSheet.style.overflow = 'visible';
                        if (clonedSheet.parentElement) {
                            clonedSheet.parentElement.style.visibility = 'visible';
                            clonedSheet.parentElement.style.width = captureW + 'px';
                            clonedSheet.parentElement.style.overflow = 'visible';
                        }
                    }
                },
            });

            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
            const usableW = pdf.internal.pageSize.getWidth() - margin * 2;
            const usableH = pdf.internal.pageSize.getHeight() - margin * 2;
            const imgW = usableW;
            const imgH = (canvas.height * imgW) / canvas.width;
            const pagePx = Math.max(1, Math.floor(usableH * canvas.width / imgW) - 8);

            function addCanvasPage(pageCanvas, isFirst) {
                if (!isFirst) pdf.addPage();
                const drawH = (pageCanvas.height * imgW) / pageCanvas.width;
                const fitH = Math.min(drawH, usableH);
                const fitW = drawH > usableH ? (imgW * usableH / drawH) : imgW;
                pdf.addImage(pageCanvas.toDataURL('image/jpeg', jpegQuality), 'JPEG', margin, margin, fitW, fitH);
            }

            function stackSlices(slices) {
                const width = canvas.width;
                const height = Math.max(1, slices.reduce((sum, part) => sum + Math.max(1, Math.round(part.sh)), 0));
                const out = document.createElement('canvas');
                out.width = width;
                out.height = height;
                const ctx = out.getContext('2d');
                ctx.fillStyle = '#fff';
                ctx.fillRect(0, 0, width, height);
                let dy = 0;
                slices.forEach((part) => {
                    const sy = Math.max(0, Math.min(canvas.height - 1, Math.round(part.sy)));
                    const sh = Math.max(1, Math.min(canvas.height - sy, Math.round(part.sh)));
                    ctx.drawImage(canvas, 0, sy, width, sh, 0, dy, width, sh);
                    dy += sh;
                });
                return out;
            }

            function collectTableLayout() {
                const prevSheetVis = sheet.style.visibility;
                const parent = sheet.parentElement;
                const prevParentVis = parent ? parent.style.visibility : '';
                sheet.style.visibility = 'visible';
                if (parent) parent.style.visibility = 'visible';
                try {
                    const scale = canvas.height / Math.max(1, sheet.scrollHeight || sheet.offsetHeight || 1);
                    const origin = sheet.getBoundingClientRect().top;
                    const toY = (el, edge) => {
                        const box = el.getBoundingClientRect();
                        return (box[edge] - origin) * scale;
                    };
                    const table = sheet.querySelector('table');
                    if (!table) return null;
                    const thead = table.tHead;
                    const rows = [];
                    table.querySelectorAll('tbody tr, tfoot tr').forEach((tr) => {
                        rows.push({ top: toY(tr, 'top'), bottom: toY(tr, 'bottom') });
                    });
                    if (!rows.length) return null;
                    return {
                        theadTop: thead ? toY(thead, 'top') : 0,
                        theadBottom: thead ? toY(thead, 'bottom') : 0,
                        rows,
                    };
                } finally {
                    sheet.style.visibility = prevSheetVis;
                    if (parent) parent.style.visibility = prevParentVis;
                }
            }

            function buildRowAwarePages(layout) {
                const pages = [];
                const rows = layout.rows;
                const headerH = Math.max(0, layout.theadBottom - layout.theadTop);
                let i = 0;
                let first = true;
                while (i < rows.length) {
                    if (first) {
                        const startY = 0;
                        let endY = Math.max(layout.theadBottom, startY);
                        let fitted = 0;
                        while (i < rows.length && (rows[i].bottom - startY) <= pagePx) {
                            endY = rows[i].bottom;
                            i += 1;
                            fitted += 1;
                        }
                        if (fitted === 0 && i < rows.length) {
                            endY = Math.min(rows[i].bottom, startY + pagePx);
                            i += 1;
                        }
                        pages.push([{ sy: startY, sh: Math.min(canvas.height, endY) - startY }]);
                        first = false;
                    } else {
                        const startRow = i;
                        const rowStart = rows[startRow].top;
                        let endY = rows[startRow].bottom;
                        let fitted = 0;
                        while (i < rows.length && (headerH + (rows[i].bottom - rowStart)) <= pagePx) {
                            endY = rows[i].bottom;
                            i += 1;
                            fitted += 1;
                        }
                        if (fitted === 0) {
                            endY = Math.min(rows[i].bottom, rowStart + Math.max(pagePx - headerH, 1));
                            i += 1;
                        }
                        const slices = [];
                        if (headerH > 1) {
                            slices.push({ sy: layout.theadTop, sh: headerH });
                        }
                        slices.push({ sy: rowStart, sh: endY - rowStart });
                        pages.push(slices);
                    }
                    if (pages.length >= maxPages) break;
                }
                return pages;
            }

            if (imgH <= usableH) {
                pdf.addImage(canvas.toDataURL('image/jpeg', jpegQuality), 'JPEG', margin, margin, imgW, imgH);
            } else {
                const layout = collectTableLayout();
                const rowPages = layout ? buildRowAwarePages(layout) : null;
                if (rowPages && rowPages.length) {
                    rowPages.forEach((slices, idx) => addCanvasPage(stackSlices(slices), idx === 0));
                } else {
                    let remaining = imgH;
                    let srcY = 0;
                    const pxPerMm = canvas.height / imgH;
                    let page = 0;
                    while (remaining > 0.5 && page < maxPages) {
                        const sliceH = Math.min(usableH, remaining);
                        addCanvasPage(stackSlices([{
                            sy: srcY * pxPerMm,
                            sh: sliceH * pxPerMm,
                        }]), page === 0);
                        srcY += sliceH;
                        remaining -= sliceH;
                        page += 1;
                    }
                }
            }
            return pdf.output('blob');
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

        const initialTab = new URLSearchParams(window.location.search).get('tab');
        activateTab(initialTab);

        // Click handlers: update URL with tab parameter
        tabs.forEach((btn) => {
            btn.addEventListener('click', function () {
                const targetId = this.dataset.tabTarget;
                // Update URL without reload
                const url = new URL(window.location);
                url.searchParams.set('tab', targetId);
                window.history.replaceState({}, '', url);
                activateTab(targetId);
            });
        });

        window.addEventListener('popstate', function () {
            const tabParam = new URLSearchParams(window.location.search).get('tab');
            activateTab(tabParam);
        });        // ── Category performance select sync (unchanged) ──
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

                const payload = {
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
                const recordId = document.getElementById('pqRecordId')?.value;
                if (recordId) payload.id = recordId;
                return payload;
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
                    if (!body.updated && body.next_quotation_number) {
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
                        if (body.updated) {
                            alert('Product quotation updated. Status now reflects the payment amount.');
                            const dash = (window.__SALES_CONFIG__ && window.__SALES_CONFIG__.dashboardUrl) || window.location.pathname;
                            window.location.href = `${dash}?tab=product-quotation-tab`;
                            return;
                        }
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

            function setPqEditMode(id, number) {
                const recordId = document.getElementById('pqRecordId');
                const banner = document.getElementById('pqEditBanner');
                const title = document.getElementById('pqFormTitle');
                if (recordId) recordId.value = id ? String(id) : '';
                if (id) {
                    if (banner) {
                        banner.hidden = false;
                        banner.textContent = `Editing ${number || 'saved quotation'}. Change Initial Payment to update status (Unpaid / Partial / Paid).`;
                    }
                    if (title) title.textContent = '📦 Edit Product Quotation';
                } else {
                    if (banner) banner.hidden = true;
                    if (title) title.textContent = '📦 Create Product Quotation';
                }
            }

            function fillPqForm(data) {
                setPqEditMode(data.id, data.quotation_number);
                const pqNumber = document.getElementById('pqNumber');
                if (pqNumber) pqNumber.value = data.quotation_number || '';
                document.getElementById('pqDate').value = data.quotation_date || todayISO();
                document.getElementById('pqValidUntil').value = data.valid_until || '';
                currencySelect.value = data.currency || 'PHP';
                const isOther = currencySelect.value === 'OTHER';
                currencyOther.hidden = !isOther;
                currencyOther.value = data.currency_other || '';
                document.getElementById('pqCustomerCompany').value = data.customer?.company || '';
                document.getElementById('pqCustomerContact').value = data.customer?.contact || '';
                document.getElementById('pqCustomerAddress').value = data.customer?.address || '';
                document.getElementById('pqCustomerEmail').value = data.customer?.email || '';
                document.getElementById('pqCustomerPhone').value = data.customer?.phone || '';
                document.getElementById('pqPaymentTerms').value = data.payment_terms || '';
                document.getElementById('pqDeliveryTerms').value = data.delivery_terms || '';
                document.getElementById('pqWarranty').value = data.warranty || '';
                document.getElementById('pqOtherTerms').value = data.other_terms || '';
                taxInput.value = money(parseMoney(data.tax));
                discountInput.value = money(parseMoney(data.discount));
                shippingInput.value = money(parseMoney(data.shipping));
                initialPaymentInput.value = money(parseMoney(data.initial_payment));
                document.getElementById('pqPreparedName').value = data.prepared_by?.name || '';
                document.getElementById('pqPreparedPosition').value = data.prepared_by?.title || '';
                document.getElementById('pqPreparedSignature').value = data.prepared_by?.signature || '';
                document.getElementById('pqPreparedDate').value = data.prepared_by?.date || '';
                document.getElementById('pqApprovedSignature').value = data.approved_by?.signature || '';
                document.getElementById('pqApprovedDate').value = data.approved_by?.date || '';

                const items = Array.isArray(data.items) && data.items.length ? data.items : [{}];
                const template = itemsBody.querySelector('tr').cloneNode(true);
                itemsBody.innerHTML = '';
                items.forEach((item, idx) => {
                    const row = template.cloneNode(true);
                    row.querySelector('.pq-col-no').value = item.no || (idx + 1);
                    row.querySelector('.pq-col-desc').value = item.description || '';
                    row.querySelector('.pq-qty').value = item.qty || 1;
                    row.querySelector('.pq-col-unit').value = item.unit || '';
                    row.querySelector('.pq-unit-price').value = money(parseMoney(item.unit_price));
                    row.querySelector('.pq-line-total').value = money(parseMoney(item.total));
                    itemsBody.appendChild(row);
                });
                bindMoneyInputs(itemsBody, '.pq-unit-price');
                renumberRows();
                recalcAll();
            }

            async function loadPqForEdit() {
                const params = new URLSearchParams(window.location.search);
                if (params.get('tab') !== 'product-quotation-tab') return;
                const editId = params.get('edit');
                if (!editId) return;
                const tmpl = (window.__SALES_CONFIG__ && window.__SALES_CONFIG__.quotationJsonUrlTemplate) || '';
                const url = tmpl.replace('/0/', `/${editId}/`);
                try {
                    const response = await fetch(url, { credentials: 'same-origin' });
                    const contentType = response.headers.get('content-type') || '';
                    if (!contentType.includes('application/json')) {
                        throw new Error('Unable to load quotation.');
                    }
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.error || 'Unable to load quotation.');
                    fillPqForm(data);
                } catch (error) {
                    alert('Unable to load product quotation: ' + (error.message || error));
                }
            }

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
                setPqEditMode('', '');
                recalcAll();
            });

            recalcAll();
            loadPqForEdit();
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

                const payload = {
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
                const recordId = document.getElementById('svqRecordId')?.value;
                if (recordId) payload.id = recordId;
                return payload;
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
                    if (!body.updated && body.next_quotation_number) {
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
                        if (body.updated) {
                            alert('Service quotation updated. Status now reflects the payment amount.');
                            const dash = (window.__SALES_CONFIG__ && window.__SALES_CONFIG__.dashboardUrl) || window.location.pathname;
                            window.location.href = `${dash}?tab=service-quotation-tab`;
                            return;
                        }
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

            function setSvqEditMode(id, number) {
                const recordId = document.getElementById('svqRecordId');
                const banner = document.getElementById('svqEditBanner');
                const title = document.getElementById('svqFormTitle');
                if (recordId) recordId.value = id ? String(id) : '';
                if (id) {
                    if (banner) {
                        banner.hidden = false;
                        banner.textContent = `Editing ${number || 'saved quotation'}. Change Initial Payment to update status (Unpaid / Partial / Paid).`;
                    }
                    if (title) title.textContent = '🛠️ Edit Service Quotation';
                } else {
                    if (banner) banner.hidden = true;
                    if (title) title.textContent = '🛠️ Create Service Quotation';
                }
            }

            function fillSvqForm(data) {
                setSvqEditMode(data.id, data.quotation_number);
                const svqNumber = document.getElementById('svqNumber');
                if (svqNumber) svqNumber.value = data.quotation_number || '';
                document.getElementById('svqDate').value = data.quotation_date || todayISO();
                document.getElementById('svqValidUntil').value = data.valid_until || '';
                currencySelect.value = data.currency || 'PHP';
                const isOther = currencySelect.value === 'OTHER';
                currencyOther.hidden = !isOther;
                currencyOther.value = data.currency_other || '';
                document.getElementById('svqCustomerCompany').value = data.customer?.company || '';
                document.getElementById('svqCustomerContact').value = data.customer?.contact || '';
                document.getElementById('svqCustomerAddress').value = data.customer?.address || '';
                document.getElementById('svqCustomerEmail').value = data.customer?.email || '';
                document.getElementById('svqCustomerPhone').value = data.customer?.phone || '';
                document.getElementById('svqPaymentTerms').value = data.payment_terms || '';
                document.getElementById('svqServiceSchedule').value = data.service_schedule || '';
                document.getElementById('svqWarranty').value = data.warranty || '';
                document.getElementById('svqOtherTerms').value = data.other_terms || '';
                taxInput.value = money(parseMoney(data.tax));
                discountInput.value = money(parseMoney(data.discount));
                otherFeesInput.value = money(parseMoney(data.other_fees));
                initialPaymentInput.value = money(parseMoney(data.initial_payment));
                document.getElementById('svqPreparedName').value = data.prepared_by?.name || '';
                document.getElementById('svqPreparedPosition').value = data.prepared_by?.title || '';
                document.getElementById('svqPreparedSignature').value = data.prepared_by?.signature || '';
                document.getElementById('svqPreparedDate').value = data.prepared_by?.date || '';
                document.getElementById('svqApprovedSignature').value = data.approved_by?.signature || '';
                document.getElementById('svqApprovedDate').value = data.approved_by?.date || '';

                const items = Array.isArray(data.items) && data.items.length ? data.items : [{}];
                const template = itemsBody.querySelector('tr').cloneNode(true);
                itemsBody.innerHTML = '';
                items.forEach((item, idx) => {
                    const row = template.cloneNode(true);
                    row.querySelector('.svq-col-no').value = item.no || (idx + 1);
                    row.querySelector('.svq-col-desc').value = item.description || '';
                    row.querySelector('.svq-line-total').value = money(parseMoney(item.total || item.unit_price));
                    itemsBody.appendChild(row);
                });
                bindMoneyInputs(itemsBody, '.svq-line-total');
                renumberRows();
                recalcAll();
            }

            async function loadSvqForEdit() {
                const params = new URLSearchParams(window.location.search);
                if (params.get('tab') !== 'service-quotation-tab') return;
                const editId = params.get('edit');
                if (!editId) return;
                const tmpl = (window.__SALES_CONFIG__ && window.__SALES_CONFIG__.serviceQuotationJsonUrlTemplate) || '';
                const url = tmpl.replace('/0/', `/${editId}/`);
                try {
                    const response = await fetch(url, { credentials: 'same-origin' });
                    const contentType = response.headers.get('content-type') || '';
                    if (!contentType.includes('application/json')) {
                        throw new Error('Unable to load quotation.');
                    }
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.error || 'Unable to load quotation.');
                    fillSvqForm(data);
                } catch (error) {
                    alert('Unable to load service quotation: ' + (error.message || error));
                }
            }

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
                setSvqEditMode('', '');
                recalcAll();
            });

            recalcAll();
            loadSvqForEdit();
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
            const cfg = window.__SALES_CONFIG__ || {};
            const itemsBody = document.getElementById('aaItemsBody');
            if (!itemsBody) return;

            const asOfInput = document.getElementById('aaAsOfDate');
            const noteInput = document.getElementById('aaNote');
            const reportIdInput = document.getElementById('aaReportId');
            const prevBody = document.getElementById('aaPrevItemsBody');
            const importFileInput = document.getElementById('aaImportFile');
            let storedReportTotals = null;

            function setStoredReportTotals(data) {
                if (data && data.total_amount != null && data.total_amount !== '') {
                    storedReportTotals = {
                        amount: parseAmount(data.total_amount),
                        paid: parseAmount(data.total_amount_paid),
                    };
                } else {
                    storedReportTotals = null;
                }
            }

            function currentLineTotals() {
                const rows = Array.from(itemsBody.querySelectorAll('tr'));
                return {
                    amount: rows.reduce((s, row) => s + parseAmount(row.querySelector('.aa-item-amount')?.value), 0),
                    paid: rows.reduce((s, row) => s + parseAmount(row.querySelector('.aa-item-paid')?.value), 0),
                };
            }

            function activeReportTotals() {
                if (storedReportTotals) return storedReportTotals;
                return currentLineTotals();
            }

            function ageingJsonUrl(reportId) {
                return (cfg.ageingAccountsJsonUrlTemplate || '').replace('/0/', `/${reportId}/`);
            }

            function ageingDeleteUrl(reportId) {
                return (cfg.ageingAccountsDeleteUrlTemplate || ageingJsonUrl(reportId).replace('/json/', '/delete/')).replace('/0/', `/${reportId}/`);
            }

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

            function displayAmountInput(input) {
                const raw = (input?.dataset.raw || '').trim();
                const value = (input?.value || '').trim();
                if (raw && (!value || parseAmount(value) === 0)) return raw;
                return formatMoney(parseAmount(value));
            }

            function createRow(data = {}) {
                const amountValue = data.amount || data.amount_raw || '0.00';
                const paidValue = data.amount_paid || data.amount_paid_raw || '0.00';
                const terms = String(data.terms_of_payment || '');
                const termsOptions = [
                    ['', '—'],
                    ['7', '7 days'],
                    ['15', '15 days'],
                    ['30', '30 days'],
                    ['60', '60 days'],
                ].map(([value, label]) => (
                    `<option value="${value}"${terms === value ? ' selected' : ''}>${label}</option>`
                )).join('');
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><input type="date" class="aa-item-date" value="${escapeHtml(data.line_date || '')}"></td>
                    <td><input type="text" class="aa-item-customer" placeholder="CUSTOMER NAME" value="${escapeHtml(data.customer_name || '')}"></td>
                    <td><input type="text" class="aa-item-po" placeholder="PO No." value="${escapeHtml(data.po_number || '')}"></td>
                    <td><input type="text" class="aa-item-agent" placeholder="Agent" value="${escapeHtml(data.agent || '')}"></td>
                    <td><input type="text" class="aa-item-bi" placeholder="BI#" value="${escapeHtml(data.bi_number || '')}"></td>
                    <td><input type="text" class="aa-item-si" placeholder="SI#" value="${escapeHtml(data.si_number || '')}"></td>
                    <td><input type="text" class="aa-item-cr" placeholder="CR#" value="${escapeHtml(data.cr_number || '')}"></td>
                    <td><input type="text" class="aa-item-ci" placeholder="CI#" value="${escapeHtml(data.ci_number || '')}"></td>
                    <td><input type="text" class="aa-item-ar" placeholder="AR#" value="${escapeHtml(data.ar_number || '')}"></td>
                    <td><input type="text" class="aa-item-dr" placeholder="DR No." value="${escapeHtml(data.dr_number || '')}"></td>
                    <td>
                        <select class="aa-item-terms" aria-label="Terms of payment">${termsOptions}</select>
                    </td>
                    <td><input type="text" class="aa-item-amount" value="${escapeHtml(amountValue)}" placeholder="0.00" inputmode="decimal" style="text-align:right;" data-raw="${escapeHtml(data.amount_raw || '')}"></td>
                    <td><input type="text" class="aa-item-paid" value="${escapeHtml(paidValue)}" placeholder="0.00" inputmode="decimal" style="text-align:right;" data-raw="${escapeHtml(data.amount_paid_raw || '')}"></td>
                    <td><input type="text" class="aa-item-paid-items" placeholder="Paid items" value="${escapeHtml(data.paid_items || '')}"></td>
                    <td style="text-align:center;">
                        <button type="button" class="aa-row-remove"
                            style="padding:4px 8px; background:#f5f5f5; border:1px solid var(--line); border-radius:4px; cursor:pointer; color:var(--danger); font-weight:600;">✕</button>
                    </td>
                `;
                if (data.line_date_raw && !data.line_date) {
                    const dateInput = tr.querySelector('.aa-item-date');
                    if (dateInput) {
                        dateInput.type = 'text';
                        dateInput.value = data.line_date_raw;
                        dateInput.dataset.rawDate = data.line_date_raw;
                    }
                }
                return tr;
            }

            function termsLabel(value) {
                const map = { '7': '7 days', '15': '15 days', '30': '30 days', '60': '60 days' };
                return map[String(value || '')] || '';
            }

            function collectLinesFromForm() {
                return Array.from(itemsBody.querySelectorAll('tr')).map((row) => {
                    const dateInput = row.querySelector('.aa-item-date');
                    const lineDate = dateInput?.type === 'date' ? (dateInput.value || '') : '';
                    const lineDateRaw = dateInput?.dataset.rawDate || (dateInput?.type !== 'date' ? (dateInput?.value || '') : '');
                    return {
                        line_date: lineDate,
                        line_date_raw: lineDateRaw,
                        customer_name: row.querySelector('.aa-item-customer')?.value.trim() || '',
                        po_number: row.querySelector('.aa-item-po')?.value.trim() || '',
                        agent: row.querySelector('.aa-item-agent')?.value.trim() || '',
                        bi_number: row.querySelector('.aa-item-bi')?.value.trim() || '',
                        si_number: row.querySelector('.aa-item-si')?.value.trim() || '',
                        cr_number: row.querySelector('.aa-item-cr')?.value.trim() || '',
                        ci_number: row.querySelector('.aa-item-ci')?.value.trim() || '',
                        ar_number: row.querySelector('.aa-item-ar')?.value.trim() || '',
                        dr_number: row.querySelector('.aa-item-dr')?.value.trim() || '',
                        terms_of_payment: row.querySelector('.aa-item-terms')?.value || '',
                        amount: row.querySelector('.aa-item-amount')?.value.trim() || '',
                        amount_raw: row.querySelector('.aa-item-amount')?.dataset.raw || '',
                        amount_paid: row.querySelector('.aa-item-paid')?.value.trim() || '',
                        amount_paid_raw: row.querySelector('.aa-item-paid')?.dataset.raw || '',
                        paid_items: row.querySelector('.aa-item-paid-items')?.value.trim() || '',
                    };
                }).filter((line) => line.customer_name || line.po_number || line.agent || line.dr_number || line.terms_of_payment || line.amount || line.amount_paid || line.amount_raw || line.amount_paid_raw);
            }

            function populateForm(data) {
                if (reportIdInput) reportIdInput.value = data?.id ? String(data.id) : '';
                asOfInput.value = data?.as_of_date || todayISO();
                noteInput.value = data?.note || '';
                setStoredReportTotals(data);
                itemsBody.innerHTML = '';
                const lines = data?.lines?.length ? data.lines : [{}];
                lines.forEach((line) => itemsBody.appendChild(createRow(line)));
                bindMoneyInputs(itemsBody, '.aa-item-amount, .aa-item-paid');
                applyAaRowSearch();
                refreshPreview();
            }

            function rowSearchText(row) {
                const parts = [
                    row.querySelector('.aa-item-date')?.value,
                    row.querySelector('.aa-item-customer')?.value,
                    row.querySelector('.aa-item-po')?.value,
                    row.querySelector('.aa-item-agent')?.value,
                    row.querySelector('.aa-item-bi')?.value,
                    row.querySelector('.aa-item-si')?.value,
                    row.querySelector('.aa-item-cr')?.value,
                    row.querySelector('.aa-item-ci')?.value,
                    row.querySelector('.aa-item-ar')?.value,
                    row.querySelector('.aa-item-dr')?.value,
                    termsLabel(row.querySelector('.aa-item-terms')?.value),
                    row.querySelector('.aa-item-amount')?.value,
                    row.querySelector('.aa-item-paid')?.value,
                    row.querySelector('.aa-item-paid-items')?.value,
                ];
                return parts.join(' ').toLowerCase();
            }

            function applyAaRowSearch() {
                const searchInput = document.getElementById('aaSearchInput');
                const meta = document.getElementById('aaSearchMeta');
                if (!searchInput) return;
                const query = searchInput.value.trim().toLowerCase();
                const rows = Array.from(itemsBody.querySelectorAll('tr'));
                let visible = 0;
                rows.forEach((row) => {
                    const match = !query || rowSearchText(row).includes(query);
                    row.hidden = !match;
                    if (match) visible += 1;
                });
                if (meta) {
                    meta.textContent = query
                        ? `Showing ${visible} of ${rows.length} row${rows.length === 1 ? '' : 's'}`
                        : (rows.length ? `${rows.length} row${rows.length === 1 ? '' : 's'}` : '');
                }
            }

            async function loadReport(reportId) {
                const url = reportId ? ageingJsonUrl(reportId) : (cfg.ageingAccountsLatestJsonUrl || '');
                if (!url) return;
                const response = await fetch(url, { credentials: 'same-origin' });
                const body = await response.json();
                if (!response.ok) throw new Error(body?.error || 'Unable to load ageing report.');
                if (!body?.lines?.length && !body?.id) {
                    populateForm({ as_of_date: todayISO(), lines: [{}] });
                    return;
                }
                populateForm(body);
            }

            async function saveReportToDb() {
                const totals = activeReportTotals();
                const payload = {
                    id: reportIdInput?.value || null,
                    as_of_date: asOfInput.value || todayISO(),
                    note: noteInput.value || '',
                    lines: collectLinesFromForm(),
                    total_amount: String(totals.amount),
                    total_amount_paid: String(totals.paid),
                };
                const response = await fetch(cfg.saveAgeingAccountsUrl || '', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                    },
                    body: JSON.stringify(payload),
                });
                const body = await response.json();
                if (!response.ok) throw new Error(body?.error || 'Unable to save ageing report.');
                if (reportIdInput) reportIdInput.value = String(body.id);
                setStoredReportTotals(body);
                return body;
            }

            function refreshPreview() {
                document.getElementById('aaPrevTitle').textContent =
                    'AGEING OF ACCOUNTS AS OF ' + formatDisplayDate(asOfInput.value) + '.';
                const note = (noteInput.value || '').trim();
                document.getElementById('aaPrevNote').textContent = note ? note.toUpperCase() : '';

                const rows = Array.from(itemsBody.querySelectorAll('tr'));
                prevBody.innerHTML = '';

                const usable = rows.filter((row) => {
                    const customer = row.querySelector('.aa-item-customer')?.value.trim();
                    const amount = parseAmount(row.querySelector('.aa-item-amount')?.value);
                    const paid = parseAmount(row.querySelector('.aa-item-paid')?.value);
                    const po = row.querySelector('.aa-item-po')?.value.trim();
                    const agent = row.querySelector('.aa-item-agent')?.value.trim();
                    const dr = row.querySelector('.aa-item-dr')?.value.trim();
                    const amountRaw = row.querySelector('.aa-item-amount')?.dataset.raw;
                    const paidRaw = row.querySelector('.aa-item-paid')?.dataset.raw;
                    return customer || amount || paid || po || agent || dr || amountRaw || paidRaw;
                });

                if (!usable.length) {
                    const empty = document.createElement('tr');
                    empty.innerHTML = '<td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td class="aa-center">&nbsp;</td><td class="aa-num">&nbsp;</td><td class="aa-num">&nbsp;</td><td>&nbsp;</td>';
                    prevBody.appendChild(empty);
                } else {
                    usable.forEach((row) => {
                        const tr = document.createElement('tr');
                        const dateInput = row.querySelector('.aa-item-date');
                        const dateVal = dateInput?.type === 'date'
                            ? (dateInput.value || '')
                            : (dateInput?.dataset.rawDate || dateInput?.value || '');
                        const amountText = displayAmountInput(row.querySelector('.aa-item-amount'));
                        const paidText = displayAmountInput(row.querySelector('.aa-item-paid'));
                        const termsText = termsLabel(row.querySelector('.aa-item-terms')?.value);
                        tr.innerHTML = `
                            <td>${escapeHtml(formatShortDate(dateVal) || dateVal || '\u00a0')}</td>
                            <td>${escapeHtml((row.querySelector('.aa-item-customer')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-center">${escapeHtml((row.querySelector('.aa-item-po')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-center">${escapeHtml((row.querySelector('.aa-item-agent')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-center">${escapeHtml((row.querySelector('.aa-item-bi')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-center">${escapeHtml((row.querySelector('.aa-item-si')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-center">${escapeHtml((row.querySelector('.aa-item-cr')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-center">${escapeHtml((row.querySelector('.aa-item-ci')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-center">${escapeHtml((row.querySelector('.aa-item-ar')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-center">${escapeHtml((row.querySelector('.aa-item-dr')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                            <td class="aa-center">${escapeHtml(termsText) || '&nbsp;'}</td>
                            <td class="aa-num">${escapeHtml(amountText)}</td>
                            <td class="aa-num">${escapeHtml(paidText)}</td>
                            <td>${escapeHtml((row.querySelector('.aa-item-paid-items')?.value || '').toUpperCase()) || '&nbsp;'}</td>
                        `;
                        prevBody.appendChild(tr);
                    });
                }

                const totals = activeReportTotals();
                document.getElementById('aaTotalAmount').textContent = formatPHP(totals.amount);
                document.getElementById('aaTotalPaid').textContent = formatPHP(totals.paid);
                document.getElementById('aaPrevTotalAmount').textContent = formatMoney(totals.amount);
                document.getElementById('aaPrevTotalPaid').textContent = formatMoney(totals.paid);
            }

            itemsBody.addEventListener('input', () => {
                applyAaRowSearch();
                refreshPreview();
            });
            itemsBody.addEventListener('change', () => {
                applyAaRowSearch();
                refreshPreview();
            });
            asOfInput.addEventListener('input', refreshPreview);
            asOfInput.addEventListener('change', refreshPreview);
            noteInput.addEventListener('input', refreshPreview);
            bindMoneyInputs(itemsBody, '.aa-item-amount, .aa-item-paid');

            const aaSearchInput = document.getElementById('aaSearchInput');
            const aaSearchClear = document.getElementById('aaSearchClear');
            if (aaSearchInput) {
                aaSearchInput.addEventListener('input', applyAaRowSearch);
            }
            if (aaSearchClear) {
                aaSearchClear.addEventListener('click', () => {
                    if (aaSearchInput) aaSearchInput.value = '';
                    applyAaRowSearch();
                    aaSearchInput?.focus();
                });
            }

            itemsBody.addEventListener('click', (e) => {
                const btn = e.target.closest('.aa-row-remove');
                if (!btn) return;
                const rows = itemsBody.querySelectorAll('tr');
                if (rows.length <= 1) {
                    rows[0].querySelectorAll('input, textarea, select').forEach((el) => {
                        if (el.classList.contains('aa-item-amount') || el.classList.contains('aa-item-paid')) el.value = '0.00';
                        else el.value = '';
                    });
                } else {
                    btn.closest('tr').remove();
                }
                applyAaRowSearch();
                refreshPreview();
            });

            document.getElementById('aaAddRow').addEventListener('click', () => {
                itemsBody.appendChild(createRow());
                bindMoneyInputs(itemsBody, '.aa-item-amount, .aa-item-paid');
                applyAaRowSearch();
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
                let savedReportId = reportIdInput?.value || null;
                try {
                    if (mode === 'save') {
                        const saved = await saveReportToDb();
                        savedReportId = saved.id;
                    }

                    const pageW = 1400;
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
                            max-width: none !important;
                            background: #fff !important;
                            color: #111 !important;
                            font-family: Arial, Helvetica, sans-serif !important;
                            font-size: 12px !important;
                            box-sizing: border-box !important;
                            padding: 12px 16px 20px !important;
                            overflow: visible !important;
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
                            table-layout: fixed !important; font-size: 9px !important;
                            page-break-inside: auto !important;
                        }
                        #aa-print-sheet .aa-items thead { display: table-header-group !important; }
                        #aa-print-sheet .aa-items tr {
                            break-inside: avoid !important;
                            page-break-inside: avoid !important;
                        }
                        #aa-print-sheet .aa-items th, #aa-print-sheet .aa-items td {
                            border: 1px solid #222 !important; padding: 3px 4px !important; vertical-align: top !important;
                            word-break: break-word !important; overflow-wrap: anywhere !important;
                            white-space: normal !important; color: #111 !important;
                        }
                        #aa-print-sheet .aa-items th {
                            background: #dbeafe !important; color: #000 !important; font-weight: 700 !important;
                            text-align: center !important; text-transform: uppercase !important; font-size: 8px !important;
                        }
                        #aa-print-sheet .aa-num { text-align: right !important; white-space: normal !important; }
                        #aa-print-sheet .aa-center { text-align: center !important; }
                        #aa-print-sheet .aa-total-row td { font-weight: 700 !important; background: #f8fafc !important; }
                        #aa-print-sheet .aa-total-label { text-align: right !important; }
                    `;

                    const sheet = document.createElement('div');
                    sheet.id = 'aa-print-sheet';
                    const bodyClone = bodyNode ? bodyNode.cloneNode(true) : document.createElement('div');
                    while (bodyClone.firstChild) sheet.appendChild(bodyClone.firstChild);
                    holder.appendChild(styleEl);
                    holder.appendChild(sheet);
                    document.body.appendChild(holder);

                    const pdfBlob = await landscapePdfFromSheet(sheet, { width: pageW, margin: 6, maxPages: 16, jpegQuality: 0.98 });
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
                            sourceId: savedReportId,
                        });
                        alert('Ageing of Accounts saved to the database and PDF archived.');
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

            if (importFileInput) {
                importFileInput.addEventListener('change', async () => {
                    const file = importFileInput.files?.[0];
                    importFileInput.value = '';
                    if (!file) return;
                    if (!file.name.toLowerCase().endsWith('.xlsx')) {
                        alert('Please choose an .xlsx file.');
                        return;
                    }
                    const formData = new FormData();
                    formData.append('xlsx', file);
                    formData.append('as_of_date', asOfInput.value || todayISO());
                    formData.append('note', noteInput.value || '');
                    try {
                        const response = await fetch(cfg.importAgeingAccountsUrl || '', {
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: { 'X-CSRFToken': getCsrfToken() },
                            body: formData,
                        });
                        const body = await response.json();
                        if (!response.ok) throw new Error(body?.error || 'Import failed.');
                        populateForm(body);
                        alert(`Imported ${body.lines.length} rows from ${file.name}.`);
                        window.location.reload();
                    } catch (error) {
                        alert(error.message || 'Could not import Excel file.');
                    }
                });
            }

            document.querySelectorAll('.aa-load-report').forEach((button) => {
                button.addEventListener('click', async () => {
                    try {
                        await loadReport(button.dataset.reportId);
                        activateTab('ageing-accounts-tab');
                    } catch (error) {
                        alert(error.message || 'Could not load report.');
                    }
                });
            });

            document.querySelectorAll('.aa-delete-report').forEach((button) => {
                button.addEventListener('click', async () => {
                    const reportId = button.dataset.reportId;
                    if (!reportId || !confirm('Delete this ageing report? This cannot be undone.')) return;
                    try {
                        const response = await fetch(ageingDeleteUrl(reportId), {
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: { 'X-CSRFToken': getCsrfToken() },
                        });
                        const body = await response.json();
                        if (!response.ok) throw new Error(body?.error || 'Delete failed.');
                        window.location.href = `${cfg.dashboardUrl || ''}?tab=ageing-accounts-tab`;
                    } catch (error) {
                        alert(error.message || 'Could not delete report.');
                    }
                });
            });

            document.getElementById('aaReset').addEventListener('click', () => {
                populateForm({ as_of_date: todayISO(), lines: [{}] });
            });

            const urlParams = new URLSearchParams(window.location.search);
            const editId = urlParams.get('aa_edit') || cfg.latestAgeingReportId;
            loadReport(editId).catch((error) => {
                console.error(error);
                populateForm({ as_of_date: todayISO(), lines: [{}] });
            });
        })();

        // ══════════════════════════════════════════════════════════════
        // RETENTION SUMMARY
        // ══════════════════════════════════════════════════════════════

        (function initRetentionSummary() {
            const cfg = window.__SALES_CONFIG__ || {};
            const itemsBody = document.getElementById('rsItemsBody');
            if (!itemsBody) return;

            const asOfInput = document.getElementById('rsAsOfDate');
            const noteInput = document.getElementById('rsNote');
            const reportIdInput = document.getElementById('rsReportId');
            const prevBody = document.getElementById('rsPrevItemsBody');
            const importFileInput = document.getElementById('rsImportFile');
            let storedReportTotals = null;

            function setStoredReportTotals(data) {
                if (data && data.total_trxn_amount != null && data.total_trxn_amount !== '') {
                    storedReportTotals = {
                        trxn: parseAmount(data.total_trxn_amount),
                        amount: parseAmount(data.total_retention_amount),
                    };
                } else {
                    storedReportTotals = null;
                }
            }

            function currentLineTotals() {
                const rows = Array.from(itemsBody.querySelectorAll('tr'));
                return {
                    trxn: rows.reduce((s, row) => s + parseAmount(row.querySelector('.rs-item-trxn')?.value), 0),
                    amount: rows.reduce((s, row) => s + parseAmount(row.querySelector('.rs-item-amount')?.value), 0),
                };
            }

            function activeReportTotals() {
                if (storedReportTotals) return storedReportTotals;
                return currentLineTotals();
            }

            function retentionJsonUrl(reportId) {
                return (cfg.retentionSummaryJsonUrlTemplate || '').replace('/0/', `/${reportId}/`);
            }

            function retentionDeleteUrl(reportId) {
                return (cfg.retentionSummaryDeleteUrlTemplate || retentionJsonUrl(reportId).replace('/json/', '/delete/')).replace('/0/', `/${reportId}/`);
            }

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

            function createRow(data = {}) {
                const trxnValue = data.trxn_amount || data.trxn_amount_raw || '0.00';
                const amountValue = data.amount || data.amount_raw || '0.00';
                const percentValue = data.percent != null && data.percent !== '' ? data.percent : '10';
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><input type="date" class="rs-item-date" value="${escapeHtml(data.delivery_date || '')}"></td>
                    <td><input type="text" class="rs-item-client" placeholder="CLIENT NAME" value="${escapeHtml(data.client_name || '')}"></td>
                    <td><input type="text" class="rs-item-trxn" value="${escapeHtml(trxnValue)}" placeholder="0.00" inputmode="decimal" style="text-align:right;" data-raw="${escapeHtml(data.trxn_amount_raw || '')}"></td>
                    <td><input type="text" class="rs-item-percent" value="${escapeHtml(percentValue)}" placeholder="10%" style="text-align:right;"></td>
                    <td><input type="text" class="rs-item-amount" value="${escapeHtml(amountValue)}" placeholder="0.00" data-auto="${data.amount || data.amount_raw ? '0' : '1'}" inputmode="decimal" style="text-align:right;" data-raw="${escapeHtml(data.amount_raw || '')}"></td>
                    <td><textarea class="rs-item-remarks" rows="2" placeholder="Remarks">${escapeHtml(data.remarks || '')}</textarea></td>
                    <td>
                        <div class="rs-flag">
                            <label><input type="checkbox" class="rs-flag-red"${data.flag_red_remarks ? ' checked' : ''}> Red remarks</label>
                            <label><input type="checkbox" class="rs-flag-client"${data.flag_yellow_client ? ' checked' : ''}> Yellow client</label>
                            <label><input type="checkbox" class="rs-flag-row"${data.flag_pink_row ? ' checked' : ''}> Pink row</label>
                        </div>
                    </td>
                    <td style="text-align:center;">
                        <button type="button" class="rs-row-remove"
                            style="padding:4px 8px; background:#f5f5f5; border:1px solid var(--line); border-radius:4px; cursor:pointer; color:var(--danger); font-weight:600;">✕</button>
                    </td>
                `;
                if (data.delivery_date_raw && !data.delivery_date) {
                    const dateInput = tr.querySelector('.rs-item-date');
                    if (dateInput) {
                        dateInput.type = 'text';
                        dateInput.value = data.delivery_date_raw;
                        dateInput.dataset.rawDate = data.delivery_date_raw;
                    }
                }
                return tr;
            }

            function collectLinesFromForm() {
                return Array.from(itemsBody.querySelectorAll('tr')).map((row) => {
                    const dateInput = row.querySelector('.rs-item-date');
                    const deliveryDate = dateInput?.type === 'date' ? (dateInput.value || '') : '';
                    const deliveryDateRaw = dateInput?.dataset.rawDate || (dateInput?.type !== 'date' ? (dateInput?.value || '') : '');
                    return {
                        delivery_date: deliveryDate,
                        delivery_date_raw: deliveryDateRaw,
                        client_name: row.querySelector('.rs-item-client')?.value.trim() || '',
                        trxn_amount: row.querySelector('.rs-item-trxn')?.value.trim() || '',
                        trxn_amount_raw: row.querySelector('.rs-item-trxn')?.dataset.raw || '',
                        percent: row.querySelector('.rs-item-percent')?.value.trim() || '',
                        amount: row.querySelector('.rs-item-amount')?.value.trim() || '',
                        amount_raw: row.querySelector('.rs-item-amount')?.dataset.raw || '',
                        remarks: row.querySelector('.rs-item-remarks')?.value.trim() || '',
                        flag_red_remarks: Boolean(row.querySelector('.rs-flag-red')?.checked),
                        flag_yellow_client: Boolean(row.querySelector('.rs-flag-client')?.checked),
                        flag_pink_row: Boolean(row.querySelector('.rs-flag-row')?.checked),
                    };
                }).filter((line) => line.client_name || line.trxn_amount || line.amount || line.remarks || line.delivery_date || line.delivery_date_raw || line.trxn_amount_raw || line.amount_raw);
            }

            function populateForm(data) {
                if (reportIdInput) reportIdInput.value = data?.id ? String(data.id) : '';
                asOfInput.value = data?.as_of_date || todayISO();
                noteInput.value = data?.note || '';
                setStoredReportTotals(data);
                itemsBody.innerHTML = '';
                const lines = data?.lines?.length ? data.lines : [{}];
                lines.forEach((line) => itemsBody.appendChild(createRow(line)));
                bindMoneyInputs(itemsBody, '.rs-item-trxn, .rs-item-amount');
                refreshPreview();
            }

            async function loadReport(reportId) {
                const url = reportId ? retentionJsonUrl(reportId) : (cfg.retentionSummaryLatestJsonUrl || '');
                if (!url) return;
                const response = await fetch(url, { credentials: 'same-origin' });
                const body = await response.json();
                if (!response.ok) throw new Error(body?.error || 'Unable to load retention report.');
                if (!body?.lines?.length && !body?.id) {
                    populateForm({ as_of_date: todayISO(), lines: [{}] });
                    return;
                }
                populateForm(body);
            }

            async function saveReportToDb() {
                const totals = activeReportTotals();
                const payload = {
                    id: reportIdInput?.value || null,
                    as_of_date: asOfInput.value || todayISO(),
                    note: noteInput.value || '',
                    lines: collectLinesFromForm(),
                    total_trxn_amount: String(totals.trxn),
                    total_retention_amount: String(totals.amount),
                };
                const response = await fetch(cfg.saveRetentionSummaryUrl || '', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                    },
                    body: JSON.stringify(payload),
                });
                const body = await response.json();
                if (!response.ok) throw new Error(body?.error || 'Unable to save retention report.');
                if (reportIdInput) reportIdInput.value = String(body.id);
                setStoredReportTotals(body);
                return body;
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

                if (!usable.length) {
                    const empty = document.createElement('tr');
                    empty.innerHTML = '<td>&nbsp;</td><td>&nbsp;</td><td class="rs-num">&nbsp;</td><td class="rs-center">&nbsp;</td><td class="rs-num">&nbsp;</td><td>&nbsp;</td>';
                    prevBody.appendChild(empty);
                } else {
                    usable.forEach((row) => {
                        const trxn = parseAmount(row.querySelector('.rs-item-trxn')?.value);
                        const amount = parseAmount(row.querySelector('.rs-item-amount')?.value);
                        const dateInput = row.querySelector('.rs-item-date');
                        const dateVal = dateInput?.type === 'date'
                            ? (dateInput.value || '')
                            : (dateInput?.dataset.rawDate || dateInput?.value || '');
                        const client = (row.querySelector('.rs-item-client')?.value || '').toUpperCase();
                        const pctText = formatPercent(row.querySelector('.rs-item-percent')?.value);
                        const remarks = row.querySelector('.rs-item-remarks')?.value || '';
                        const red = row.querySelector('.rs-flag-red')?.checked;
                        const clientHl = row.querySelector('.rs-flag-client')?.checked;
                        const rowHl = row.querySelector('.rs-flag-row')?.checked;

                        const tr = document.createElement('tr');
                        if (rowHl) tr.classList.add('rs-row-hl');
                        tr.innerHTML = `
                            <td>${escapeHtml(formatShortDate(dateVal) || dateVal || '\u00a0')}</td>
                            <td class="${clientHl ? 'rs-client-hl' : ''}">${escapeHtml(client) || '&nbsp;'}</td>
                            <td class="rs-num">${escapeHtml(formatMoney(trxn))}</td>
                            <td class="rs-center">${escapeHtml(pctText) || '&nbsp;'}</td>
                            <td class="rs-num">${escapeHtml(formatMoney(amount))}</td>
                            <td class="${red ? 'rs-remarks-red' : ''}">${escapeHtml(remarks) || '&nbsp;'}</td>
                        `;
                        prevBody.appendChild(tr);
                    });
                }

                const totals = activeReportTotals();
                document.getElementById('rsTotalTrxn').textContent = formatPHP(totals.trxn);
                document.getElementById('rsTotalAmount').textContent = formatPHP(totals.amount);
                document.getElementById('rsPrevTotalTrxn').textContent = formatMoney(totals.trxn);
                document.getElementById('rsPrevTotalAmount').textContent = formatMoney(totals.amount);
            }

            itemsBody.addEventListener('input', (e) => {
                const row = e.target.closest('tr');
                if (!row) return;
                if (e.target.classList.contains('rs-item-trxn') || e.target.classList.contains('rs-item-percent')) {
                    syncRetentionAmount(row);
                    storedReportTotals = null;
                }
                if (e.target.classList.contains('rs-item-amount')) {
                    e.target.dataset.auto = '0';
                    storedReportTotals = null;
                }
                refreshPreview();
            });
            itemsBody.addEventListener('blur', (e) => {
                if (!e.target.classList.contains('rs-item-trxn')) return;
                const row = e.target.closest('tr');
                if (row) syncRetentionAmount(row);
                refreshPreview();
            }, true);
            itemsBody.addEventListener('change', () => {
                storedReportTotals = null;
                refreshPreview();
            });
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
                storedReportTotals = null;
                refreshPreview();
            });

            document.getElementById('rsAddRow').addEventListener('click', () => {
                itemsBody.appendChild(createRow());
                bindMoneyInputs(itemsBody, '.rs-item-trxn, .rs-item-amount');
                storedReportTotals = null;
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
                let savedReportId = reportIdInput?.value || null;
                try {
                    if (mode === 'save') {
                        const saved = await saveReportToDb();
                        savedReportId = saved.id;
                    }

                    const pageW = 1400;
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
                            max-width: none !important;
                            background: #fff !important;
                            color: #111 !important;
                            font-family: Arial, Helvetica, sans-serif !important;
                            font-size: 12px !important;
                            box-sizing: border-box !important;
                            padding: 12px 16px 20px !important;
                            overflow: visible !important;
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
                            table-layout: fixed !important; font-size: 9px !important;
                        }
                        #rs-print-sheet .rs-items th, #rs-print-sheet .rs-items td {
                            border: 1px solid #222 !important; padding: 3px 4px !important; vertical-align: top !important;
                            word-break: break-word !important; overflow-wrap: anywhere !important;
                            white-space: normal !important; color: #111 !important;
                        }
                        #rs-print-sheet .rs-items th {
                            background: #dbeafe !important; color: #000 !important; font-weight: 700 !important;
                            text-align: center !important; text-transform: uppercase !important; font-size: 8px !important;
                        }
                        #rs-print-sheet .rs-num { text-align: right !important; white-space: normal !important; }
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
                    sheet.appendChild(bodyNode.cloneNode(true));
                    holder.appendChild(styleEl);
                    holder.appendChild(sheet);
                    document.body.appendChild(holder);

                    const pdfBlob = await landscapePdfFromSheet(sheet, { width: pageW, margin: 6, maxPages: 16, jpegQuality: 0.98 });
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
                            sourceId: savedReportId,
                        });
                        alert('Retention Summary saved to the database and PDF archived.');
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

            if (importFileInput) {
                importFileInput.addEventListener('change', async () => {
                    const file = importFileInput.files?.[0];
                    importFileInput.value = '';
                    if (!file) return;
                    if (!file.name.toLowerCase().endsWith('.xlsx')) {
                        alert('Please choose an .xlsx file.');
                        return;
                    }
                    const formData = new FormData();
                    formData.append('xlsx', file);
                    formData.append('as_of_date', asOfInput.value || todayISO());
                    formData.append('note', noteInput.value || '');
                    try {
                        const response = await fetch(cfg.importRetentionSummaryUrl || '', {
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: { 'X-CSRFToken': getCsrfToken() },
                            body: formData,
                        });
                        const body = await response.json();
                        if (!response.ok) throw new Error(body?.error || 'Import failed.');
                        populateForm(body);
                        alert(`Imported ${body.lines.length} rows from ${file.name}.`);
                        window.location.href = `${cfg.dashboardUrl || ''}?tab=retention-summary-tab`;
                    } catch (error) {
                        alert(error.message || 'Could not import Excel file.');
                    }
                });
            }

            document.querySelectorAll('.rs-load-report').forEach((button) => {
                button.addEventListener('click', async () => {
                    try {
                        await loadReport(button.dataset.reportId);
                        activateTab('retention-summary-tab');
                    } catch (error) {
                        alert(error.message || 'Could not load report.');
                    }
                });
            });

            document.querySelectorAll('.rs-delete-report').forEach((button) => {
                button.addEventListener('click', async () => {
                    const reportId = button.dataset.reportId;
                    if (!reportId || !confirm('Delete this retention report? This cannot be undone.')) return;
                    try {
                        const response = await fetch(retentionDeleteUrl(reportId), {
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: { 'X-CSRFToken': getCsrfToken() },
                        });
                        const body = await response.json();
                        if (!response.ok) throw new Error(body?.error || 'Delete failed.');
                        window.location.href = `${cfg.dashboardUrl || ''}?tab=retention-summary-tab`;
                    } catch (error) {
                        alert(error.message || 'Could not delete report.');
                    }
                });
            });

            document.getElementById('rsReset').addEventListener('click', () => {
                populateForm({ as_of_date: todayISO(), lines: [{}] });
            });

            const urlParams = new URLSearchParams(window.location.search);
            const editId = urlParams.get('rs_edit') || cfg.latestRetentionReportId;
            loadReport(editId).catch((error) => {
                console.error(error);
                populateForm({ as_of_date: todayISO(), lines: [{}] });
            });
        })();

        // ══════════════════════════════════════════════════════════════
        // PETTY CASH / REVOLVING FUND REPLENISHMENT REPORT
        // ══════════════════════════════════════════════════════════════

                (function initPettyCash() {
            const cfg = window.__SALES_CONFIG__ || {};
            const itemsBody = document.getElementById('pcItemsBody');
            if (!itemsBody) return;

            const reprInput = document.getElementById('pcReprNumber');
            const reportDateInput = document.getElementById('pcReportDate');
            const noteInput = document.getElementById('pcNote');
            const reportIdInput = document.getElementById('pcReportId');
            const prevBody = document.getElementById('pcPrevItemsBody');
            const importFileInput = document.getElementById('pcImportFile');
            let storedReportTotals = null;

            const CAT_FIELDS = [
                'input-tax', 'fuel', 'fare', 'lodging', 'meal', 'purchases',
                'repair', 'freight', 'meeting', 'office', 'communication',
                'bidding', 'fines', 'misc'
            ];
            const CAT_TO_API = {
                'input-tax': 'input_tax',
                fuel: 'fuel',
                fare: 'fare',
                lodging: 'lodging',
                meal: 'meal',
                purchases: 'purchases',
                repair: 'repair',
                freight: 'freight',
                meeting: 'meeting',
                office: 'office',
                communication: 'communication',
                bidding: 'bidding',
                fines: 'fines',
                misc: 'misc',
            };
            function setStoredReportTotals(data) {
                if (data && data.total_cash_in_bank != null && data.total_cash_in_bank !== '') {
                    storedReportTotals = { cash: parseMoney(data.total_cash_in_bank) };
                } else {
                    storedReportTotals = null;
                }
            }

            function currentCashTotal() {
                return Array.from(itemsBody.querySelectorAll('tr')).reduce(
                    (s, row) => s + parseMoney(row.querySelector('.pc-item-cash')?.value),
                    0
                );
            }

            function activeCashTotal() {
                if (storedReportTotals) return storedReportTotals.cash;
                return currentCashTotal();
            }

            function pettyJsonUrl(reportId) {
                return (cfg.pettyCashJsonUrlTemplate || '').replace('/0/', `/${reportId}/`);
            }

            function pettyDeleteUrl(reportId) {
                return (cfg.pettyCashDeleteUrlTemplate || pettyJsonUrl(reportId).replace('/json/', '/delete/')).replace('/0/', `/${reportId}/`);
            }

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

            function moneyCellsHtml(data = {}) {
                return CAT_FIELDS.map((key) => {
                    const apiKey = CAT_TO_API[key];
                    const value = data[apiKey] || '0.00';
                    return `<td><input type="text" class="pc-item-${key} pc-money pc-cat" value="${escapeHtml(value)}" inputmode="decimal" style="text-align:right;"></td>`;
                }).join('');
            }

            function createRow(data = {}) {
                const cashValue = data.cash_in_bank || '0.00';
                const autoCash = data.cash_in_bank ? '0' : '1';
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><input type="date" class="pc-item-date" value="${escapeHtml(data.line_date || '')}"></td>
                    <td><input type="text" class="pc-item-particulars" placeholder="Name" value="${escapeHtml(data.particulars || '')}"></td>
                    <td><input type="text" class="pc-item-explanation" placeholder="Explanation" value="${escapeHtml(data.explanation || '')}"></td>
                    <td><input type="text" class="pc-item-tin" placeholder="TIN" value="${escapeHtml(data.tin || '')}"></td>
                    <td><input type="text" class="pc-item-pcv" placeholder="PCV#" value="${escapeHtml(data.pcv_number || '')}"></td>
                    <td><input type="text" class="pc-item-cash pc-money" value="${escapeHtml(cashValue)}" data-auto="${autoCash}" inputmode="decimal" style="text-align:right;"></td>
                    ${moneyCellsHtml(data)}
                    <td style="text-align:center;">
                        <button type="button" class="pc-row-remove"
                            style="padding:4px 8px; background:#f5f5f5; border:1px solid var(--line); border-radius:4px; cursor:pointer; color:var(--danger); font-weight:600;">✕</button>
                    </td>
                `;
                if (data.line_date_raw && !data.line_date) {
                    const dateInput = tr.querySelector('.pc-item-date');
                    if (dateInput) {
                        dateInput.type = 'text';
                        dateInput.value = data.line_date_raw;
                        dateInput.dataset.rawDate = data.line_date_raw;
                    }
                }
                return tr;
            }

            function blankMoney(n) {
                return n ? formatMoney(n) : '&nbsp;';
            }

            function collectLinesFromForm() {
                return Array.from(itemsBody.querySelectorAll('tr')).map((row) => {
                    const dateInput = row.querySelector('.pc-item-date');
                    const lineDate = dateInput?.type === 'date' ? (dateInput.value || '') : '';
                    const lineDateRaw = dateInput?.dataset.rawDate || (dateInput?.type !== 'date' ? (dateInput?.value || '') : '');
                    const line = {
                        line_date: lineDate,
                        line_date_raw: lineDateRaw,
                        particulars: row.querySelector('.pc-item-particulars')?.value.trim() || '',
                        explanation: row.querySelector('.pc-item-explanation')?.value.trim() || '',
                        tin: row.querySelector('.pc-item-tin')?.value.trim() || '',
                        pcv_number: row.querySelector('.pc-item-pcv')?.value.trim() || '',
                        cash_in_bank: row.querySelector('.pc-item-cash')?.value.trim() || '',
                    };
                    CAT_FIELDS.forEach((key) => {
                        line[CAT_TO_API[key]] = row.querySelector('.pc-item-' + key)?.value.trim() || '';
                    });
                    return line;
                }).filter((line) => (
                    line.particulars || line.explanation || line.pcv_number || line.line_date || line.line_date_raw
                    || line.cash_in_bank || CAT_FIELDS.some((key) => line[CAT_TO_API[key]])
                ));
            }

            function populateForm(data) {
                if (reportIdInput) reportIdInput.value = data?.id ? String(data.id) : '';
                reprInput.value = data?.repr_number || '';
                reportDateInput.value = data?.report_date || todayISO();
                noteInput.value = data?.note || '';
                setStoredReportTotals(data);
                itemsBody.innerHTML = '';
                const lines = data?.lines?.length ? data.lines : [{}];
                lines.forEach((line) => itemsBody.appendChild(createRow(line)));
                bindMoneyInputs(itemsBody, '.pc-money');
                refreshPreview();
            }

            async function loadReport(reportId) {
                const url = reportId ? pettyJsonUrl(reportId) : (cfg.pettyCashLatestJsonUrl || '');
                if (!url) return;
                const response = await fetch(url, { credentials: 'same-origin' });
                const body = await response.json();
                if (!response.ok) throw new Error(body?.error || 'Unable to load petty cash report.');
                if (!body?.lines?.length && !body?.id) {
                    populateForm({ report_date: todayISO(), lines: [{}] });
                    return;
                }
                populateForm(body);
            }

            async function saveReportToDb() {
                const payload = {
                    id: reportIdInput?.value || null,
                    repr_number: reprInput.value || '',
                    report_date: reportDateInput.value || todayISO(),
                    note: noteInput.value || '',
                    lines: collectLinesFromForm(),
                    total_cash_in_bank: String(activeCashTotal()),
                };
                const response = await fetch(cfg.savePettyCashUrl || '', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                    },
                    body: JSON.stringify(payload),
                });
                const body = await response.json();
                if (!response.ok) throw new Error(body?.error || 'Unable to save petty cash report.');
                if (reportIdInput) reportIdInput.value = String(body.id);
                setStoredReportTotals(body);
                return body;
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
                        const dateInput = row.querySelector('.pc-item-date');
                        const dateVal = dateInput?.type === 'date'
                            ? (dateInput.value || '')
                            : (dateInput?.dataset.rawDate || dateInput?.value || '');
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td>${escapeHtml(formatShortDate(dateVal) || dateVal || '\u00a0')}</td>
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

                totals.cash = activeCashTotal();
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
                if (e.target.classList.contains('pc-cat')) {
                    syncCash(row);
                    storedReportTotals = null;
                }
                if (e.target.classList.contains('pc-item-cash')) {
                    e.target.dataset.auto = '0';
                    storedReportTotals = null;
                }
                refreshPreview();
            });
            itemsBody.addEventListener('change', () => {
                storedReportTotals = null;
                refreshPreview();
            });
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
                storedReportTotals = null;
                refreshPreview();
            });

            document.getElementById('pcAddRow').addEventListener('click', () => {
                itemsBody.appendChild(createRow());
                bindMoneyInputs(itemsBody, '.pc-money');
                storedReportTotals = null;
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
                let savedReportId = reportIdInput?.value || null;
                try {
                    if (mode === 'save') {
                        const saved = await saveReportToDb();
                        savedReportId = saved.id;
                    }

                    const pageW = 1600;
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
                            min-width: ${pageW}px !important;
                            max-width: none !important;
                            background: #fff !important;
                            color: #111 !important;
                            font-family: Arial, Helvetica, sans-serif !important;
                            font-size: 10px !important;
                            box-sizing: border-box !important;
                            padding: 10px 12px 16px !important;
                            overflow: visible !important;
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
                            table-layout: fixed !important; font-size: 7px !important;
                        }
                        #pc-print-sheet .pc-items th, #pc-print-sheet .pc-items td {
                            border: 1px solid #222 !important; padding: 2px 2px !important; vertical-align: top !important;
                            word-break: break-word !important; overflow-wrap: anywhere !important;
                            white-space: normal !important; color: #111 !important;
                        }
                        #pc-print-sheet .pc-items th {
                            background: #e5e7eb !important; font-weight: 700 !important; text-align: center !important;
                            text-transform: uppercase !important; font-size: 6px !important; line-height: 1.15 !important;
                        }
                        #pc-print-sheet .pc-num { text-align: right !important; white-space: normal !important; }
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

                    const pdfBlob = await landscapePdfFromSheet(sheet, { width: pageW, margin: 6, maxPages: 16, jpegQuality: 0.96 });
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
                            sourceId: savedReportId,
                        });
                        alert('Petty cash saved to the database and PDF archived.');
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

            if (importFileInput) {
                importFileInput.addEventListener('change', async () => {
                    const file = importFileInput.files?.[0];
                    importFileInput.value = '';
                    if (!file) return;
                    if (!file.name.toLowerCase().endsWith('.xlsx')) {
                        alert('Please choose an .xlsx file.');
                        return;
                    }
                    const formData = new FormData();
                    formData.append('xlsx', file);
                    formData.append('report_date', reportDateInput.value || todayISO());
                    formData.append('repr_number', reprInput.value || '');
                    formData.append('note', noteInput.value || '');
                    try {
                        const response = await fetch(cfg.importPettyCashUrl || '', {
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: { 'X-CSRFToken': getCsrfToken() },
                            body: formData,
                        });
                        const body = await response.json();
                        if (!response.ok) throw new Error(body?.error || 'Import failed.');
                        populateForm(body);
                        alert(`Imported ${body.lines.length} rows from ${file.name}.`);
                        window.location.href = `${cfg.dashboardUrl || ''}?tab=petty-cash-tab`;
                    } catch (error) {
                        alert(error.message || 'Could not import Excel file.');
                    }
                });
            }

            document.querySelectorAll('.pc-load-report').forEach((button) => {
                button.addEventListener('click', async () => {
                    try {
                        await loadReport(button.dataset.reportId);
                        activateTab('petty-cash-tab');
                    } catch (error) {
                        alert(error.message || 'Could not load report.');
                    }
                });
            });

            document.querySelectorAll('.pc-delete-report').forEach((button) => {
                button.addEventListener('click', async () => {
                    const reportId = button.dataset.reportId;
                    if (!reportId || !confirm('Delete this petty cash report? This cannot be undone.')) return;
                    try {
                        const response = await fetch(pettyDeleteUrl(reportId), {
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: { 'X-CSRFToken': getCsrfToken() },
                        });
                        const body = await response.json();
                        if (!response.ok) throw new Error(body?.error || 'Delete failed.');
                        window.location.href = `${cfg.dashboardUrl || ''}?tab=petty-cash-tab`;
                    } catch (error) {
                        alert(error.message || 'Could not delete report.');
                    }
                });
            });

            document.getElementById('pcReset').addEventListener('click', () => {
                populateForm({ report_date: todayISO(), lines: [{}] });
            });

            const urlParams = new URLSearchParams(window.location.search);
            const editId = urlParams.get('pc_edit') || cfg.latestPettyCashReportId;
            loadReport(editId).catch((error) => {
                console.error(error);
                populateForm({ report_date: todayISO(), lines: [{}] });
            });
        })();

        // CHECK VOUCHER
        (function initCheckVoucher() {
            const cfg = window.__SALES_CONFIG__ || {};
            const linesBody = document.getElementById('cvLinesBody');
            if (!linesBody) return;
            const creditLinesBody = document.getElementById('cvCreditLinesBody');
            const accountLinesBody = document.getElementById('cvAccountLinesBody');

            const cvSubtabButtons = document.querySelectorAll('.cv-subtab[data-cv-view]');
            const cvSubpanels = document.querySelectorAll('.cv-subpanel');
            const cvViewInput = document.getElementById('cvViewInput');

            function activateCvView(view, pushUrl) {
                const target = view === 'monitoring' ? 'monitoring' : 'form';
                cvSubtabButtons.forEach((btn) => {
                    const isActive = btn.dataset.cvView === target;
                    btn.classList.toggle('is-active', isActive);
                    btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
                });
                cvSubpanels.forEach((panel) => {
                    const isFormPanel = panel.classList.contains('cv-subpanel-form');
                    const isActive = target === 'form' ? isFormPanel : !isFormPanel;
                    panel.classList.toggle('is-active', isActive);
                });
                if (cvViewInput) {
                    cvViewInput.value = target;
                }
                if (pushUrl) {
                    const url = new URL(window.location.href);
                    url.searchParams.set('tab', 'check-voucher-tab');
                    url.searchParams.set('cv_view', target);
                    window.history.pushState({}, '', url);
                }
            }

            cvSubtabButtons.forEach((btn) => {
                btn.addEventListener('click', () => activateCvView(btn.dataset.cvView, true));
            });

            const initialCvView = new URLSearchParams(window.location.search).get('cv_view') === 'monitoring' ? 'monitoring' : 'form';
            activateCvView(initialCvView, false);

            const fields = {
                id: document.getElementById('cvVoucherId'),
                company: document.getElementById('cvCompany'),
                cv_number: document.getElementById('cvNumber'),
                voucher_date: document.getElementById('cvDate'),
                payee: document.getElementById('cvPayee'),
                payee_address: document.getElementById('cvPayeeAddress'),
                particulars: document.getElementById('cvParticulars'),
                payment_for: document.getElementById('cvPaymentFor'),
                bank: document.getElementById('cvBank'),
                check_number: document.getElementById('cvCheckNumber'),
                check_date: document.getElementById('cvCheckDate'),
                received_by: document.getElementById('cvReceivedBy'),
                signatory_prepared: document.getElementById('cvSignPrepared'),
                signatory_checked: document.getElementById('cvSignChecked'),
                signatory_approved: document.getElementById('cvSignApproved'),
                signatory_approver: document.getElementById('cvSignApprover'),
                signatory_prepared_title: document.getElementById('cvSignPreparedTitle'),
                signatory_checked_title: document.getElementById('cvSignCheckedTitle'),
                signatory_approved_title: document.getElementById('cvSignApprovedTitle'),
                signatory_received_title: document.getElementById('cvSignReceivedTitle'),
                category: document.getElementById('cvCategory'),
                categoryAmount: document.getElementById('cvCategoryAmount'),
                withholding_tax: document.getElementById('cvWithholdingTax'),
                withholding_label: document.getElementById('cvWithholdingLabel'),
            };
            const CV_CATEGORY_KEYS = ['purchases', 'expenses', 'commission', 'contributions', 'misc', 'payment', 'salaries'];
            const CV_COMPANIES = {
                mdspii: {
                    name: 'METRO DAVAO SUPREME PUMPS INDUSTRIES, INC.',
                    address: '#406 DIAMOND ST., SAN JUAN SUBD., PANACAN, DAVAO CITY',
                    receivedFrom: 'Received from MDSPII',
                },
                versatec: {
                    name: 'VERSATEC INDUSTRIAL CORPORATION',
                    address: 'Lot 30-B, Prk. Batong, Brgy. Nanyo, Panabo City, Davao del Norte 8105',
                    receivedFrom: 'Received from VERSATEC',
                },
                mdtcii: {
                    name: 'METRO DAVAO TRADE & CONSTRUCTION INDUSTRIES, INC.',
                    address: '#406 DIAMOND ST., SAN JUAN SUBD., PANACAN, DAVAO CITY',
                    receivedFrom: 'Received from MDTCII',
                },
                dai: {
                    name: 'DAI HOLDINGS, INC.',
                    address: '#406 St. San Juan Subdivision, Diamond St., Panacan, Bunawan Dist., Davao City',
                    receivedFrom: 'Received from DAI HOLDINGS, INC.',
                    layout: 'dai',
                },
            };
            function normalizeCompany(value) {
                const key = String(value || 'mdspii').trim().toLowerCase();
                return CV_COMPANIES[key] ? key : 'mdspii';
            }
            // Original breakdown of the loaded voucher (for split preservation).
            let cvOriginalBreakdown = null;
            let cvCategoryDirty = false;

            function dominantCategory(breakdown) {
                let best = 'expenses';
                let bestValue = 0;
                CV_CATEGORY_KEYS.forEach((key) => {
                    const value = parseMoney(breakdown?.[key] ?? 0);
                    if (value > bestValue) {
                        bestValue = value;
                        best = key;
                    }
                });
                return best;
            }

            function isSplitBreakdown(breakdown) {
                if (!breakdown) return false;
                return CV_CATEGORY_KEYS.filter((key) => parseMoney(breakdown[key] ?? 0) > 0).length > 1;
            }

            function cvJsonUrl(id) {
                return (cfg.checkVoucherJsonUrlTemplate || '').replace('/0/', `/${id}/`);
            }

            function cvDeleteUrl(id) {
                return (cfg.checkVoucherDeleteUrlTemplate || cvJsonUrl(id).replace('/json/', '/delete/')).replace('/0/', `/${id}/`);
            }

            function cvCellUrl(id) {
                return (cfg.checkVoucherCellUrlTemplate || cvJsonUrl(id).replace('/json/', '/cell/')).replace('/0/', `/${id}/`);
            }

            function todayISO() {
                const d = new Date();
                return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
            }

            function escapeHtml(str) {
                return String(str || '')
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;');
            }

            function formatLongDate(iso) {
                if (!iso) return '';
                const d = new Date(iso + 'T00:00:00');
                if (Number.isNaN(d.getTime())) return iso;
                return d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
            }

            function formatDaiCheckDate(iso) {
                if (!iso) return '';
                const d = new Date(iso + 'T00:00:00');
                if (Number.isNaN(d.getTime())) return iso;
                return `${d.getMonth() + 1}-${d.getDate()}-${String(d.getFullYear()).slice(-2)}`;
            }

            function createLine(data = {}) {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><input type="text" class="cv-line-description" value="${escapeHtml(data.description || '')}" placeholder="BILLING NO. 26-1175"></td>
                    <td><input type="text" class="cv-line-amount cv-money-input" value="${escapeHtml(data.debit_amount || '')}" inputmode="decimal" style="text-align:right;"></td>
                    <td style="text-align:center;"><button type="button" class="cv-line-remove" style="padding:4px 8px; border:1px solid var(--line); border-radius:4px; color:var(--danger);">x</button></td>
                `;
                return tr;
            }

            function createCreditLine(data = {}) {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><input type="text" class="cv-credit-line-description" value="${escapeHtml(data.description || '')}" placeholder="HDMF CONTRIBUTION"></td>
                    <td><input type="text" class="cv-credit-line-amount cv-money-input" value="${escapeHtml(data.credit_amount || '')}" inputmode="decimal" style="text-align:right;"></td>
                    <td style="text-align:center;"><button type="button" class="cv-credit-line-remove" style="padding:4px 8px; border:1px solid var(--line); border-radius:4px; color:var(--danger);">x</button></td>
                `;
                return tr;
            }

            function createAccountLine(data = {}) {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><input type="text" class="cv-account-line-description" value="${escapeHtml(data.description || '')}" placeholder="LOANS PAYABLE"></td>
                    <td><input type="text" class="cv-account-line-debit cv-money-input" value="${escapeHtml(data.debit_amount || '')}" inputmode="decimal" style="text-align:right;"></td>
                    <td><input type="text" class="cv-account-line-credit cv-money-input" value="${escapeHtml(data.credit_amount || '')}" inputmode="decimal" style="text-align:right;"></td>
                    <td style="text-align:center;"><button type="button" class="cv-account-line-remove" style="padding:4px 8px; border:1px solid var(--line); border-radius:4px; color:var(--danger);">x</button></td>
                `;
                return tr;
            }

            function debitTotal() {
                return Array.from(linesBody.querySelectorAll('.cv-line-amount'))
                    .reduce((sum, input) => sum + parseMoney(input.value), 0);
            }

            function creditLinesTotal() {
                if (!creditLinesBody) return 0;
                return Array.from(creditLinesBody.querySelectorAll('.cv-credit-line-amount'))
                    .reduce((sum, input) => sum + parseMoney(input.value), 0);
            }

            function withholdingTotal() {
                const raw = parseMoney(fields.withholding_tax?.value || '');
                if (!raw || raw < 0) return 0;
                const available = Math.max(0, debitTotal() - creditLinesTotal());
                return Math.min(raw, available);
            }

            function cashTotal() {
                return Math.max(0, debitTotal() - creditLinesTotal() - withholdingTotal());
            }

            function collectLines() {
                return Array.from(linesBody.querySelectorAll('tr')).map((row) => ({
                    description: row.querySelector('.cv-line-description')?.value.trim() || '',
                    debit_amount: row.querySelector('.cv-line-amount')?.value.trim() || '',
                })).filter((line) => line.description || line.debit_amount);
            }

            function collectCreditLines() {
                if (!creditLinesBody) return [];
                return Array.from(creditLinesBody.querySelectorAll('tr')).map((row) => ({
                    description: row.querySelector('.cv-credit-line-description')?.value.trim() || '',
                    credit_amount: row.querySelector('.cv-credit-line-amount')?.value.trim() || '',
                })).filter((line) => line.description || line.credit_amount);
            }

            function collectAccountLines() {
                if (!accountLinesBody) return [];
                return Array.from(accountLinesBody.querySelectorAll('tr')).map((row) => ({
                    description: row.querySelector('.cv-account-line-description')?.value.trim() || '',
                    debit_amount: row.querySelector('.cv-account-line-debit')?.value.trim() || '',
                    credit_amount: row.querySelector('.cv-account-line-credit')?.value.trim() || '',
                })).filter((line) => line.description || line.debit_amount || line.credit_amount);
            }

            function accountDebitTotal() {
                if (!accountLinesBody) return 0;
                return Array.from(accountLinesBody.querySelectorAll('.cv-account-line-debit'))
                    .reduce((sum, input) => sum + parseMoney(input.value), 0);
            }

            function accountCreditTotal() {
                if (!accountLinesBody) return 0;
                return Array.from(accountLinesBody.querySelectorAll('.cv-account-line-credit'))
                    .reduce((sum, input) => sum + parseMoney(input.value), 0);
            }

            function payloadFromForm() {
                const withholding = withholdingTotal();
                const cash = cashTotal();
                const selectedCategory = fields.category?.value || 'expenses';
                const payload = {
                    id: fields.id?.value || null,
                    company: normalizeCompany(fields.company?.value),
                    cv_number: fields.cv_number.value.trim(),
                    voucher_date: fields.voucher_date.value || todayISO(),
                    payee: fields.payee.value.trim(),
                    payee_address: fields.payee_address?.value.trim() || '',
                    particulars: fields.particulars?.value.trim() || '',
                    payment_for: fields.payment_for.value.trim(),
                    bank: fields.bank.value.trim(),
                    check_number: fields.check_number.value.trim(),
                    check_date: fields.check_date.value || '',
                    received_by: fields.received_by.value.trim(),
                    signatory_prepared: fields.signatory_prepared.value.trim(),
                    signatory_checked: fields.signatory_checked.value.trim(),
                    signatory_approved: fields.signatory_approved.value.trim(),
                    signatory_approver: fields.signatory_approver.value.trim(),
                    signatory_prepared_title: fields.signatory_prepared_title?.value.trim() || '',
                    signatory_checked_title: fields.signatory_checked_title?.value.trim() || '',
                    signatory_approved_title: fields.signatory_approved_title?.value.trim() || '',
                    signatory_received_title: fields.signatory_received_title?.value.trim() || '',
                    withholding_tax: String(withholding),
                    withholding_label: (fields.withholding_label?.value.trim() || 'WITHHOLDING TAX'),
                    cash_in_bank: String(cash),
                    check_amount: String(cash),
                    category: selectedCategory,
                    lines: collectLines(),
                    credit_lines: collectCreditLines(),
                    account_lines: collectAccountLines(),
                };
                if (!cvCategoryDirty && isSplitBreakdown(cvOriginalBreakdown)) {
                    // Preserve an imported / previously split breakdown unless
                    // the user explicitly picked a new category.
                    CV_CATEGORY_KEYS.forEach((key) => {
                        payload[key] = cvOriginalBreakdown[key] ?? '0';
                    });
                } else {
                    CV_CATEGORY_KEYS.forEach((key) => {
                        payload[key] = key === selectedCategory ? String(cash) : '0';
                    });
                }
                return payload;
            }

            function populateForm(data = {}) {
                fields.id.value = data.id ? String(data.id) : '';
                if (fields.company) fields.company.value = normalizeCompany(data.company || 'mdspii');
                fields.cv_number.value = data.cv_number || cfg.nextCvNumber || '';
                fields.voucher_date.value = data.voucher_date || todayISO();
                fields.payee.value = data.payee || '';
                if (fields.payee_address) fields.payee_address.value = data.payee_address || '';
                if (fields.particulars) fields.particulars.value = data.particulars || '';
                fields.payment_for.value = data.payment_for || data.payee || '';
                fields.bank.value = data.bank || '';
                fields.check_number.value = data.check_number || '';
                fields.check_date.value = data.check_date || '';
                fields.received_by.value = data.received_by || '';
                fields.signatory_prepared.value = data.signatory_prepared || 'ANGELMARIE M. DAPAR';
                fields.signatory_checked.value = data.signatory_checked || 'Ms. BEVERLY TAN';
                fields.signatory_approved.value = data.signatory_approved || 'CHRISTINE JOY ILOGON';
                fields.signatory_approver.value = data.signatory_approver || 'ENGR. ARTURO I DAVIS, PME';
                if (fields.signatory_prepared_title) fields.signatory_prepared_title.value = data.signatory_prepared_title || 'Executive Asst.';
                if (fields.signatory_checked_title) fields.signatory_checked_title.value = data.signatory_checked_title || 'Asst. Head';
                if (fields.signatory_approved_title) fields.signatory_approved_title.value = data.signatory_approved_title || 'President/CEO';
                if (fields.signatory_received_title) fields.signatory_received_title.value = data.signatory_received_title || '';
                if (fields.withholding_tax) fields.withholding_tax.value = data.withholding_tax || '';
                if (fields.withholding_label) fields.withholding_label.value = data.withholding_label || 'WITHHOLDING TAX';
                cvOriginalBreakdown = {};
                CV_CATEGORY_KEYS.forEach((key) => {
                    cvOriginalBreakdown[key] = data[key] ?? '0';
                });
                cvCategoryDirty = false;
                if (fields.category) {
                    const incoming = data.category || dominantCategory(cvOriginalBreakdown);
                    fields.category.value = CV_CATEGORY_KEYS.includes(incoming) ? incoming : 'expenses';
                    const hint = document.getElementById('cvCategoryHint');
                    if (hint) {
                        hint.textContent = isSplitBreakdown(cvOriginalBreakdown)
                            ? 'This voucher has a split breakdown from an import. Pick a category above to re-assign the full amount, or leave it to keep the split.'
                            : 'The full check amount will be saved to the selected category. Imported workbooks keep their breakdowns; split breakdowns can still be fine-tuned in the CV Monitoring table below.';
                    }
                }
                linesBody.innerHTML = '';
                (data.lines && data.lines.length ? data.lines : [{}, {}]).forEach((line) => linesBody.appendChild(createLine(line)));
                bindMoneyInputs(linesBody, '.cv-money-input');
                if (creditLinesBody) {
                    creditLinesBody.innerHTML = '';
                    (data.credit_lines && data.credit_lines.length ? data.credit_lines : [{}, {}]).forEach((line) => creditLinesBody.appendChild(createCreditLine(line)));
                    bindMoneyInputs(creditLinesBody, '.cv-money-input');
                }
                if (accountLinesBody) {
                    accountLinesBody.innerHTML = '';
                    (data.account_lines && data.account_lines.length ? data.account_lines : [{}, {}]).forEach((line) => accountLinesBody.appendChild(createAccountLine(line)));
                    bindMoneyInputs(accountLinesBody, '.cv-money-input');
                }
                refreshPreview();
            }

            function refreshPreview() {
                const total = debitTotal();
                const credits = creditLinesTotal();
                const withholding = withholdingTotal();
                const cash = cashTotal();
                const deductionsTotal = credits + withholding;
                const totalsCredit = cash + deductionsTotal;
                const withholdingLabel = (fields.withholding_label?.value.trim() || 'WITHHOLDING TAX').toUpperCase();
                document.getElementById('cvDebitTotal').textContent = 'PHP ' + formatMoney(total);
                const creditLinesTotalEl = document.getElementById('cvCreditLinesTotal');
                if (creditLinesTotalEl) creditLinesTotalEl.textContent = 'PHP ' + formatMoney(credits);
                const withholdingTotalEl = document.getElementById('cvWithholdingTotal');
                if (withholdingTotalEl) withholdingTotalEl.textContent = 'PHP ' + formatMoney(withholding);
                document.getElementById('cvCreditTotal').textContent = 'PHP ' + formatMoney(cash);
                const acctDebitEl = document.getElementById('cvAccountDebitTotal');
                if (acctDebitEl) acctDebitEl.textContent = 'PHP ' + formatMoney(accountDebitTotal());
                const acctCreditEl = document.getElementById('cvAccountCreditTotal');
                if (acctCreditEl) acctCreditEl.textContent = 'PHP ' + formatMoney(accountCreditTotal());
                if (fields.categoryAmount) {
                    const label = (fields.category?.selectedOptions?.[0]?.textContent || fields.category?.value || '').trim();
                    fields.categoryAmount.value = cash > 0 && label ? `${label} — PHP ${formatMoney(cash)}` : `PHP ${formatMoney(cash)}`;
                }
                const companyKey = normalizeCompany(fields.company?.value);
                const profile = CV_COMPANIES[companyKey];
                const textHead = document.getElementById('cvTextLetterhead');
                const imageHead = document.getElementById('cvImageLetterhead');
                if (textHead) textHead.style.display = companyKey === 'versatec' ? 'none' : '';
                if (imageHead) imageHead.style.display = companyKey === 'versatec' ? '' : 'none';
                const companyNameEl = document.getElementById('cvPrevCompany');
                if (companyNameEl) companyNameEl.textContent = profile.name;
                const companyAddrEl = document.getElementById('cvPrevCompanyAddress');
                if (companyAddrEl) companyAddrEl.textContent = profile.address;
                const receivedFromEl = document.getElementById('cvReceivedFromLabel');
                if (receivedFromEl) receivedFromEl.textContent = profile.receivedFrom;
                document.getElementById('cvPrevNumber').textContent = fields.cv_number.value.trim() || cfg.nextCvNumber || '';
                document.getElementById('cvPrevDate').textContent = formatLongDate(fields.voucher_date.value);
                document.getElementById('cvPrevPayee').textContent = (fields.payee.value || '').toUpperCase();
                document.getElementById('cvPrevWithholdingLabel').textContent = withholdingLabel;
                document.getElementById('cvPrevWithholding').textContent = formatMoney(withholding);
                const withholdingRow = document.getElementById('cvPrevWithholdingRow');
                if (withholdingRow) withholdingRow.style.display = withholding > 0 ? '' : 'none';
                document.getElementById('cvPrevCash').textContent = formatMoney(cash);
                document.getElementById('cvPrevDebitTotal').textContent = formatMoney(total);
                document.getElementById('cvPrevCreditTotal').textContent = formatMoney(totalsCredit);
                document.getElementById('cvPrevPaymentFor').textContent = (fields.payment_for.value || fields.payee.value || '\u00a0').toUpperCase();
                document.getElementById('cvPrevCheckAmount').textContent = formatMoney(cash);
                document.getElementById('cvPrevCheckNumber').textContent = fields.check_number.value || '';
                document.getElementById('cvPrevBank').textContent = fields.bank.value || '';
                document.getElementById('cvPrevReceivedBy').textContent = fields.received_by.value || '';
                document.getElementById('cvPrevSignPrepared').textContent = fields.signatory_prepared.value || 'ANGELMARIE M. DAPAR';
                document.getElementById('cvPrevSignChecked').textContent = fields.signatory_checked.value || 'Ms. BEVERLY TAN';
                document.getElementById('cvPrevSignApproved').textContent = fields.signatory_approved.value || 'CHRISTINE JOY ILOGON';
                document.getElementById('cvPrevSignApprover').textContent = fields.signatory_approver.value || 'ENGR. ARTURO I DAVIS, PME';

                const preview = document.getElementById('cvPreviewLines');
                preview.innerHTML = '';
                const lines = collectLines();
                const creditLines = collectCreditLines();
                const rows = lines.length ? lines : [{}];
                rows.forEach((line) => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `<td colspan="2" class="cv-desc">${escapeHtml(line.description || '\u00a0').toUpperCase()}</td><td class="cv-money">${line.debit_amount ? formatMoney(parseMoney(line.debit_amount)) : '\u00a0'}</td><td class="cv-money">&nbsp;</td>`;
                    preview.appendChild(tr);
                });
                creditLines.forEach((line) => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `<td colspan="2" class="cv-desc">${escapeHtml(line.description || '\u00a0').toUpperCase()}</td><td class="cv-money">&nbsp;</td><td class="cv-money">${line.credit_amount ? formatMoney(parseMoney(line.credit_amount)) : '\u00a0'}</td>`;
                    preview.appendChild(tr);
                });
                for (let i = rows.length + creditLines.length; i < 6; i += 1) {
                    const tr = document.createElement('tr');
                    tr.innerHTML = '<td colspan="2" class="cv-desc">&nbsp;</td><td class="cv-money">&nbsp;</td><td class="cv-money">&nbsp;</td>';
                    preview.appendChild(tr);
                }

                renderDaiPreview(companyKey, { cash, total });
            }

            function renderDaiPreview(companyKey, amounts = {}) {
                const isDai = companyKey === 'dai';
                const stdDoc = document.getElementById('cvDocument');
                const daiDoc = document.getElementById('cvDocumentDai');
                if (stdDoc) stdDoc.style.display = isDai ? 'none' : '';
                if (daiDoc) daiDoc.style.display = isDai ? '' : 'none';
                document.body.classList.toggle('is-cv-dai', isDai);
                if (!isDai || !daiDoc) return;
                const profile = CV_COMPANIES.dai;
                const setText = (id, val) => {
                    const el = document.getElementById(id);
                    if (el) el.textContent = val == null ? '' : String(val);
                };
                setText('cvDaiCompany', profile.name);
                setText('cvDaiCompanyAddress', profile.address);
                setText('cvDaiPayee', (fields.payee.value || '').toUpperCase());
                setText('cvDaiNumber', fields.cv_number.value.trim() || cfg.nextCvNumber || '');
                setText('cvDaiAddress', (fields.payee_address?.value || '').toUpperCase());
                setText('cvDaiDate', formatLongDate(fields.voucher_date.value));
                const particulars = fields.particulars?.value?.trim() || fields.payment_for.value || '';
                setText('cvDaiParticulars', particulars.toUpperCase());
                setText('cvDaiCheckNumber', fields.check_number.value || '');
                setText('cvDaiCheckDate', formatDaiCheckDate(fields.check_date.value));
                setText('cvDaiBank', fields.bank.value || '');
                setText('cvDaiPhp', formatMoney(amounts.cash || 0));
                setText('cvDaiTotal', formatMoney(amounts.total || 0));
                setText('cvDaiSignPrepared', fields.signatory_prepared.value || '');
                setText('cvDaiSignPreparedTitle', fields.signatory_prepared_title?.value || '');
                setText('cvDaiSignChecked', fields.signatory_checked.value || '');
                setText('cvDaiSignCheckedTitle', fields.signatory_checked_title?.value || '');
                setText('cvDaiSignApproved', fields.signatory_approved.value || '');
                setText('cvDaiSignApprovedTitle', fields.signatory_approved_title?.value || '');
                setText('cvDaiSignApprover', fields.signatory_approver.value || '');
                setText('cvDaiSignReceivedTitle', fields.signatory_received_title?.value || '');
                const items = document.getElementById('cvDaiItems');
                if (items) {
                    items.innerHTML = '';
                    (collectLines().length ? collectLines() : [{}]).forEach((line) => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `<td class="cv-dai-item-desc">${escapeHtml((line.description || '').toUpperCase())}</td><td class="cv-dai-item-amt">${line.debit_amount ? formatMoney(parseMoney(line.debit_amount)) : ''}</td>`;
                        items.appendChild(tr);
                    });
                }
                const dist = document.getElementById('cvDaiDistLines');
                if (dist) {
                    dist.innerHTML = '';
                    collectAccountLines().forEach((line) => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `<td class="cv-dai-dist-line-desc">${escapeHtml((line.description || '').toUpperCase())}</td><td class="cv-dai-dist-line-dr">${line.debit_amount ? formatMoney(parseMoney(line.debit_amount)) : ''}</td><td class="cv-dai-dist-line-cr">${line.credit_amount ? formatMoney(parseMoney(line.credit_amount)) : ''}</td>`;
                        dist.appendChild(tr);
                    });
                }
                const distDebit = accountDebitTotal();
                const distCredit = accountCreditTotal();
                setText('cvDaiDistDebitTotal', distDebit ? formatMoney(distDebit) : '');
                setText('cvDaiDistCreditTotal', distCredit ? formatMoney(distCredit) : '');
            }

            async function loadVoucher(id) {
                const url = id ? cvJsonUrl(id) : (cfg.checkVoucherLatestJsonUrl || '');
                if (!url) throw new Error('Check-voucher URL is not configured.');
                const response = await fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                const contentType = response.headers.get('content-type') || '';
                if (!contentType.includes('application/json')) {
                    throw new Error('Session expired or server returned a non-JSON response. Please refresh and log in again.');
                }
                const body = await response.json();
                if (!response.ok) throw new Error(body?.error || 'Unable to load check voucher.');
                if (!body?.id) {
                    populateForm({});
                    return body;
                }
                populateForm(body);
                return body;
            }

            async function saveVoucherToDb() {
                const response = await fetch(cfg.saveCheckVoucherUrl || '', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                    },
                    body: JSON.stringify(payloadFromForm()),
                });
                const body = await response.json();
                if (!response.ok) throw new Error(body?.error || 'Unable to save check voucher.');
                fields.id.value = String(body.id);
                cvOriginalBreakdown = {};
                CV_CATEGORY_KEYS.forEach((key) => {
                    cvOriginalBreakdown[key] = body[key] ?? '0';
                });
                cvCategoryDirty = false;
                return body;
            }

            function showCvModal(message, type = 'success') {
                return new Promise((resolve) => {
                    try {
                        document.querySelectorAll('dialog[open]').forEach((d) => {
                            try { d.close(); } catch (_) { /* ignore */ }
                        });
                    } catch (_) { /* ignore */ }
                    const old = document.getElementById('cvConfirmModal');
                    if (old) old.remove();
                    const kind = type === 'error' ? 'error' : 'success';
                    const dialog = document.createElement('dialog');
                    dialog.className = 'flash-modal';
                    dialog.id = 'cvConfirmModal';
                    dialog.innerHTML = `<div class="flash-modal-card">
                        <div class="flash-modal-icon ${kind}" aria-hidden="true">${kind === 'error' ? '✕' : '✓'}</div>
                        <h2 class="flash-modal-title ${kind}">${kind === 'error' ? 'Error' : 'Success'}</h2>
                        <div class="flash-modal-body"><p class="flash-modal-text"></p></div>
                        <form method="dialog"><button type="submit" class="flash-modal-ok">OK</button></form>
                    </div>`;
                    dialog.querySelector('.flash-modal-text').textContent = message;
                    document.body.appendChild(dialog);
                    let settled = false;
                    const done = () => {
                        if (settled) return;
                        settled = true;
                        try { dialog.close(); } catch (_) { /* ignore */ }
                        dialog.remove();
                        resolve();
                    };
                    dialog.addEventListener('close', done, { once: true });
                    dialog.querySelector('form').addEventListener('submit', done);
                    dialog.addEventListener('click', (event) => {
                        const box = dialog.getBoundingClientRect();
                        const outside = event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom;
                        if (outside) done();
                    });
                    if (typeof dialog.showModal === 'function') dialog.showModal();
                    else dialog.setAttribute('open', '');
                    const okBtn = dialog.querySelector('.flash-modal-ok');
                    if (okBtn) okBtn.focus();
                });
            }

            function showCvConfirm(message) {
                return new Promise((resolve) => {
                    try {
                        document.querySelectorAll('dialog[open]').forEach((d) => {
                            try { d.close(); } catch (_) { /* ignore */ }
                        });
                    } catch (_) { /* ignore */ }
                    const old = document.getElementById('cvConfirmModal');
                    if (old) old.remove();
                    const dialog = document.createElement('dialog');
                    dialog.className = 'flash-modal';
                    dialog.id = 'cvConfirmModal';
                    dialog.innerHTML = `<div class="flash-modal-card">
                        <div class="flash-modal-icon info" aria-hidden="true">?</div>
                        <h2 class="flash-modal-title info">Confirm save</h2>
                        <div class="flash-modal-body"><p class="flash-modal-text"></p></div>
                        <form method="dialog" class="flash-modal-actions">
                            <button type="button" class="flash-modal-cancel">Cancel</button>
                            <button type="submit" class="flash-modal-ok">Save</button>
                        </form>
                    </div>`;
                    dialog.querySelector('.flash-modal-text').textContent = message;
                    document.body.appendChild(dialog);
                    let settled = false;
                    const done = (value) => {
                        if (settled) return;
                        settled = true;
                        try { dialog.close(); } catch (_) { /* ignore */ }
                        dialog.remove();
                        resolve(value);
                    };
                    dialog.addEventListener('close', () => done(false), { once: true });
                    dialog.querySelector('form').addEventListener('submit', () => done(true));
                    dialog.querySelector('.flash-modal-cancel').addEventListener('click', () => done(false));
                    dialog.addEventListener('click', (event) => {
                        const box = dialog.getBoundingClientRect();
                        const outside = event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom;
                        if (outside) done(false);
                    });
                    dialog.addEventListener('keydown', (event) => {
                        if (event.key === 'Escape') done(false);
                    });
                    if (typeof dialog.showModal === 'function') dialog.showModal();
                    else dialog.setAttribute('open', '');
                    const saveBtn = dialog.querySelector('.flash-modal-ok');
                    if (saveBtn) saveBtn.focus();
                });
            }

            async function runVoucherPdf(mode) {
                if (mode === 'save') {
                    const cvnoPreview = (fields.cv_number && fields.cv_number.value.trim()) || cfg.nextCvNumber || 'new voucher';
                    const confirmed = await showCvConfirm(`Save check voucher ${cvnoPreview}? It will be added to the CV Monitoring table below.`);
                    if (!confirmed) return;
                }
                const url = new URL(window.location);
                url.searchParams.set('tab', 'check-voucher-tab');
                window.history.pushState({}, '', url);
                activateTab('check-voucher-tab');
                activateCvView('form', false);

                const isDaiLayout = normalizeCompany(fields.company?.value) === 'dai';
                const docEl = document.getElementById(isDaiLayout ? 'cvDocumentDai' : 'cvDocument');
                if (!docEl) return;
                if (typeof html2canvas === 'undefined' || !(window.jspdf && window.jspdf.jsPDF)) {
                    await showCvModal('PDF libraries failed to load. Please refresh and try again.', 'error');
                    return;
                }

                const btn = document.getElementById(mode === 'save' ? 'cvSave' : 'cvPrint');
                const prevLabel = btn ? btn.textContent : '';
                if (btn) {
                    btn.disabled = true;
                    btn.textContent = mode === 'save' ? 'Saving...' : 'Preparing...';
                }

                let holder = null;
                let savedId = fields.id.value || null;
                try {
                    if (mode === 'save') {
                        const saved = await saveVoucherToDb();
                        savedId = saved.id;
                    }
                    holder = document.createElement('div');
                    holder.style.cssText = 'position:fixed;left:0;top:0;width:1200px;background:#fff;visibility:hidden;pointer-events:none;z-index:-1;';
                    const sheet = docEl.cloneNode(true);
                    sheet.style.width = '1200px';
                    sheet.style.maxWidth = 'none';
                    sheet.style.display = '';
                    holder.appendChild(sheet);
                    document.body.appendChild(holder);
                    const pdfBlob = await landscapePdfFromSheet(sheet, { width: 1200, margin: 8, maxPages: 2, jpegQuality: 0.98 });
                    holder.remove();
                    holder = null;
                    if (mode === 'save') {
                        const cvno = fields.cv_number.value.trim() || 'check_voucher';
                        await uploadSalesDocumentPdf({
                            blob: pdfBlob,
                            documentType: 'check_voucher',
                            title: `Check Voucher ${cvno}`,
                            reference: cvno,
                            fileName: `check_voucher_${cvno}`,
                            sourceId: savedId,
                        });
                        let upserted = false;
                        try {
                            let fresh = null;
                            try {
                                const resp = await fetch(cvJsonUrl(savedId), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                                const contentType = resp.headers.get('content-type') || '';
                                if (resp.ok && contentType.includes('application/json')) fresh = await resp.json();
                            } catch (fetchError) {
                                console.warn('CV fresh fetch failed, using form data:', fetchError);
                            }
                            const rowData = (fresh && fresh.id) ? fresh : { ...payloadFromForm(), id: savedId };
                            upserted = !!(upsertMonitoringRow(rowData) || {}).row;
                        } catch (upsertError) {
                            console.error('CV monitoring upsert failed:', upsertError);
                            try { upserted = !!(upsertMonitoringRow({ ...payloadFromForm(), id: savedId }) || {}).row; }
                            catch (fallbackError) { console.error('CV monitoring fallback failed:', fallbackError); }
                        }
                        await showCvModal('Check voucher saved to the database and PDF archived.');
                        // Always land back on this tab with the table re-rendered
                        // server-side, so the new entry is visible without a
                        // manual refresh. The cv_edit id highlights its row.
                        window.location.href = `${cfg.dashboardUrl || ''}?tab=check-voucher-tab&cv_view=monitoring&cv_edit=${encodeURIComponent(String(savedId || ''))}#cvMonitoringWrap`;
                        return;
                    } else {
                        printPdfBlob(pdfBlob);
                    }
                } catch (error) {
                    if (holder) holder.remove();
                    console.error('Check voucher PDF error:', error);
                    await showCvModal(error && error.message ? error.message : 'Could not prepare check voucher PDF.', 'error');
                } finally {
                    if (btn) {
                        btn.disabled = false;
                        btn.textContent = prevLabel;
                    }
                }
            }

            Object.values(fields).forEach((field) => {
                if (!field) return;
                field.addEventListener('input', refreshPreview);
                field.addEventListener('change', refreshPreview);
            });
            if (fields.category) {
                fields.category.addEventListener('change', () => {
                    cvCategoryDirty = true;
                    refreshPreview();
                });
            }
            bindMoneyInputs(document.getElementById('check-voucher-tab'), '#cvWithholdingTax');
            linesBody.addEventListener('input', refreshPreview);
            linesBody.addEventListener('change', refreshPreview);
            linesBody.addEventListener('click', (event) => {
                const btn = event.target.closest('.cv-line-remove');
                if (!btn) return;
                if (linesBody.querySelectorAll('tr').length <= 1) {
                    linesBody.innerHTML = '';
                    linesBody.appendChild(createLine());
                } else {
                    btn.closest('tr').remove();
                }
                refreshPreview();
            });

            document.getElementById('cvAddRow').addEventListener('click', () => {
                linesBody.appendChild(createLine());
                bindMoneyInputs(linesBody, '.cv-money-input');
                refreshPreview();
            });
            if (creditLinesBody) {
                creditLinesBody.addEventListener('input', refreshPreview);
                creditLinesBody.addEventListener('change', refreshPreview);
                creditLinesBody.addEventListener('click', (event) => {
                    const btn = event.target.closest('.cv-credit-line-remove');
                    if (!btn) return;
                    if (creditLinesBody.querySelectorAll('tr').length <= 1) {
                        creditLinesBody.innerHTML = '';
                        creditLinesBody.appendChild(createCreditLine());
                    } else {
                        btn.closest('tr').remove();
                    }
                    refreshPreview();
                });
            }
            const cvAddCreditRow = document.getElementById('cvAddCreditRow');
            if (cvAddCreditRow) {
                cvAddCreditRow.addEventListener('click', () => {
                    if (!creditLinesBody) return;
                    creditLinesBody.appendChild(createCreditLine());
                    bindMoneyInputs(creditLinesBody, '.cv-money-input');
                    refreshPreview();
                });
            }
            if (accountLinesBody) {
                accountLinesBody.addEventListener('input', refreshPreview);
                accountLinesBody.addEventListener('change', refreshPreview);
                accountLinesBody.addEventListener('click', (event) => {
                    const btn = event.target.closest('.cv-account-line-remove');
                    if (!btn) return;
                    if (accountLinesBody.querySelectorAll('tr').length <= 1) {
                        accountLinesBody.innerHTML = '';
                        accountLinesBody.appendChild(createAccountLine());
                    } else {
                        btn.closest('tr').remove();
                    }
                    refreshPreview();
                });
            }
            const cvAddAccountRow = document.getElementById('cvAddAccountRow');
            if (cvAddAccountRow) {
                cvAddAccountRow.addEventListener('click', () => {
                    if (!accountLinesBody) return;
                    accountLinesBody.appendChild(createAccountLine());
                    bindMoneyInputs(accountLinesBody, '.cv-money-input');
                    refreshPreview();
                });
            }
            function nativePrint(bodyClass) {
                const cvView = bodyClass === 'cv-print-monitoring' ? 'monitoring' : 'form';
                const url = new URL(window.location);
                url.searchParams.set('tab', 'check-voucher-tab');
                url.searchParams.set('cv_view', cvView);
                window.history.pushState({}, '', url);
                activateTab('check-voucher-tab');
                activateCvView(cvView, false);
                refreshPreview();
                // Voucher = letter portrait (1/2 crosswise); monitoring = A4 landscape.
                try {
                    let pageStyle = document.getElementById('sales-print-page-style');
                    if (!pageStyle) {
                        pageStyle = document.createElement('style');
                        pageStyle.id = 'sales-print-page-style';
                        document.head.appendChild(pageStyle);
                    }
                    pageStyle.textContent = bodyClass === 'cv-print-voucher'
                        ? '@media print { @page { size: letter portrait; margin: 8mm; } }'
                        : '@media print { @page { size: A4 landscape; margin: 6mm; } }';
                } catch (e) { /* ignore page-style errors */ }
                document.body.classList.add(bodyClass);
                const done = () => document.body.classList.remove(bodyClass);
                window.addEventListener('afterprint', done, { once: true });
                setTimeout(done, 8000);
                window.print();
            }
            document.getElementById('cvReset').addEventListener('click', () => populateForm({ company: 'mdspii', cv_number: cfg.nextCvNumber || '', voucher_date: todayISO() }));
            document.getElementById('cvPrint').addEventListener('click', () => nativePrint('cv-print-voucher'));
            document.getElementById('cvSave').addEventListener('click', () => runVoucherPdf('save'));
            const printMonitoringBtn = document.getElementById('cvPrintMonitoring');
            if (printMonitoringBtn) {
                printMonitoringBtn.addEventListener('click', () => nativePrint('cv-print-monitoring'));
            }

            const importInput = document.getElementById('cvImportFile');
            if (importInput) {
                importInput.addEventListener('change', async () => {
                    const file = importInput.files?.[0];
                    importInput.value = '';
                    if (!file) return;
                    if (!file.name.toLowerCase().endsWith('.xlsx')) {
                        alert('Please choose an .xlsx file.');
                        return;
                    }
                    const formData = new FormData();
                    formData.append('xlsx', file);
                    try {
                        const response = await fetch(cfg.importCheckVoucherUrl || '', {
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: { 'X-CSRFToken': getCsrfToken() },
                            body: formData,
                        });
                        const body = await response.json();
                        if (!response.ok) throw new Error(body?.error || 'Import failed.');
                        populateForm(body);
                        alert(`Imported ${body.imported_count || 1} check voucher(s) from ${file.name}.`);
                        window.location.href = `${cfg.dashboardUrl || ''}?tab=check-voucher-tab&cv_view=monitoring`;
                    } catch (error) {
                        alert(error.message || 'Could not import Excel file.');
                    }
                });
            }

            document.querySelectorAll('.cv-load-voucher').forEach((button) => {
                button.addEventListener('click', async () => {
                    const vid = button.dataset.voucherId;
                    if (!vid) {
                        alert('Missing voucher id.');
                        return;
                    }
                    const prevLabel = button.textContent;
                    button.disabled = true;
                    button.textContent = 'Loading...';
                    try {
                        await loadVoucher(vid);
                        activateTab('check-voucher-tab');
                        activateCvView('form', false);
                        try {
                            const url = new URL(window.location);
                            url.searchParams.set('tab', 'check-voucher-tab');
                            url.searchParams.set('cv_view', 'form');
                            url.searchParams.set('cv_edit', String(vid));
                            window.history.pushState({}, '', url);
                        } catch (e) { /* ignore URL errors */ }
                        const editor = document.getElementById('cvNumber');
                        if (editor) {
                            const panel = editor.closest('.panel') || editor;
                            if (panel.scrollIntoView) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                            try {
                                editor.focus({ preventScroll: true });
                                const flashEl = editor.closest('fieldset') || panel;
                                const prevOutline = flashEl.style.outline;
                                const prevTransition = flashEl.style.transition;
                                flashEl.style.transition = 'outline 0.3s ease';
                                flashEl.style.outline = '2px solid var(--brand, #0e7490)';
                                setTimeout(() => {
                                    flashEl.style.outline = prevOutline;
                                    flashEl.style.transition = prevTransition;
                                }, 1200);
                            } catch (e) { /* ignore focus errors */ }
                        }
                    } catch (error) {
                        console.error('Load voucher failed:', error);
                        alert(error.message || 'Could not load check voucher.');
                    } finally {
                        button.disabled = false;
                        button.textContent = prevLabel;
                    }
                });
            });

            document.querySelectorAll('.cv-delete-voucher').forEach((button) => {
                button.addEventListener('click', async () => {
                    const id = button.dataset.voucherId;
                    if (!id || !confirm('Delete this check voucher? This cannot be undone.')) return;
                    try {
                        const response = await fetch(cvDeleteUrl(id), {
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: { 'X-CSRFToken': getCsrfToken() },
                        });
                        const body = await response.json();
                        if (!response.ok) throw new Error(body?.error || 'Delete failed.');
                        window.location.href = `${cfg.dashboardUrl || ''}?tab=check-voucher-tab&cv_view=monitoring`;
                    } catch (error) {
                        alert(error.message || 'Could not delete check voucher.');
                    }
                });
            });

            // Format monitoring money cells as 10,000.00 (commas + 2 decimals)
            const CV_MONEY_COLS = ['check_amount', 'purchases', 'expenses', 'commission', 'contributions', 'misc', 'payment', 'salaries'];
            bindMoneyInputs(document.getElementById('cvMonitoringWrap'), '.cv-money-input');

            function refreshMonitoringTotals() {
                CV_MONEY_COLS.forEach((col) => {
                    let total = 0;
                    document.querySelectorAll(`.cv-cell-input[data-money-col="${col}"]`).forEach((el) => { total += parseMoney(el.value); });
                    const totalEl = document.querySelector(`[data-money-total="${col}"]`);
                    if (totalEl) totalEl.textContent = `₱${formatMoney(total)}`;
                    const summaryEl = document.querySelector('.cv-report-summary');
                    if (summaryEl) {
                        const label = col === 'check_amount' ? 'Total' : col.charAt(0).toUpperCase() + col.slice(1);
                        const re = new RegExp(`${label}: (₱|PHP)\\s?[\\d,.-]+`);
                        if (re.test(summaryEl.innerHTML)) {
                            summaryEl.innerHTML = summaryEl.innerHTML.replace(re, `${label}: ₱${formatMoney(total)}`);
                        }
                    }
                });
                const rowCount = document.querySelectorAll('#cvMonitoringWrap tbody tr[data-cv-row]').length;
                const summaryCount = document.querySelector('.cv-report-summary strong');
                if (summaryCount) summaryCount.textContent = String(rowCount);
                const footLabel = document.querySelector('#cvMonitoringWrap tfoot td[colspan="5"]');
                if (footLabel) footLabel.textContent = `TOTAL (${rowCount})`;
            }

            function ensureMonitoringTfoot() {
                const table = document.querySelector('#cvMonitoringWrap table');
                if (!table || table.querySelector('tfoot')) return;
                const tfoot = document.createElement('tfoot');
                tfoot.innerHTML = `<tr>
                    <td colspan="5" style="text-align:right;font-weight:700;">TOTAL (0)</td>
                    <td style="font-weight:700;" data-money-total="check_amount">₱0.00</td>
                    <td class="cv-breakdown-col" style="font-weight:700;" data-money-total="purchases">₱0.00</td>
                    <td class="cv-breakdown-col" style="font-weight:700;" data-money-total="expenses">₱0.00</td>
                    <td class="cv-breakdown-col" style="font-weight:700;" data-money-total="commission">₱0.00</td>
                    <td class="cv-breakdown-col" style="font-weight:700;" data-money-total="contributions">₱0.00</td>
                    <td class="cv-breakdown-col" style="font-weight:700;" data-money-total="misc">₱0.00</td>
                    <td class="cv-breakdown-col" style="font-weight:700;" data-money-total="payment">₱0.00</td>
                    <td class="cv-breakdown-col" style="font-weight:700;" data-money-total="salaries">₱0.00</td>
                    <td colspan="4"></td>
                    <td class="cv-actions-col"></td>
                </tr>`;
                table.appendChild(tfoot);
            }

            async function handleMonitoringCellChange(input) {
                const vid = input.dataset.voucherId;
                const field = input.dataset.field;
                if (!vid || !field) return;
                if (input.value === input.dataset.initial) return;
                const moneyCol = input.dataset.moneyCol || '';
                const isMoney = input.classList.contains('cv-money-input');
                input.classList.remove('is-saved', 'is-error');
                input.classList.add('is-saving');
                try {
                    const response = await fetch(cvCellUrl(vid), {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCsrfToken(),
                        },
                        body: JSON.stringify({ field, value: input.value }),
                    });
                    const body = await response.json();
                    if (!response.ok) throw new Error(body?.error || 'Save failed.');
                    if (isMoney) {
                        input.value = formatMoney(parseMoney(input.value));
                    }
                    input.dataset.initial = input.value;
                    input.classList.remove('is-saving');
                    input.classList.add('is-saved');
                    setTimeout(() => input.classList.remove('is-saved'), 1200);
                    if (moneyCol) refreshMonitoringTotals();
                } catch (error) {
                    input.classList.remove('is-saving');
                    input.classList.add('is-error');
                    alert(error.message || 'Could not save change.');
                    setTimeout(() => input.classList.remove('is-error'), 1500);
                }
            }

            function attachMonitoringCell(input) {
                if (input.dataset.cvBound === '1') return;
                input.dataset.cvBound = '1';
                if (input.classList.contains('cv-money-input')) {
                    input.value = formatMoney(parseMoney(input.value));
                }
                input.dataset.initial = input.value;
                input.addEventListener('change', () => handleMonitoringCellChange(input));
                if (input.dataset.field === 'company') {
                    input.addEventListener('change', () => {
                        const badge = input.closest('.cv-company-cell')?.querySelector('.cv-company-acronym');
                        if (badge) badge.textContent = String(input.value || '').toUpperCase();
                    });
                }
                if (input.dataset.field === 'liquidation_status') {
                    const syncStatusText = () => {
                        const label = input.closest('td')?.querySelector('.cv-status-text');
                        if (label) label.textContent = input.selectedOptions?.[0]?.textContent || input.value;
                    };
                    syncStatusText();
                    input.addEventListener('change', syncStatusText);
                }
            }

            function attachMonitoringRowButtons(tr) {
                const loadBtn = tr.querySelector('.cv-load-voucher');
                if (loadBtn && loadBtn.dataset.cvBound !== '1') {
                    loadBtn.dataset.cvBound = '1';
                    loadBtn.addEventListener('click', async () => {
                        const vid = loadBtn.dataset.voucherId;
                        if (!vid) { alert('Missing voucher id.'); return; }
                        const prevLabel = loadBtn.textContent;
                        loadBtn.disabled = true;
                        loadBtn.textContent = 'Loading...';
                        try {
                            await loadVoucher(vid);
                            activateTab('check-voucher-tab');
                            activateCvView('form', false);
                            try {
                                const url = new URL(window.location);
                                url.searchParams.set('tab', 'check-voucher-tab');
                                url.searchParams.set('cv_view', 'form');
                                url.searchParams.set('cv_edit', String(vid));
                                window.history.pushState({}, '', url);
                            } catch (e) { /* ignore URL errors */ }
                            const editor = document.getElementById('cvNumber');
                            if (editor && editor.scrollIntoView) editor.scrollIntoView({ behavior: 'smooth', block: 'start' });
                        } catch (error) {
                            console.error('Load voucher failed:', error);
                            alert(error.message || 'Could not load check voucher.');
                        } finally {
                            loadBtn.disabled = false;
                            loadBtn.textContent = prevLabel;
                        }
                    });
                }
                const delBtn = tr.querySelector('.cv-delete-voucher');
                if (delBtn && delBtn.dataset.cvBound !== '1') {
                    delBtn.dataset.cvBound = '1';
                    delBtn.addEventListener('click', async () => {
                        const id = delBtn.dataset.voucherId;
                        if (!id || !confirm('Delete this check voucher? This cannot be undone.')) return;
                        try {
                            const response = await fetch(cvDeleteUrl(id), {
                                method: 'POST',
                                credentials: 'same-origin',
                                headers: { 'X-CSRFToken': getCsrfToken() },
                            });
                            const body = await response.json();
                            if (!response.ok) throw new Error(body?.error || 'Delete failed.');
                            tr.remove();
                            refreshMonitoringTotals();
                        } catch (error) {
                            alert(error.message || 'Could not delete check voucher.');
                        }
                    });
                }
            }

            function monitoringMoneyCell(id, field, raw) {
                return `<div class="cv-peso-wrap"><span class="cv-peso-sign">₱</span><input type="text" inputmode="decimal" placeholder="0.00" class="cv-cell-input cv-money-input" data-voucher-id="${escapeHtml(String(id))}" data-field="${field}" data-money-col="${field}" value="${escapeHtml(formatMoney(parseMoney(raw)))}"></div>`;
            }

            function monitoringCompanyCell(id, raw) {
                const value = normalizeCompany(raw);
                const mdspii = value === 'mdspii' ? ' selected' : '';
                const versatec = value === 'versatec' ? ' selected' : '';
                const mdtcii = value === 'mdtcii' ? ' selected' : '';
                const dai = value === 'dai' ? ' selected' : '';
                return `<span class="cv-company-cell"><select class="cv-cell-input" data-voucher-id="${escapeHtml(String(id))}" data-field="company" style="padding:6px 8px;min-width:110px;"><option value="mdspii"${mdspii}>METRO DAVAO SUPREME …</option><option value="versatec"${versatec}>VERSATEC INDUSTRIAL …</option><option value="mdtcii"${mdtcii}>METRO DAVAO TRADE …</option><option value="dai"${dai}>DAI HOLDINGS, INC.</option></select><span class="cv-company-acronym">${escapeHtml(String(value).toUpperCase())}</span></span>`;
            }

            function monitoringStatusCell(id, raw) {
                const value = String(raw || 'unliquidated').toLowerCase() === 'liquidated' ? 'liquidated' : 'unliquidated';
                const unliquidated = value === 'unliquidated' ? ' selected' : '';
                const liquidated = value === 'liquidated' ? ' selected' : '';
                const label = value === 'liquidated' ? 'Liquidated' : 'Unliquidated';
                return `<select class="cv-cell-input cv-status-select" data-voucher-id="${escapeHtml(String(id))}" data-field="liquidation_status" style="padding:6px 8px;min-width:130px;"><option value="unliquidated"${unliquidated}>Unliquidated</option><option value="liquidated"${liquidated}>Liquidated</option></select><span class="cv-status-text">${label}</span>`;
            }

            function upsertMonitoringRow(data) {
                if (!data || !data.id) return;
                const id = String(data.id);
                const tbody = document.querySelector('#cvMonitoringWrap tbody');
                if (!tbody) return;
                const emptyRow = tbody.querySelector('tr:not([data-cv-row])');
                let tr = tbody.querySelector(`tr[data-cv-row="${CSS.escape(id)}"]`);
                const isNew = !tr;
                if (!tr) {
                    tr = document.createElement('tr');
                    tr.setAttribute('data-cv-row', id);
                    tbody.prepend(tr);
                }
                const vDate = String(data.voucher_date || '').slice(0, 10);
                const cDate = String(data.check_date || '').slice(0, 10);
                tr.setAttribute('data-cv-row', id);
                tr.innerHTML = `
                    <td><input type="date" class="cv-cell-input" data-voucher-id="${escapeHtml(id)}" data-field="voucher_date" value="${escapeHtml(vDate)}"></td>
                    <td><input type="text" class="cv-cell-input" data-voucher-id="${escapeHtml(id)}" data-field="cv_number" value="${escapeHtml(data.cv_number || '')}"></td>
                    <td>${monitoringCompanyCell(id, data.company)}</td>
                    <td><input type="text" class="cv-cell-input" data-voucher-id="${escapeHtml(id)}" data-field="payee" value="${escapeHtml(data.payee || '')}"></td>
                    <td><input type="text" class="cv-cell-input" data-voucher-id="${escapeHtml(id)}" data-field="payment_for" value="${escapeHtml(data.payment_for || '')}" placeholder="-"></td>
                    <td>${monitoringMoneyCell(id, 'check_amount', data.check_amount)}</td>
                    <td class="cv-breakdown-col">${monitoringMoneyCell(id, 'purchases', data.purchases)}</td>
                    <td class="cv-breakdown-col">${monitoringMoneyCell(id, 'expenses', data.expenses)}</td>
                    <td class="cv-breakdown-col">${monitoringMoneyCell(id, 'commission', data.commission)}</td>
                    <td class="cv-breakdown-col">${monitoringMoneyCell(id, 'contributions', data.contributions)}</td>
                    <td class="cv-breakdown-col">${monitoringMoneyCell(id, 'misc', data.misc)}</td>
                    <td class="cv-breakdown-col">${monitoringMoneyCell(id, 'payment', data.payment)}</td>
                    <td class="cv-breakdown-col">${monitoringMoneyCell(id, 'salaries', data.salaries)}</td>
                    <td><input type="date" class="cv-cell-input" data-voucher-id="${escapeHtml(id)}" data-field="check_date" value="${escapeHtml(cDate)}"></td>
                    <td><input type="text" class="cv-cell-input" data-voucher-id="${escapeHtml(id)}" data-field="bank" value="${escapeHtml(data.bank || '')}" placeholder="-"></td>
                    <td><input type="text" class="cv-cell-input" data-voucher-id="${escapeHtml(id)}" data-field="check_number" value="${escapeHtml(data.check_number || '')}" placeholder="-"></td>
                    <td>${monitoringStatusCell(id, data.liquidation_status)}</td>
                    <td class="cv-actions-col" style="text-align:right; white-space:nowrap;">
                        <button type="button" class="action cv-load-voucher" data-voucher-id="${escapeHtml(id)}" style="font-size:0.75rem;padding:4px 12px;margin-right:6px;">Load</button>
                        <button type="button" class="action cv-delete-voucher" data-voucher-id="${escapeHtml(id)}" style="font-size:0.75rem;padding:4px 12px;color:var(--danger);">Delete</button>
                    </td>`;
                if (emptyRow && tbody.querySelector('tr[data-cv-row]')) emptyRow.remove();
                tr.querySelectorAll('.cv-cell-input').forEach(attachMonitoringCell);
                attachMonitoringRowButtons(tr);
                ensureMonitoringTfoot();
                refreshMonitoringTotals();
                try { tr.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); } catch (_) { /* ignore */ }
                tr.style.transition = 'background 0.6s ease';
                tr.style.background = '#dcfce7';
                setTimeout(() => { tr.style.background = ''; }, 1600);
                return { row: tr, isNew };
            }

            document.querySelectorAll('#cvMonitoringWrap .cv-cell-input').forEach(attachMonitoringCell);

            const editId = new URLSearchParams(window.location.search).get('cv_edit') || cfg.latestCheckVoucherId;
            loadVoucher(editId).catch((error) => {
                console.error(error);
                populateForm({ cv_number: cfg.nextCvNumber || '', voucher_date: todayISO() });
            });
            try {
                const highlightId = new URLSearchParams(window.location.search).get('cv_edit');
                if (highlightId) {
                    const cssEscape = (typeof CSS !== 'undefined' && CSS.escape) ? CSS.escape : (s) => String(s).replace(/[^a-zA-Z0-9_-]/g, '');
                    const savedRow = document.querySelector(`#cvMonitoringWrap tbody tr[data-cv-row="${cssEscape(String(highlightId))}"]`);
                    if (savedRow) {
                        savedRow.style.transition = 'background 0.6s ease';
                        savedRow.style.background = '#dcfce7';
                        setTimeout(() => { savedRow.style.background = ''; }, 2200);
                    }
                }
            } catch (_) { /* ignore highlight errors */ }
        })();

        // Sales summary row delete
        (function initSalesSummaryDelete() {
            const cfg = window.__SALES_CONFIG__ || {};
            const deleteUrl = cfg.salesSummaryDeleteUrl || '';
            const formatAmount = (value) => Number(value || 0).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            });
            document.querySelectorAll('.sales-summary-table').forEach((table) => {
                function recomputeTotals() {
                    let gross = 0;
                    let outputVat = 0;
                    let net = 0;
                    table.querySelectorAll('tbody .sales-summary-row').forEach((row) => {
                        gross += Number(row.dataset.gross || 0);
                        outputVat += Number(row.dataset.outputVat || 0);
                        net += Number(row.dataset.net || 0);
                    });
                    table.querySelectorAll('tfoot [data-total="gross"]').forEach((cell) => {
                        cell.textContent = formatAmount(gross);
                    });
                    table.querySelectorAll('tfoot [data-total="output_vat"]').forEach((cell) => {
                        cell.textContent = formatAmount(outputVat);
                    });
                    table.querySelectorAll('tfoot [data-total="net"]').forEach((cell) => {
                        cell.textContent = formatAmount(net);
                    });
                }

                table.querySelectorAll('.sales-summary-delete').forEach((button) => {
                    button.addEventListener('click', async () => {
                        const sourceType = button.dataset.sourceType;
                        const sourceId = button.dataset.sourceId;
                        if (!sourceType || !sourceId || !deleteUrl) return;
                        if (!confirm('Remove this row from the Sales Summary? The water billing payment record will remain.')) return;

                        button.disabled = true;
                        try {
                            const formData = new FormData();
                            formData.append('source_type', sourceType);
                            formData.append('source_id', sourceId);
                            const response = await fetch(deleteUrl, {
                                method: 'POST',
                                credentials: 'same-origin',
                                headers: { 'X-CSRFToken': getCsrfToken() },
                                body: formData,
                            });
                            const body = await response.json();
                            if (!response.ok) throw new Error(body?.error || 'Delete failed.');

                            button.closest('tr')?.remove();
                            recomputeTotals();
                            if (!table.querySelector('tbody .sales-summary-row')) {
                                const tab = table.closest('.tab-panel')?.id || 'sales-tab';
                                window.location.href = `${cfg.dashboardUrl || ''}?tab=${tab}`;
                            }
                        } catch (error) {
                            alert(error.message || 'Could not remove this sales summary row.');
                            button.disabled = false;
                        }
                    });
                });
            });
        })();

        // Modern line charts for analytics period cards
        (function initSalesLineCharts() {
            const charts = Array.from(document.querySelectorAll('.sales-line-chart'));
            if (!charts.length) return;

            function formatMoney(value) {
                const n = Number(value || 0);
                return '₱' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            }
            function compactMoney(value) {
                const n = Number(value || 0);
                const abs = Math.abs(n);
                if (abs >= 1000000) return '₱' + (n / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
                if (abs >= 1000) return '₱' + (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
                return '₱' + n.toLocaleString('en-US', { maximumFractionDigits: 0 });
            }

            charts.forEach((el, idx) => {
                const valuesId = el.dataset.valuesId;
                const dataScript = valuesId ? document.getElementById(valuesId) : null;
                let data = [];
                try { data = dataScript ? JSON.parse(dataScript.textContent || '[]') : []; } catch (_) { data = []; }
                data = (Array.isArray(data) ? data : []).map((d) => ({
                    label: String(d && d.label != null ? d.label : ''),
                    amount: Number(d && d.amount != null ? d.amount : 0) || 0,
                }));
                if (!data.length) return;

                const w = 640;
                const h = 220;
                const pad = { t: 18, r: 18, b: 34, l: 58 };
                const plotW = w - pad.l - pad.r;
                const plotH = h - pad.t - pad.b;
                const values = data.map((d) => d.amount);
                let maxV = Math.max.apply(null, values.concat([0]));
                if (!(maxV > 0)) maxV = 1;
                const niceMax = maxV * 1.15;
                const minV = 0;
                const xFor = (i) => pad.l + (data.length === 1 ? plotW / 2 : (i / (data.length - 1)) * plotW);
                const yFor = (v) => pad.t + plotH - ((v - minV) / (niceMax - minV || 1)) * plotH;

                function linePath(pts) {
                    if (!pts.length) return '';
                    if (pts.length === 1) return 'M ' + pts[0].x + ' ' + pts[0].y;
                    let d = 'M ' + pts[0].x + ' ' + pts[0].y;
                    for (let i = 0; i < pts.length - 1; i++) {
                        const p0 = pts[i - 1] || pts[i];
                        const p1 = pts[i];
                        const p2 = pts[i + 1];
                        const p3 = pts[i + 2] || p2;
                        const cp1x = p1.x + (p2.x - p0.x) / 6;
                        const cp1y = p1.y + (p2.y - p0.y) / 6;
                        const cp2x = p2.x - (p3.x - p1.x) / 6;
                        const cp2y = p2.y - (p3.y - p1.y) / 6;
                        d += ' C ' + cp1x + ' ' + cp1y + ', ' + cp2x + ' ' + cp2y + ', ' + p2.x + ' ' + p2.y;
                    }
                    return d;
                }

                const pts = data.map((d, i) => ({ x: xFor(i), y: yFor(d.amount), label: d.label, amount: d.amount }));
                const dLine = linePath(pts);
                const baseY = yFor(0);
                const dArea = dLine + ' L ' + pts[pts.length - 1].x + ' ' + baseY + ' L ' + pts[0].x + ' ' + baseY + ' Z';

                const uid = (el.dataset.chartId || ('slc-' + idx)) + '-' + Math.random().toString(36).slice(2, 7);
                const gradId = 'slc-grad-' + uid;
                const stroke = '#0f766e';
                const stroke2 = '#14b8a6';

                const gridLines = 4;
                let gridSvg = '';
                for (let i = 0; i <= gridLines; i++) {
                    const v = (niceMax / gridLines) * i;
                    const y = yFor(v);
                    gridSvg += '<line class="slc-grid" x1="' + pad.l + '" y1="' + y + '" x2="' + (w - pad.r) + '" y2="' + y + '" />';
                    gridSvg += '<text class="slc-axis-label" x="' + (pad.l - 8) + '" y="' + (y + 4) + '" text-anchor="end">' + compactMoney(v) + '</text>';
                }

                const labelStep = Math.max(1, Math.ceil(data.length / 4));
                let xLabels = '';
                data.forEach((d, i) => {
                    if (i === 0 || i === data.length - 1 || i % labelStep === 0) {
                        const short = d.label.length > 7 ? d.label.slice(5) : d.label;
                        xLabels += '<text class="slc-axis-label" x="' + pts[i].x + '" y="' + (h - 10) + '" text-anchor="middle">' + short + '</text>';
                    }
                });

                const pointsSvg = pts.map((p, i) =>
                    '<circle class="slc-point" cx="' + p.x + '" cy="' + p.y + '" r="4" stroke="' + stroke + '" data-i="' + i + '" />'
                ).join('');

                el.innerHTML = ''
                    + '<svg viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="xMidYMid meet" aria-hidden="true">'
                    +   '<defs>'
                    +     '<linearGradient id="' + gradId + '" x1="0" y1="0" x2="0" y2="1">'
                    +       '<stop offset="0%" stop-color="' + stroke2 + '" stop-opacity="0.45" />'
                    +       '<stop offset="100%" stop-color="' + stroke2 + '" stop-opacity="0.02" />'
                    +     '</linearGradient>'
                    +   '</defs>'
                    +   gridSvg
                    +   '<path class="slc-area" d="' + dArea + '" fill="url(#' + gradId + ')"></path>'
                    +   '<path class="slc-line" d="' + dLine + '" stroke="' + stroke + '"></path>'
                    +   pointsSvg
                    +   '<line class="slc-focus-line" x1="0" y1="' + pad.t + '" x2="0" y2="' + (pad.t + plotH) + '" style="display:none"></line>'
                    +   xLabels
                    + '</svg>'
                    + '<div class="slc-tooltip"><span class="slc-tip-label"></span><span class="slc-tip-value"></span></div>';

                const svg = el.querySelector('svg');
                const tip = el.querySelector('.slc-tooltip');
                const tipLabel = el.querySelector('.slc-tip-label');
                const tipValue = el.querySelector('.slc-tip-value');
                const focusLine = el.querySelector('.slc-focus-line');
                const circles = Array.from(el.querySelectorAll('.slc-point'));
                if (!svg || !tip || !tipLabel || !tipValue || !focusLine) return;

                function showTip(i) {
                    const p = pts[i];
                    if (!p) return;
                    circles.forEach((c, ci) => {
                        c.classList.toggle('is-active', ci === i);
                        c.setAttribute('r', ci === i ? '5.5' : '4');
                    });
                    tipLabel.textContent = p.label;
                    tipValue.textContent = formatMoney(p.amount);
                    tip.style.display = 'block';
                    const svgRect = svg.getBoundingClientRect();
                    const px = (p.x / w) * svgRect.width;
                    const py = (p.y / h) * svgRect.height;
                    let left = px;
                    left = Math.max(44, Math.min(svgRect.width - 44, left));
                    tip.style.left = left + 'px';
                    tip.style.top = py + 'px';
                    focusLine.setAttribute('x1', String(p.x));
                    focusLine.setAttribute('x2', String(p.x));
                    focusLine.style.display = 'block';
                }
                function hideTip() {
                    tip.style.display = 'none';
                    focusLine.style.display = 'none';
                    circles.forEach((c) => { c.classList.remove('is-active'); c.setAttribute('r', '4'); });
                }
                function nearestIndex(clientX) {
                    const rect = svg.getBoundingClientRect();
                    const mx = ((clientX - rect.left) / rect.width) * w;
                    let best = 0;
                    let bestD = Infinity;
                    pts.forEach((p, i) => {
                        const d = Math.abs(p.x - mx);
                        if (d < bestD) { bestD = d; best = i; }
                    });
                    return best;
                }

                el.addEventListener('mousemove', (e) => { showTip(nearestIndex(e.clientX)); });
                el.addEventListener('mouseleave', hideTip);
                el.addEventListener('touchstart', (e) => {
                    if (e.touches && e.touches[0]) showTip(nearestIndex(e.touches[0].clientX));
                }, { passive: true });
                el.addEventListener('touchmove', (e) => {
                    if (e.touches && e.touches[0]) showTip(nearestIndex(e.touches[0].clientX));
                }, { passive: true });
            });
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
