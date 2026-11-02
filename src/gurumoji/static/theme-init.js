/* Applies the saved colour theme before the page paints, so it never flashes the default. */
(function () {
  try {
    var theme = localStorage.getItem('gurumoji.theme.v1');
    if (theme) document.documentElement.setAttribute('data-theme', theme);
  } catch (_) {
    // Storage can be blocked; the default theme is used.
  }
}());
