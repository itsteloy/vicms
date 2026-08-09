(function () {
    const modal = document.getElementById('workspaceLoginModal');
    const closeBtn = document.getElementById('closeWorkspaceLogin');
    const workspaceNameEl = document.getElementById('modalWorkspaceName');
    const workspaceKeyInput = document.getElementById('modalWorkspaceKey');
    const hintBox = document.getElementById('modalCredentialHint');
    const hintUser = document.getElementById('modalHintUser');
    const hintPass = document.getElementById('modalHintPass');
    const usernameInput = document.getElementById('modalUsername');
    const passwordInput = document.getElementById('modalPassword');
    const loginError = document.getElementById('modalLoginError');
    const pickers = document.querySelectorAll('.workspace-picker');

    function openModal(button) {
      const name = button.dataset.workspaceName || 'workspace';
      const key = button.dataset.workspaceKey || '';
      const user = button.dataset.workspaceUsername || '';
      const pass = button.dataset.workspacePassword || '';

      workspaceNameEl.textContent = name;
      workspaceKeyInput.value = key;
      usernameInput.value = '';
      passwordInput.value = '';

      if (user && pass) {
        hintUser.textContent = user;
        hintPass.textContent = pass;
        hintBox.hidden = false;
      } else {
        hintBox.hidden = true;
      }

      modal.classList.add('is-open');
      modal.setAttribute('aria-hidden', 'false');
      usernameInput.focus();
    }

    function closeModal() {
      modal.classList.remove('is-open');
      modal.setAttribute('aria-hidden', 'true');
      if (loginError) {
        loginError.hidden = true;
      }
    }

    pickers.forEach(function (button) {
      button.addEventListener('click', function () {
        openModal(button);
      });
    });

    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', function (event) {
      if (event.target === modal) {
        closeModal();
      }
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && modal.classList.contains('is-open')) {
        closeModal();
      }
    });

    
    const selectCfg = window.__DASHBOARD_SELECT_CONFIG__ || {};
    if (selectCfg.selectedWorkspace) {
      const preselected = document.querySelector('[data-workspace-key="' + selectCfg.selectedWorkspace + '"]');
      if (preselected) {
        openModal(preselected);
        if (selectCfg.loginError && loginError) {
          loginError.hidden = false;
        }
      }
    }
  })();
