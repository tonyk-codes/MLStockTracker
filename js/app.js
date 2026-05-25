/* ================================================================
   Machine Learning Signal Platform — app.js
   ================================================================ */

const DATA_URL = 'data/analysis.json';

let DATA = null;
let currentFilter = 'ALL';
let sortCol = null;
let sortDir = 'desc';
let portfolio = null;

// ============================================================
// Init
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
    setupTabs();
    setupFilters();
    setupRunModal();
    setupUpload();
    await loadData();
});

// ============================================================
// Tabs
// ============================================================
function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
            btn.classList.add('active');
            document.getElementById('panel-' + tab).classList.remove('hidden');
            if (tab === 'correlation' && DATA?.correlation) renderCorrelation(DATA.correlation);
        });
    });
}

// ============================================================
// Data load
// ============================================================
async function loadData() {
    try {
        const res = await fetch(DATA_URL + '?t=' + Date.now());
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        if (!data.stocks || !Array.isArray(data.stocks)) {
            throw new Error('stale_schema');
        }
        DATA = data;
        renderMeta(data);
        renderSummary(data);
        renderSignals(data.stocks, currentFilter, sortCol, sortDir);
        if (portfolio) applyPortfolioSignals();
    } catch (err) {
        if (err.message === 'stale_schema') {
            showMsg('Data schema outdated. Click "Run Analysis" to regenerate.');
        } else {
            showMsg('No analysis data found. Click "Run Analysis" to generate.');
        }
    }
}

function showMsg(text) {
    const tbody = document.getElementById('signals-tbody');
    if (tbody) tbody.innerHTML = `<tr class="loading-row"><td colspan="14">${text}</td></tr>`;
}

// ============================================================
// Meta bar
// ============================================================
function renderMeta(data) {
    const ts = data.generated_at ? new Date(data.generated_at) : null;
    const genEl = document.getElementById('meta-generated');
    if (genEl) genEl.textContent = ts
        ? ts.toLocaleString('en-US', {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'})
        : '--';
    const qqq = data.qqq_5d_ret;
    const el = document.getElementById('meta-qqq');
    if (el && qqq != null) {
        el.textContent = (qqq >= 0 ? '+' : '') + qqq.toFixed(2) + '%';
        el.className = 'meta-value ' + (qqq >= 0 ? 'pos' : 'neg');
    }
}

// ============================================================
// Summary counts
// ============================================================
function renderSummary(data) {
    const counts = data.counts || {};
    const stocks = data.stocks || [];
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    set('cnt-total', counts.total ?? stocks.length);
    set('cnt-buy',   counts.buy   ?? stocks.filter(s => s.signal === 'BUY').length);
    set('cnt-sell',  counts.sell  ?? stocks.filter(s => s.signal === 'SELL').length);
    set('cnt-hold',  counts.hold  ?? stocks.filter(s => s.signal === 'HOLD').length);
    set('cnt-tl',    counts.tl    ?? stocks.filter(s => s.classification === 'TL').length);
}

// ============================================================
// Filter + Sort setup
// ============================================================
function setupFilters() {
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.dataset.filter;
            if (DATA) renderSignals(DATA.stocks, currentFilter, sortCol, sortDir);
        });
    });
    document.querySelectorAll('#signals-table th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const col = th.dataset.col;
            if (sortCol === col) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
            else { sortCol = col; sortDir = 'desc'; }
            document.querySelectorAll('#signals-table th').forEach(h => h.classList.remove('sort-asc','sort-desc'));
            th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
            if (DATA) renderSignals(DATA.stocks, currentFilter, sortCol, sortDir);
        });
    });
}

// ============================================================
// Signal Table render
// ============================================================
function renderSignals(stocks, filter, col, dir) {
    let rows = stocks.slice();
    if (filter === 'BUY')  rows = rows.filter(s => s.signal === 'BUY');
    else if (filter === 'SELL') rows = rows.filter(s => s.signal === 'SELL');
    else if (filter === 'HOLD') rows = rows.filter(s => s.signal === 'HOLD');
    else if (filter === 'TL')   rows = rows.filter(s => s.classification === 'TL');

    if (col) {
        rows.sort((a, b) => {
            let va = a[col], vb = b[col];
            if (typeof va === 'string') va = va.toLowerCase();
            if (typeof vb === 'string') vb = vb.toLowerCase();
            if (va == null) va = dir === 'asc' ? Infinity : -Infinity;
            if (vb == null) vb = dir === 'asc' ? Infinity : -Infinity;
            return dir === 'asc' ? (va > vb ? 1 : va < vb ? -1 : 0) : (va < vb ? 1 : va > vb ? -1 : 0);
        });
    }

    const tbody = document.getElementById('signals-tbody');
    if (!rows.length) {
        tbody.innerHTML = '<tr class="loading-row"><td colspan="14">No signals match the current filter.</td></tr>';
        return;
    }
    tbody.innerHTML = rows.map(buildRow).join('');
}

