const API_URL = window.location.origin.replace(':8080', ':8001');
const state = { strategies: [], signals: [], loading: false, activeTab: 'home' };

document.addEventListener('DOMContentLoaded', () => {
  setupTabs();
  loadHome();
  setInterval(checkConnection, 30000);
  checkConnection();
});

function setupTabs() {
  document.querySelectorAll('#tab-nav .tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#tab-nav .tab').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
      state.activeTab = btn.dataset.tab;
      loadTab(btn.dataset.tab);
    });
  });
}

async function loadTab(tab) {
  switch(tab) {
    case 'home': await loadHome(); break;
    case 'builder': await loadBuilder(); break;
    case 'library': await loadLibrary(); break;
    case 'backtest': await loadBacktest(); break;
    case 'signals': await loadSignals(); break;
  }
}

function showLoading() { document.getElementById('loading').classList.remove('hidden'); }
function hideLoading() { document.getElementById('loading').classList.add('hidden'); }
function showToast(msg, type='') {
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'toast ' + type;
  setTimeout(() => t.classList.add('hidden'), 3000);
}

async function api(path, method='GET', body=null) {
  try {
    const opts = { method, headers: {'Content-Type':'application/json'} };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(API_URL + path, opts);
    return await res.json();
  } catch(e) {
    showToast('API Error: ' + e.message, 'error');
    return null;
  }
}

async function checkConnection() {
  const el = document.getElementById('connection-status');
  try {
    const r = await fetch(API_URL + '/health');
    const d = await r.json();
    el.textContent = '● Online'; el.className = 'status-online';
  } catch {
    el.textContent = '● Offline'; el.className = 'status-offline';
  }
}

async function loadHome() {
  const el = document.getElementById('tab-home');
  el.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';
  const data = await api('/strategies');
  const total = data ? data.length : 0;
  el.innerHTML = `
    <div class="card" style="border-left:4px solid #4a4aff">
      <h3>📊 Overview</h3>
      <p>Total Strategies: <span class="text-blue">${total}</span></p>
      <p>Backend: <span class="text-green">Running</span></p>
    </div>
    <div class="flex-between mt-1 mb-1">
      <button class="btn btn-primary" onclick="loadTab('builder')">🤖 Build New Strategy</button>
      <button class="btn btn-secondary" onclick="loadTab('signals')">🔔 Scan Signals</button>
    </div>
    <div class="card mt-1">
      <h3>⚡ Quick Actions</h3>
      <button class="btn btn-sm btn-primary mb-1" onclick="loadTab('backtest')">📊 Run Backtest</button>
      <button class="btn btn-sm btn-secondary" onclick="loadTab('library')">📚 View Library</button>
    </div>
  `;
  hideLoading();
}

async function loadBuilder() {
  const el = document.getElementById('tab-builder');
  el.innerHTML = `
    <div class="card">
      <h3>🤖 AI Strategy Builder</h3>
      <p>Describe your strategy in natural language</p>
      <div class="form-group">
        <label class="label">Strategy Description</label>
        <textarea id="builder-input" placeholder="e.g. Buy BTC when RSI below 30 and EMA 20 crosses above EMA 50..."></textarea>
      </div>
      <div class="form-group">
        <label class="label">Symbol</label>
        <select id="builder-symbol"><option value="BTC/USDT">BTC/USDT</option><option value="ETH/USDT">ETH/USDT</option><option value="SOL/USDT">SOL/USDT</option></select>
      </div>
      <button class="btn btn-primary" onclick="buildStrategy()">🚀 Build Strategy</button>
    </div>
    <div id="builder-result"></div>
  `;
}

