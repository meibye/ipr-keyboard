/* Dates and times in the viewer's time zone.
 *
 * Every time the device shows is presented in the time zone of the browser
 * looking at it, never the device's own.  The server therefore sends
 * instants only: epoch seconds, ISO 8601 with "Z" or an offset, or journal
 * lines in `journalctl -o short-iso` form ("2026-10-10T19:27:40+02:00 ...").
 * This file turns those into local wall-clock text.  No dependencies, no
 * build step; loaded by every page that shows a time.
 */
(function (global) {
  'use strict';

  function pad(n) { return String(n).padStart(2, '0'); }

  // A Date from epoch seconds, an ISO string, or a Date; null if unusable.
  function toDate(value) {
    if (value === null || value === undefined || value === '') return null;
    var d;
    if (value instanceof Date) d = value;
    else if (typeof value === 'number') d = new Date(value * 1000);
    else if (/^\d+(\.\d+)?$/.test(String(value))) d = new Date(Number(value) * 1000);
    else d = new Date(String(value));
    return isNaN(d.getTime()) ? null : d;
  }

  // The viewer's zone abbreviation ("CEST", "GMT+2"), or '' if unavailable.
  function zoneName(d) {
    try {
      var parts = new Intl.DateTimeFormat(undefined, { timeZoneName: 'short' }).formatToParts(d);
      for (var i = 0; i < parts.length; i++) {
        if (parts[i].type === 'timeZoneName') return parts[i].value;
      }
    } catch (e) { /* old browser: no zone label */ }
    return '';
  }

  // "2026-10-10 19:27:40" in the viewer's zone; withZone appends " CEST".
  // Unusable input is returned unchanged, so nothing is ever blanked out.
  function formatTime(value, withZone) {
    var d = toDate(value);
    if (!d) return value === null || value === undefined ? '' : String(value);
    var s = d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' +
      pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
    if (withZone) {
      var z = zoneName(d);
      if (z) s += ' ' + z;
    }
    return s;
  }

  // Journal lines: rewrite each leading short-iso stamp to local time.
  var LINE_STAMP = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2}))(?=\s)/;
  function localizeLines(text) {
    return String(text || '').split('\n').map(function (line) {
      var m = line.match(LINE_STAMP);
      if (!m) return line;
      // Safari wants "+02:00", journalctl may print "+0200".
      var iso = m[1].replace(/([+-]\d{2})(\d{2})$/, '$1:$2');
      var d = toDate(iso);
      return d ? formatTime(d) + line.slice(m[1].length) : line;
    }).join('\n');
  }

  // A clock that shows the device's time, ticking, in the viewer's zone.
  // `epoch` is the device clock in seconds when the page got it.
  var clocks = [];
  function startClock(el, epoch) {
    var base = toDate(epoch);
    if (!el || !base) return;
    var entry = { el: el, base: base.getTime(), at: Date.now() };
    for (var i = 0; i < clocks.length; i++) {
      if (clocks[i].el === el) { clocks[i] = entry; entry = null; break; }
    }
    if (entry) clocks.push(entry);
    var tick = function () {
      for (var j = 0; j < clocks.length; j++) {
        var c = clocks[j];
        c.el.textContent = formatTime(new Date(c.base + (Date.now() - c.at)), true);
      }
    };
    tick();
    if (!startClock.timer) startClock.timer = setInterval(tick, 1000);
  }

  // Server-rendered pages mark times for conversion:
  //   <time data-ipr-time datetime="2026-10-10T17:27:40Z">...</time>
  //   <pre data-ipr-log>...short-iso journal lines...</pre>
  //   <span data-ipr-clock="1791652060.5">...</span>
  function localizePage(root) {
    root = root || document;
    var i, els;
    els = root.querySelectorAll('[data-ipr-time]');
    for (i = 0; i < els.length; i++) {
      var v = els[i].getAttribute('datetime') || els[i].getAttribute('data-ipr-time');
      if (v) els[i].textContent = formatTime(v, els[i].hasAttribute('data-ipr-zone'));
    }
    els = root.querySelectorAll('[data-ipr-log]');
    for (i = 0; i < els.length; i++) els[i].textContent = localizeLines(els[i].textContent);
    els = root.querySelectorAll('[data-ipr-clock]');
    for (i = 0; i < els.length; i++) startClock(els[i], els[i].getAttribute('data-ipr-clock'));
  }

  global.iprTime = {
    format: formatTime,
    localizeLines: localizeLines,
    startClock: startClock,
    localizePage: localizePage,
    zoneName: zoneName,
  };

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () { localizePage(); });
    } else {
      localizePage();
    }
  }
})(typeof window !== 'undefined' ? window : globalThis);