function buildRow(s) {
    const sig = s.signal || 'HOLD';
    const cls = s.classification || 'N';
    const sigCls = sig === 'BUY' ? 'sig-buy' : sig === 'SELL' ? 'sig-sell' : 'sig-hold';
    const clsCls = cls === 'TL' ? 'cls-tl' : 'cls-n';

    const fmt  = (v, d=2) => v == null ? '--' : (+v).toFixed(d);
    const pct  = v => v == null ? '--' : (v >= 0 ? '+' : '') + (+v).toFixed(2) + '%';
    const cpct = v => {
        if (v == null) return '<span style="color:var(--text-faint)">--</span>';
        const c = v > 0.5 ? 'pos' : v < -0.5 ? 'neg' : '';
        return `<span class="${c}">${pct(v)}</span>`;
    };
    const rsi = v => {
        if (v == null) return '--';
        const c = v >= 70 ? 'rsi-ob' : v <= 30 ? 'rsi-os' : 'rsi-mid';
        return `<span class="${c}">${(+v).toFixed(1)}</span>`;
    };

    let pnlTag = '';
    if (portfolio && portfolio[s.ticker]) {
        const ph = portfolio[s.ticker];
        if (s.price && ph.avgCost) {
            const pnlPct = (s.price - ph.avgCost) / ph.avgCost * 100;
            const isPnlSell = (cls === 'TL' && pnlPct >= 25 && (s.rsi14||0) >= 75) ||
                               (cls === 'N'  && pnlPct >= 12 && (s.rsi14||0) > 65);
            pnlTag = ` <span class="${isPnlSell ? 'sig-sell' : pnlPct >= 0 ? 'pos' : 'neg'}" style="font-size:10px">${isPnlSell ? '[PNL-SELL]' : (pnlPct>=0?'+':'')+pnlPct.toFixed(1)+'%'}</span>`;
        }
    }

    return `<tr>
        <td class="col-ticker" style="font-family:var(--mono);font-weight:700">${s.ticker}${pnlTag}</td>
        <td class="col-name" style="color:var(--text-dim);font-size:11px">${s.name||''}</td>
        <td class="col-signal"><span class="${sigCls}">${sig}</span></td>
        <td class="col-cls"><span class="${clsCls}">${cls}</span></td>
        <td style="font-family:var(--mono)">${fmt(s.price)}</td>
        <td>${cpct(s.change_1d)}</td>
        <td>${cpct(s.dist_ma20_pct)}</td>
        <td>${cpct(s.dist_ma50_pct)}</td>
        <td style="font-family:var(--mono)">${rsi(s.rsi14)}</td>
        <td>${cpct(s.ret5d)}</td>
        <td>${cpct(s.ret20d)}</td>
        <td>${cpct(s.ret60d)}</td>
        <td>${cpct(s.ret120d)}</td>
        <td class="col-reason">${s.reason||''}</td>
    </tr>`;
}

// ============================================================
// Portfolio Upload
// ============================================================
function setupUpload() {
    const input = document.getElementById('portfolio-upload');
    if (!input) return;
    input.addEventListener('change', e => {
        const file = e.target.files[0];
        if (!file) return;
        parsePortfolio(file);
        input.value = '';
    });
    document.getElementById('portfolio-close')?.addEventListener('click', () => {
        portfolio = null;
        document.getElementById('portfolio-panel').classList.add('hidden');
        document.getElementById('portfolio-tbody').innerHTML = '';
        if (DATA) renderSignals(DATA.stocks, currentFilter, sortCol, sortDir);
    });
}

function parsePortfolio(file) {
    const name = file.name.toLowerCase();
    if (name.endsWith('.csv')) {
        const reader = new FileReader();
        reader.onload = e => parseCSV(e.target.result);
        reader.readAsText(file);
    } else {
        const reader = new FileReader();
        reader.onload = e => {
            if (typeof XLSX === 'undefined') {
                showToast('XLSX library not loaded. Try again in a moment.');
                return;
            }
            const wb = XLSX.read(e.target.result, {type:'array'});
            const ws = wb.Sheets[wb.SheetNames[0]];
            const rows = XLSX.utils.sheet_to_json(ws, {header:1});
            processPortfolioRows(rows);
        };
        reader.readAsArrayBuffer(file);
    }
}

function parseCSV(text) {
    const lines = text.trim().split('\n').map(l =>
        l.split(',').map(c => c.trim().replace(/^"|"$/g,''))
    );
    processPortfolioRows(lines);
}

