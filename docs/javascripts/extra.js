(function () {
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function reveal() {
    var els = document.querySelectorAll(".sm-reveal:not(.in)");
    if (reduce || !("IntersectionObserver" in window)) {
      els.forEach(function (e) { e.classList.add("in"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
      });
    }, { threshold: 0.12 });
    els.forEach(function (e) { io.observe(e); });
  }
  function progress() {
    var bar = document.getElementById("sm-progress");
    if (!bar) return;
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + "%";
  }
  window.addEventListener("scroll", progress, { passive: true });
  if (window.document$) { document$.subscribe(function () { reveal(); progress(); }); }
  else { document.addEventListener("DOMContentLoaded", function () { reveal(); progress(); }); }
})();
