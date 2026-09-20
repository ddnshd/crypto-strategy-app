/* Crypto Strategy Web App - fixed endpoints + offline-first */
let API_BASE = localStorage.getItem('cs_api_base') || '';
let ONLINE = false;
let LAST_ERROR = '';
let TRIED_URLS = [];
let DEVICE_ID = localStorage.getItem('cs_device_id') || '';
if (!DEVICE_ID) { DEVICE_ID = 'dev-' + Math.random().toString(36).slice(2, 10); localStorage.setItem('cs_device_id', DEVICE_ID); }
const state = { strategies: [], signals: [], scanners: [], prices: {}, activeTab: 'home', lastAI: null };

function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function showLoading() { var el = document.getElementById('loading'); if (el) el.classList.remove('hidden'); }
function hideLoading() { var el = document.getElementById('loading'); if (el) el.classList.add('hidden'); }
function showToast(msg, type) {
  var t = document.getElementById('toast'); if (!t) return;
  t.textContent = msg; t.className = 'toast ' + (type || '');
  setTimeout(function () { t.classList.add('hidden'); }, 2800);
}
function saveCache(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
function loadCache(k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }

function apiCandidates() {
  var list = [];
  try {
    var proto = window.location.protocol, host = window.location.hostname;
    if (proto.indexOf('http') === 0 && host) list.push(proto + '//' + host + ':8001');
  } catch (e) {}
  list.push('http://127.0.0.1:8001');
  list.push('http://localhost:8001');
  list.push('http://10.0.2.2:8001');
  var out = [], seen = {};
  list.forEach(function (u) { if (u && !seen[u]) { seen[u] = 1; out.push(u); } });
  if (API_BASE) out = [API_BASE].concat(out.filter(function (u) { return u !== API_BASE; }));
  return out;
}
async function fetchTimeout(url, opts, ms) {
  ms = ms || 8000;
  var ctl = new AbortController();
  var t = setTimeout(function () { ctl.abort(); }, ms);
  try {
    var r = await fetch(url, Object.assign({}, opts || {}, { signal: ctl.signal }));
    clearTimeout(t); return r;
  } catch (e) { clearTimeout(t); throw e; }
}
async function detectApi() {
  var cands = apiCandidates();
  TRIED_URLS = cands.slice();
  for (var i = 0; i < cands.length; i++) {
    try {
      var r = await fetchTimeout(cands[i] + '/health', {}, 4000);
      if (r.ok) { API_BASE = cands[i]; localStorage.setItem('cs_api_base', API_BASE); LAST_ERROR = ''; return API_BASE; }
      LAST_ERROR = 'HTTP ' + r.status + ' @ ' + cands[i];
    } catch (e) { LAST_ERROR = (e.name === 'AbortError' ? 'timeout' : e.message) + ' @ ' + cands[i]; }
  }
  return API_BASE || cands[0];
}
async function api(path, method, body) {
  method = method || 'GET';
  var opts = { method: method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  var r;
  try { r = await fetchTimeout(API_BASE + path, opts, 90000); }
  catch (e) {
    LAST_ERROR = (e.name === 'AbortError' ? 'timeout 15s' : e.message) + ' @ ' + API_BASE + path;
    throw e;
  }
  var txt = await r.text(), data = null;
  try { data = txt ? JSON.parse(txt) : null; } catch (e) { data = { raw: txt }; }
  if (!r.ok) {
    var msg = (data && data.detail) || ('HTTP ' + r.status);
    LAST_ERROR = (typeof msg === 'string' ? msg : JSON.stringify(msg)) + ' @ ' + API_BASE + path;
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  LAST_ERROR = '';
  return data;
}
function setConn(online) {
  var el = document.getElementById('connection-status');
  var banner = document.getElementById('offline-banner');
  ONLINE = !!online;
  if (el) { el.textContent = online ? '● Online' : '● Offline'; el.className = 'pill ' + (online ? 'online' : 'offline'); }
  if (banner) banner.classList.toggle('hidden', !!online);
}
async function checkConnection() {
  try {
    var r = await fetchTimeout(API_BASE + '/health', {}, 5000);
    if (r.ok) { setConn(true); LAST_ERROR = ''; return true; }
    LAST_ERROR = 'HTTP ' + r.status + ' @ ' + API_BASE + '/health';
  } catch (e) { LAST_ERROR = (e.name === 'AbortError' ? 'timeout' : e.message) + ' @ ' + API_BASE + '/health'; }
  setConn(false); return false;
}
function demoStrategies() {
  return [
    { id: 'demo-rsi', name: 'RSI Mean Reversion (Demo)', pair: 'BTC/USDT', timeframe: '1h', style: 'intraday', description: 'Beli saat RSI<30, jual saat RSI>70. Contoh offline.', definition: { name: 'RSI Demo' }, is_backtested: true, backtest_score: 63.5, _demo: true },
    { id: 'demo-ema', name: 'EMA Cross Trend (Demo)', pair: 'ETH/USDT', timeframe: '4h', style: 'swing', description: 'EMA20 cross di atas EMA50. Contoh offline.', definition: { name: 'EMA Demo' }, is_backtested: false, backtest_score: null, _demo: true }
  ];
}
function demoSignals() {
  var now = new Date().toISOString();
  return [
    { id: 'd1', pair: 'BTC/USDT', direction: 'long', entry_price: 67200, stop_loss: 65800, take_profit: 70000, reason: 'RSI oversold + support EMA (demo)', triggered_at: now, _demo: true },
    { id: 'd2', pair: 'ETH/USDT', direction: 'short', entry_price: 3520, stop_loss: 3610, take_profit: 3380, reason: 'MACD bearish cross (demo)', triggered_at: now, _demo: true },
    { id: 'd3', pair: 'SOL/USDT', direction: 'long', entry_price: 172.4, stop_loss: 165, take_profit: 188, reason: 'Breakout volume (demo)', triggered_at: now, _demo: true }
  ];
}

document.addEventListener('DOMContentLoaded', async function () {
  setupTabs();
  showLoading();
  await detectApi();
  await checkConnection();
  hideLoading();
  await loadHome();
  setInterval(checkConnection, 30000);
});
function setupTabs() {
  document.querySelectorAll('#tab-nav .tab').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('#tab-nav .tab').forEach(function (b) { b.classList.remove('active'); });
      document.querySelectorAll('.tab-content').forEach(function (c) { c.classList.remove('active'); });
      btn.classList.add('active');
      document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
      state.activeTab = btn.dataset.tab;
      loadTab(btn.dataset.tab);
    });
  });
}
async function loadTab(tab) {
  if (tab === 'home') await loadHome();
  else if (tab === 'builder') loadBuilder();
  else if (tab === 'library') await loadLibrary();
  else if (tab === 'backtest') await loadBacktest();
  else if (tab === 'signals') await loadSignals();
  else if (tab === 'settings') await loadSettings();
}
window.loadTab = loadTab;

