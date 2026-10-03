/* VICMS logout confirmation — intercepts logout links site-wide. */
(function () {
  var pendingUrl = null;
  var overlay = null;

  function logoutPath() {
    try {
      return new URL(window.__LOGOUT_URL__ || '/logout/', location.origin).pathname;
    } catch (e) {
      return '/logout/';
    }
  }

  function isLogoutLink(a) {
    if (!a || !a.href) return false;
    try {
      return new URL(a.href, location.origin).pathname === logoutPath();
    } catch (e) {
      return false;
    }
  }

  function buildModal() {
    overlay = document.createElement('div');
    overlay.className = 'logout-confirm-overlay';
    overlay.hidden = true;
    overlay.setAttribute('aria-hidden', 'true');
    overlay.innerHTML =
      '<div class="logout-confirm-card" role="dialog" aria-modal="true" aria-labelledby="logoutConfirmTitle">' +
        '<h2 id="logoutConfirmTitle">Log out?</h2>' +
        '<p>You will be signed out of your workspace.</p>' +
        '<div class="logout-confirm-actions">' +
          '<button type="button" class="logout-confirm-cancel">Cancel</button>' +
          '<button type="button" class="logout-confirm-ok">Log out</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);
    overlay.querySelector('.logout-confirm-cancel').addEventListener('click', close);
    overlay.querySelector('.logout-confirm-ok').addEventListener('click', function () {
      var url = pendingUrl;
      close();
      if (url) location.href = url;
    });
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && overlay && !overlay.hidden) close();
    });
  }

  function open(url) {
    pendingUrl = url;
    if (!overlay) buildModal();
    overlay.hidden = false;
    overlay.setAttribute('aria-hidden', 'false');
    var ok = overlay.querySelector('.logout-confirm-ok');
    if (ok) ok.focus();
  }

  function close() {
    pendingUrl = null;
    if (overlay) {
      overlay.hidden = true;
      overlay.setAttribute('aria-hidden', 'true');
    }
  }

  document.addEventListener('click', function (e) {
    var a = e.target.closest ? e.target.closest('a[href]') : null;
    if (a && isLogoutLink(a)) {
      e.preventDefault();
      open(a.href);
    }
  });
})();