async function buildStrategy() {
  const desc = document.getElementById('builder-input').value.trim();
  if (!desc) return showToast('Enter a description', 'error');
  const symbol = document.getElementById('builder-symbol').value;
  showLoading();
  const res = await api('/ai/build', 'POST', { description: desc, symbol });
  hideLoading();
  if (res) {
    const r = document.getElementById('builder-result');
    const score = res.score || res.performance_score || 0;
    const scoreColor = score > 60 ? 'text-green' : score > 40 ? 'text-yellow' : 'text-red';
    r.innerHTML = `
      <div class="card" style="border-left:4px solid #0a6">
        <h3>✅ Strategy Built</h3>
        <p><strong>Name:</strong> ${res.name || 'Strategy'}</p>
        <p><strong>Symbol:</strong> ${res.symbol || symbol}</p>
        <p><strong>Score:</strong> <span class="${scoreColor}">${score}/100</span></p>
        <p><strong>Indicators:</strong> ${res.indicators?.join(', ') || 'N/A'}</p>
        <p><strong>Logic:</strong> ${res.logic || res.description || 'N/A'}</p>
        <pre style="background:#0a0a2e;padding:8px;border-radius:4px;margin-top:8px;font-size:0.75rem;overflow-x:auto;color:#aaa">${JSON.stringify(res, null, 2)}</pre>
      </div>
    `;
    showToast('Strategy built!', 'success');
  }
}

async function loadLibrary() {
  const el = document.getElementById('tab-library');
  el.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';
  const data = await api('/strategies');
  hideLoading();
  if (!data || data.length === 0) {
    el.innerHTML = '<div class="empty-state"><div class="icon">📚</div><p>No strategies yet. Build one!</p></div>';
    return;
  }
  const cards = data.map(s => `
    <div class="strategy-card" onclick="showDetail('${s.id}')">
      <div class="flex-between">
        <span class="name">${s.name || 'Strategy'}</span>
        <span class="score">${s.score || s.performance_score || '--'}</span>
      </div>
      <div class="meta">${s.symbol || '--'} | ${s.indicators?.slice(0,3).join(', ') || 'N/A'} | ${s.status || 'active'}</div>
    </div>
  `).join('');
  el.innerHTML = `
    <div class="flex-between mb-1">
      <h2>📚 Strategy Library (${data.length})</h2>
      <button class="btn btn-sm btn-primary" onclick="loadTab('builder')">+ New</button>
    </div>
    ${cards}
  `;
}

async function showDetail(id) {
  const data = await api(`/strategies/${id}`);
  if (!data) return;
  const score = data.score || data.performance_score || 0;
  const scoreColor = score > 60 ? '#0f0' : score > 40 ? '#ffaa00' : '#f44';
  const el = document.getElementById('tab-library');
  el.innerHTML = `
    <div class="card">
      <div class="flex-between">
        <h3>${data.name || 'Strategy'}</h3>
        <button class="btn btn-sm btn-secondary" onclick="loadLibrary()">← Back</button>
      </div>
      <p><strong>Symbol:</strong> ${data.symbol || '--'}</p>
      <p><strong>Description:</strong> ${data.description || 'N/A'}</p>
      <p><strong>Status:</strong> ${data.status || 'active'}</p>
      <p><strong>Score:</strong> <span style="color:${scoreColor}">${score}/100</span></p>
      <div class="score-bar"><div class="score-bar-fill" style="width:${score}%;background:${scoreColor}"></div></div>
      <p style="margin-top:12px"><strong>Indicators:</strong> ${data.indicators?.join(', ') || 'N/A'}</p>
      <pre style="background:#0a0a2e;padding:8px;border-radius:4px;font-size:0.75rem;overflow-x:auto;color:#aaa;margin-top:8px">${JSON.stringify(data, null, 2)}</pre>
      <div class="flex mt-1">
        <button class="btn btn-sm btn-primary" onclick="runBacktest('${id}')">📊 Backtest</button>
        <button class="btn btn-sm btn-danger" onclick="deleteStrategy('${id}')">🗑 Delete</button>
      </div>
    </div>
  `;
}

async function deleteStrategy(id) {
  if (!confirm('Delete this strategy?')) return;
  await api(`/strategies/${id}`, 'DELETE');
  showToast('Deleted', 'success');
  loadLibrary();
}

