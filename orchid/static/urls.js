"use strict";
(function(root) {
  function createAppURL(scriptURL) {
    const base = new URL('.', scriptURL).pathname.replace(/\/$/, '');
    return value => {
      if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return value;
      if (base && (value === base || value.startsWith(base + '/'))) return value;
      return base + value;
    };
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {createAppURL};
  if (root.document) root.OrchidURL = createAppURL(document.currentScript.src);
})(typeof globalThis !== 'undefined' ? globalThis : this);
