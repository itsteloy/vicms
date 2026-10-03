/* VICMS light/dark theme — pilot: inventory. Persists per browser via localStorage. */
(function () {
  var STORAGE_KEY = 'vic-theme';
  var LIGHT = 'light';
  var DARK = 'dark';

  function getStoredTheme() {
    try {
      var v = localStorage.getItem(STORAGE_KEY);
      return v === DARK || v === LIGHT ? v : null;
    } catch (e) {
      return null;
    }
  }

  function getTheme() {
    return getStoredTheme() || LIGHT; // first visit defaults to light
  }

  function syncToggleUi(theme) {
    var isDark = theme === DARK;
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      btn.setAttribute('aria-pressed', isDark ? 'true' : 'false');
      btn.title = isDark ? 'Switch to light mode' : 'Switch to dark mode';
      var icon = btn.querySelector('[data-theme-toggle-icon]');
      var label = btn.querySelector('[data-theme-toggle-label]');
      if (icon) icon.textContent = isDark ? '☀️' : '🌙';
      if (label) label.textContent = isDark ? 'Light' : 'Dark';
      if (!icon && !label) btn.textContent = isDark ? '☀️ Light' : '🌙 Dark';
    });
  }

  function setTheme(theme, persist) {
    var next = theme === DARK ? DARK : LIGHT;
    document.documentElement.dataset.theme = next;
    if (persist !== false) {
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch (e) {}
    }
    syncToggleUi(next);
  }

  function toggleTheme() {
    setTheme(getTheme() === DARK ? LIGHT : DARK);
  }

  // Apply early (FOUC script in <head> already set it; re-assert here).
  setTheme(getTheme(), false);

  document.addEventListener('DOMContentLoaded', function () {
    syncToggleUi(getTheme());
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      btn.addEventListener('click', toggleTheme);
    });
  });

  window.VicTheme = { get: getTheme, set: setTheme, toggle: toggleTheme, key: STORAGE_KEY };
})();