function processPortfolioRows(rows) {
    if (rows.length < 2) { showToast('Portfolio file is empty or invalid.'); return; }
    const header = rows[0].map(h => String(h).toLowerCase().trim());
    const col = (keys) => header.findIndex(h => keys.some(k => h.includes(k)));

    const ti = col(['ticker','symbol','code','stock']);
    const si = col(['shares','quantity','qty','units']);
    const ci = col(['avgcost','avg cost','average cost','cost','price paid','purchase price','avg price']);

    if (ti < 0) { showToast('Could not find ticker/symbol column.'); return; }

    const map = {};
    const tableRows = [];
    for (let i = 1; i < rows.length; i++) {
        const row = rows[i];
        const ticker = String(row[ti]||'').trim().toUpperCase();
        if (!ticker) continue;
        const shares  = si >= 0 ? parseFloat(row[si]) || 0 : 0;
        const avgCost = ci >= 0 ? parseFloat(row[ci]) || 0 : 0;
        map[ticker] = { shares, avgCost };
        tableRows.push({ ticker, shares, avgCost });
    }

    portfolio = map;
    renderPortfolioTable(tableRows);
    if (DATA) renderSignals(DATA.stocks, currentFilter, sortCol, sortDir);
    showToast('Portfolio loaded: ' + tableRows.length + ' position' + (tableRows.length !== 1 ? 's' : ''));
}

function applyPortfolioSignals() {
    if (DATA) renderSignals(DATA.stocks, currentFilter, sortCol, sortDir);
}

function renderPortfolioTable(rows) {
    document.getElementById('portfolio-panel').classList.remove('hidden');
    const tbody = document.getElementById('portfolio-tbody');
    tbody.innerHTML = rows.map(r => {
        const stock = DATA?.stocks?.find(s => s.ticker === r.ticker);
        const price = stock?.price;
        const cls   = stock?.classification || 'N';
        const pnlPct = (price && r.avgCost) ? ((price - r.avgCost) / r.avgCost * 100) : null;
        const mktVal = (price && r.shares) ? price * r.shares : null;
        const isPnlSell = pnlPct != null && (
            (cls === 'TL' && pnlPct >= 25 && (stock?.rsi14||0) >= 75) ||
            (cls === 'N'  && pnlPct >= 12 && (stock?.rsi14||0) > 65)
        );
        const sigStr = stock?.signal || '--';
        const sigCls = sigStr === 'BUY' ? 'sig-buy' : sigStr === 'SELL' ? 'sig-sell' : sigStr === 'HOLD' ? 'sig-hold' : '';
        const pnlCls = isPnlSell ? 'sig-sell' : pnlPct == null ? '' : pnlPct >= 0 ? 'pos' : 'neg';
        const pnlStr = pnlPct == null ? '--' : (isPnlSell ? '[SELL] ' : '') + (pnlPct >= 0 ? '+' : '') + pnlPct.toFixed(2) + '%';
        const mktStr = mktVal == null ? '--' : '$' + Math.round(mktVal).toLocaleString();

        return `<tr>
            <td style="font-family:var(--mono);font-weight:700">${r.ticker}</td>
            <td style="text-align:right;font-family:var(--mono)">${r.shares||'--'}</td>
            <td style="text-align:right;font-family:var(--mono)">${r.avgCost ? '$'+r.avgCost.toFixed(2) : '--'}</td>
            <td style="text-align:right;font-family:var(--mono)">${price ? '$'+price.toFixed(2) : '--'}</td>
            <td style="text-align:right"><span class="${pnlCls}">${pnlStr}</span></td>
            <td style="text-align:right;font-family:var(--mono)">${mktStr}</td>
            <td style="text-align:right"><span class="${sigCls}">${sigStr}</span></td>
        </tr>`;
    }).join('');
}

// ============================================================
// Run Analysis Modal
// ============================================================
function setupRunModal() {
    const openBtn  = document.getElementById('btn-run');
    const modal    = document.getElementById('run-modal');
    const closeBtn = document.getElementById('modal-close');
    const submitBtn= document.getElementById('modal-submit');

    const cancelBtn = document.getElementById('modal-cancel');
    openBtn?.addEventListener('click',   () => modal?.classList.remove('hidden'));
    closeBtn?.addEventListener('click',  () => modal?.classList.add('hidden'));
    cancelBtn?.addEventListener('click', () => modal?.classList.add('hidden'));
    modal?.addEventListener('click', e => { if (e.target === modal) modal.classList.add('hidden'); });
    submitBtn?.addEventListener('click', async () => {
        const pat = document.getElementById('run-token')?.value.trim();
        if (!pat) { setRunStatus('Enter a GitHub Personal Access Token.', 'err'); return; }
        await triggerAnalysis(pat);
    });
}