async function loadHome() {
  var el = document.getElementById('tab-home');
  el.innerHTML = '<div class="card"><h3>⏳ Memuat...</h3><p>Menghubungi backend...</p></div>';
  var strats = [], sigs = [], scans = [], prices = {};
  var ok = await checkConnection();
  if (ok) {
    try {
      var s = await api('/api/v1/strategies?device_id=' + encodeURIComponent(DEVICE_ID));
      strats = Array.isArray(s) ? s : [];
      saveCache('cs_strategies', strats);
    } catch (e) { strats = loadCache('cs_strategies', []); }
    try {
      var g = await api('/api/v1/signals?device_id=' + encodeURIComponent(DEVICE_ID) + '&limit=50');
      sigs = Array.isArray(g) ? g : [];
      saveCache('cs_signals', sigs);
    } catch (e) { sigs = loadCache('cs_signals', []); }
    try {
      var sc = await api('/api/v1/scanners?device_id=' + encodeURIComponent(DEVICE_ID));
      scans = Array.isArray(sc) ? sc : [];
      saveCache('cs_scanners', scans);
    } catch (e) { scans = loadCache('cs_scanners', []); }
    for (var i = 0; i < ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'].length; i++) {
      var p = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'][i];
      try { var pr = await api('/api/v1/market/price/' + p); prices[p] = pr.price; } catch (e) {}
    }
  } else {
    strats = loadCache('cs_strategies', []);
    sigs = loadCache('cs_signals', []);
    scans = loadCache('cs_scanners', []);
    if (!strats.length && !sigs.length) { strats = demoStrategies(); sigs = demoSignals(); }
  }
  state.strategies = strats; state.signals = sigs; state.scanners = scans; state.prices = prices;
  var tested = strats.filter(function (s) { return s.is_backtested; }).length;
  var avg = 0, n = 0;
  strats.forEach(function (s) { if (s.backtest_score != null) { avg += s.backtest_score; n++; } });
  avg = n ? (avg / n).toFixed(1) : '-';
  var priceHtml = Object.keys(prices).length
    ? Object.keys(prices).map(function (k) { return '<div class="stat"><b>$' + Number(prices[k]).toLocaleString() + '</b><span>' + esc(k) + '</span></div>'; }).join('')
    : '<div class="stat"><b>-</b><span>Harga live perlu backend</span></div>';
  el.innerHTML =
    (!ok ? backendCardHTML(false) : '') +
    '<div class="card hero"><h3>⚡ Selamat datang</h3>' +
    '<div class="big">' + strats.length + ' strategi</div>' +
    '<p>Device: ' + esc(DEVICE_ID) + ' • Backend: ' + esc(API_BASE || 'belum ketemu') + '</p>' +
    '<div class="stat-row">' +
    '<div class="stat"><b>' + tested + '</b><span>Backtested</span></div>' +
    '<div class="stat"><b>' + avg + '</b><span>Avg skor</span></div>' +
    '<div class="stat"><b>' + sigs.length + '</b><span>Signals</span></div>' +
    '</div></div>' +
    '<div class="section-title">💹 Harga pasar</div>' +
    '<div class="stat-row">' + priceHtml + '</div>' +
    '<div class="card"><h3>🚀 Aksi cepat</h3>' +
    '<div class="btn-row"><button class="btn btn-primary" onclick="goTab(\'builder\')">🤖 Builder</button>' +
    '<button class="btn btn-secondary" onclick="goTab(\'signals\')">🔔 Signals</button></div>' +
    '<div class="btn-row"><button class="btn btn-secondary" onclick="goTab(\'backtest\')">📊 Backtest</button>' +
    '<button class="btn btn-secondary" onclick="goTab(\'library\')">📚 Library</button></div>' +
    '<p class="hint mt-1">Jika tombol Scanner meminta backtest dulu dan skor ≥ 50, jalankan backtest dari halaman Backtest.</p></div>';
}
window.goTab = function (t) {
  var b = document.querySelector('#tab-nav .tab[data-tab="' + t + '"]');
  if (b) b.click();
};

