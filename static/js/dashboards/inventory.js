(function () {
    // ── Sidebar tab switching ──
    const tabButtons = document.querySelectorAll('.sidebar-nav .tab-button');
    const panels = {
      managePanel: document.getElementById('managePanel'),
      allItemsPanel: document.getElementById('allItemsPanel'),
      deliveriesPanel: document.getElementById('deliveriesPanel'),
      purchaseOrderPanel: document.getElementById('purchaseOrderPanel'),
    };

    function activateTab(targetId) {
      tabButtons.forEach(b => {
        const isTarget = b.dataset.tabTarget === targetId;
        b.setAttribute('aria-selected', isTarget ? 'true' : 'false');
      });
      Object.keys(panels).forEach(id => {
        if (panels[id]) {
          panels[id].classList.toggle('is-active', id === targetId);
        }
      });
    }

    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get('tab');
    const defaultTab = 'managePanel';
    const initialTab = tabParam && panels[tabParam] ? tabParam : defaultTab;
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

    // ── Inventory management ──
    const storageKey = 'inventory-management-data-v1';
    const inventoryDataElement = document.getElementById('inventory-data');
    const nextProductCodesElement = document.getElementById('next-product-codes');
    const form = document.getElementById('inventoryForm');
    const searchInput = document.getElementById('searchInput');
    const categoryFilter = document.getElementById('categoryFilter');
    const clearSearchBtn = document.getElementById('clearSearchBtn');
    const resetBtn = document.getElementById('resetBtn');
    const viewItemsBtn = document.getElementById('viewItemsBtn');
    const inventoryTableBody = document.getElementById('inventoryTableBody');
    const emptyNotice = document.getElementById('emptyNotice');
    const formTitle = document.getElementById('formTitle');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

    const picturePreview = document.getElementById('picturePreview');
    const fields = {
      itemId: document.getElementById('itemId'),
      productCode: document.getElementById('productCode'),
      itemName: document.getElementById('categoryId'),
      categoryId: document.getElementById('categoryId'),
      picture: document.getElementById('picture'),
      reusePicture: document.getElementById('reusePicture'),
      stockAvailable: document.getElementById('stockAvailable'),
      description: document.getElementById('description'),
      notes: document.getElementById('notes'),
    };

    function isMobileCatMenu() {
      return window.matchMedia('(max-width: 768px)').matches;
    }

    function resetPickerMenuLayout(picker) {
      const menu = picker?.querySelector('.cat-picker-menu');
      if (!menu) return;
      menu.classList.remove('cat-picker-menu--mobile');
      menu.style.position = '';
      menu.style.top = '';
      menu.style.left = '';
      menu.style.right = '';
      menu.style.width = '';
      menu.style.maxHeight = '';
    }

    function positionPickerMenu(picker) {
      const menu = picker.querySelector('.cat-picker-menu');
      const trigger = picker.querySelector('.cat-picker-trigger');
      if (!menu || !trigger) return;

      if (isMobileCatMenu()) {
        const rect = trigger.getBoundingClientRect();
        menu.classList.add('cat-picker-menu--mobile');
        menu.style.position = 'fixed';
        menu.style.left = '12px';
        menu.style.right = '12px';
        menu.style.width = 'auto';
        menu.style.top = `${Math.min(rect.bottom + 6, window.innerHeight - 12)}px`;
        menu.style.maxHeight = `${Math.max(160, window.innerHeight - rect.bottom - 20)}px`;
        return;
      }

      resetPickerMenuLayout(picker);
    }

    function resetSubmenuStyles(submenu) {
      if (!submenu) return;
      submenu.classList.remove('cat-menu-submenu--floating');
      submenu.style.position = '';
      submenu.style.top = '';
      submenu.style.left = '';
    }

    function openMenuBranch(picker, item) {
      if (!picker || !item) return;

      picker.querySelectorAll('.cat-menu-item.is-open').forEach(openItem => {
        if (openItem === item || openItem.contains(item)) {
          return;
        }
        openItem.classList.remove('is-open');
        resetSubmenuStyles(openItem.querySelector(':scope > .cat-menu-submenu'));
      });

      if (!item.classList.contains('has-children')) {
        return;
      }

      const parentList = item.parentElement;
      parentList?.querySelectorAll(':scope > .cat-menu-item.is-open').forEach(sibling => {
        if (sibling !== item) {
          sibling.classList.remove('is-open');
          resetSubmenuStyles(sibling.querySelector(':scope > .cat-menu-submenu'));
        }
      });

      item.classList.add('is-open');
      positionFloatingSubmenu(item);
    }

    function resetFloatingSubmenus(picker) {
      picker?.querySelectorAll('.cat-menu-submenu--floating').forEach(submenu => {
        resetSubmenuStyles(submenu);
      });
    }

    function positionFloatingSubmenu(item) {
      if (isMobileCatMenu()) return;
      const submenu = item.querySelector(':scope > .cat-menu-submenu');
      const row = item.querySelector('.cat-menu-row');
      if (!submenu || !row) return;

      submenu.classList.add('cat-menu-submenu--floating');
      submenu.style.position = 'fixed';
      const rect = row.getBoundingClientRect();
      const submenuWidth = submenu.offsetWidth || 220;
      let left = rect.right - 4;
      if (left + submenuWidth > window.innerWidth - 8) {
        left = Math.max(8, rect.left - submenuWidth + 4);
      }
      let top = rect.top - 4;
      const submenuHeight = submenu.offsetHeight;
      if (top + submenuHeight > window.innerHeight - 8) {
        top = Math.max(8, window.innerHeight - submenuHeight - 8);
      }
      submenu.style.left = `${left}px`;
      submenu.style.top = `${top}px`;
    }

    function closeCatPicker(picker) {
      if (!picker) return;
      picker.classList.remove('is-open');
      picker.querySelector('.cat-picker-trigger')?.setAttribute('aria-expanded', 'false');
      picker.querySelectorAll('.cat-menu-item.is-open').forEach(item => item.classList.remove('is-open'));
      resetPickerMenuLayout(picker);
      resetFloatingSubmenus(picker);
    }

    function closeAllCatPickers(exceptPicker) {
      document.querySelectorAll('[data-cat-picker]').forEach(picker => {
        if (picker !== exceptPicker) closeCatPicker(picker);
      });
    }

    function setCatPickerValue(input, value, label) {
      if (!input) return;
      input.value = value ? String(value) : '';
      const picker = input.closest('[data-cat-picker]');
      if (!picker) return;
      const valueEl = picker.querySelector('.cat-picker-value');
      const placeholder = valueEl?.dataset.placeholder || 'Select';
      const activeItem = picker.querySelector(`.cat-menu-item[data-value="${CSS.escape(String(value || ''))}"]`);
      const display = label || activeItem?.dataset.path || placeholder;
      if (valueEl) {
        valueEl.textContent = display;
        valueEl.classList.toggle('is-placeholder', !value);
      }
      picker.querySelectorAll('.cat-menu-item').forEach(item => {
        item.classList.toggle('is-active', item.dataset.value === String(value || ''));
      });
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function initCatPickers() {
      document.querySelectorAll('[data-cat-picker]').forEach(picker => {
        const input = picker.querySelector('input[type="hidden"]');
        const trigger = picker.querySelector('.cat-picker-trigger');
        const valueEl = picker.querySelector('.cat-picker-value');
        if (!input || !trigger || !valueEl) return;

        if (!valueEl.dataset.placeholder) {
          valueEl.dataset.placeholder = valueEl.textContent.trim();
        }

        if (input.value) {
          setCatPickerValue(input, input.value);
        }

        trigger.addEventListener('click', (event) => {
          event.preventDefault();
          event.stopPropagation();
          const willOpen = !picker.classList.contains('is-open');
          closeAllCatPickers(picker);
          picker.classList.toggle('is-open', willOpen);
          trigger.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
          if (willOpen) {
            positionPickerMenu(picker);
          }
        });

        picker.querySelectorAll('.cat-menu-row').forEach(row => {
          row.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            const item = row.closest('.cat-menu-item');
            if (!item) return;

            if (item.classList.contains('has-children') && isMobileCatMenu()) {
              const parentList = item.parentElement;
              parentList?.querySelectorAll(':scope > .cat-menu-item.is-open').forEach(sibling => {
                if (sibling !== item) sibling.classList.remove('is-open');
              });
              item.classList.toggle('is-open');
              return;
            }

            setCatPickerValue(
              input,
              item.dataset.value || '',
              item.dataset.path || valueEl.dataset.placeholder,
            );
            closeCatPicker(picker);
          });
        });

        picker.querySelectorAll('.cat-menu-item').forEach(item => {
          item.addEventListener('mouseenter', () => {
            if (isMobileCatMenu()) return;
            openMenuBranch(picker, item);
          });
        });

        const menuRoot = picker.querySelector('.cat-menu-root');
        if (menuRoot) {
          menuRoot.addEventListener('scroll', () => {
            picker.querySelectorAll('.cat-menu-item.has-children.is-open').forEach(openItem => {
              positionFloatingSubmenu(openItem);
            });
          });
        }
      });

      document.addEventListener('click', (event) => {
        if (!event.target.closest('[data-cat-picker]')) {
          closeAllCatPickers();
        }
      });

      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeAllCatPickers();
      });

      window.addEventListener('resize', () => {
        document.querySelectorAll('[data-cat-picker].is-open').forEach(picker => {
          positionPickerMenu(picker);
          picker.querySelectorAll('.cat-menu-item.has-children.is-open').forEach(openItem => {
            positionFloatingSubmenu(openItem);
          });
        });
      });
    }

    let inventory = [];
    let editingId = null;
    let currentPictureData = '';
    let savedCategoryId = '';
    let savedProductCode = '';
    let nextProductCodes = {};

    if (nextProductCodesElement?.textContent) {
      try { nextProductCodes = JSON.parse(nextProductCodesElement.textContent); } catch { nextProductCodes = {}; }
    }

    function updateProductCodePreview() {
      if (!fields.productCode) return;
      const catId = fields.categoryId?.value || '';
      if (editingId && catId && catId === savedCategoryId) {
        fields.productCode.value = savedProductCode || '';
        return;
      }
      if (catId) {
        fields.productCode.value = nextProductCodes[catId] || nextProductCodes[String(catId)] || '';
      } else {
        fields.productCode.value = '';
      }
    }

    function normalizeInventory(data) {
      if (Array.isArray(data)) return data;
      if (data && typeof data === 'object') {
        if (Array.isArray(data.items)) return data.items;
        if (Array.isArray(data.inventory)) return data.inventory;
      }
      return [];
    }

    function loadInventory() {
      const raw = inventoryDataElement?.textContent;
      if (!raw) { inventory = []; return; }
      try { inventory = normalizeInventory(JSON.parse(raw)); } catch { inventory = []; }
    }

    function isRenderablePicture(src) {
      return Boolean(src) && (/^https?:\/\//i.test(src) || /^data:image\//i.test(src) || src.startsWith('/'));
    }

    function renderPicturePreview(src) {
      picturePreview.innerHTML = isRenderablePicture(src)
        ? `<img src="${src}" alt="Preview" style="width:100%;max-width:180px;border:1px solid #eaecf0;object-fit:cover;border-radius:6px;">`
        : '<span style="color:#667085;">No image</span>';
    }

    function getFilteredInventory() {
      const items = Array.isArray(inventory) ? inventory : [];
      const query = searchInput.value.trim().toLowerCase();
      const category = categoryFilter.value.trim();
      return items.filter(item => {
        const matchesCategory = !category || String(item.categoryId || '') === category
          || String(item.name || '').toLowerCase() === category.toLowerCase();
        const matchesSearch = !query || [item.productCode, item.name, item.categoryPath, item.stockAvailable, item.description, item.notes]
          .join(' ').toLowerCase().includes(query);
        return matchesCategory && matchesSearch;
      });
    }

    const PAGE_SIZE = 20;
    let inventoryPage = 1;
    const inventoryPager = document.getElementById('inventoryPager');
    const inventoryPagerInfo = document.getElementById('inventoryPagerInfo');
    const inventoryPrevPage = document.getElementById('inventoryPrevPage');
    const inventoryNextPage = document.getElementById('inventoryNextPage');

    function renderInventory(resetPage) {
      if (resetPage) inventoryPage = 1;
      const items = getFilteredInventory();
      const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
      if (inventoryPage > totalPages) inventoryPage = totalPages;
      const start = (inventoryPage - 1) * PAGE_SIZE;
      const pageItems = items.slice(start, start + PAGE_SIZE);
      const visibleIds = new Set(pageItems.map(i => String(i.id)));
      const rows = Array.from(inventoryTableBody.querySelectorAll('tr[data-id]'));
      const noResultsRow = inventoryTableBody.querySelector('[data-empty-state]');
      rows.forEach(row => {
        row.style.display = visibleIds.has(String(row.dataset.id)) ? '' : 'none';
      });
      if (noResultsRow) noResultsRow.style.display = items.length ? 'none' : '';
      emptyNotice.style.display = inventory.length ? 'none' : 'block';
      if (inventoryPager) {
        inventoryPager.hidden = inventory.length === 0;
        if (inventoryPagerInfo) {
          inventoryPagerInfo.textContent = items.length
            ? `Page ${inventoryPage} of ${totalPages} · ${items.length} item${items.length === 1 ? '' : 's'}`
            : 'No matching items';
        }
        if (inventoryPrevPage) inventoryPrevPage.disabled = inventoryPage <= 1 || !items.length;
        if (inventoryNextPage) inventoryNextPage.disabled = inventoryPage >= totalPages || !items.length;
      }
    }

    function resetForm() {
      form.reset();
      fields.itemId.value = '';
      editingId = null;
      currentPictureData = '';
      if (fields.reusePicture) fields.reusePicture.value = '';
      highlightReuseImage('');
      renderPicturePreview('');
      formTitle.textContent = 'Add Inventory Item';
      fields.stockAvailable.value = 0;
      savedCategoryId = '';
      savedProductCode = '';
      setCatPickerValue(fields.categoryId, '', fields.categoryId?.closest('[data-cat-picker]')?.querySelector('.cat-picker-value')?.dataset.placeholder);
      updateProductCodePreview();
    }

    function fillForm(item) {
      fields.itemId.value = item.id || '';
      savedCategoryId = item.categoryId ? String(item.categoryId) : '';
      savedProductCode = item.productCode || '';
      setCatPickerValue(fields.categoryId, item.categoryId ? String(item.categoryId) : '', item.categoryPath || item.name || '');
      updateProductCodePreview();
      fields.picture.value = '';
      if (fields.reusePicture) fields.reusePicture.value = item.pictureName || '';
      highlightReuseImage(item.pictureName || '');
      currentPictureData = item.picture || '';
      renderPicturePreview(currentPictureData);
      fields.stockAvailable.value = item.stockAvailable;
      fields.description.value = item.description || '';
      if (fields.notes) fields.notes.value = item.notes || '';
      editingId = item.id;
      formTitle.textContent = 'Edit Inventory Item';
      activateTab('managePanel');
    }

    function highlightReuseImage(name) {
      document.querySelectorAll('.reuse-image-btn').forEach((btn) => {
        btn.classList.toggle('is-selected', Boolean(name) && btn.dataset.name === name);
      });
    }

    function handlePictureChange() {
      const file = fields.picture.files?.[0];
      if (file && fields.reusePicture) fields.reusePicture.value = '';
      highlightReuseImage('');
      if (!file) { if (!currentPictureData) renderPicturePreview(''); return; }
      const reader = new FileReader();
      reader.onload = () => { currentPictureData = reader.result; renderPicturePreview(currentPictureData); };
      reader.readAsDataURL(file);
    }

    const reuseImageGrid = document.getElementById('reuseImageGrid');
    reuseImageGrid?.addEventListener('click', (event) => {
      const btn = event.target.closest('.reuse-image-btn');
      if (!btn) return;
      if (fields.picture) fields.picture.value = '';
      if (fields.reusePicture) fields.reusePicture.value = btn.dataset.name || '';
      currentPictureData = btn.dataset.url || '';
      highlightReuseImage(btn.dataset.name || '');
      renderPicturePreview(currentPictureData);
    });

    let pendingDeleteId = null;

    function showDeleteModal(itemId) {
      pendingDeleteId = itemId;
      const modal = document.getElementById('deleteModal');
      const input = document.getElementById('deletePassword');
      const errorDiv = document.getElementById('deleteError');
      modal.style.display = 'flex';
      input.value = '';
      errorDiv.style.display = 'none';
      input.focus();
    }

    function hideDeleteModal() {
      document.getElementById('deleteModal').style.display = 'none';
      pendingDeleteId = null;
    }

    function showItemViewModal(item) {
      const modal = document.getElementById('itemViewModal');
      if (!modal) return;
      const pictureEl = document.getElementById('itemViewPicture');
      const notesWrap = document.getElementById('itemViewNotesWrap');
      const notes = (item.notes || '').trim();
      document.getElementById('itemViewCode').textContent = item.productCode || '-';
      document.getElementById('itemViewTitle').textContent = item.name || 'Inventory item';
      document.getElementById('itemViewCategory').textContent = item.categoryPath || '-';
      document.getElementById('itemViewStock').textContent = item.stockAvailable ?? '0';
      document.getElementById('itemViewDescription').textContent = (item.description || '').trim() || '-';
      document.getElementById('itemViewNotes').textContent = notes;
      notesWrap.style.display = notes ? '' : 'none';
      pictureEl.innerHTML = isRenderablePicture(item.picture)
        ? `<img src="${item.picture}" alt="">`
        : 'No image';
      modal.classList.add('is-open');
    }

    function hideItemViewModal() {
      document.getElementById('itemViewModal')?.classList.remove('is-open');
      if (!document.getElementById('viewAllModal')?.classList.contains('is-open')) {
        document.body.style.overflow = '';
      }
    }

    function escapeHtml(value) {
      return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function groupInventoryByCategory(items) {
      const groups = new Map();
      items.forEach((item) => {
        const key = (item.categoryPath || '').trim() || 'Uncategorized';
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(item);
      });
      return Array.from(groups.entries())
        .sort((a, b) => a[0].localeCompare(b[0], undefined, { sensitivity: 'base' }))
        .map(([label, groupItems]) => ({
          label,
          items: groupItems.slice().sort((a, b) =>
            String(a.name || a.productCode || '').localeCompare(String(b.name || b.productCode || ''), undefined, { sensitivity: 'base' })
          ),
        }));
    }

    function renderViewAllCatalog() {
      const catalog = document.getElementById('viewAllCatalog');
      const subtitle = document.getElementById('viewAllSubtitle');
      if (!catalog) return;
      const items = getFilteredInventory();
      if (subtitle) {
        subtitle.textContent = items.length
          ? `${items.length} item${items.length === 1 ? '' : 's'} · grouped by category`
          : 'No matching products';
      }
      if (!items.length) {
        catalog.innerHTML = `
          <div class="view-all-empty">
            <strong>No matching items.</strong>
            <p>Try clearing filters or searching a different term.</p>
          </div>`;
        return;
      }
      const sections = groupInventoryByCategory(items);
      catalog.innerHTML = sections.map((section) => {
        const cards = section.items.map((item) => {
          const stock = Number(item.stockAvailable ?? 0);
          const low = stock > 0 && stock <= 5;
          const media = isRenderablePicture(item.picture)
            ? `<img src="${escapeHtml(item.picture)}" alt="">`
            : 'No image';
          const desc = (item.description || '').trim() || '—';
          return `
            <button type="button" class="view-all-card" data-view-all-id="${escapeHtml(item.id)}" aria-label="View ${escapeHtml(item.name || item.productCode || 'item')}">
              <div class="view-all-card-media">${media}</div>
              <div class="view-all-card-body">
                <p class="view-all-card-code">${escapeHtml(item.productCode || '-')}</p>
                <h3 class="view-all-card-name">${escapeHtml(item.name || 'Untitled')}</h3>
                <p class="view-all-card-desc">${escapeHtml(desc)}</p>
                <span class="view-all-card-stock${low ? ' is-low' : ''}">Stock: ${escapeHtml(item.stockAvailable ?? 0)}</span>
              </div>
            </button>`;
        }).join('');
        return `
          <section class="view-all-section">
            <h3 class="view-all-section-title">
              ${escapeHtml(section.label)}
              <span class="view-all-section-count">${section.items.length}</span>
            </h3>
            <div class="view-all-grid">${cards}</div>
          </section>`;
      }).join('');
    }

    function showViewAllModal() {
      const modal = document.getElementById('viewAllModal');
      if (!modal) return;
      renderViewAllCatalog();
      modal.classList.add('is-open');
      modal.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
      document.getElementById('viewAllCloseBtn')?.focus();
    }

    function hideViewAllModal() {
      const modal = document.getElementById('viewAllModal');
      if (!modal) return;
      hideItemViewModal();
      modal.classList.remove('is-open');
      modal.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
    }

    async function performDelete(itemId, password) {
      const formData = new FormData();
      formData.append('action', 'delete');
      formData.append('itemId', itemId);
      formData.append('password', password);
      formData.append('csrfmiddlewaretoken', csrfToken);

      const response = await fetch(window.location.pathname, {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Delete failed.');
      }
      return response.json();
    }

    async function handleTableClick(e) {
      const button = e.target.closest('[data-action]');
      if (!button) return;
      e.preventDefault();
      e.stopPropagation();
      const row = button.closest('tr');
      const itemId = row?.dataset?.id;
      if (!itemId) return;
      const action = button.dataset.action;
      const item = inventory.find(entry => String(entry.id) === String(itemId));
      if (action === 'view') {
        if (!item) return;
        showItemViewModal(item);
        return;
      }
      if (action === 'edit') {
        if (!item) return;
        fillForm(item);
        return;
      }
      if (action === 'delete') {
        showDeleteModal(itemId);
      }
    }

    document.getElementById('deleteConfirmBtn').addEventListener('click', async function () {
      const modal = document.getElementById('deleteModal');
      if (!modal || modal.style.display !== 'flex') return;
      const passwordInput = document.getElementById('deletePassword');
      const errorDiv = document.getElementById('deleteError');
      const password = passwordInput.value.trim();
      if (!password) {
        errorDiv.textContent = 'Password is required.';
        errorDiv.style.display = 'block';
        return;
      }
      errorDiv.style.display = 'none';
      const itemId = pendingDeleteId;
      if (!itemId) return;
      this.disabled = true;
      try {
        const result = await performDelete(itemId, password);
        if (!result.deleted) throw new Error('Not deleted.');
        inventory = inventory.filter(entry => String(entry.id) !== String(itemId));
        localStorage.setItem(storageKey, JSON.stringify(inventory));
        renderInventory();
        hideDeleteModal();
      } catch (err) {
        errorDiv.textContent = err.message || 'An error occurred.';
        errorDiv.style.display = 'block';
      }
      this.disabled = false;
    });

    document.getElementById('deleteCancelBtn').addEventListener('click', hideDeleteModal);
    document.getElementById('deleteModal').addEventListener('click', function (e) {
      if (e.target === this) {
        hideDeleteModal();
      }
    });

    const itemViewModal = document.getElementById('itemViewModal');
    document.getElementById('itemViewCloseBtn')?.addEventListener('click', hideItemViewModal);
    itemViewModal?.addEventListener('click', function (e) {
      if (e.target === this) hideItemViewModal();
    });

    const viewAllModal = document.getElementById('viewAllModal');
    document.getElementById('viewAllItemsBtn')?.addEventListener('click', showViewAllModal);
    document.getElementById('viewAllCloseBtn')?.addEventListener('click', hideViewAllModal);
    viewAllModal?.addEventListener('click', function (e) {
      if (e.target === this) hideViewAllModal();
      const card = e.target.closest('[data-view-all-id]');
      if (!card || !this.contains(card)) return;
      const item = inventory.find(entry => String(entry.id) === String(card.dataset.viewAllId));
      if (item) showItemViewModal(item);
    });

    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      if (itemViewModal?.classList.contains('is-open')) {
        hideItemViewModal();
        return;
      }
      if (viewAllModal?.classList.contains('is-open')) {
        hideViewAllModal();
      }
    });

    document.getElementById('deletePassword').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        document.getElementById('deleteConfirmBtn').click();
      }
    });

    const togglePassword = document.getElementById('togglePassword');
    const passwordInput = document.getElementById('deletePassword');

    togglePassword.addEventListener('click', function () {
      const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
      passwordInput.setAttribute('type', type);
      const icon = this.querySelector('img');
      if (icon) {
        icon.src = type === 'password' ? (this.dataset.hideSrc || icon.src) : (this.dataset.showSrc || icon.src);
      }
      this.setAttribute('aria-label', type === 'password' ? 'Show password' : 'Hide password');
    });

    function clearSearch() {
      searchInput.value = '';
      setCatPickerValue(categoryFilter, '', categoryFilter?.closest('[data-cat-picker]')?.querySelector('.cat-picker-value')?.dataset.placeholder);
      renderInventory(true);
      searchInput.focus();
    }

    viewItemsBtn.addEventListener('click', () => {
      document.querySelector('.sidebar-nav .tab-button[data-tab-target="allItemsPanel"]').click();
    });
    resetBtn.addEventListener('click', resetForm);
    fields.picture.addEventListener('change', handlePictureChange);
    inventoryTableBody.addEventListener('click', handleTableClick);
    searchInput.addEventListener('input', () => renderInventory(true));
    categoryFilter?.addEventListener('change', () => renderInventory(true));
    fields.categoryId?.addEventListener('change', updateProductCodePreview);
    clearSearchBtn.addEventListener('click', clearSearch);
    inventoryPrevPage?.addEventListener('click', () => {
      if (inventoryPage > 1) {
        inventoryPage -= 1;
        renderInventory();
      }
    });
    inventoryNextPage?.addEventListener('click', () => {
      inventoryPage += 1;
      renderInventory();
    });

    initCatPickers();
    loadInventory();
    renderInventory();

    // ── Delivery form: add/remove item rows ──
    const deliveryContainer = document.getElementById('deliveryItemsContainer');
    const addItemBtn = document.getElementById('addItemRow');

    function createItemRow() {
      const template = deliveryContainer.querySelector('.delivery-item-row');
      const clone = template.cloneNode(true);
      // Clear input values
      clone.querySelectorAll('input').forEach(input => input.value = '');
      // Set defaults
      const qtyInput = clone.querySelector('input[name="quantity_cartons[]"]');
      if (qtyInput) qtyInput.value = 1;
      const pcsInput = clone.querySelector('input[name="pcs_per_carton[]"]');
      if (pcsInput) pcsInput.value = 1;
      const costInput = clone.querySelector('input[name="cost_per_carton[]"]');
      if (costInput) costInput.value = '0.00';
      // Attach remove event
      const removeBtn = clone.querySelector('.remove-item-row');
      removeBtn.addEventListener('click', function () {
        if (deliveryContainer.children.length > 1) {
          clone.remove();
        } else {
          alert('You need at least one item row.');
        }
      });
      return clone;
    }

    addItemBtn.addEventListener('click', function () {
      const newRow = createItemRow();
      deliveryContainer.appendChild(newRow);
      // Focus first input
      newRow.querySelector('input')?.focus();
    });

    // Attach remove events to existing rows (except the first)
    document.querySelectorAll('.delivery-item-row').forEach((row, index) => {
      if (index > 0) {
        const removeBtn = row.querySelector('.remove-item-row');
        removeBtn.addEventListener('click', function () {
          if (deliveryContainer.children.length > 1) {
            row.remove();
          } else {
            alert('You need at least one item row.');
          }
        });
      }
    });

    // Reset button: clear rows to only one
    document.querySelector('#deliveryForm .clear')?.addEventListener('click', function (e) {
      // Prevent default reset which may not clear all
      e.preventDefault();
      // Keep only first row
      const rows = deliveryContainer.querySelectorAll('.delivery-item-row');
      rows.forEach((row, idx) => {
        if (idx === 0) {
          row.querySelectorAll('input').forEach(inp => inp.value = '');
          row.querySelector('input[name="quantity_cartons[]"]').value = 1;
          row.querySelector('input[name="pcs_per_carton[]"]').value = 1;
          row.querySelector('input[name="cost_per_carton[]"]').value = '0.00';
        } else {
          row.remove();
        }
      });
      // Also reset header fields (they are not in this form's reset)
      document.querySelector('#deliveryForm input[name="delivery_date"]').value = '';
      document.querySelector('#deliveryForm input[name="driver"]').value = '';
      document.querySelector('#deliveryForm input[name="delivered_from"]').value = '';
      document.querySelector('#deliveryForm input[name="delivered_to"]').value = '';
    });

    // ── Purchase Order tab ──
    (function () {
      const printArea = document.getElementById('poPrintArea');
      const itemsBody = document.getElementById('poItemsBody');
      const addRowBtn = document.getElementById('poAddRowBtn');
      const printBtn = document.getElementById('poPrintBtn');
      const downloadPdfBtn = document.getElementById('poDownloadPdfBtn');
      const resetBtn = document.getElementById('poResetBtn');
      const currencySelect = document.getElementById('poCurrency');
      const currencyOther = document.getElementById('poCurrencyOther');
      const orderDateInput = document.getElementById('poOrderDate');
      const subtotalInput = document.getElementById('poSubtotal');
      const taxInput = document.getElementById('poTax');
      const discountInput = document.getElementById('poDiscount');
      const shippingInput = document.getElementById('poShipping');
      const grandTotalInput = document.getElementById('poGrandTotal');

      if (!printArea) return; // panel not present

      function todayISO() {
        const d = new Date();
        return d.toISOString().slice(0, 10);
      }
      if (orderDateInput && !orderDateInput.value) orderDateInput.value = todayISO();

      function money(n) {
        n = Number(n) || 0;
        return n.toFixed(2);
      }

      function recalcRow(row) {
        const qty = parseFloat(row.querySelector('.po-qty')?.value) || 0;
        const cost = parseFloat(row.querySelector('.po-cost')?.value) || 0;
        const totalField = row.querySelector('.po-line-total');
        if (totalField) totalField.value = money(qty * cost);
      }

      function recalcAll() {
        let subtotal = 0;
        itemsBody.querySelectorAll('tr').forEach(row => {
          recalcRow(row);
          subtotal += parseFloat(row.querySelector('.po-line-total')?.value) || 0;
        });
        subtotalInput.value = money(subtotal);
        const tax = parseFloat(taxInput.value) || 0;
        const discount = parseFloat(discountInput.value) || 0;
        const shipping = parseFloat(shippingInput.value) || 0;
        const grand = subtotal + tax + shipping - discount;
        grandTotalInput.value = money(grand);
      }

      function renumberRows() {
        itemsBody.querySelectorAll('tr').forEach((row, idx) => {
          const noInput = row.querySelector('.col-no input');
          if (noInput) noInput.value = idx + 1;
        });
      }

      function addRow() {
        const template = itemsBody.querySelector('tr');
        if (!template) return;

        const clone = template.cloneNode(true);
        clone.querySelectorAll('input, textarea').forEach(el => {
          if (el.classList.contains('po-qty')) {
            el.value = 1;
            return;
          }
          if (el.classList.contains('po-cost')) {
            el.value = '0.00';
            return;
          }
          if (el.classList.contains('po-line-total')) {
            el.value = '0.00';
            return;
          }
          el.value = '';
        });

        const rowCount = itemsBody.querySelectorAll('tr').length + 1;
        const noInput = clone.querySelector('.col-no input');
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
        const btn = e.target.closest('.po-row-remove');
        if (!btn) return;
        removeRow(btn.closest('tr'));
      });

      addRowBtn.addEventListener('click', function (e) {
        e.preventDefault();
        addRow();
      });

      [taxInput, discountInput, shippingInput].forEach(el => {
        el.addEventListener('input', recalcAll);
      });

      currencySelect.addEventListener('change', function () {
        const isOther = this.value === 'OTHER';
        currencyOther.hidden = !isOther;
        if (isOther) currencyOther.focus();
      });

      // ── Python (ReportLab) PDF download — accurate Long Bond pagination ──
      function collectPoPayload() {
        const currency = currencySelect?.value || 'PHP';
        const items = [];
        itemsBody.querySelectorAll('tr').forEach(row => {
          items.push({
            no: row.querySelector('.col-no input')?.value || '',
            code: row.querySelector('.col-code input')?.value || '',
            description: row.querySelector('.col-desc textarea')?.value || '',
            qty: row.querySelector('.po-qty')?.value || '0',
            unit: row.querySelector('.col-unit input')?.value || '',
            unit_cost: row.querySelector('.po-cost')?.value || '0',
            total: row.querySelector('.po-line-total')?.value || '0',
          });
        });

        return {
          po_number: document.getElementById('poNumber')?.value || '',
          currency,
          currency_other: currencyOther?.value || '',
          order_date: orderDateInput?.value || '',
          delivery_date: document.getElementById('poDeliveryDate')?.value || '',
          buyer: {
            company: document.getElementById('poBuyerCompany')?.value || '',
            address: document.getElementById('poBuyerAddress')?.value || '',
            contact: document.getElementById('poBuyerContact')?.value || '',
            email: document.getElementById('poBuyerEmail')?.value || '',
          },
          seller: {
            company: document.getElementById('poSellerCompany')?.value || '',
            address: document.getElementById('poSellerAddress')?.value || '',
            contact: document.getElementById('poSellerContact')?.value || '',
            email: document.getElementById('poSellerEmail')?.value || '',
          },
          items,
          subtotal: subtotalInput?.value || '0',
          tax: taxInput?.value || '0',
          discount: discountInput?.value || '0',
          shipping: shippingInput?.value || '0',
          grand_total: grandTotalInput?.value || '0',
          payment_terms: document.getElementById('poPaymentTerms')?.value || '',
          payment_method: document.getElementById('poPaymentMethod')?.value || '',
          payment_due_date: document.getElementById('poPaymentDueDate')?.value || '',
          return_policy: document.getElementById('poReturnPolicy')?.value || '',
          warranty: document.getElementById('poWarranty')?.value || '',
          delivery_conditions: document.getElementById('poDeliveryConditions')?.value || '',
          other_terms: document.getElementById('poOtherTerms')?.value || '',
          prepared_by: {
            name: document.getElementById('poPreparedName')?.value || '',
            title: document.getElementById('poPreparedPosition')?.value || '',
            signature: document.getElementById('poPreparedSignature')?.value || '',
            date: document.getElementById('poPreparedDate')?.value || '',
          },
          approved_by: {
            name: 'Engr. Arturo I. Davis, PME',
            title: 'President / CEO',
            signature: document.getElementById('poApprovedSignature')?.value || '',
            date: document.getElementById('poApprovedDate')?.value || '',
          },
        };
      }

      async function fetchPoPdfBlob() {
        const payload = collectPoPayload();
        const token = document.querySelector('[name=csrfmiddlewaretoken]')?.value || csrfToken || '';

        const response = await fetch((window.__INVENTORY_CONFIG__ && window.__INVENTORY_CONFIG__.poPdfUrl) || '', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': token,
          },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          let message = 'Could not generate the PDF.';
          try {
            const err = await response.json();
            if (err.error) message = err.error;
          } catch (_) { /* ignore */ }
          throw new Error(message);
        }

        const blob = await response.blob();
        return { blob, payload };
      }

      async function downloadPdf() {
        try {
          const { blob, payload } = await fetchPoPdfBlob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          const fileName = (payload.po_number || 'purchase-order').replace(/[^a-zA-Z0-9-_]/g, '_');
          a.href = url;
          a.download = `${fileName}.pdf`;
          document.body.appendChild(a);
          a.click();
          a.remove();
          setTimeout(() => URL.revokeObjectURL(url), 2000);
        } catch (error) {
          console.error('PDF generation error:', error);
          alert(error && error.message ? error.message : 'Could not generate the PDF.');
        }
      }

      async function printPoPdf() {
        try {
          const { blob } = await fetchPoPdfBlob();
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
              // Fallback: open PDF in a new tab for print / save
              window.open(url, '_blank');
            } finally {
              cleanup();
            }
          };
        } catch (error) {
          console.error('PDF print error:', error);
          alert(error && error.message ? error.message : 'Could not generate the PDF for printing.');
        }
      }

      downloadPdfBtn.addEventListener('click', function (e) {
        e.preventDefault();
        downloadPdf();
      });

      // Same Python PDF as Download — open browser print dialog on that file
      printBtn.addEventListener('click', function (e) {
        e.preventDefault();
        printPoPdf();
      });

      resetBtn.addEventListener('click', function () {
        if (!confirm('Reset the Purchase Order form? All entered data will be cleared.')) return;
        const rows = itemsBody.querySelectorAll('tr');
        rows.forEach((row, idx) => { if (idx > 0) row.remove(); });
        const first = itemsBody.querySelector('tr');
        first.querySelectorAll('input, textarea').forEach(el => {
          if (el.classList.contains('col-no')) return;
          if (el.classList.contains('po-qty')) { el.value = 1; return; }
          if (el.classList.contains('po-cost')) { el.value = '0.00'; return; }
          if (el.classList.contains('po-line-total')) { el.value = '0.00'; return; }
          el.value = '';
        });
        first.querySelector('.col-no input').value = 1;
        taxInput.value = '0.00';
        discountInput.value = '0.00';
        shippingInput.value = '0.00';
        currencySelect.value = 'PHP';
        currencyOther.hidden = true;
        currencyOther.value = '';
        orderDateInput.value = todayISO();
        document.getElementById('poDeliveryDate').value = '';
        recalcAll();
      });

      recalcAll();
    })();

  })();
