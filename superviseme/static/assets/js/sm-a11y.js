/* Progressive accessibility enhancements shared by every page (loaded from the common footer).
   - Tabs: tablist/tab/tabpanel roles, aria-selected, arrow-key navigation.
   - Board carousels (.sv-carousel): region + slide semantics, live item counter, labelled dots,
     keyboard paging with the arrow keys.
   - Modals: dialog role and aria-labelledby from the modal title.
   - Icon-only buttons and links get an accessible name from their title. */
(function () {
    'use strict';
    var uid = 0;
    function id(el, prefix) { if (!el.id) el.id = prefix + '-' + (++uid); return el.id; }

    function enhanceTabs(root) {
        root.querySelectorAll('.nav [role="tab"]').forEach(function (tab) {
            var list = tab.closest('.nav');
            if (list && !list.hasAttribute('role')) list.setAttribute('role', 'tablist');
            var href = tab.getAttribute('href') || '', panel = href.charAt(0) === '#' ? document.getElementById(href.slice(1)) : null;
            id(tab, 'sm-tab');
            if (panel) { tab.setAttribute('aria-controls', panel.id); panel.setAttribute('role', 'tabpanel'); panel.setAttribute('aria-labelledby', tab.id); }
            tab.setAttribute('aria-selected', tab.classList.contains('active') ? 'true' : 'false');
            tab.setAttribute('tabindex', tab.classList.contains('active') ? '0' : '-1');
        });
    }
    document.addEventListener('keydown', function (e) {
        var tab = e.target.closest && e.target.closest('[role="tab"]');
        if (!tab || (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft' && e.key !== 'Home' && e.key !== 'End')) return;
        var tabs = Array.prototype.slice.call(tab.closest('[role="tablist"]').querySelectorAll('[role="tab"]'));
        var i = tabs.indexOf(tab);
        i = e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : (i + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        e.preventDefault();
        tabs[i].focus();
        tabs[i].click();
    });
    document.addEventListener('click', function (e) {
        var tab = e.target.closest && e.target.closest('[role="tab"]');
        if (!tab) return;
        setTimeout(function () { enhanceTabs(document); }, 0);
    });

    function enhanceCarousels(root) {
        root.querySelectorAll('.sv-carousel').forEach(function (car) {
            var section = car.closest('.card') || car.parentElement, title = section && section.querySelector('.card-header h6');
            car.setAttribute('role', 'region');
            car.setAttribute('aria-roledescription', 'carousel');
            if (title && !car.hasAttribute('aria-label')) car.setAttribute('aria-label', title.textContent.trim());
            var viewport = car.querySelector('.sv-viewport');
            if (viewport) { viewport.setAttribute('tabindex', '0'); viewport.setAttribute('aria-live', 'polite'); }
            car.querySelectorAll('.sv-page').forEach(function (p, i, all) {
                p.setAttribute('role', 'group'); p.setAttribute('aria-roledescription', 'slide');
                p.setAttribute('aria-label', (i + 1) + ' / ' + all.length);
            });
            ['sv-prev', 'sv-next'].forEach(function (c) {
                var b = car.querySelector('.' + c); if (b && !b.getAttribute('aria-label')) b.setAttribute('aria-label', c === 'sv-prev' ? 'Previous' : 'Next');
            });
        });
        root.querySelectorAll('.sv-dots').forEach(function (d) {
            d.setAttribute('role', 'group'); d.setAttribute('aria-label', 'Pages');
            d.querySelectorAll('.sv-dot').forEach(function (b, i) {
                b.setAttribute('aria-label', 'Page ' + (i + 1));
                if (b.classList.contains('active')) b.setAttribute('aria-current', 'true'); else b.removeAttribute('aria-current');
            });
        });
        root.querySelectorAll('[id$="Count"].small, #usCount, #thCount').forEach(function (c) { c.setAttribute('aria-live', 'polite'); });
    }
    document.addEventListener('keydown', function (e) {
        var vp = e.target.closest && e.target.closest('.sv-viewport');
        if (!vp || e.target !== vp || (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft')) return;
        var btn = vp.closest('.sv-carousel').querySelector(e.key === 'ArrowRight' ? '.sv-next' : '.sv-prev');
        if (btn && !btn.disabled) { e.preventDefault(); btn.click(); }
    });

    function enhanceModals(root) {
        root.querySelectorAll('.modal').forEach(function (m) {
            m.setAttribute('role', m.getAttribute('role') || 'dialog');
            m.setAttribute('aria-modal', 'true');
            var t = m.querySelector('.modal-title');
            if (t && !m.getAttribute('aria-labelledby')) m.setAttribute('aria-labelledby', id(t, 'sm-modal-title'));
        });
    }

    function nameIcons(root) {
        root.querySelectorAll('button, a.btn, a.dropdown-toggle').forEach(function (b) {
            if (b.hasAttribute('aria-label') || b.textContent.trim() || b.getAttribute('aria-labelledby')) return;
            var label = b.getAttribute('title') || b.getAttribute('data-original-title');
            if (label) b.setAttribute('aria-label', label);
        });
    }

    function run(root) { enhanceTabs(root); enhanceCarousels(root); enhanceModals(root); nameIcons(root); }
    var pending = false;
    function schedule() { if (pending) return; pending = true; setTimeout(function () { pending = false; run(document); }, 50); }
    document.addEventListener('DOMContentLoaded', function () {
        run(document);
        new MutationObserver(schedule).observe(document.body, {childList: true, subtree: true});
    });
    if (document.readyState !== 'loading') { run(document); }
})();