function loadBuilder() {
  var el = document.getElementById('tab-builder');
  el.innerHTML =
    '<div class="card accent"><h3>🤖 AI Strategy Builder</h3><p>Jelaskan strategi dengan bahasa santai. AI akan menyusun definisi + penjelasan.</p>' +
    '<label class="label">Deskripsi strategi</label>' +
    '<textarea id="builder-input" placeholder="cth: beli BTC saat RSI di bawah 30 di timeframe 1h, TP 2%, SL 1%"></textarea>' +
    '<div class="grid-2">' +
    '<div><label class="label">Style</label><select id="builder-style"><option value="scalp">Scalp</option><option value="intraday" selected>Intraday</option><option value="swing">Swing</option><option value="position">Position</option></select></div>' +
    '<div><label class="label">Pair</label><select id="builder-pair"><option>BTC/USDT</option><option>ETH/USDT</option><option>SOL/USDT</option></select></div>' +
    '</div>' +
    '<label class="label">Timeframe</label><select id="builder-tf"><option value="15m">15m</option><option value="1h" selected>1h</option><option value="4h">4h</option><option value="1d">1d</option></select>' +
    '<button class="btn btn-primary" onclick="buildStrategy()">🚀 Generate dengan AI</button>' +
    '<p class="hint mt-1">Butuh backend + AI online. Kunci & model diatur di tab ⚙️ AI. Saat offline, hasil tidak bisa di-generate (data lokal tetap bisa dibuka).</p></div>' +
    '<div id="builder-result"></div>';
}
window.buildStrategy = async function () {
  var desc = (document.getElementById('builder-input').value || '').trim();
  if (!desc) { showToast('Tulis deskripsi dulu', 'error'); return; }
  var ok = ONLINE || await checkConnection();
  if (!ok) {
    for (var i = 0; i < apiCandidates().length && !ok; i++) {
      try {
        var r = await fetchTimeout(apiCandidates()[i] + '/health', {}, 4000);
        if (r.ok) { API_BASE = apiCandidates()[i]; ok = true; ONLINE = true; setConn(true); }
      } catch (e) {}
    }
  }
  if (!ok) { showToast('Offline — AI butuh backend online', 'error'); return; }
  showLoading();
  try {
    var res = await api('/api/v1/strategies/generate', 'POST', { user_input: desc, device_id: DEVICE_ID });
    state.lastAI = res;
    var st = res.strategy || {};
    var r = document.getElementById('builder-result');
    r.innerHTML = '<div class="card good"><h3>✅ Draf strategi jadi</h3>' +
      '<div class="kv"><span>Nama</span><b>' + esc(st.name || '-') + '</b></div>' +
      '<div class="kv"><span>Pair / TF</span><b>' + esc(st.pair || '-') + ' / ' + esc(st.timeframe || '-') + '</b></div>' +
      '<p class="mt-1">' + esc(res.explanation || '') + '</p>' +
      '<div class="chips">' + (res.suggestions || []).map(function (s) { return '<span class="chip">💡 ' + esc(s) + '</span>'; }).join('') + '</div>' +
      '<div class="chips">' + (res.warnings || []).map(function (s) { return '<span class="chip">⚠️ ' + esc(s) + '</span>'; }).join('') + '</div>' +
      '<pre class="json">' + esc(JSON.stringify(st, null, 2)) + '</pre>' +
      '<label class="label">Nama simpan</label><input class="input" id="save-name" value="' + esc(st.name || 'Strategi baruku') + '">' +
      '<button class="btn btn-primary" onclick="saveAIStrategy()">💾 Simpan ke Library</button></div>';
    showToast('AI selesai', 'success');
  } catch (e) {
    showToast('Gagal: ' + e.message, 'error');
    var r = document.getElementById('builder-result');
    if (r) r.innerHTML = '<div class="card warn"><h3>❌ Generate gagal</h3><p>' + esc(e.message) + '</p>' +
      '<p class="hint">Pastikan backend + AI online. Error: ' + esc(LAST_ERROR || '-') + '</p>' +
      '<div class="btn-row"><button class="btn btn-secondary" onclick="buildStrategy()">🔄 Coba lagi</button></div></div>';
  }
  hideLoading();
};
window.saveAIStrategy = async function () {
  if (!state.lastAI) return;
  var st = state.lastAI.strategy || {};
  var name = (document.getElementById('save-name').value || st.name || 'Strategi').trim();
  var pair = (document.getElementById('builder-pair').value || st.pair || 'BTC/USDT');
  var tf = (document.getElementById('builder-tf').value || st.timeframe || '1h');
  var style = (document.getElementById('builder-style').value || st.style || 'intraday');
  showLoading();
  try {
    var saved = await api('/api/v1/strategies', 'POST', {
      name: name, description: state.lastAI.explanation || '', style: style,
      pair: pair, timeframe: tf, definition: Object.assign({}, st, { name: name, pair: pair, timeframe: tf, style: style }),
      device_id: DEVICE_ID
    });
    showToast('Tersimpan!', 'success');
    await loadLibrary();
    goTab('library');
  } catch (e) { showToast('Gagal simpan: ' + e.message, 'error'); }
  hideLoading();
};

async function loadLibrary() {
  var el = document.getElementById('tab-library');
  el.innerHTML = '<div class="card"><h3>⏳ Memuat library...</h3></div>';
  var data = [];
  if (await checkConnection()) {
    try {
      var s = await api('/api/v1/strategies?device_id=' + encodeURIComponent(DEVICE_ID));
      data = Array.isArray(s) ? s : [];
      saveCache('cs_strategies', data);
    } catch (e) { data = loadCache('cs_strategies', []); showToast('Gagal load: ' + e.message, 'error'); }
  } else {
    data = loadCache('cs_strategies', []);
    if (!data.length) data = demoStrategies();
  }
  state.strategies = data;
  if (!data.length) {
    el.innerHTML = '<div class="empty-state"><div class="icon">📚</div><p>Belum ada strategi.<br>Buat dari Builder.</p><div class="btn-row" style="max-width:280px;margin:14px auto 0"><button class="btn btn-primary" onclick="goTab(\'builder\')">+ Buat</button></div></div>';
    return;
  }
  el.innerHTML = '<div class="flex-between mb-1"><h2 class="section-title">📚 Library (' + data.length + ')</h2>' +
    '<button class="btn btn-sm btn-primary" onclick="goTab(\'builder\')">+ Baru</button></div>' +
    data.map(function (s) {
      var sc = s.backtest_score;
      var cls = sc == null ? '' : (sc >= 60 ? '' : (sc >= 50 ? 'mid' : 'low'));
      return '<div class="strategy-card" onclick="showDetail(\'' + s.id + '\')">' +
        '<div class="flex-between"><span class="name">' + esc(s.name || 'Strategi') + (s._demo ? ' <span class="chip">demo</span>' : '') + '</span>' +
        '<span class="score ' + cls + '">' + (sc == null ? '--' : Number(sc).toFixed(1)) + '</span></div>' +
        '<div class="meta">' + esc(s.pair || '-') + ' • ' + esc(s.timeframe || '-') + ' • ' + esc(s.style || '-') + (s.is_backtested ? ' • ✅ tested' : '') + '</div></div>';
    }).join('');
}
window.loadLibrary = loadLibrary;

