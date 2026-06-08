/* Loaded LAST — every toolkit module and game is registered by now, so it is safe to boot
   the reader. (Kept in its own file so the boot call never races game registration.) */
(function () {
  "use strict";
  function go() { if (window.GB && window.GB.boot) window.GB.boot(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go);
  else go();
})();
