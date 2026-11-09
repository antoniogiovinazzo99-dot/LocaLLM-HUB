(function () {
  'use strict';
  var PLATFORMS = ['windows', 'mac'];
  var CAT = { speed: 'Velocita', speculative: 'Speculative', 'quality-tiny': 'Qualita tiny', 'quality-suite-s': 'Suite S', agent: 'Agente', armature: 'Armature', harness: 'Harness', other: 'Altro' };
  var LABEL = { decode_tps_1: 't/s', tps_media: 't/s medi', q_medio: 'tiny', indice_uso: 'indice uso', agente_mini: 'agente', humaneval: 'HumanEval', draft_acceptance_pct: 'accett. %', prompt_tps: 'prompt t/s' };
  var state = { exp: [], ideas: [], proj: [], queue: null, cat: 'all', q: '', tab: 'exp', sort: { k: 'indice_uso', d: -1 }, detail: {} };
  var REPO = 'https://github.com/mtom123/LocaLLM-HUB/blob/main/';

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function fetchJSON(u) {
    return fetch(u, { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
  }
  function fmt(v) {
    if (typeof v === 'number') return Number.isInteger(v) ? String(v) : String(Math.round(v * 10) / 10);
    if (v && typeof v === 'object') return JSON.stringify(v);
    return String(v);
  }
  function modelLine(x) {
    return [x.model, x.quant, x.size_gb ? x.size_gb + ' GB' : null, x.engine].filter(Boolean).join(' · ');
  }

  function load() {
    var jobs = PLATFORMS.map(function (p) {
      return fetchJSON('results/' + p + '/index.json').then(function (d) { return d.experiments || []; }).catch(function () { return []; });
    });
    jobs.push(fetchJSON('data/ideas.json').catch(function () { return []; }));
    jobs.push(fetchJSON('data/projects.json').then(function (d) { return d.projects || []; }).catch(function () { return []; }));
    jobs.push(fetchJSON('data/queue.json').catch(function () { return null; }));
    Promise.all(jobs).then(function (r) {
      state.exp = r[0].concat(r[1]);
      state.ideas = r[2];
      state.proj = r[3];
      state.queue = r[4];
      render();
    });
  }

  function visible(x) {
    if (state.cat !== 'all' && x.category !== state.cat) return false;
    if (state.q) {
      var s = [x.title, x.model, x.quant, x.engine, x.summary, (x.tags || []).join(' ')].join(' ').toLowerCase();
      if (s.indexOf(state.q) < 0) return false;
    }
    return true;
  }

  function renderStats() {
    var s = document.getElementById('stats');
    s.textContent = '';
    var by = { windows: 0, mac: 0 };
    var models = {};
    state.exp.forEach(function (x) { by[x.platform] = (by[x.platform] || 0) + 1; models[x.model] = 1; });
    [[by.windows, 'test Windows'], [by.mac, 'test Mac'], [Object.keys(models).length, 'modelli']].forEach(function (a) {
      var d = el('div', 'stat'); d.appendChild(el('b', null, a[0])); d.appendChild(el('span', null, a[1])); s.appendChild(d);
    });
  }

  function renderChips() {
    var c = document.getElementById('chips');
    c.textContent = '';
    var present = {};
    state.exp.forEach(function (x) { present[x.category] = 1; });
    var cats = ['all'].concat(Object.keys(CAT).filter(function (k) { return present[k]; }));
    cats.forEach(function (k) {
      var b = el('button', 'chip' + (state.cat === k ? ' on' : ''), k === 'all' ? 'Tutte' : CAT[k]);
      b.onclick = function () { state.cat = k; render(); };
      c.appendChild(b);
    });
  }

  function card(x) {
    var c = el('article', 'card');
    var h = el('header');
    var left = el('div');
    var t = el('h3', null, x.title);
    if (x.ref) t.appendChild(el('span', 'st', ' riferimento'));
    left.appendChild(t);
    left.appendChild(el('div', 'meta', modelLine(x) + ' · ' + x.date));
    h.appendChild(left);
    var right = el('div');
    right.appendChild(el('span', 'badge', CAT[x.category] || x.category));
    right.appendChild(el('span', 'st ' + x.status, x.status === 'ok' ? '' : x.status));
    h.appendChild(right);
    c.appendChild(h);
    var p = el('div', 'pills');
    Object.keys(x.headline || {}).forEach(function (k) {
      var s = el('span', 'pill'); s.appendChild(el('b', null, fmt(x.headline[k]))); s.appendChild(document.createTextNode(' ' + (LABEL[k] || k))); p.appendChild(s);
    });
    if (p.childNodes.length) c.appendChild(p);
    c.appendChild(el('p', 'sum', x.summary));
    var d = el('details');
    d.appendChild(el('summary', null, 'Dettagli'));
    var body = el('div', 'detail');
    d.appendChild(body);
    d.addEventListener('toggle', function () { if (d.open && !body.childNodes.length) loadDetail(x, body); });
    c.appendChild(d);
    return c;
  }

  function loadDetail(x, body) {
    body.textContent = 'Carico...';
    fetchJSON(x.file).then(function (e) {
      body.textContent = '';
      var rows = [];
      function add(k, v) { if (v !== undefined && v !== null && v !== '') rows.push([k, v]); }
      add('autore', e.author); add('hardware', e.hardware && Object.keys(e.hardware).map(function (k) { return e.hardware[k]; }).join(', '));
      add('motore', e.engine && [e.engine.name, e.engine.version].filter(Boolean).join(' '));
      add('argomenti', e.engine && (e.engine.args || []).join(' '));
      add('file', e.model && e.model.file); add('repo modello', e.model && e.model.repo);
      add('suite', e.benchmark && [e.benchmark.suite, e.benchmark.version && 'v' + e.benchmark.version, e.benchmark.harness].filter(Boolean).join(' · '));
      var tb = el('table');
      rows.forEach(function (r) { var tr = el('tr'); tr.appendChild(el('td', null, r[0])); tr.appendChild(el('td', null, String(r[1]))); tb.appendChild(tr); });
      body.appendChild(tb);
      var mt = el('table');
      Object.keys(e.metrics || {}).forEach(function (k) { var tr = el('tr'); tr.appendChild(el('td', null, k)); tr.appendChild(el('td', null, fmt(e.metrics[k]))); mt.appendChild(tr); });
      body.appendChild(el('div', 'meta', 'Metriche')); body.appendChild(mt);
      if (e.notes) { body.appendChild(el('div', 'meta', 'Note')); body.appendChild(el('pre', null, e.notes)); }
      var a = el('a', null, 'Apri il file JSON su GitHub');
      a.href = REPO + x.file; a.target = '_blank'; a.rel = 'noopener';
      body.appendChild(a);
    }).catch(function () { body.textContent = 'Dettagli non disponibili.'; });
  }

  function renderExp() {
    PLATFORMS.forEach(function (p) {
      var list = document.getElementById('list-' + p);
      list.textContent = '';
      var xs = state.exp.filter(function (x) { return x.platform === p; });
      var vs = xs.filter(visible);
      vs.forEach(function (x) { list.appendChild(card(x)); });
      if (!vs.length) {
        var e = el('div', 'empty');
        if (!xs.length && p === 'mac') {
          e.appendChild(el('b', null, 'Ancora nessun test dal Mac'));
          e.appendChild(document.createTextNode('Pietro: leggi AGENTS.md, esegui tools/speedtest.py e fai push. Il primo test compare qui.'));
        } else {
          e.appendChild(el('b', null, 'Nessun risultato con questi filtri'));
        }
        list.appendChild(e);
      }
    });
  }

  function best(rows, key) {
    var v = null;
    rows.forEach(function (r) { var m = r.metrics[key]; if (typeof m === 'number' && (v === null || m > v)) v = m; });
    return v;
  }

  // la classifica usa le metriche complete dei file: le leggiamo una volta e le teniamo in memoria
  function renderRank() {
    var t = document.getElementById('rank');
    t.textContent = 'Carico...';
    var need = state.exp.filter(function (x) { return x.status !== 'failed' && !state.detail[x.id]; });
    Promise.all(need.map(function (x) { return fetchJSON(x.file).then(function (e) { state.detail[x.id] = e; }).catch(function () { state.detail[x.id] = { metrics: {} }; }); })).then(drawRank);
  }
  function drawRank() {
    var t = document.getElementById('rank');
    var groups = {};
    state.exp.forEach(function (x) {
      if (x.status === 'failed' || !visible(x)) return;
      var key = x.platform + '|' + x.model + '|' + (x.quant || '');
      (groups[key] = groups[key] || { platform: x.platform, model: x.model, quant: x.quant, size: x.size_gb, rows: [] }).rows.push({ metrics: (state.detail[x.id] || {}).metrics || {} });
    });
    var cols = [['decode_tps_1', 't/s'], ['tps_media', 't/s medi'], ['q_medio', 'tiny'], ['indice_uso', 'indice uso'], ['agente_mini', 'agente %'], ['humaneval', 'HumanEval']];
    var rows = Object.keys(groups).map(function (k) {
      var g = groups[k]; var r = { platform: g.platform, model: g.model + (g.quant ? ' ' + g.quant : ''), size: g.size };
      cols.forEach(function (c) { r[c[0]] = best(g.rows, c[0]); });
      return r;
    });
    var s = state.sort;
    rows.sort(function (a, b) { var x = a[s.k], y = b[s.k]; if (x === null || x === undefined) x = -Infinity; if (y === null || y === undefined) y = -Infinity; if (typeof x === 'string') return s.d * x.localeCompare(y); return s.d * (x - y); });
    t.textContent = '';
    var hr = el('tr');
    [['platform', 'Macchina'], ['model', 'Modello']].concat(cols).concat([['size', 'GB']]).forEach(function (c) {
      var th = el('th', null, c[1] + (s.k === c[0] ? (s.d < 0 ? ' ▼' : ' ▲') : ''));
      th.onclick = function () { state.sort = { k: c[0], d: s.k === c[0] ? -s.d : -1 }; drawRank(); };
      hr.appendChild(th);
    });
    var th = el('thead'); th.appendChild(hr); t.appendChild(th);
    var tb = el('tbody');
    rows.forEach(function (r) {
      var tr = el('tr');
      var td = el('td'); td.appendChild(el('span', 'tag ' + r.platform, r.platform)); tr.appendChild(td);
      tr.appendChild(el('td', null, r.model));
      cols.forEach(function (c) { tr.appendChild(el('td', null, r[c[0]] === null ? '–' : fmt(r[c[0]]))); });
      tr.appendChild(el('td', null, r.size ? fmt(r.size) : '–'));
      tb.appendChild(tr);
    });
    t.appendChild(tb);
  }

  function renderIdeas() {
    var box = document.getElementById('ideas');
    box.textContent = '';
    var g = {};
    state.ideas.forEach(function (i) {
      var s = (i.titolo + ' ' + i.descr + ' ' + i.cat).toLowerCase();
      if (state.q && s.indexOf(state.q) < 0) return;
      (g[i.cat] = g[i.cat] || []).push(i);
    });
    Object.keys(g).forEach(function (k) {
      var grp = el('div', 'idea-group'); grp.appendChild(el('h3', null, k));
      g[k].forEach(function (i) {
        var d = el('div', 'idea'); var r = el('div', 'row');
        r.appendChild(el('b', null, i.titolo)); r.appendChild(el('span', 'badge', i.stato)); d.appendChild(r);
        d.appendChild(el('p', null, i.descr));
        if (i.atteso) d.appendChild(el('p', null, 'Atteso: ' + i.atteso));
        grp.appendChild(d);
      });
      box.appendChild(grp);
    });
    if (!box.childNodes.length) box.appendChild(el('div', 'empty', 'Nessuna idea corrisponde.'));
  }

  var STATUS_ORDER = { attivo: 0, bloccato: 1, provato: 2, idea: 3, chiuso: 4 };
  function renderProj() {
    var box = document.getElementById('proj');
    box.textContent = '';
    var xs = state.proj.filter(function (p) {
      var s = [p.title, p.summary, (p.techniques || []).join(' '), p.owner].join(' ').toLowerCase();
      return !state.q || s.indexOf(state.q) >= 0;
    }).sort(function (a, b) { return (STATUS_ORDER[a.status] || 9) - (STATUS_ORDER[b.status] || 9); });
    var byId = {};
    state.exp.forEach(function (x) { byId[x.id] = x; });
    xs.forEach(function (p) {
      var c = el('article', 'card'); c.style.marginBottom = '10px';
      var h = el('header'); var l = el('div'); l.appendChild(el('h3', null, p.title));
      l.appendChild(el('div', 'meta', p.owner + ' · ' + (p.platform || ''))); h.appendChild(l);
      h.appendChild(el('span', 'badge', p.status)); c.appendChild(h);
      c.appendChild(el('p', 'sum', p.summary));
      if ((p.techniques || []).length) { var t = el('div', 'pills'); p.techniques.forEach(function (x) { t.appendChild(el('span', 'pill', x)); }); c.appendChild(t); }
      if ((p.tests || []).length) {
        var tl = el('div', 'meta', 'Test: ');
        p.tests.forEach(function (id, i) { var x = byId[id]; var a = el('span', null, (x ? x.title : id) + (i < p.tests.length - 1 ? ', ' : '')); tl.appendChild(a); });
        c.appendChild(tl);
      }
      if (p.next) c.appendChild(el('p', 'meta', 'Prossimo passo: ' + p.next));
      (p.links || []).forEach(function (u) { var a = el('a', 'meta', u + '  '); a.href = /^https?:/.test(u) ? u : REPO + u; a.target = '_blank'; a.rel = 'noopener'; a.style.marginRight = '10px'; c.appendChild(a); });
      box.appendChild(c);
    });
    if (!xs.length) box.appendChild(el('div', 'empty', 'Nessun progetto corrisponde.'));
  }

  function renderQueue() {
    var box = document.getElementById('queue');
    box.textContent = '';
    var q = state.queue;
    if (!q || !q.items || !q.items.length) { box.appendChild(el('div', 'empty', 'Coda vuota o non disponibile.')); return; }
    box.appendChild(el('div', 'meta', 'Coda · aggiornata ' + (q.updated || '')));
    q.items.filter(function (i) { return !state.q || (i.name + ' ' + i.kind + ' ' + (i.why || '')).toLowerCase().indexOf(state.q) >= 0; }).forEach(function (i) {
      var d = el('div', 'idea'); var r = el('div', 'row');
      r.appendChild(el('b', null, (i.platform === 'mac' ? 'Mac ' : 'Windows ') + i.order + '. ' + i.name)); r.appendChild(el('span', 'badge', i.kind)); d.appendChild(r);
      if (i.why) d.appendChild(el('p', null, i.why));
      box.appendChild(d);
    });
  }

  function render() {
    renderStats(); renderChips();
    ['exp', 'rank', 'proj', 'queue', 'ideas'].forEach(function (t) { document.getElementById('view-' + t).hidden = state.tab !== t; });
    document.getElementById('chips').hidden = state.tab !== 'exp' && state.tab !== 'rank';
    if (state.tab === 'exp') renderExp();
    if (state.tab === 'rank') renderRank();
    if (state.tab === 'proj') renderProj();
    if (state.tab === 'queue') renderQueue();
    if (state.tab === 'ideas') renderIdeas();
  }

  document.querySelectorAll('.tab').forEach(function (b) {
    b.onclick = function () {
      state.tab = b.dataset.tab;
      document.querySelectorAll('.tab').forEach(function (x) { x.classList.toggle('on', x === b); });
      render();
    };
  });
  document.getElementById('q').addEventListener('input', function (e) { state.q = e.target.value.trim().toLowerCase(); render(); });
  load();
})();