window.showDetail = async function (id) {
  var el = document.getElementById('tab-library');
  var local = (state.strategies || []).find(function (x) { return x.id === id; });
  if (local && local._demo) {
    el.innerHTML = '<div class="card"><div class="flex-between"><h3>' + esc(local.name) + '</h3>' +
      '<button class="btn btn-sm btn-secondary" onclick="loadLibrary()">← Kembali</button></div>' +
      '<p>' + esc(local.description || '') + '</p>' +
      '<div class="kv"><span>Pair</span><b>' + esc(local.pair) + '</b></div>' +
      '<div class="kv"><span>Timeframe</span><b>' + esc(local.timeframe) + '</b></div>' +
      '<p class="hint mt-1">Ini data demo offline. Sambungkan backend untuk detail penuh, backtest, dan scanner.</p></div>';
    return;
  }
  showLoading();
  try {
    var d = await api('/api/v1/strategies/' + id);
    var vers = [];
    try { vers = await api('/api/v1/strategies/' + id + '/versions'); } catch (e) {}
    var sc = d.backtest_score;
    var color = sc == null ? '#9aa0c7' : (sc >= 60 ? '#22dd88' : (sc >= 50 ? '#ffb020' : '#ff5b6e'));
    el.innerHTML = '<div class="card"><div class="flex-between"><h3>' + esc(d.name) + '</h3>' +
      '<button class="btn btn-sm btn-secondary" onclick="loadLibrary()">← Kembali</button></div>' +
      '<p>' + esc(d.description || '-') + '</p>' +
      '<div class="kv"><span>Pair</span><b>' + esc(d.pair) + '</b></div>' +
      '<div class="kv"><span>Timeframe</span><b>' + esc(d.timeframe) + '</b></div>' +
      '<div class="kv"><span>Style</span><b>' + esc(d.style) + '</b></div>' +
      '<div class="kv"><span>Status</span><b>' + (d.is_backtested ? '✅ backtested' : '⬜ belum backtest') + ' • skor ' + (sc == null ? '-' : Number(sc).toFixed(1)) + '</b></div>' +
      '<div class="score-bar"><div class="score-bar-fill" style="width:' + (sc || 0) + '%;background:' + color + '"></div></div>' +
      '<pre class="json">' + esc(JSON.stringify(d.definition || {}, null, 2)) + '</pre>' +
      '<div class="btn-row"><button class="btn btn-primary" onclick="goBacktest(\'' + d.id + '\')">📊 Backtest</button>' +
      '<button class="btn btn-secondary" onclick="activateScanner(\'' + d.id + '\')">📡 Scanner</button></div>' +
      '<div class="btn-row"><button class="btn btn-secondary" onclick="duplicateStrategy(\'' + d.id + '\')">⧉ Duplikat</button>' +
      '<button class="btn btn-danger" onclick="deleteStrategy(\'' + d.id + '\')">🗑 Hapus</button></div>' +
      (vers && vers.length ? '<p class="hint mt-1">Versi: ' + vers.map(function (v) { return 'v' + v.version; }).join(', ') + '</p>' : '') +
      '</div>';
  } catch (e) { showToast('Gagal: ' + e.message, 'error'); }
  hideLoading();
};
window.deleteStrategy = async function (id) {
  if (!confirm('Hapus strategi ini?')) return;
  showLoading();
  try { await api('/api/v1/strategies/' + id, 'DELETE'); showToast('Dihapus', 'success'); await loadLibrary(); }
  catch (e) { showToast('Gagal: ' + e.message, 'error'); }
  hideLoading();
};
window.duplicateStrategy = async function (id) {
  showLoading();
  try {
    await api('/api/v1/strategies/' + id + '/duplicate?device_id=' + encodeURIComponent(DEVICE_ID), 'POST');
    showToast('Diduplikat!', 'success'); await loadLibrary();
  } catch (e) { showToast('Gagal: ' + e.message, 'error'); }
  hideLoading();
};
window.activateScanner = async function (id) {
  showLoading();
  try {
    await api('/api/v1/scanners/activate', 'POST', { strategy_id: id, device_id: DEVICE_ID });
    showToast('Scanner aktif!', 'success');
  } catch (e) { showToast('Gagal: ' + e.message, 'error'); }
  hideLoading();
};
window.goBacktest = function (id) {
  goTab('backtest');
  setTimeout(function () { var i = document.getElementById('bt-id'); if (i) i.value = id; }, 300);
};

