/* Paged carousel with client-side filtering, shared by the board-style lists.
   Markup: <section id="root"> ... <div class="sv-carousel"><button class="sv-prev"/><div class="sv-viewport"><div class="sv-track"/></div><button class="sv-next"/></div>
           <div class="sv-dots"/> ... </section>
   Items: elements matching `source` (hidden); the first child of each is cloned into the visible pages.
   Remote mode (server-side pagination, for long lists): pass `remote: {url, params: function () { return {q: ...}; }}`
   instead of `source`/`matches`. The endpoint gets `page` (1-based), `per` plus params() and answers JSON
   {total, page, pages, html}; html holds the `.sv-item` elements of that page only. */
(function (w) {
    w.SmCarousel = function (o) {
        var $ = w.jQuery;
        var $root = $(o.root), items = o.source ? $root.find(o.source).toArray() : [], filtered = items.slice(), page = 0;
        var remote = o.remote || null, pages = 1, total = 0, seq = 0, timer = null;
        var $track = $root.find('.sv-track'), $dots = $root.find('.sv-dots'), $prev = $root.find('.sv-prev'), $next = $root.find('.sv-next');
        var $carousel = $root.find('.sv-carousel'), $empty = $(o.empty);
        function cols() { return o.cols(); }
        function perPage() { return cols() * (o.rows || 1); }
        function paint() {
            var size = perPage(), from = total ? page * size + 1 : 0, to = Math.min(total, (page + 1) * size);
            if (o.count) $(o.count).text(total ? from + '–' + to + ' / ' + total : '0');
            $prev.prop('disabled', page === 0); $next.prop('disabled', page >= pages - 1);
            $carousel.toggle(total > 0); $empty.toggle(total === 0);
            $dots.empty();
            if (pages > 1) for (var j = 0; j < pages; j++) $('<button type="button" class="sv-dot" aria-label="' + (j + 1) + '"></button>').toggleClass('active', j === page).attr('data-page', j).appendTo($dots);
            if (o.onRender) o.onRender();
        }
        function load() {
            var mine = ++seq, q = $.extend({}, remote.params ? remote.params() : {}, {page: page + 1, per: perPage()});
            $root.attr('aria-busy', 'true');
            $.getJSON(remote.url, q).done(function (d) {
                if (mine !== seq) return;
                total = d.total; pages = d.pages; page = d.page - 1;
                var $p = $('<div class="sv-page"></div>').css('grid-template-columns', 'repeat(' + cols() + ', minmax(0, 1fr))');
                $('<div></div>').html(d.html).children().each(function () {
                    var $c = $(this).children().first(), $s = $('<div class="sv-slot"></div>').append($c);
                    $s.attr('data-uid', this.getAttribute('data-uid') || '');
                    $p.append($s);
                });
                $track.empty().append($p).css('transform', 'translateX(0)');
                paint();
            }).always(function () { if (mine === seq) $root.removeAttr('aria-busy'); });
        }
        function render() {
            if (remote) { load(); return; }
            var size = perPage(), pages = Math.max(1, Math.ceil(filtered.length / size));
            page = Math.min(page, pages - 1);
            $track.empty();
            for (var i = 0; i < pages; i++) {
                var $p = $('<div class="sv-page"></div>').css('grid-template-columns', 'repeat(' + cols() + ', minmax(0, 1fr))');
                filtered.slice(i * size, (i + 1) * size).forEach(function (el) {
                    var $c = $(el).children().first().clone(true, true), $s = $('<div class="sv-slot"></div>').append($c);
                    if ($c.hasClass('is-open')) $s.css('grid-column', '1 / -1');
                    $s.attr('data-uid', el.getAttribute('data-uid') || '');
                    $p.append($s);
                });
                $track.append($p);
            }
            $track.css('transform', 'translateX(' + (-100 * page) + '%)');
            var from = filtered.length ? page * size + 1 : 0, to = Math.min(filtered.length, (page + 1) * size);
            if (o.count) $(o.count).text(filtered.length ? from + '–' + to + ' / ' + filtered.length : '0');
            $prev.prop('disabled', page === 0); $next.prop('disabled', page >= pages - 1);
            $carousel.toggle(filtered.length > 0); $empty.toggle(filtered.length === 0);
            $dots.empty();
            if (pages > 1) for (var j = 0; j < pages; j++) $('<button type="button" class="sv-dot"></button>').toggleClass('active', j === page).attr('data-page', j).appendTo($dots);
            if (o.onRender) o.onRender();
        }
        function apply(reset) {
            if (remote) {
                if (reset) page = 0;
                clearTimeout(timer); timer = setTimeout(load, reset ? 200 : 0);
                return;
            }
            filtered = items.filter(o.matches);
            if (o.sorter) filtered.sort(o.sorter);
            if (reset) page = 0;
            render();
        }
        $prev.on('click', function () { if (page > 0) { page--; render(); } });
        $next.on('click', function () { page++; render(); });
        $dots.on('click', '.sv-dot', function () { page = parseInt($(this).attr('data-page'), 10); render(); });
        var x0 = null;
        $root.find('.sv-viewport').on('touchstart', function (e) { x0 = e.originalEvent.touches[0].clientX; })
            .on('touchend', function (e) { if (x0 === null) return; var dx = e.originalEvent.changedTouches[0].clientX - x0; if (dx > 50) $prev.click(); else if (dx < -50) $next.click(); x0 = null; });
        var last = perPage();
        $(w).on('resize', function () { if (perPage() !== last) { last = perPage(); render(); } });
        apply(true);
        return { apply: apply, render: render, items: items };
    };
})(window);