function setRunStatus(msg, type) {
    const el = document.getElementById('run-status');
    if (!el) return;
    el.textContent = msg;
    el.className = 'run-status ' + (type || 'info');
    el.classList.remove('hidden');
}

async function triggerAnalysis(pat) {
    let owner = '', repo = '';
    const host = window.location.hostname;
    const parts = window.location.pathname.split('/').filter(Boolean);
    if (host.endsWith('.github.io')) {
        owner = host.replace('.github.io', '');
        repo  = parts[0] || '';
    }
    if (!owner || !repo) {
        owner = prompt('GitHub username / organization:') || '';
        repo  = prompt('Repository name:') || '';
    }
    if (!owner || !repo) { setRunStatus('Could not determine repository.', 'err'); return; }

    setRunStatus('Dispatching workflow...', 'info');
    try {
        const res = await fetch(
            `https://api.github.com/repos/${owner}/${repo}/actions/workflows/analyze.yml/dispatches`,
            {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${pat}`,
                    'Accept': 'application/vnd.github+json',
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ ref: 'main' })
            }
        );
        if (res.status === 204) {
            setRunStatus('Workflow dispatched. Analysis will complete in ~2 minutes.', 'ok');
            showToast('Analysis workflow triggered successfully.');
        } else {
            const txt = await res.text();
            setRunStatus('API error ' + res.status + ': ' + txt.slice(0, 120), 'err');
        }
    } catch (err) {
        setRunStatus('Network error: ' + err.message, 'err');
    }
}

// ============================================================
// Correlation Heatmap
// ============================================================
function renderCorrelation(corr) {
    if (!corr || !corr.tickers || !corr.matrix) {
        showMsg('No correlation data. Run analysis first.');
        return;
    }
    drawHeatmap(corr.tickers, corr.matrix);
    renderCorrTable('corr-pos-tbody', corr.top_positive, true);
    renderCorrTable('corr-neg-tbody', corr.top_negative, false);
}

function drawHeatmap(tickers, matrix) {
    const n = tickers.length;
    const CELL  = 22;
    const LABEL = 54;
    const W = LABEL + n * CELL;
    const H = LABEL + n * CELL;

    const canvas = document.getElementById('corr-canvas');
    if (!canvas) return;
    canvas.width  = W;
    canvas.height = H;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, W, H);

    for (let i = 0; i < n; i++) {
        for (let j = 0; j < n; j++) {
            const val = (matrix[tickers[i]] && matrix[tickers[i]][tickers[j]] != null)
                ? matrix[tickers[i]][tickers[j]] : 0;
            ctx.fillStyle = heatColor(val);
            ctx.fillRect(LABEL + j * CELL, LABEL + i * CELL, CELL - 1, CELL - 1);
        }
    }

    ctx.font = 'bold 8.5px JetBrains Mono, monospace';
    ctx.fillStyle = '#7d8fa8';

    // Row labels
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let i = 0; i < n; i++) {
        ctx.fillText(tickers[i], LABEL - 5, LABEL + i * CELL + CELL / 2);
    }
    // Column labels (rotated)
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    for (let j = 0; j < n; j++) {
        ctx.save();
        ctx.translate(LABEL + j * CELL + CELL / 2, LABEL - 5);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText(tickers[j], 0, 0);
        ctx.restore();
    }
}

function heatColor(v) {
    const a = Math.min(1, Math.abs(v));
    if (v >= 0) {
        const g = Math.round(63 + 122 * a);
        return `rgba(0,${g},0,${0.2 + a * 0.65})`;
    } else {
        const r = Math.round(100 + 148 * a);
        return `rgba(${r},0,0,${0.2 + a * 0.65})`;
    }
}

function renderCorrTable(tbodyId, pairs, positive) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    if (!pairs || !pairs.length) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--text-faint);padding:12px;font-size:11px">No data available</td></tr>';
        return;
    }
    tbody.innerHTML = pairs.slice(0, 20).map(([t1, t2, v]) =>
        `<tr>
            <td style="font-family:var(--mono);font-weight:700">${t1}</td>
            <td style="font-family:var(--mono);font-weight:700">${t2}</td>
            <td style="text-align:right"><span class="${positive?'pos':'neg'}">${(+v).toFixed(3)}</span></td>
        </tr>`
    ).join('');
}

// ============================================================
// Toast
// ============================================================
let _toastTimer = null;
function showToast(msg) {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.classList.remove('hidden');
    if (_toastTimer) clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => el.classList.add('hidden'), 3500);
}
