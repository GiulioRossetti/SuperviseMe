/* Live search helpers.
 * 1) <form method="get" data-live-region="#id">: refreshes #id as you type / change filters / paginate, by
 *    re-requesting the same page and swapping that region (works on any server-rendered GET page).
 * 2) Topbar search box: shows quick suggestions from /search/suggest while typing.
 */
(function () {
    'use strict';
    if (!window.fetch || !window.URLSearchParams) { return; }

    function debounce(fn, ms) { var t; return function () { var a = arguments, c = this; clearTimeout(t); t = setTimeout(function () { fn.apply(c, a); }, ms); }; }

    function liveForm(form) {
        var sel = form.getAttribute('data-live-region'), seq = 0;
        function region() { return document.querySelector(sel); }
        function url() {
            var p = new URLSearchParams(new FormData(form));
            Array.from(p.keys()).forEach(function (k) { if (!p.get(k)) { p.delete(k); } });
            var q = p.toString();
            return (form.getAttribute('action') || location.pathname) + (q ? '?' + q : '');
        }
        function load(target) {
            var box = region(), id = ++seq;
            if (!box) { return; }
            box.style.opacity = '.55';
            fetch(target, {headers: {'X-Requested-With': 'fetch'}, credentials: 'same-origin'})
                .then(function (r) { return r.ok ? r.text() : Promise.reject(); })
                .then(function (html) {
                    if (id !== seq) { return; }
                    var fresh = new DOMParser().parseFromString(html, 'text/html').querySelector(sel);
                    if (fresh) { box.innerHTML = fresh.innerHTML; }
                    box.style.opacity = '';
                    history.replaceState(null, '', target);
                })
                .catch(function () { if (id === seq) { box.style.opacity = ''; } });
        }
        var typing = debounce(function () { load(url()); }, 280);
        form.addEventListener('submit', function (e) { e.preventDefault(); load(url()); });
        form.addEventListener('input', function (e) { if (e.target.matches('input[type=search],input[type=text]')) { typing(); } });
        form.addEventListener('change', function (e) { if (e.target.matches('select,input[type=checkbox],input[type=radio],input[type=date]')) { load(url()); } });
        document.addEventListener('click', function (e) {
            var a = e.target.closest(sel + ' .pagination a');
            if (a && a.getAttribute('href') && a.getAttribute('href') !== '#') { e.preventDefault(); load(a.getAttribute('href')); }
        });
    }

    function suggestions(input) {
        var form = input.closest('form'), box = document.createElement('div'), seq = 0;
        box.className = 'sm-suggest list-group shadow'; box.hidden = true;
        box.style.cssText = 'position:absolute;z-index:1050;top:100%;left:0;right:0;max-height:70vh;overflow:auto;min-width:280px';
        var host = input.closest('.input-group') || form;
        host.style.position = 'relative'; host.appendChild(box);
        function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }
        function render(items, term) {
            if (!items.length) { box.innerHTML = '<div class="list-group-item small text-muted">' + esc(box.dataset.empty || '—') + '</div>'; box.hidden = false; return; }
            var last = null, html = '';
            items.forEach(function (it) {
                if (it.group !== last) { html += '<div class="list-group-item py-1 small text-uppercase text-muted bg-light">' + esc(it.group) + '</div>'; last = it.group; }
                html += '<a class="list-group-item list-group-item-action py-2" href="' + esc(it.url) + '"><div class="font-weight-bold small">' + esc(it.title) + '</div>' +
                    (it.sub ? '<div class="small text-muted">' + esc(it.sub) + '</div>' : '') + '</a>';
            });
            html += '<a class="list-group-item list-group-item-action small text-primary" href="' + esc(form.action) + '?q=' + encodeURIComponent(term) + '">' + esc(box.dataset.all || 'All results') + ' &rarr;</a>';
            box.innerHTML = html; box.hidden = false;
        }
        var run = debounce(function () {
            var term = input.value.trim(), id = ++seq;
            if (term.length < 2) { box.hidden = true; return; }
            fetch(form.getAttribute('data-suggest-url') + '?q=' + encodeURIComponent(term), {credentials: 'same-origin'})
                .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
                .then(function (d) { if (id === seq && input.value.trim() === term) { box.dataset.empty = d.empty; box.dataset.all = d.all; render(d.items || [], term); } })
                .catch(function () { box.hidden = true; });
        }, 220);
        input.addEventListener('input', run);
        input.addEventListener('keydown', function (e) { if (e.key === 'Escape') { box.hidden = true; } });
        document.addEventListener('click', function (e) { if (!host.contains(e.target)) { box.hidden = true; } });
    }

    document.addEventListener('DOMContentLoaded', function () {
        Array.prototype.forEach.call(document.querySelectorAll('form[data-live-region]'), liveForm);
        Array.prototype.forEach.call(document.querySelectorAll('form[data-suggest-url] input[name=q]'), suggestions);
    });
})();