async function loadBacktest() {
  var el = document.getElementById('tab-backtest');
  var opts = (state.strategies || []).map(function (s) { return '<option value="' + s.id + '">' + esc(s.name) + '</option>'; }).join('');
  if (!opts) {
    try {
      var s = await api('/api/v1/strategies?device_id=' + encodeURIComponent(DEVICE_ID));
      state.strategies = Array.isArray(s) ? s : [];
      opts = state.strategies.map(function (x) { return '<option value="' + x.id + '">' + esc(x.name) + '</option>'; }).join('');
    } catch (e) {}
  }
  el.innerHTML = '<div class="card accent"><h3>📊 Backtest Engine</h3>' +
    '<label class="label">Strategi</label><select id="bt-id">' + (opts || '<option value="">-- kosong --</option>') + '</select>' +
    '<div class="grid-2"><div><label class="label">Pair</label><select id="bt-pair"><option>BTC/USDT</option><option>ETH/USDT</option><option>SOL/USDT</option></select></div>' +
    '<div><label class="label">Timeframe</label><select id="bt-tf"><option value="15m">15m</option><option value="1h" selected>1h</option><option value="4h">4h</option><option value="1d">1d</option></select></div></div>' +
    '<div class="grid-2"><div><label class="label">Jangka Waktu</label><select id="bt-period"><option value="1m">1 Bulan</option><option value="3m">3 Bulan</option><option value="6m">6 Bulan</option><option value="1y" selected>1 Tahun</option><option value="2y">2 Tahun</option></select></div>' +
    '<div></div></div>' +
    '<button class="btn btn-primary" onclick="runBacktest()">▶ Jalankan Backtest</button></div>' +
    '<div id="backtest-result"></div>' +
    '<div class="card"><h3>📜 Riwayat</h3><div id="bt-history"><p class="hint">Pilih strategi lalu jalankan, atau lihat riwayat.</p></div></div>';
  var sel = document.getElementById('bt-id');
  if (sel && sel.value) loadHistory(sel.value);
  if (sel) sel.onchange = function () { loadHistory(sel.value); };
}
window.loadBacktest = loadBacktest;
async function loadHistory(sid) {
  var h = document.getElementById('bt-history');
  if (!h || !sid) return;
  try {
    var list = await api('/api/v1/backtest/strategy/' + sid);
    if (!list || !list.length) { h.innerHTML = '<p class="hint">Belum ada hasil backtest.</p>'; return; }
    h.innerHTML = list.slice(0, 5).map(function (b) {
      var wr = Number(b.win_rate || 0) * 100;
      return '<div class="kv"><span>' + esc((b.created_at || '').slice(0, 10)) + ' • ' + b.total_trades + ' trades</span><b>WR ' + wr.toFixed(1) + '% • skor ' + Number(b.score).toFixed(1) + '</b></div>';
    }).join('') + '<button class="btn btn-sm btn-secondary mt-1" onclick="showBacktest(\'' + list[0].id + '\')">Lihat hasil terbaru</button>';
  } catch (e) { h.innerHTML = '<p class="hint">Offline / gagal load riwayat.</p>'; }
}
window.runBacktest = async function (presetId) {
  var sid = presetId || (document.getElementById('bt-id') || {}).value;
  if (!sid) { showToast('Pilih strategi dulu', 'error'); return; }
  var ok = ONLINE || await checkConnection();
  if (!ok) {
    for (var i = 0; i < apiCandidates().length && !ok; i++) {
      try {
        var r = await fetchTimeout(apiCandidates()[i] + '/health', {}, 4000);
        if (r.ok) { API_BASE = apiCandidates()[i]; ok = true; ONLINE = true; setConn(true); }
      } catch (e) {}
    }
  }
  if (!ok) { showToast('Offline — backtest butuh backend', 'error'); return; }
  var pair = (document.getElementById('bt-pair') || {}).value || 'BTC/USDT';
  var tf = (document.getElementById('bt-tf') || {}).value || '1h';
  var period = (document.getElementById('bt-period') || {}).value || '1y';
  showLoading();
  var resEl = document.getElementById('backtest-result');
  if (resEl) resEl.innerHTML = '<div class="card"><h3>⏳ Backtest berjalan...</h3><p>Fetching data + simulasi. Biasanya 10-30 detik.</p><div id="bt-progress" class="hint">Memulai...</div></div>';
  try {
    var start = await api('/api/v1/backtest/run', 'POST', { strategy_id: sid, pair: pair, timeframe: tf, period: period });
    var bid = start.backtest_id;
    var res = null;
    for (var i = 0; i < 60; i++) {
      await new Promise(function (r) { setTimeout(r, 2000); });
      var prog = document.getElementById('bt-progress');
      if (prog) prog.textContent = 'Polling... (' + (i + 1) + '/60)';
      try {
        res = await api('/api/v1/backtest/' + bid);
        if (res && res.status === 'failed') {
          if (resEl) resEl.innerHTML = '<div class="card warn"><h3>❌ Backtest gagal</h3><p>' + esc(res.error || 'Unknown error') + '</p>' +
            '<div class="btn-row"><button class="btn btn-secondary" onclick="runBacktest(\'' + sid + '\')">🔄 Coba lagi</button></div></div>';
          showToast('Backtest gagal: ' + (res.error || 'error'), 'error');
          hideLoading();
          return;
        }
        if (res && res.status === 'running') continue;
        if (res && res.id && res.total_trades !== undefined) break;
      } catch (e) {}
    }
    if (res && res.id && res.total_trades !== undefined) showBacktestData(res);
    else {
      if (resEl) resEl.innerHTML = '<div class="card warn"><h3>⏱ Timeout</h3><p>Backtest butuh waktu lebih lama dari biasanya.</p>' +
        '<p class="hint">Coba gunakan pair yang lebih likuid (BTC/USDT) atau timeframe lebih besar (4h/1d).</p>' +
        '<div class="btn-row"><button class="btn btn-secondary" onclick="runBacktest(\'' + sid + '\')">🔄 Coba lagi</button></div></div>';
      showToast('Timeout — coba lagi nanti', 'error');
    }
  } catch (e) {
    showToast('Gagal: ' + e.message, 'error');
    if (resEl) resEl.innerHTML = '<div class="card warn"><h3>❌ Error</h3><p>' + esc(e.message) + '</p></div>';
  }
  hideLoading();
};
window.showBacktest = async function (bid) {
  showLoading();
  try { var res = await api('/api/v1/backtest/' + bid); showBacktestData(res); }
  catch (e) { showToast('Gagal: ' + e.message, 'error'); }
  hideLoading();
};
function showBacktestData(res) {
  var r = document.getElementById('backtest-result');
  if (!r) return;
  var wr = Number(res.win_rate || 0) * 100;
  var ret = Number(res.total_return || 0) * 100;
  var dd = Number(res.max_drawdown || 0) * 100;
  var dir = res.direction || 'long';
  var dirLabel = dir === 'short' ? '📉 SHORT' : '📈 LONG';
  var commission = res.total_commission || 0;
  var h = '<div class="card good"><h3>📊 Hasil Backtest</h3>' +
    '<div class="kv"><span>Direction</span><b>' + dirLabel + '</b></div>' +
    '<div class="kv"><span>Periode</span><b>' + esc(res.start_date || '?') + ' → ' + esc(res.end_date || '?') + '</b></div>' +
    '<div class="grid-2">' +
    '<div class="stat"><b>' + res.total_trades + '</b><span>Trades</span></div>' +
    '<div class="stat"><b>' + wr.toFixed(1) + '%</b><span>Win rate</span></div>' +
    '<div class="stat"><b>' + Number(res.profit_factor || 0).toFixed(2) + '</b><span>Profit factor</span></div>' +
    '<div class="stat"><b>' + Number(res.score || 0).toFixed(1) + '</b><span>Skor</span></div>' +
    '<div class="stat"><b>' + (ret >= 0 ? '+' : '') + ret.toFixed(1) + '%</b><span>Return</span></div>' +
    '<div class="stat"><b>' + dd.toFixed(1) + '%</b><span>Max DD</span></div>' +
    '</div>' +
    '<div class="grid-2">' +
    '<div class="stat"><b>' + Number(res.sharpe_ratio || 0).toFixed(2) + '</b><span>Sharpe</span></div>' +
    '<div class="stat"><b>' + Number(res.avg_rr || 0).toFixed(2) + '</b><span>Avg R:R</span></div>' +
    '<div class="stat"><b>$' + commission.toFixed(2) + '</b><span>Commission</span></div>' +
    '<div class="stat"><b>' + (res.winning_trades || 0) + '/' + (res.losing_trades || 0) + '</b><span>Win/Loss</span></div>' +
    '</div>' +
    '<canvas class="chart" id="eqchart" width="400" height="120"></canvas>';
  if (res.error) h += '<p class="hint mt-1">⚠️ Catatan: ' + esc(res.error) + '</p>';
  h += '<p class="hint mt-1">' + (res.is_qualified ? '✅ Lolos kualifikasi (skor ≥ 50). Bisa aktifkan scanner.' : '⚠️ Belum lolos (skor < 50).') + '</p></div>';
  if (res.walk_forward) {
    var wf = res.walk_forward;
    h += '<div class="card"><h3>🔀 Walk-Forward Analysis</h3>';
    if (wf.in_sample && wf.out_of_sample) {
      h += '<div class="grid-2">' +
        '<div class="kv"><span>In-sample</span><b>WR ' + Number(wf.in_sample.win_rate * 100).toFixed(1) + '% • PF ' + Number(wf.in_sample.profit_factor).toFixed(2) + ' • skor ' + Number(wf.in_sample.avg_score || 0).toFixed(1) + '</b></div>' +
        '<div class="kv"><span>Out-of-sample</span><b>WR ' + Number(wf.out_of_sample.win_rate * 100).toFixed(1) + '% • PF ' + Number(wf.out_of_sample.profit_factor).toFixed(2) + ' • skor ' + Number(wf.out_of_sample.avg_score || 0).toFixed(1) + '</b></div>' +
        '</div>';
      var deg = Number(wf.degradation_pct || 0);
      var degColor = deg < 10 ? '#22dd88' : (deg < 25 ? '#ffb020' : '#ff5b6e');
      h += '<p class="hint">Degradasi: <span style="color:' + degColor + '">' + deg.toFixed(1) + '%</span> ' +
        (deg < 10 ? '✅ Konsisten' : (deg < 25 ? '⚠️ Sedikit overfit' : '❌ Overfitting')) + '</p>';
    }
    if (wf.folds && wf.folds.length) {
      h += '<details class="mt-1"><summary class="hint">Detail ' + wf.folds.length + ' folds</summary>';
      wf.folds.forEach(function (f, idx) {
        h += '<div class="kv"><span>Fold ' + (idx + 1) + ' (' + esc(f.period || '') + ')</span>' +
          '<b>WR ' + Number(f.win_rate * 100).toFixed(1) + '% • ' + f.total_trades + ' trades • skor ' + Number(f.score || 0).toFixed(1) + '</b></div>';
      });
      h += '</details>';
    }
    h += '</div>';
  }
  r.innerHTML = h;
  drawEquity(res.equity_curve || []);
}
function drawEquity(curve) {
  var c = document.getElementById('eqchart');
  if (!c || !curve.length) return;
  var ctx = c.getContext('2d');
  var vals = curve.map(function (p) { return Number(p.equity || p.value || 0); }).filter(function (v) { return isFinite(v); });
  if (!vals.length) return;
  var min = Math.min.apply(null, vals), max = Math.max.apply(null, vals);
  if (max === min) max = min + 1;
  ctx.clearRect(0, 0, c.width, c.height);
  ctx.beginPath();
  vals.forEach(function (v, i) {
    var x = (i / (vals.length - 1)) * (c.width - 16) + 8;
    var y = c.height - 12 - ((v - min) / (max - min)) * (c.height - 28);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = '#5b5bff'; ctx.lineWidth = 3; ctx.stroke();
}

async function loadSignals() {
  var el = document.getElementById('tab-signals');
  el.innerHTML = '<div class="card"><h3>⏳ Memuat signals...</h3></div>';
  var data = [];
  if (await checkConnection()) {
    try {
      var g = await api('/api/v1/signals?device_id=' + encodeURIComponent(DEVICE_ID) + '&limit=50');
      data = Array.isArray(g) ? g : [];
      saveCache('cs_signals', data);
    } catch (e) { data = loadCache('cs_signals', []); }
  } else {
    data = loadCache('cs_signals', []);
    if (!data.length) data = demoSignals();
  }
  state.signals = data;
  if (!data.length) {
    el.innerHTML = '<div class="empty-state"><div class="icon">🔔</div><p>Belum ada sinyal.<br>Aktifkan scanner pada strategi yang sudah backtest.</p></div>';
    return;
  }
  el.innerHTML = '<div class="flex-between mb-1"><h2 class="section-title">🔔 Signals (' + data.length + ')' + (ONLINE ? '' : ' <span class="chip">offline</span>') + '</h2>' +
    '<button class="btn btn-sm btn-primary" onclick="loadSignals()">🔄 Refresh</button></div>' +
    data.map(function (s) {
      var dir = (s.direction || 'hold').toLowerCase();
      var cls = dir === 'long' || dir === 'buy' ? 'buy' : (dir === 'short' || dir === 'sell' ? 'sell' : '');
      return '<div class="signal-item ' + cls + '">' +
        '<div class="flex-between"><span class="pair">' + esc(s.pair || '-') + '</span>' +
        '<span class="chip">' + esc(s.strategy_name || '') + '</span></div>' +
        '<p class="mt-1"><b class="' + (cls === 'buy' ? 'text-green' : (cls === 'sell' ? 'text-red' : 'text-yellow')) + '">' + esc(String(s.direction || '').toUpperCase()) + '</b>' +
        ' @ ' + esc(s.entry_price != null ? s.entry_price : '-') + '</p>' +
        '<p class="hint">SL ' + esc(s.stop_loss != null ? s.stop_loss : '-') + ' • TP ' + esc(s.take_profit != null ? s.take_profit : '-') + '</p>' +
        '<p class="hint">' + esc(s.reason || '') + '</p></div>';
    }).join('');
}
window.loadSignals = loadSignals;

function hasBridge() {
  try { return typeof window.AndroidBackend !== 'undefined' && window.AndroidBackend !== null; }
  catch (e) { return false; }
}
function backendCmdText() {
  try { if (hasBridge()) return window.AndroidBackend.backendCommand(); } catch (e) {}
  return 'bash ~/crypto-strategy-app/apps/backend/server.sh start';
}
function backendCardHTML(withRestart) {
  var cmd = esc(backendCmdText());
  var h = '<div class="card warn"><h3>🔴 Backend mati</h3>' +
    '<p>Tidak bisa menghubungi <b>' + esc(API_BASE || 'backend') + '</b>. Nyalakan backend lalu coba lagi.</p>' +
    (LAST_ERROR ? '<p class="hint">Error: ' + esc(LAST_ERROR) + '</p>' : '') +
    '<div class="btn-row">' +
    (hasBridge()
      ? '<button class="btn btn-primary" onclick="tryStartBackend(\'start\')">▶ Nyalakan Backend</button>'
      : '<button class="btn btn-primary" onclick="copyBackendCmd()">📋 Salin perintah</button>') +
    '<button class="btn btn-secondary" onclick="retryConnection()">🔄 Coba lagi</button></div>';
  if (withRestart && hasBridge()) {
    h += '<div class="btn-row"><button class="btn btn-secondary" onclick="tryStartBackend(\'restart\')">↻ Restart Backend</button>' +
      '<button class="btn btn-secondary" onclick="openTermuxApp()">📱 Buka Termux</button></div>';
  }
  if (!hasBridge()) {
    h += '<pre class="json">' + cmd + '</pre><p class="hint">Jalankan perintah di atas di Termux, lalu tekan Coba lagi.</p>';
  } else {
    h += '<div id="backend-manual" class="hidden"><pre class="json">' + cmd + '</pre>' +
      '<div class="btn-row"><button class="btn btn-secondary" onclick="openTermuxApp()">📱 Buka Termux</button>' +
      '<button class="btn btn-secondary" onclick="copyBackendCmd()">📋 Salin</button></div>' +
      '<p class="hint">Kalau otomatis gagal, jalankan manual di Termux.</p></div>';
  }
  return h + '</div>';
}
window.tryStartBackend = async function (action) {
  action = action === 'restart' ? 'restart' : 'start';
  if (!hasBridge()) { copyBackendCmd(); return; }
  var termux = false;
  try { termux = window.AndroidBackend.isTermuxInstalled(); } catch (e) {}
  if (!termux) { showToast('Aplikasi Termux tidak ditemukan', 'error'); return; }
  showToast('Mengirim perintah ' + action + ' ke Termux...', '');
  var res = 'error';
  try { res = window.AndroidBackend.startBackend(action); } catch (e) { res = 'error: ' + e; }
  showToast('Termux dibuka. Paste perintah di Termux.', 'success');
  for (var i = 0; i < 10; i++) {
    await new Promise(function (r) { setTimeout(r, 3000); });
    if (await checkConnection()) {
      showToast('Backend online! 🎉', 'success');
      await loadTab(state.activeTab || 'home');
      return;
    }
  }
  showToast('Backend belum online — jalankan manual di Termux', 'error');
};
window.retryConnection = async function () {
  showLoading();
  await detectApi();
  var ok = await checkConnection();
  hideLoading();
  if (ok) { showToast('Terhubung!', 'success'); await loadTab(state.activeTab || 'home'); }
  else showToast('Masih offline', 'error');
};
window.copyBackendCmd = function () {
  var t = backendCmdText();
  if (hasBridge()) {
    try { window.AndroidBackend.copyCommand(t); showToast('Command copied!', 'success'); return; } catch (e) {}
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(t).then(
      function () { showToast('Perintah disalin!', 'success'); },
      function () { prompt('Salin perintah ini:', t); }
    );
  } else { prompt('Salin perintah ini:', t); }
};
window.openTermuxApp = function () {
  try { if (hasBridge() && window.AndroidBackend.openTermux()) return; } catch (e) {}
  showToast('Termux tidak ditemukan', 'error');
};

async function loadSettings() {
  var el = document.getElementById('tab-settings');
  el.innerHTML = '<div class="card"><h3>⏳ Memuat pengaturan AI...</h3></div>';
  var cfg = null;
  var ok = ONLINE || await checkConnection();
  if (!ok) {
    for (var i = 0; i < apiCandidates().length && !ok; i++) {
      try {
        var base = apiCandidates()[i];
        var r = await fetchTimeout(base + '/api/v1/settings/ai', { method: 'GET', headers: { 'Content-Type': 'application/json' } }, 5000);
        if (r.ok) { cfg = await r.json(); API_BASE = base; ok = true; saveCache('cs_ai_settings', cfg); LAST_ERROR = ''; }
      } catch (e) { LAST_ERROR = (e.name === 'AbortError' ? 'timeout' : e.message) + ' @ ' + apiCandidates()[i]; }
    }
  }
  if (!cfg && ok) {
    try { cfg = await api('/api/v1/settings/ai'); saveCache('cs_ai_settings', cfg); } catch (e) { cfg = loadCache('cs_ai_settings', null); }
  }
  if (!cfg) cfg = loadCache('cs_ai_settings', null);
  if (!cfg) {
    el.innerHTML = backendCardHTML(true) + diagCardHTML() +
      '<div class="empty-state"><div class="icon">⚙️</div><p>Backend offline dan belum ada cache.<br>Nyalakan backend untuk mengatur AI.</p></div>';
    return;
  }
  el.innerHTML =
    (!ok ? backendCardHTML(true) : '') +
    '<div class="card accent"><h3>⚙️ Pengaturan AI</h3>' +
    '<p>Endpoint OpenAI-compatible + model + temperatur. API key tidak pernah ditampilkan penuh.</p>' +
    '<div class="kv"><span>Status</span><b>' + (ONLINE ? '<span class="text-green">● Online</span>' : '<span class="text-red">● Offline (cache)</span>') + '</b></div>' +
    '<div class="kv"><span>API base dipakai</span><b>' + esc(API_BASE || '-') + '</b></div>' +
    '<div class="kv"><span>Error terakhir</span><b>' + esc(LAST_ERROR || '-') + '</b></div>' +
    '<div class="kv"><span>URL dicoba</span><b>' + esc(TRIED_URLS.join(', ') || '-') + '</b></div>' +
    '<div class="kv"><span>API key</span><b>' + esc(cfg.api_key || '-') + '</b></div>' +
    '<div class="btn-row"><button class="btn btn-secondary" onclick="copyDiag()">📋 Salin diagnostik</button>' +
    '<button class="btn btn-secondary" onclick="forceRefreshSettings()">🔄 Muat ulang dari backend</button></div></div>' +
    '<div class="card"><h3>🔌 Koneksi</h3>' +
    '<label class="label">Base URL</label>' +
    '<input class="input" id="ai-base-url" value="' + esc(cfg.base_url || '') + '" placeholder="https://.../v1" inputmode="url">' +
    '<label class="label">API key baru (kosongkan = tidak diubah)</label>' +
    '<input class="input" id="ai-key" type="password" placeholder="••••" autocomplete="off">' +
    '<label class="label">Model</label>' +
    '<input class="input" id="ai-model" list="ai-models" value="' + esc(cfg.model || '') + '" placeholder="Ketik atau pilih model...">' +
    '<datalist id="ai-models"></datalist>' +
    '<label class="label">Max tokens (100–32000)</label>' +
    '<input class="input" id="ai-max" type="number" min="100" max="32000" step="100" value="' + esc(cfg.max_tokens != null ? cfg.max_tokens : 2000) + '">' +
    '<div class="btn-row"><button class="btn btn-primary" onclick="saveAISettings()">💾 Simpan</button>' +
    '<button class="btn btn-secondary" onclick="testAISettings()">🧪 Tes koneksi</button></div>' +
    '<div id="ai-test-result"></div></div>' +
    '<div class="card"><h3>🌡️ Temperatur (0–2)</h3>' +
    '<p class="hint">Generate: kreativitas saat menyusun strategi. Explain/chat: gaya bahasa penjelasan & diskusi.</p>' +
    '<label class="label">Generate strategi</label>' +
    '<input class="input" id="ai-temp-gen" type="number" min="0" max="2" step="0.1" value="' + esc(cfg.temperature_generate != null ? cfg.temperature_generate : 0.3) + '">' +
    '<label class="label">Penjelasan</label>' +
    '<input class="input" id="ai-temp-exp" type="number" min="0" max="2" step="0.1" value="' + esc(cfg.temperature_explain != null ? cfg.temperature_explain : 0.5) + '">' +
    '<label class="label">Chat</label>' +
    '<input class="input" id="ai-temp-chat" type="number" min="0" max="2" step="0.1" value="' + esc(cfg.temperature_chat != null ? cfg.temperature_chat : 0.7) + '">' +
    '<button class="btn btn-primary" onclick="saveAISettings()">💾 Simpan temperatur</button></div>' +
    '<div class="card"><h3>🔍 Debug (raw response)</h3><pre class="json" style="font-size:11px;max-height:200px;overflow:auto">' +
    esc(JSON.stringify(cfg, null, 2)) + '</pre></div>';
  populateModelList();
}
window.loadSettings = loadSettings;

window.forceRefreshSettings = async function () {
  localStorage.removeItem('cs_ai_settings');
  ONLINE = false;
  showToast('Cache dibersihkan, mencoba koneksi ulang...', '');
  await detectApi();
  await loadSettings();
};

async function populateModelList() {
  var dl = document.getElementById('ai-models');
  if (!dl) return;
  var defaults = ['ag/claude-sonnet-4-6', 'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku', 'gemini-1.5-pro', 'gemini-1.5-flash', 'llama-3.1-405b', 'llama-3.1-70b', 'deepseek-chat', 'deepseek-coder'];
  defaults.forEach(function (m) { var o = document.createElement('option'); o.value = m; dl.appendChild(o); });
  try {
    var data = await api('/api/v1/settings/ai/models');
    var models = data.models || [];
    if (models.length) {
      dl.innerHTML = '';
      var seen = {};
      models.forEach(function (m) {
        var id = typeof m === 'string' ? m : (m.id || m.name || '');
        if (id && !seen[id]) { seen[id] = 1; var o = document.createElement('option'); o.value = id; dl.appendChild(o); }
      });
      if (!dl.children.length) {
        defaults.forEach(function (m) { var o = document.createElement('option'); o.value = m; dl.appendChild(o); });
      }
      showToast('Model dimuat: ' + dl.children.length + ' model', 'success');
    }
  } catch (e) {
    showToast('Gagal load model, pakai default', 'error');
  }
}
window.populateModelList = populateModelList;

function diagCardHTML() {
  return '<div class="card"><h3>🩺 Diagnostik koneksi</h3>' +
    '<div class="kv"><span>API base</span><b>' + esc(API_BASE || '-') + '</b></div>' +
    '<div class="kv"><span>Error terakhir</span><b>' + esc(LAST_ERROR || '-') + '</b></div>' +
    '<div class="kv"><span>URL dicoba</span><b>' + esc(TRIED_URLS.join(', ') || '-') + '</b></div>' +
    '<div class="btn-row"><button class="btn btn-secondary" onclick="copyDiag()">📋 Salin diagnostik</button>' +
    '<button class="btn btn-secondary" onclick="retryConnection()">🔄 Coba lagi</button></div></div>';
}
window.copyDiag = function () {
  var t = JSON.stringify({ api_base: API_BASE, online: ONLINE, last_error: LAST_ERROR, tried: TRIED_URLS, device: DEVICE_ID }, null, 2);
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(t).then(
      function () { showToast('Diagnostik disalin!', 'success'); },
      function () { prompt('Salin info ini:', t); }
    );
  } else { prompt('Salin info ini:', t); }
};

window.saveAISettings = async function () {
  if (!ONLINE && !(await checkConnection())) { showToast('Offline — butuh backend online', 'error'); return; }
  function num(id) {
    var v = (document.getElementById(id).value || '').trim();
    return v === '' ? null : Number(v);
  }
  var payload = {
    base_url: (document.getElementById('ai-base-url').value || '').trim() || null,
    api_key: (document.getElementById('ai-key').value || '') || null,
    model: (document.getElementById('ai-model').value || '').trim() || null,
    max_tokens: num('ai-max'),
    temperature_generate: num('ai-temp-gen'),
    temperature_explain: num('ai-temp-exp'),
    temperature_chat: num('ai-temp-chat')
  };
  Object.keys(payload).forEach(function (k) { if (payload[k] === null) delete payload[k]; });
  if (!Object.keys(payload).length) { showToast('Tidak ada perubahan', 'error'); return; }
  showLoading();
  try {
    var cfg = await api('/api/v1/settings/ai', 'PUT', payload);
    saveCache('cs_ai_settings', cfg);
    showToast('Pengaturan AI tersimpan!', 'success');
    await loadSettings();
  } catch (e) { showToast('Gagal: ' + e.message, 'error'); }
  hideLoading();
};

window.testAISettings = async function () {
  if (!ONLINE && !(await checkConnection())) { showToast('Offline — butuh backend online', 'error'); return; }
  var r = document.getElementById('ai-test-result');
  if (r) r.innerHTML = '<p class="hint mt-1">🧪 Menghubungi AI...</p>';
  try {
    var res = await api('/api/v1/settings/ai/test', 'POST');
    if (r) r.innerHTML = '<div class="card good mt-1"><h3>✅ AI terhubung</h3><p>' + esc(res.reply || 'ok') + '</p></div>';
    showToast('AI terhubung!', 'success');
  } catch (e) {
    if (r) r.innerHTML = '<div class="card warn mt-1"><h3>❌ Gagal</h3><p>' + esc(e.message) + '</p></div>';
    showToast('Gagal: ' + e.message, 'error');
  }
};
