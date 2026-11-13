// Links hover across the storage page's secondary charts. Dash serves every .js in assets/ automatically.
// - Hovering the cumulative chart highlights that day's samples on it and shows the tooltip on all three charts.
// - Hovering a daily chart highlights that day on the cumulative chart (no tooltip there) and mirrors the
//   tooltip on the other daily chart.
(function () {
    const CUMULATIVE = 'cumulative-graph';
    const DAILY = ['daily-graph', 'daily-energy-graph'];
    const HIGHLIGHT = 'day-highlight';
    const DAY_MS = 24 * 60 * 60 * 1000;
    let syncing = false;
    let redrawing = 0;  // restyling the highlight unhovers the cumulative chart; ignore that unhover

    function plotDiv(id) {
        const el = document.getElementById(id);
        return el && el.querySelector('.js-plotly-plot');
    }

    // Plotly date axes count milliseconds in naive (UTC-like) time
    function dayStart(ms) {
        return Math.floor(ms / DAY_MS) * DAY_MS;
    }

    // Index range of each day's samples, cached until the figure gets new data.
    // _fullData holds the decoded arrays (gd.data may carry them base64-encoded).
    function dayIndex(gd) {
        const x = gd._fullData[0].x;
        if (gd._dayIndex && gd._dayIndex.x === x) return gd._dayIndex.days;
        const days = new Map();
        const xa = gd._fullLayout.xaxis;
        for (let i = 0; i < x.length; i++) {
            const d = dayStart(xa.d2c(x[i]));
            const range = days.get(d);
            if (range) range[1] = i + 1; else days.set(d, [i, i + 1]);
        }
        gd._dayIndex = {x: x, days: days};
        return days;
    }

    function highlightDay(day) {
        const gd = plotDiv(CUMULATIVE);
        if (!gd || !gd.data) return Promise.resolve();
        const trace = gd.data.findIndex(function (t) { return t.name === HIGHLIGHT; });
        const current = gd._highlighted;
        if (trace < 0 || (current && current.day === day && current.x === gd._fullData[0].x)) return Promise.resolve();
        gd._highlighted = {day: day, x: gd._fullData[0].x};
        let x = [], y = [];
        const range = day === null ? null : dayIndex(gd).get(day);
        if (range) {
            // Include the previous sample so the highlighted segment starts at the day boundary
            const from = Math.max(range[0] - 1, 0);
            x = gd._fullData[0].x.slice(from, range[1]);
            y = Array.from(gd._fullData[0].y.slice(from, range[1]));
        }
        redrawing++;
        return window.Plotly.restyle(gd, {x: [x], y: [y]}, [trace]).finally(function () { redrawing--; });
    }

    function hoverOthers(sourceId, xval) {
        DAILY.forEach(function (id) {
            const gd = plotDiv(id);
            if (id !== sourceId && gd && gd._fullLayout) window.Plotly.Fx.hover(gd, {xval: xval}, 'xy');
        });
    }

    function onHover(sourceId, evt) {
        if (syncing || !evt.points || !evt.points.length) return;
        const src = plotDiv(sourceId);
        const x = src._fullLayout.xaxis.d2c(evt.points[0].x);
        const day = dayStart(x);
        syncing = true;
        try {
            hoverOthers(sourceId, day);
        } finally {
            syncing = false;
        }
        const redraw = highlightDay(day);
        if (sourceId === CUMULATIVE) {
            // Redrawing the highlight clears this chart's own tooltip, so put it back at the same position
            redraw.then(function () {
                syncing = true;
                try {
                    window.Plotly.Fx.hover(src, {xval: x}, 'xy');
                } finally {
                    syncing = false;
                }
            });
        }
    }

    function onUnhover(sourceId) {
        if (syncing || redrawing) return;
        syncing = true;
        try {
            DAILY.forEach(function (id) {
                const gd = plotDiv(id);
                if (id !== sourceId && gd) window.Plotly.Fx.unhover(gd);
            });
        } finally {
            syncing = false;
        }
        highlightDay(null);
    }

    // Graphs mount when the page is navigated to and their plot div can be recreated, so re-bind as needed
    function bind() {
        [CUMULATIVE].concat(DAILY).forEach(function (id) {
            const gd = plotDiv(id);
            if (!gd || !gd.on || gd._hoverSyncBound === gd._ev) return;
            gd.on('plotly_hover', function (evt) { onHover(id, evt); });
            gd.on('plotly_unhover', function () { onUnhover(id); });
            gd._hoverSyncBound = gd._ev;
        });
    }

    setInterval(bind, 500);
})();
