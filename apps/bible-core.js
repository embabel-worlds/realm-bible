/*
 * The shared core of realm-bible's apps: passage search, the reader, the people in a chapter, and one verse
 * across seven translations. Every edition's page (scripture-search.html, catholic.html, …) loads this and
 * wires its own front page around it, so a fix to the reader reaches every edition at once.
 *
 * A classic script, not a module, because the pages run as plain <script> includes; it defines one global,
 * BibleCore, and nothing else. It talks to the world only through the app runtime (embabel.views.invoke),
 * like any page here.
 *
 *   var core = BibleCore({ state, results, reader });   // the page's elements
 *   core.wire();                                          // search box, examples, cards, reader clicks
 *   core.search('bears eat boys who mocked a prophet');
 *   core.openPassage('Luke 1', { highlight: [26, 27, 28] });
 */
(function () {
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function rowsOf(r) {
    if (!r) return [];
    if (Array.isArray(r.data)) return r.data;
    if (r.data && Array.isArray(r.data.rows)) return r.data.rows;
    if (Array.isArray(r.rows)) return r.rows;
    return [];
  }
  function warningsOf(r) {
    if (!r) return [];
    if (Array.isArray(r.warnings)) return r.warnings;
    if (r.data && Array.isArray(r.data.warnings)) return r.data.warnings;
    return [];
  }
  function problem(msg) { return '<div class="problem">' + esc(msg) + '</div>'; }
  /* The public envelope carries warnings as {code, message}; older shapes carry strings. */
  function warnText(w) { return typeof w === 'string' ? w : (w && (w.message || w.code)) || String(w); }
  function errText(e) { return e && e.message ? e.message : String(e); }

  /* A verse is "matched" when its World English wording appears in the excerpt the search matched. The
     excerpt is WEB text, so the comparison is always against v.web, whichever translation is shown. */
  function norm(s) { return String(s || '').toLowerCase().replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim(); }
  function matchedVerses(row) {
    if (row.highlight) return row.highlight;
    var excerpt = norm(row.matched);
    if (!excerpt) return [];
    return (row.verses || []).filter(function (v) {
      var w = norm(v.web);
      if (!w) return false;
      var probe = w.length > 40 ? w.slice(0, 40) : w;
      var tail = w.length > 40 ? w.slice(-40) : w;
      return excerpt.indexOf(probe) >= 0 || excerpt.indexOf(tail) >= 0;
    }).map(function (v) { return v.n; });
  }
  /* The search's judged fit, 0 to 1: 1.0 means it read the chapter and judged that it narrates or contains what
     was described. Shown only below 1.0, where it is information — a column of "1.0" is noise. */
  function fitLabel(f) {
    var n = Number(f);
    if (!isFinite(n) || n >= 1) return '';
    return ' · <span title="How well the search judged this chapter fits your description, from 0 to 1">fit ' + n.toFixed(2) + '</span>';
  }
  /* The divine name as English Bibles print it: LORD, and GOD after "Lord", in small capitals. Applied to
     already-escaped text, so it only ever wraps words it found. */
  function sacred(escapedText) {
    return escapedText.replace(/\b(LORD|GOD)\b/g, function (w) { return '<span class="sc">' + w.charAt(0) + w.slice(1).toLowerCase() + '</span>'; });
  }
  function roman(n) {
    var map = [[100, 'C'], [90, 'XC'], [50, 'L'], [40, 'XL'], [10, 'X'], [9, 'IX'], [5, 'V'], [4, 'IV'], [1, 'I']], out = '';
    map.forEach(function (m) { while (n >= m[0]) { out += m[1]; n -= m[0]; } });
    return out;
  }
  /* "Luke 1:26-38" → { passage: 'Luke 1', verses: [26..38] }; "Matthew 3" → { passage: 'Matthew 3', verses: [] }. */
  function parseRef(ref) {
    var m = String(ref || '').match(/^(.*?\d+):(\d+)(?:\s*[-–]\s*(\d+))?\s*$/);
    if (!m) return { passage: String(ref || '').trim(), verses: [] };
    var from = Number(m[2]), to = m[3] ? Number(m[3]) : from, verses = [];
    for (var i = from; i <= to && verses.length < 200; i++) verses.push(i);
    return { passage: m[1].trim(), verses: verses };
  }
  var NT = /^(Matthew|Mark|Luke|John|Acts|Romans|1 Corinthians|2 Corinthians|Galatians|Ephesians|Philippians|Colossians|1 Thessalonians|2 Thessalonians|1 Timothy|2 Timothy|Titus|Philemon|Hebrews|James|1 Peter|2 Peter|1 John|2 John|3 John|Jude|Revelation) /;

  function BibleCore(opts) {
    var stateEl = opts.state, resultsEl = opts.results, readerEl = opts.reader;
    var translation = opts.translation || 'kjv';
    var rows = [];            // the shown search results
    var current = null;       // the row in the reader — from the results, or a passage opened by name
    var searchToken = 0;
    var peopleCache = {}, compareCache = {}, passageCache = {};
    /* What the shown rows answer: the reader's own description, or a story (a news headline, a saint's life).
       The cards and the reader are the same either way; only the sentence above them and the evidence line differ. */
    var asked = { kind: 'query', text: '' };
    var listeners = { search: [] };

    function verseText(v) { return translation === 'web' ? (v.web || v.kjv) : v.kjv; }

    function renderResults() {
      if (!resultsEl) return;
      if (!rows.length) {
        resultsEl.innerHTML = asked.kind === 'story'
          ? '<div class="placeholder">No chapter was judged to tell an event like this one. Not every story has a biblical ' +
            'parallel, and the search says so rather than reaching for one.</div>'
          : '<div class="placeholder">No chapter was judged to fit that description. Try it another way — ' +
            'what happens, who is there, or a phrase you remember.</div>';
        return;
      }
      var lead = asked.kind === 'story'
        ? 'Chapters the search judged to tell the same kind of event as <span class="storyline">“' + esc(asked.text) + '”</span>. ' +
          'Under each is the reading it judged by — a parallel, not a prophecy.'
        : 'Chapters judged to fit your description, best first — highlighted verses are the evidence the search read.';
      resultsEl.innerHTML = '<p class="note">' + lead + ' Showing the ' + (translation === 'web' ? 'World English Bible' : 'King James Version') + '.</p>' +
        rows.map(function (row) {
          var hits = matchedVerses(row);
          var shown = (hits.length ? row.verses.filter(function (v) { return hits.indexOf(v.n) >= 0; }) : row.verses.slice(0, 2)).slice(0, 3);
          return '<div class="card' + (current && row.osis === current.osis ? ' open' : '') + '" data-osis="' + esc(row.osis) + '" tabindex="0">' +
            '<div class="top"><span class="rank">' + esc(row.rank) + '</span><span class="passage">' + esc(row.passage) + '</span>' +
            '<span class="testament">' + esc(row.testament || '') + fitLabel(row.fit) + '</span></div>' +
            '<div class="verses scripture">' + shown.map(function (v) {
              return '<span class="vn">' + esc(v.n) + '</span>' + sacred(esc(verseText(v))) + ' ';
            }).join('') + '</div>' +
            /* For a story the link is an analogy the search drew, so its reasoning is shown, not just the
               verses: a judge fooled by a pun ("a plot of ground") is then visible as one. */
            (asked.kind === 'story' && row.matched ? '<div class="why">' + esc(row.matched) + '</div>' : '') + '</div>';
        }).join('');
    }

    function run(what, view, params, expectation) {
      var token = ++searchToken;
      asked = what;
      current = null;
      resultsEl.innerHTML = '<div class="placeholder">Reading candidate chapters…</div>';
      readerEl.innerHTML = '<div class="placeholder scripture">❦<br>Open a chapter to read it here.</div>';
      return embabel.views.invoke(view, params, { state: stateEl, expectation: expectation })
        .then(function (res) {
          if (token !== searchToken) return;
          rows = rowsOf(res);
          var w = warningsOf(res);
          renderResults();
          if (w.length) resultsEl.insertAdjacentHTML('afterbegin', problem('Partial answer: ' + w.map(warnText).join(' · ')));
          if (rows.length) openChapter(rows[0].osis);
        })
        .catch(function (e) {
          if (token !== searchToken) return;
          rows = [];
          resultsEl.innerHTML = problem('The search could not run: ' + errText(e) +
            ' — this is the search failing, not an absence of passages.');
        });
    }

    function search(q) {
      q = (q || '').trim();
      if (!q) return;
      listeners.search.forEach(function (f) { f(q); });
      try { history.replaceState(null, '', '?q=' + encodeURIComponent(q) + location.hash); } catch (e) { /* preview frames */ }
      return run({ kind: 'query', text: q }, 'SearchPassages', { query: q, limit: 8 },
        'Reading candidate chapters and judging which ones fit — usually 4 to 8 seconds.');
    }

    function openChapter(osis) {
      var row = rows.filter(function (r) { return r.osis === osis; })[0];
      if (row) openRow(row);
    }

    function openRow(row) {
      current = row;
      renderResults();
      var hits = matchedVerses(row);
      var book = row.passage.replace(/\s+\d+$/, ''), chapterNo = Number((row.passage.match(/(\d+)$/) || [])[1]);
      readerEl.innerHTML =
        '<div class="book" data-passage="' + esc(row.passage) + '">' + esc(book) + '</div>' +
        '<h2 class="scripture">' + (chapterNo ? 'Chapter ' + roman(chapterNo) : esc(row.passage)) + '</h2>' +
        '<div class="sub">' + (translation === 'web' ? 'World English Bible' : 'The King James Version') +
        (row.why ? ' · ' + esc(row.why) : ' · shaded verses are the ones the search read') + ' · touch a verse to compare translations</div>' +
        '<div class="fleuron" aria-hidden="true">❦</div>' +
        '<div class="chapter scripture">' + row.verses.map(function (v, i) {
          var cls = [i === 0 ? 'first' : '', hits.indexOf(v.n) >= 0 ? 'match' : ''].filter(Boolean).join(' ');
          /* The first verse opens with the illuminated initial, so its number stays out of the way. */
          return '<p data-ref="' + esc(v.ref) + '" data-n="' + esc(v.n) + '"' + (cls ? ' class="' + cls + '"' : '') + '>' +
            (i === 0 ? '' : '<span class="vn">' + esc(v.n) + '</span>') + sacred(esc(verseText(v))) + '</p>';
        }).join('') + '</div>' +
        '<div class="fleuron" aria-hidden="true">❦</div><h3>People in this chapter</h3><div id="people" class="people"><span class="note">Looking up who is mentioned…</span></div>' +
        '<div id="compare"></div>';
      var first = readerEl.querySelector('p.match');
      if (first) first.scrollIntoView({ block: 'center', behavior: 'smooth' });
      loadPeople(row.passage);
    }

    /* A chapter opened by name — from a Rosary mystery, a saint's chapters — rather than from search results.
       Both stored translations are read (two calls over stored verses, cached), so the toggle costs nothing. */
    function openPassage(passage, o) {
      o = o || {};
      readerEl.innerHTML = '<div class="placeholder scripture">❦<br>Opening ' + esc(passage) + '…</div>';
      if (o.scroll !== false) readerEl.scrollIntoView({ block: 'start', behavior: 'smooth' });
      var cached = passageCache[passage];
      var p = cached ? Promise.resolve(cached) : Promise.all([
        embabel.views.invoke('ReadPassage', { passage: passage, translation: 'kjv' }),
        embabel.views.invoke('ReadPassage', { passage: passage, translation: 'web' }),
      ]).then(function (both) {
        var kjv = rowsOf(both[0]), web = rowsOf(both[1]);
        var byN = {};
        web.forEach(function (r) { byN[r.verse] = r.text; });
        var verses = kjv.map(function (r) { return { n: r.verse, kjv: r.text, web: byN[r.verse], ref: passage + ':' + r.verse }; });
        passageCache[passage] = verses;
        return verses;
      });
      return p.then(function (verses) {
        if (!verses.length) {
          readerEl.innerHTML = problem('No chapter called ' + passage + ' is in this Bible.');
          return;
        }
        openRow({ osis: 'name:' + passage, passage: passage, verses: verses, highlight: o.highlight || [], why: o.why || 'shaded verses are the reading' });
      }).catch(function (e) {
        readerEl.innerHTML = problem('Could not open ' + passage + ': ' + errText(e));
      });
    }

    /* A reference with a verse range ("Luke 1:26-38") opens its chapter with those verses shaded. */
    function openRef(ref, why) {
      var r = parseRef(ref);
      return openPassage(r.passage, { highlight: r.verses, why: why });
    }

    function loadPeople(passage) {
      var el = document.getElementById('people');
      var cached = peopleCache[passage];
      var p = cached ? Promise.resolve(cached) : embabel.views.invoke('PeopleInPassage', { passage: passage }, { state: stateEl })
        .then(function (res) { var packed = { rows: rowsOf(res), warnings: warningsOf(res) }; peopleCache[passage] = packed; return packed; });
      p.then(function (packed) {
        var shown = readerEl.querySelector('[data-passage]');
        if (!document.getElementById('people') || !shown || shown.getAttribute('data-passage') !== passage) return;
        if (!packed.rows.length) {
          el.innerHTML = '<span class="note">Theographic tags no one in this chapter.</span>';
          return;
        }
        el.innerHTML = packed.rows.map(function (r) {
          return '<button class="person-chip" aria-pressed="false" data-verses="' + esc((r.verseNumbers || []).join(',')) + '">' +
            esc(r.person) + '<small>' + esc(r.verses) + (r.verses === 1 ? ' verse' : ' verses') + '</small></button>';
        }).join('') + (packed.warnings.length ? problem('Partial: ' + packed.warnings.map(warnText).join(' · ')) : '');
      }).catch(function (e) {
        if (el) el.innerHTML = problem('Could not look up the people: ' + errText(e));
      });
    }

    function compare(ref, para) {
      readerEl.querySelectorAll('p.picked').forEach(function (p) { p.classList.remove('picked'); });
      para.classList.add('picked');
      var box = document.getElementById('compare');
      box.innerHTML = '<div class="compare"><h3>' + esc(ref) + ' in seven translations</h3><p class="note">Fetching the five older translations…</p></div>';
      var cached = compareCache[ref];
      /* No shared state bar: its generic "Partial result" would announce the expected YLT gap on every Old
         Testament verse, after the panel has already said why. Missing translations are named in the panel. */
      var p = cached ? Promise.resolve(cached) : embabel.views.invoke('CompareTranslations', { ref: ref })
        .then(function (res) { var packed = { rows: rowsOf(res), warnings: warningsOf(res) }; compareCache[ref] = packed; return packed; });
      p.then(function (packed) {
        /* Which translations should be here, named — the envelope's warning says only "PARTIAL", not which
           source fell short, so the rows decide. The YLT gap on an Old Testament verse is expected. */
        var got = packed.rows.map(function (r) { return r.translation; }).join(' | ');
        var nt = NT.test(ref);
        var expected = ['American Standard Version', 'Bible in Basic English', 'Darby', 'Douay-Rheims'].concat(nt ? ["Young's Literal"] : []);
        var missing = expected.filter(function (name) { return got.indexOf(name) < 0; });
        box.innerHTML = '<div class="compare"><h3>' + esc(ref) + ' in ' + packed.rows.length + ' translations</h3>' +
          packed.rows.map(function (r) {
            return '<div class="tr"><div class="name">' + esc(r.translation) + '</div><div class="text scripture">' + sacred(esc(r.text)) + '</div></div>';
          }).join('') +
          (nt ? '' : '<p class="note">Young\'s Literal is New Testament only at its source, so an Old Testament verse has no YLT row.</p>') +
          (missing.length ? problem('Could not be fetched this time: ' + missing.join(', ') + '.') : '') + '</div>';
      }).catch(function (e) {
        box.innerHTML = problem('Could not compare translations: ' + errText(e));
      });
    }

    function setTranslation(t) {
      translation = t;
      ['kjv', 'web'].forEach(function (k) {
        var b = document.getElementById('t-' + k);
        if (b) b.setAttribute('aria-pressed', String(t === k));
      });
      if (rows.length) renderResults();
      if (current) openRow(current);
    }

    /* The page's search box, example chips, translation toggle, result cards and reader — wired once. */
    function wire() {
      var form = document.getElementById('search');
      if (form) form.addEventListener('submit', function (e) { e.preventDefault(); search(document.getElementById('q').value); });
      document.querySelectorAll('[data-example]').forEach(function (b) {
        b.addEventListener('click', function () { var q = b.getAttribute('data-example'); document.getElementById('q').value = q; search(q); });
      });
      ['kjv', 'web'].forEach(function (k) {
        var b = document.getElementById('t-' + k);
        if (b) b.addEventListener('click', function () { setTranslation(k); });
      });
      if (resultsEl) {
        resultsEl.addEventListener('click', function (e) { var c = e.target.closest('.card'); if (c) openChapter(c.getAttribute('data-osis')); });
        resultsEl.addEventListener('keydown', function (e) {
          if (e.key === 'Enter') { var c = e.target.closest('.card'); if (c) openChapter(c.getAttribute('data-osis')); }
        });
      }
      readerEl.addEventListener('click', function (e) {
        var chip = e.target.closest('.person-chip');
        if (chip) {
          var on = chip.getAttribute('aria-pressed') !== 'true';
          readerEl.querySelectorAll('.person-chip').forEach(function (c) { c.setAttribute('aria-pressed', 'false'); });
          readerEl.querySelectorAll('p.person').forEach(function (p) { p.classList.remove('person'); });
          if (on) {
            chip.setAttribute('aria-pressed', 'true');
            var ns = chip.getAttribute('data-verses').split(',');
            readerEl.querySelectorAll('.chapter p').forEach(function (p) {
              if (ns.indexOf(p.getAttribute('data-n')) >= 0) p.classList.add('person');
            });
          }
          return;
        }
        var para = e.target.closest('.chapter p');
        if (para) compare(para.getAttribute('data-ref'), para);
      });
      var close = document.getElementById('close-how');
      if (close) close.addEventListener('click', function (e) {
        e.preventDefault();
        history.replaceState(null, '', location.pathname + location.search);
        document.getElementById('how-it-works').style.display = '';
      });
    }

    return {
      search: search, run: run, openChapter: openChapter, openPassage: openPassage, openRef: openRef,
      setTranslation: setTranslation, wire: wire,
      onSearch: function (f) { listeners.search.push(f); },
      translation: function () { return translation; },
    };
  }

  /* The page's manifest preflight, as one promise: resolves { ok, missing } whatever the runtime version. */
  BibleCore.ready = function () {
    return (window.embabel && embabel.manifest && embabel.manifest.ready) ? embabel.manifest.ready : Promise.resolve({ ok: true });
  };
  BibleCore.util = {
    esc: esc, rowsOf: rowsOf, warningsOf: warningsOf, problem: problem, warnText: warnText, errText: errText,
    sacred: sacred, roman: roman, parseRef: parseRef,
  };
  window.BibleCore = BibleCore;
})();