async function loadBacktest() {
  const el = document.getElementById('tab-backtest');
  el.innerHTML = `
    <div class="card">
      <h3>📊 Backtest Engine</h3>
      <div class="form-group">
        <label class="label">Strategy ID</label>
        <input class="input" id="bt-id" placeholder="Enter strategy ID">
      </div>
      <div class="form-group">
        <label class="label">Symbol</label>
        <select id="bt-symbol"><option value="BTC/USDT">BTC/USDT</option><option value="ETH/USDT">ETH/USDT</option><option value="SOL/USDT">SOL/USDT</option></select>
      </div>
      <div class="form-group">
        <label class="label">Period (days)</label>
        <select id="bt-period"><option value="30">30 days</option><option value="90" selected>90 days</option><option value="365">365 days</option></select>
      </div>
      <button class="btn btn-primary" onclick="runBacktest()">▶ Run Backtest</button>
    </div>
    <div id="backtest-result"></div>
  `;
}

async function runBacktest(id=null) {
  const strategyId = id || document.getElementById('bt-id')?.value.trim();
  if (!strategyId) return showToast('Enter strategy ID', 'error');
  const symbol = document.getElementById('bt-symbol')?.value || 'BTC/USDT';
  const period = document.getElementById('bt-period')?.value || '90';
  showLoading();
  const res = await api(`/strategies/${strategyId}/backtest`, 'POST', { symbol, period: parseInt(period) });
  hideLoading();
  if (res) {
    const r = document.getElementById('backtest-result') || document.getElementById('builder-result');
    const wr = res.win_rate || 0;
    const wrColor = wr > 50 ? 'text-green' : 'text-red';
    r.innerHTML = `
      <div class="card" style="border-left:4px solid #0a6">
        <h3>📊 Backtest Results</h3>
        <div class="grid-2">
          <div><p>Trades: <span class="text-blue">${res.total_trades || res.total || 0}</span></p></div>
          <div><p>Win Rate: <span class="${wrColor}">${wr}%</span></p></div>
          <div><p>Sharpe: <span class="text-blue">${res.sharpe_ratio || '--'}</span></p></div>
          <div><p>Max Drawdown: <span class="text-red">${res.max_drawdown || '--'}%</span></p></div>
          <div><p>Final Balance: <span class="text-green">$${(res.final_balance || 0).toLocaleString()}</span></p></div>
          <div><p>Profit: <span class="${(res.total_profit || 0) > 0 ? 'text-green' : 'text-red'}">${(res.total_profit || 0) > 0 ? '+' : ''}${(res.total_profit || 0).toLocaleString()}</span></p></div>
        </div>
        <p style="margin-top:12px"><strong>Summary:</strong> ${res.summary || 'No summary available'}</p>
      </div>
    `;
    showToast('Backtest complete!', 'success');
  }
}

async function loadSignals() {
  const el = document.getElementById('tab-signals');
  el.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';
  const data = await api('/signals/scan');
  hideLoading();
  if (!data || data.length === 0) {
    el.innerHTML = '<div class="empty-state"><div class="icon">🔔</div><p>No signals. Scan now!</p></div>';
    return;
  }
  const items = data.map(s => {
    const type = s.signal || s.action || 'hold';
    const cls = type === 'buy' ? 'buy' : type === 'sell' ? 'sell' : '';
    return `
      <div class="signal-item ${cls}">
        <div class="flex-between">
          <span class="pair">${s.symbol || s.pair || '--'}</span>
          <span class="conf">${s.confidence || s.strength || '--'}%</span>
        </div>
        <p style="margin-top:4px"><strong>Signal:</strong> <span class="${type==='buy'?'text-green':type==='sell'?'text-red':'text-yellow'}">${type.toUpperCase()}</span></p>
        <p style="font-size:0.75rem;color:#666">${s.reason || s.description || 'N/A'}</p>
      </div>
    `;
  }).join('');
  el.innerHTML = `
    <div class="flex-between mb-1">
      <h2>🔔 Signal Feed (${data.length})</h2>
      <button class="btn btn-sm btn-primary" onclick="loadSignals()">🔄 Refresh</button>
    </div>
    ${items}
  `;
}
</script>