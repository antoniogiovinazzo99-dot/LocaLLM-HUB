(function () {
  'use strict';

  var PLATFORMS = ['windows', 'mac'];
  var PLAT = {
    windows: { label: 'Windows', sub: 'Tommaso · RTX 3060 12 GB', color: '#22d3ee', dot: 'win' },
    mac: { label: 'Mac', sub: 'Pietro · Apple Silicon', color: '#f59e0b', dot: 'mac' }
  };
  var CAT = { speed: 'Velocità', speculative: 'Speculative', 'quality-tiny': 'Qualità tiny', 'quality-suite-s': 'Suite S', agent: 'Agente', armature: 'Armature', harness: 'Harness', other: 'Altro' };
  var LABEL = { decode_tps_1: 't/s', tps_media: 't/s medi', q_medio: 'tiny', indice_uso: 'suite S', agente: 'agente %', humaneval: 'HumanEval', draft_acceptance_pct: 'accett. %', prompt_tps: 'prompt t/s', duro_pct: 'duro %', agente_pct: 'agente %', harness_omp_pieno_pct: 'omp pieno %', harness_omp_parziale_pct: 'omp parziale %' };
  var COLS = [['qi', 'QI'], ['decode_tps_1', 't/s'], ['duro_pct', 'duro'], ['agente_pct', 'agente'], ['harness_omp_pieno_pct', 'omp'], ['q_medio', 'tiny'], ['indice_uso', 'suite S'], ['size', 'GB'], ['ctx', 'ctx']];
  var REPO = 'https://github.com/mtom123/LocaLLM-HUB/blob/main/';
  var state = {
    exp: [], ideas: [], proj: [], queue: null, cat: 'all', q: '', tab: 'rank', hiddenFailed: 0, detail: {},
    sort: { windows: { k: 'qi', d: -1 }, mac: { k: 'qi', d: -1 } },
    filt: { windows: { model: '', qi: '', tps: '', duro: '', omp: '', gb: '', hard: false }, mac: { model: '', qi: '', tps: '', duro: '', omp: '', gb: '', hard: false } }
  };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function esc(s) { return String(s === undefined || s === null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function fetchJSON(u) { return fetch(u, { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function fmt(v) { if (typeof v === 'number') return Number.isInteger(v) ? String(v) : String(Math.round(v * 10) / 10); if (v && typeof v === 'object') return JSON.stringify(v); return String(v); }
  function modelLine(x) { return [x.model, x.quant, x.size_gb ? x.size_gb + ' GB' : null, x.engine].filter(Boolean).join(' · '); }
  function has(v) { return typeof v === 'number' && isFinite(v); }

  // QI: un numero solo, con la fonte e il livello di affidabilità accanto.
  // rank 0 = duro (set pubblici, il benchmark comune), 1 = omp (harness reale), 2 = suite S, 3 = agente, 4 = tiny (legacy).
  function qiFrom(m) {
    var order = [['duro_pct', 'duro', 0], ['harness_omp_pieno_pct', 'omp', 1], ['indice_uso', 'suite S', 2], ['agente_pct', 'agente', 3], ['agente_mini', 'agente', 3], ['q_medio', 'tiny', 4]];
    for (var i = 0; i < order.length; i++) { if (has(m[order[i][0]])) return { v: m[order[i][0]], src: order[i][1], tier: order[i][2] <= 1 ? 0 : order[i][2] <= 3 ? 1 : 2, rank: order[i][2] }; }
    return null;
  }
  function byQi(a, b, dir) {
    var ra = a.qi ? a.qi.rank : 9, rb = b.qi ? b.qi.rank : 9;
    if (ra !== rb) return ra - rb;
    var x = a.qi ? a.qi.v : -Infinity, y = b.qi ? b.qi.v : -Infinity;
    return (dir || -1) * (x - y);
  }

  function load() {
    var jobs = PLATFORMS.map(function (p) {
      return fetchJSON('results/' + p + '/index.json').then(function (d) { return d; }).catch(function () { return { experiments: [] }; });
    });
    jobs.push(fetchJSON('data/ideas.json').catch(function () { return []; }));
    jobs.push(fetchJSON('data/projects.json').then(function (d) { return d.projects || []; }).catch(function () { return []; }));
    jobs.push(fetchJSON('data/queue.json').catch(function () { return null; }));
    Promise.all(jobs).then(function (r) {
      state.exp = (r[0].experiments || []).concat(r[1].experiments || []);
      state.hiddenFailed = (r[0].hidden_failed || 0) + (r[1].hidden_failed || 0);
      state.ideas = r[2]; state.proj = r[3]; state.queue = r[4];
      render();
    });
  }

  function visible(x) {
    if (x.status === 'failed') return false;
    if (state.cat !== 'all' && x.category !== state.cat) return false;
    if (state.q) {
      var s = [x.title, x.model, x.quant, x.engine, x.summary, (x.tags || []).join(' ')].join(' ').toLowerCase();
      if (s.indexOf(state.q) < 0) return false;
    }
    return true;
  }

  // ---------------------------------------------------------------- KPI + testate
  function renderStats() {
    var box = document.getElementById('stats'); box.textContent = '';
    var best = null, fastest = null, models = {}, qiModels = {};
    state.exp.forEach(function (x) {
      if (x.status === 'failed') return;
      models[x.model] = 1;
      var m = x.headline || {};
      var q = qiFrom(m);
      if (q) {
        qiModels[x.model] = 1;
        if (!best || q.rank < best.rank || (q.rank === best.rank && q.v > best.v)) best = { model: x.model, v: q.v, src: q.src, rank: q.rank, tier: q.tier, plat: x.platform };
      }
      if (has(m.decode_tps_1) && (!fastest || m.decode_tps_1 > fastest.tps)) fastest = { model: x.model, tps: m.decode_tps_1, plat: x.platform };
    });
    var totalModels = Object.keys(models).length, withQi = Object.keys(qiModels).length;
    var kpis = [
      [state.exp.length, 'test validi'],
      [totalModels, 'modelli'],
      [best ? fmt(best.v) + ' · ' + best.src : '—', best ? 'miglior QI · ' + best.model : 'miglior QI'],
      [fastest ? fmt(fastest.tps) + ' t/s' : '—', fastest ? 'top speed · ' + fastest.model : 'top speed'],
      [totalModels ? Math.round(100 * withQi / totalModels) + '%' : '—', 'copertura QI']
    ];
    kpis.forEach(function (k) {
      var d = el('div', 'kpi');
      d.appendChild(el('b', null, k[0]));
      d.appendChild(el('span', null, k[1]));
      box.appendChild(d);
    });
  }

  function renderChips() {
    var c = document.getElementById('chips'); c.textContent = '';
    var present = {};
    state.exp.forEach(function (x) { present[x.category] = 1; });
    var cats = ['all'].concat(Object.keys(CAT).filter(function (k) { return present[k]; }));
    cats.forEach(function (k) {
      var b = el('button', 'chip' + (state.cat === k ? ' on' : ''), k === 'all' ? 'Tutte' : CAT[k]);
      b.onclick = function () { state.cat = k; render(); };
      c.appendChild(b);
    });
  }

  // ---------------------------------------------------------------- righe modello
  // alcuni risultati Mac usano nomi diversi per lo stesso modello: normalizzo per non spaccare la classifica
  function normModel(name) {
    var n = (name || '').toLowerCase();
    if (n.indexOf('onyx-224r') >= 0 || n === 'agents-a1-35b-a3b onyx') return 'Agents-A1 ONYX-224r';
    if (n.indexOf('onyx-mini-pota240') >= 0) return 'Agents-A1 ONYX-mini-240';
    return name;
  }

  function buildRows(plat) {
    var groups = {};
    state.exp.forEach(function (x) {
      if (x.platform !== plat || x.status === 'failed') return;
      var nm = normModel(x.model);
      var isOnyx = /onyx/i.test(nm);
      var key = nm + '|' + (isOnyx ? '' : (x.quant || ''));
      var g = groups[key] || (groups[key] = { model: nm, quant: isOnyx ? '' : x.quant, repo: x.repo, size: x.size_gb, ctx: 0, rows: [] });
      if (!g.repo && x.repo) g.repo = x.repo;
      if (x.ctx) g.ctx = Math.max(g.ctx || 0, x.ctx);
      g.rows.push(x.headline || {});
    });
    var keys = ['decode_tps_1', 'tps_media', 'duro_pct', 'agente_pct', 'harness_omp_pieno_pct', 'harness_omp_parziale_pct', 'q_medio', 'indice_uso', 'humaneval', 'agente_mini'];
    var rows = Object.keys(groups).map(function (k) {
      var g = groups[k], m = {};
      keys.forEach(function (key) {
        var b = null; g.rows.forEach(function (r) { if (has(r[key]) && (b === null || r[key] > b)) b = r[key]; });
        if (b !== null) m[key] = b;
      });
      return { model: g.model, quant: g.quant, repo: g.repo, size: g.size, metrics: m, qi: qiFrom(m), n: g.rows.length, ctx: g.ctx || null };
    });
    // ricerca globale + filtri per parametro
    var f = state.filt[plat];
    var qq = state.q;
    return rows.filter(function (r) {
      var s = (r.model + ' ' + (r.quant || '')).toLowerCase();
      if (qq && s.indexOf(qq) < 0) return false;
      if (f.model && s.indexOf(f.model.toLowerCase()) < 0) return false;
      if (f.qi && (!r.qi || r.qi.v < +f.qi)) return false;
      if (f.tps && !(r.metrics.decode_tps_1 >= +f.tps)) return false;
      if (f.duro && !(r.metrics.duro_pct >= +f.duro)) return false;
      if (f.omp && !(r.metrics.harness_omp_pieno_pct >= +f.omp)) return false;
      if (f.gb && !(r.size <= +f.gb)) return false;
      if (f.hard && (!r.qi || r.qi.tier !== 0)) return false;
      return true;
    });
  }

  function sortRows(rows, plat) {
    var s = state.sort[plat];
    function val(r) { if (s.k === 'qi') return r.qi ? r.qi.v : null; if (s.k === 'size') return r.size; if (s.k === 'ctx') return r.ctx; if (s.k === 'n') return r.n; return has(r.metrics[s.k]) ? r.metrics[s.k] : null; }
    rows.sort(function (a, b) {
      if (s.k === 'qi') return byQi(a, b, s.d);
      var x = val(a), y = val(b);
      if (x === null) x = -Infinity; if (y === null) y = -Infinity;
      if (x === y) return byQi(a, b, -1);
      return s.d * (x - y);
    });
    return rows;
  }

  function qiBadge(r) {
    if (!r.qi) return el('span', 'qbadge none', 'n/d');
    var cls = r.qi.src === 'duro' ? 'hard' : r.qi.src === 'omp' ? 'hard' : r.qi.src === 'tiny' ? 'soft' : 'mid';
    var b = el('span', 'qbadge ' + cls);
    b.appendChild(el('b', null, fmt(r.qi.v)));
    b.appendChild(document.createTextNode(' ' + r.qi.src));
    return b;
  }

  // ---------------------------------------------------------------- pannello piattaforma
  function podium(rows, plat) {
    var top = rows.filter(function (r) { return r.qi; }).sort(function (a, b) { return byQi(a, b, -1); }).slice(0, 3);
    var box = el('div', 'podium');
    top.forEach(function (r, i) {
      var c = el('div', 'pod p' + (i + 1));
      c.appendChild(el('span', 'podrank', '#' + (i + 1) + (r.qi ? (r.qi.tier === 0 ? ' hard' : r.qi.tier === 2 ? ' legacy' : '') : '')));
      c.appendChild(el('b', null, r.model + (r.quant ? ' ' + r.quant : '')));
      c.appendChild(el('div', 'podqi', r.qi ? fmt(r.qi.v) : '—'));
      c.appendChild(el('span', 'podsrc', r.qi ? r.qi.src + ' · ' + fmt(r.metrics.decode_tps_1 || 0) + ' t/s · ' + r.n + ' test' : 'nessun QI'));
      box.appendChild(c);
    });
    if (!top.length) box.appendChild(el('div', 'empty', 'Nessun modello con questi filtri.'));
    return box;
  }

  function barsSvg(rows, color) {
    var top = rows.filter(function (r) { return r.qi; }).sort(function (a, b) { return byQi(a, b, -1); }).slice(0, 8);
    if (!top.length) return el('div', 'empty', 'Nessun QI disponibile.');
    var max = Math.max.apply(null, top.map(function (r) { return r.qi.v; }).concat([1]));
    var W = 460, rowH = 26, H = top.length * rowH + 6, labelW = 212;
    var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" class="chart" role="img" aria-label="QI per modello">';
    top.forEach(function (r, i) {
      var y = i * rowH + 4, w = Math.max(2, (W - labelW - 36) * r.qi.v / max);
      var full = r.model + (r.quant ? ' ' + r.quant : '');
      var name = full.length > 30 ? full.slice(0, 29) + '…' : full;
      s += '<text x="0" y="' + (y + 13) + '" class="clabel">' + esc(name) + '</text>';
      s += '<rect x="' + labelW + '" y="' + y + '" width="' + w + '" height="14" rx="2" fill="' + color + '" opacity="' + (0.9 - i * 0.07) + '"></rect>';
      s += '<text x="' + (labelW + w + 6) + '" y="' + (y + 12) + '" class="cval">' + fmt(r.qi.v) + '</text>';
    });
    s += '</svg>';
    var d = el('div', 'chartbox'); d.innerHTML = s; return d;
  }

  function tableFor(plat) {
    var rows = sortRows(buildRows(plat), plat);
    var t = el('table', 'desk-table');
    var hr = el('tr');
    var s = state.sort[plat];
    [['model', 'Modello'], ['n', 'test'], ['qi', 'QI']].concat(COLS.slice(1)).forEach(function (c) {
      var th = el('th', null, c[1] + (s.k === c[0] ? (s.d < 0 ? ' ▼' : ' ▲') : ''));
      th.onclick = function () { state.sort[plat] = { k: c[0], d: s.k === c[0] ? -s.d : -1 }; refreshTable(plat); };
      hr.appendChild(th);
    });
    var thead = el('thead'); thead.appendChild(hr); t.appendChild(thead);
    var tb = el('tbody', null, null); tb.id = 'tb-' + plat;
    fillTbody(tb, rows, plat);
    t.appendChild(tb);
    return t;
  }

  function fillTbody(tb, rows, plat) {
    tb.textContent = '';
    if (!rows.length) {
      var tr = el('tr'); var td = el('td', 'empty-cell', 'Nessun risultato con questi filtri.'); td.colSpan = 11; tr.appendChild(td); tb.appendChild(tr); return;
    }
    rows.forEach(function (r, i) {
      var tr = el('tr');
      if (i === 0) tr.className = 'top';
      var td = el('td', 'mname');
      if (i === 0) td.appendChild(el('span', 'badge', '1°'));
      td.appendChild(document.createTextNode(' ' + r.model + (r.quant ? ' ' + r.quant : '')));
      tr.appendChild(td);
      tr.appendChild(el('td', 'ncell', String(r.n)));
      var tq = el('td'); tq.appendChild(qiBadge(r)); tr.appendChild(tq);
      [['decode_tps_1'], ['duro_pct'], ['agente_pct'], ['harness_omp_pieno_pct'], ['q_medio'], ['indice_uso']].forEach(function (c) {
        tr.appendChild(el('td', null, has(r.metrics[c[0]]) ? fmt(r.metrics[c[0]]) : '–'));
      });
      tr.appendChild(el('td', null, r.size ? fmt(r.size) : '–'));
      tr.appendChild(el('td', null, r.ctx ? fmt(r.ctx) : '–'));
      tb.appendChild(tr);
    });
  }

  function refreshTable(plat) {
    var tb = document.getElementById('tb-' + plat);
    if (tb) fillTbody(tb, sortRows(buildRows(plat), plat), plat);
  }

  function filtersFor(plat) {
    var box = el('div', 'filters');
    var defs = [['model', 'modello', 'text'], ['qi', 'QI ≥', 'number'], ['tps', 't/s ≥', 'number'], ['duro', 'duro ≥', 'number'], ['omp', 'omp ≥', 'number'], ['gb', 'GB ≤', 'number']];
    defs.forEach(function (d) {
      var wrap = el('label', 'f');
      wrap.appendChild(el('span', null, d[1]));
      var inp = el('input');
      inp.type = d[2]; inp.value = state.filt[plat][d[0]] || '';
      inp.addEventListener('input', function () { state.filt[plat][d[0]] = inp.value.trim(); refreshTable(plat); });
      wrap.appendChild(inp); box.appendChild(wrap);
    });
    var reset = el('button', 'reset', 'reset');
    reset.onclick = function () { Object.keys(state.filt[plat]).forEach(function (k) { state.filt[plat][k] = k === 'hard' ? false : ''; }); renderDesk(); };
    box.appendChild(reset);
    var lab = el('label', 'f hard');
    lab.appendChild(el('span', null, 'solo hard'));
    var cb = el('input'); cb.type = 'checkbox'; cb.checked = !!state.filt[plat].hard;
    cb.addEventListener('change', function () { state.filt[plat].hard = cb.checked; refreshTable(plat); });
    lab.appendChild(cb); box.appendChild(lab);
    return box;
  }

  function panel(plat, rows) {
    var meta = PLAT[plat];
    var box = el('section', 'panel ' + plat);
    var h = el('div', 'panel-head');
    var left = el('div');
    var title = el('h2');
    title.appendChild(el('span', 'dot ' + meta.dot));
    title.appendChild(document.createTextNode(' ' + meta.label));
    left.appendChild(title);
    left.appendChild(el('div', 'meta', meta.sub));
    h.appendChild(left);
    var withQi = rows.filter(function (r) { return r.qi; }).length;
    var cov = el('div', 'coverage');
    cov.appendChild(el('b', null, withQi + '/' + rows.length));
    cov.appendChild(el('span', null, 'con QI'));
    h.appendChild(cov);
    box.appendChild(h);
    box.appendChild(podium(rows, plat));
    box.appendChild(barsSvg(rows, meta.color));
    box.appendChild(filtersFor(plat));
    var tw = el('div', 'tablewrap'); tw.appendChild(tableFor(plat)); box.appendChild(tw);
    return box;
  }

  // ---------------------------------------------------------------- grafico velocità vs QI
  function scatter(all) {
    var pts = [];
    all.forEach(function (rows, i) { rows.forEach(function (r) { if (r.qi && has(r.metrics.decode_tps_1)) pts.push({ r: r, x: r.metrics.decode_tps_1, y: r.qi.v, p: PLATFORMS[i] }); }); });
    var box = el('section', 'panel wide');
    box.appendChild(el('h2', null, 'Velocità × intelligenza'));
    box.appendChild(el('div', 'meta', 'Ogni punto è un modello. In alto a destra = veloce e intelligente. Colore = macchina.'));
    if (!pts.length) { box.appendChild(el('div', 'empty', 'Servono sia t/s sia un QI.')); return box; }
    var W = 760, H = 300, pad = 34;
    var maxX = Math.max.apply(null, pts.map(function (p) { return p.x; }).concat([10]));
    var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" class="chart scatter" role="img" aria-label="Velocità vs QI">';
    for (var g = 0; g <= 4; g++) {
      var y = pad + (H - 2 * pad) * g / 4;
      s += '<line x1="' + pad + '" x2="' + (W - 10) + '" y1="' + y + '" y2="' + y + '" class="grid"></line>';
      s += '<text x="4" y="' + (y + 4) + '" class="tick">' + Math.round(100 - 25 * g) + '</text>';
    }
    for (var gx = 0; gx <= 4; gx++) {
      var x = pad + (W - pad - 12) * gx / 4;
      s += '<text x="' + x + '" y="' + (H - 8) + '" class="tick" text-anchor="middle">' + Math.round(maxX * gx / 4) + '</text>';
    }
    s += '<text x="' + (W / 2) + '" y="' + (H - 1) + '" class="axis" text-anchor="middle">t/s decode</text>';
    pts.sort(function (a, b) { return a.y - b.y; }).forEach(function (p) {
      var cx = pad + (W - pad - 12) * Math.min(1, p.x / maxX);
      var cy = pad + (H - 2 * pad) * (1 - p.y / 100);
      s += '<circle cx="' + cx + '" cy="' + cy + '" r="4.5" fill="' + PLAT[p.p].color + '" opacity=".85"><title>' + esc(p.r.model + ' · ' + fmt(p.y) + ' ' + p.r.qi.src + ' · ' + fmt(p.x) + ' t/s') + '</title></circle>';
    });
    s += '</svg>';
    box.innerHTML += s;
    var leg = el('div', 'legend');
    PLATFORMS.forEach(function (p) { var l = el('span'); l.appendChild(el('i', 'sw ' + p)); l.appendChild(document.createTextNode(' ' + PLAT[p].label)); leg.appendChild(l); });
    box.appendChild(leg);
    return box;
  }

  // ---------------------------------------------------------------- confronto stesso modello
  function bestForRepo(repo, plat, key) {
    var v = null;
    state.exp.forEach(function (x) {
      if (x.repo !== repo || x.platform !== plat || x.status === 'failed') return;
      var m = x.headline || {};
      if (has(m[key]) && (v === null || m[key] > v)) v = m[key];
    });
    return v;
  }

  function comparisonBlock() {
    var byRepo = {};
    state.exp.forEach(function (x) { if (x.repo && x.status !== 'failed') (byRepo[x.repo] = byRepo[x.repo] || {})[x.platform] = 1; });
    var rows = Object.keys(byRepo).filter(function (r) { return byRepo[r].windows && byRepo[r].mac; });
    var box = el('section', 'panel wide');
    box.appendChild(el('h2', null, 'Stesso modello, due macchine'));
    if (!rows.length) {
      box.appendChild(el('div', 'meta', 'Nessun modello misurato su entrambe le macchine con lo stesso benchmark. Prossimo passo: Agents-A1-4B con duro/agente anche su Windows.'));
      return box;
    }
    var t = el('table', 'desk-table');
    var hr = el('tr');
    ['Modello', 'Win duro', 'Win agente', 'Win omp', 'Mac duro', 'Mac agente'].forEach(function (h) { hr.appendChild(el('th', null, h)); });
    var thead = el('thead'); thead.appendChild(hr); t.appendChild(thead);
    var tb = el('tbody');
    rows.forEach(function (r) {
      var tr = el('tr');
      tr.appendChild(el('td', 'mname', r));
      [['windows', 'duro_pct'], ['windows', 'agente_pct'], ['windows', 'harness_omp_pieno_pct'], ['mac', 'duro_pct'], ['mac', 'agente_pct']].forEach(function (c) {
        var v = bestForRepo(r, c[0], c[1]);
        tr.appendChild(el('td', null, v === null ? '–' : fmt(v)));
      });
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    var tw = el('div', 'tablewrap'); tw.appendChild(t); box.appendChild(tw);
    box.appendChild(el('div', 'meta', 'Confronti solo a parità di modello, benchmark e n. Con n=8 il rumore è ±20 punti: guarda la direzione, non il singolo punto.'));
    return box;
  }

  // ---------------------------------------------------------------- desk
  function fmtCtx(n) { if (!n) return '–'; return n >= 1000 ? Math.round(n / 1024) + 'K' : String(n); }

  function coverageMatrix(all) {
    var rows = [];
    all.forEach(function (rs, i) { rs.forEach(function (r) { rows.push({ r: r, plat: PLATFORMS[i] }); }); });
    rows.sort(function (a, b) { return byQi(a.r, b.r, -1); });
    var box = el('section', 'panel wide');
    box.appendChild(el('h2', null, 'Copertura benchmark — tutti i valori'));
    box.appendChild(el('div', 'meta', 'Una riga per modello. “–” = non misurato su quel benchmark. Il ctx è il massimo dichiarato negli argomenti del server.'));
    var tw = el('div', 'tablewrap');
    var t = el('table', 'desk-table cov');
    var hr = el('tr');
    ['Modello', 'Macchina', 'duro', 'agente', 'omp', 'ctx', 'tiny', 'GB'].forEach(function (h) { hr.appendChild(el('th', null, h)); });
    var thead = el('thead'); thead.appendChild(hr); t.appendChild(thead);
    var tb = el('tbody');
    rows.forEach(function (x) {
      var r = x.r, tr = el('tr');
      tr.appendChild(el('td', 'mname', r.model + (r.quant ? ' ' + r.quant : '')));
      tr.appendChild(el('td', null, x.plat));
      var cells = [
        ['duro', has(r.metrics.duro_pct) ? fmt(r.metrics.duro_pct) : null],
        ['agente', has(r.metrics.agente_pct) ? fmt(r.metrics.agente_pct) : has(r.metrics.agente_mini) ? fmt(r.metrics.agente_mini) : null],
        ['omp', has(r.metrics.harness_omp_pieno_pct) ? fmt(r.metrics.harness_omp_pieno_pct) : null],
        ['ctx', r.ctx ? fmtCtx(r.ctx) : null],
        ['tiny', has(r.metrics.q_medio) ? fmt(r.metrics.q_medio) : null]
      ];
      cells.forEach(function (c) {
        var td = el('td', c[1] === null ? 'miss' : 'on', c[1] === null ? '–' : c[1]);
        tr.appendChild(td);
      });
      tr.appendChild(el('td', null, r.size ? fmt(r.size) : '–'));
      tb.appendChild(tr);
    });
    t.appendChild(tb); tw.appendChild(t); box.appendChild(tw);
    return box;
  }

  function renderDesk() {
    var t = document.getElementById('desk');
    var all = PLATFORMS.map(function (p) { return buildRows(p); });
    t.textContent = '';
    var grid = el('div', 'desk-grid');
    PLATFORMS.forEach(function (p, i) { grid.appendChild(panel(p, all[i])); });
    t.appendChild(grid);
    t.appendChild(scatter(all));
    t.appendChild(comparisonBlock());
    t.appendChild(coverageMatrix(all));
    var foot = el('div', 'meta deskfoot');
    foot.textContent = 'QI = duro (set pubblici) → omp (harness reale) → suite S → agente → tiny: si usa il migliore disponibile e la fonte è scritta accanto. Non confrontare QI con fonti diverse. ' + (state.hiddenFailed ? state.hiddenFailed + ' test falliti restano nel repo ma non in dashboard.' : '');
    t.appendChild(foot);
  }

  // ---------------------------------------------------------------- esperimenti
  function card(x) {
    var c = el('article', 'card');
    var h = el('header'); var left = el('div');
    var t = el('h3', null, x.title);
    if (x.ref) t.appendChild(el('span', 'st', ' riferimento'));
    left.appendChild(t); left.appendChild(el('div', 'meta', modelLine(x) + ' · ' + x.date));
    h.appendChild(left);
    var right = el('div');
    right.appendChild(el('span', 'badge', CAT[x.category] || x.category));
    right.appendChild(el('span', 'st ' + x.status, x.status === 'ok' ? '' : x.status));
    h.appendChild(right); c.appendChild(h);
    var p = el('div', 'pills');
    Object.keys(x.headline || {}).forEach(function (k) {
      var s = el('span', 'pill'); s.appendChild(el('b', null, fmt(x.headline[k]))); s.appendChild(document.createTextNode(' ' + (LABEL[k] || k))); p.appendChild(s);
    });
    if (p.childNodes.length) c.appendChild(p);
    c.appendChild(el('p', 'sum', x.summary));
    var d = el('details'); d.appendChild(el('summary', null, 'Dettagli')); var body = el('div', 'detail'); d.appendChild(body);
    d.addEventListener('toggle', function () { if (d.open && !body.childNodes.length) loadDetail(x, body); });
    c.appendChild(d); return c;
  }

  function loadDetail(x, body) {
    body.textContent = 'Carico...';
    fetchJSON(x.file).then(function (e) {
      body.textContent = '';
      var rows = [];
      function add(k, v) { if (v !== undefined && v !== null && v !== '') rows.push([k, v]); }
      add('autore', e.author === 'Motti' ? 'Tommaso' : e.author); add('hardware', e.hardware && Object.keys(e.hardware).map(function (k) { return e.hardware[k]; }).join(', '));
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
      var a = el('a', null, 'Apri il file JSON su GitHub'); a.href = REPO + x.file; a.target = '_blank'; a.rel = 'noopener'; body.appendChild(a);
    }).catch(function () { body.textContent = 'Dettagli non disponibili.'; });
  }

  function renderExp() {
    PLATFORMS.forEach(function (p) {
      var list = document.getElementById('list-' + p); list.textContent = '';
      var xs = state.exp.filter(function (x) { return x.platform === p && x.status !== 'failed'; });
      var vs = xs.filter(visible);
      vs.forEach(function (x) { list.appendChild(card(x)); });
      if (!vs.length) {
        var e = el('div', 'empty');
        e.appendChild(el('b', null, xs.length ? 'Nessun risultato con questi filtri' : 'Nessun test valido'));
        e.appendChild(document.createTextNode(xs.length ? '' : ' I falliti sono registrati nel repo ma non in dashboard.'));
        list.appendChild(e);
      }
    });
  }

  function renderIdeas() {
    var box = document.getElementById('ideas'); box.textContent = '';
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
    var box = document.getElementById('proj'); box.textContent = '';
    var xs = state.proj.filter(function (p) {
      var s = [p.title, p.summary, (p.techniques || []).join(' '), p.owner].join(' ').toLowerCase();
      return !state.q || s.indexOf(state.q) >= 0;
    }).sort(function (a, b) { return (STATUS_ORDER[a.status] || 9) - (STATUS_ORDER[b.status] || 9); });
    var byId = {}; state.exp.forEach(function (x) { byId[x.id] = x; });
    xs.forEach(function (p) {
      var c = el('article', 'card');
      var h = el('header'); var l = el('div'); l.appendChild(el('h3', null, p.title));
      l.appendChild(el('div', 'meta', p.owner + ' · ' + (p.platform || ''))); h.appendChild(l);
      h.appendChild(el('span', 'badge', p.status)); c.appendChild(h);
      c.appendChild(el('p', 'sum', p.summary));
      if ((p.techniques || []).length) { var t = el('div', 'pills'); p.techniques.forEach(function (x) { t.appendChild(el('span', 'pill', x)); }); c.appendChild(t); }
      if ((p.tests || []).length) {
        var tl = el('div', 'meta', 'Test: ');
        p.tests.forEach(function (id, i) { var x = byId[id]; tl.appendChild(el('span', null, (x ? x.title : id) + (i < p.tests.length - 1 ? ', ' : ''))); });
        c.appendChild(tl);
      }
      if (p.next) c.appendChild(el('p', 'meta', 'Prossimo passo: ' + p.next));
      (p.links || []).forEach(function (u) { var a = el('a', 'meta', u + '  '); a.href = /^https?:/.test(u) ? u : REPO + u; a.target = '_blank'; a.rel = 'noopener'; c.appendChild(a); });
      box.appendChild(c);
    });
    if (!xs.length) box.appendChild(el('div', 'empty', 'Nessun progetto corrisponde.'));
  }

  function renderQueue() {
    var box = document.getElementById('queue'); box.textContent = '';
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

  // ---------------------------------------------------------------- render
  function render() {
    renderStats(); renderChips();
    ['exp', 'rank', 'proj', 'queue', 'ideas'].forEach(function (t) { document.getElementById('view-' + t).hidden = state.tab !== t; });
    document.getElementById('chips').hidden = state.tab !== 'exp';
    if (state.tab === 'rank') renderDesk();
    if (state.tab === 'exp') renderExp();
    if (state.tab === 'proj') renderProj();
    if (state.tab === 'queue') renderQueue();
    if (state.tab === 'ideas') renderIdeas();
  }

  function setTab(tab) {
    state.tab = tab;
    document.querySelectorAll('.tab').forEach(function (x) { x.classList.toggle('on', x.dataset.tab === tab); });
    render();
  }

  document.querySelectorAll('.tab').forEach(function (b) { b.onclick = function () { setTab(b.dataset.tab); }; });
  document.getElementById('q').addEventListener('input', function (e) {
    state.q = e.target.value.trim().toLowerCase();
    if (state.tab === 'rank') { var d = document.getElementById('desk'); if (d) d.dataset.loaded = ''; }
    render();
  });
  // chips categoria: utili nella vista Esperimenti; sul desk filtrano per nome via search
  load();
})();
