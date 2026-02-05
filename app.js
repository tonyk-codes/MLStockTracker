/*
  Portfolio Dashboard (frontend)
  
  ✅ Finance-grade UI (white theme)
  ✅ Filters (Cat./Grade)
  ✅ Sticky banner + Last updated
  ✅ Locked mode: only shows Ticker/Cat./Grade while Price/Signal/Performance are blurred

  SECURITY NOTE:
  - True security cannot be achieved on GitHub Pages alone.
  - This UI is built to work with the included backend (/server) that enforces passcode auth.
  - Without the backend, the dashboard stays Locked (no protected data is delivered).
*/

// If your backend is hosted on another domain, set this.
// Example: const API_BASE = 'https://your-backend.onrender.com';
const API_BASE = '';

const $ = (s) => document.querySelector(s);

// Stock master list (display names + tickers)
// Note: BRKB is displayed as BRKB but fetched from Yahoo as BRK-B.
const STOCKS = [
  { name: "Vanguard Growth ETF", ticker: "VUG",  yf: "VUG",  cat: "ETF", grade: "A" },
  { name: "Vanguard Total Stock Market ETF", ticker: "VTI",  yf: "VTI",  cat: "ETF", grade: "A" },
  { name: "Vanguard S&P 500 ETF", ticker: "VOO",  yf: "VOO",  cat: "ETF", grade: "A" },
  { name: "ProShares Ultra S&P500", ticker: "SSO",  yf: "SSO",  cat: "ETF", grade: "A" },
  { name: "Invesco QQQ Trust", ticker: "QQQ",  yf: "QQQ",  cat: "ETF", grade: "A" },
  { name: "ProShares UltraPro QQQ", ticker: "TQQQ", yf: "TQQQ", cat: "ETF", grade: "A" },

  { name: "Advanced Micro Devices, Inc.", ticker: "AMD",  yf: "AMD",  cat: "Tech", grade: "A" },
  { name: "GraniteShares 2x Long AMD Daily ETF", ticker: "AMDL", yf: "AMDL", cat: "Tech", grade: "A" },
  { name: "Direxion Daily TSLA Bull 2X Shares", ticker: "TSLL", yf: "TSLL", cat: "Tech", grade: "A" },
  { name: "Tesla, Inc.", ticker: "TSLA", yf: "TSLA", cat: "Tech", grade: "A" },
  { name: "Direxion Daily META Bull 2X ETF", ticker: "METU", yf: "METU", cat: "Tech", grade: "A" },
  { name: "Microsoft Corporation", ticker: "MSFT", yf: "MSFT", cat: "Tech", grade: "A" },
  { name: "Direxion Daily MSFT Bull 2X Shares", ticker: "MSFU", yf: "MSFU", cat: "Tech", grade: "A" },
  { name: "GraniteShares 2x Long NVDA Daily ETF", ticker: "NVDL", yf: "NVDL", cat: "Tech", grade: "A" },

  { name: "The Coca-Cola Company", ticker: "KO", yf: "KO", cat: "F&B", grade: "A" },

  { name: "Berkshire Hathaway Inc. (Class B)", ticker: "BRKB", yf: "BRK-B", cat: "ETF", grade: "A" },
  { name: "Direxion Daily BRKB Bull 2X Shares", ticker: "BRKU", yf: "BRKU", cat: "ETF", grade: "A" },

  { name: "Lululemon Athletica Inc.", ticker: "LULU", yf: "LULU", cat: "Cosmetic", grade: "C" },
  { name: "NIKE, Inc.", ticker: "NKE", yf: "NKE", cat: "Cosmetic", grade: "B" },
];

// Elements
const appRoot = document.body;
const lockPill = $("#lockPill");
const lastUpdatedEl = $("#lastUpdated");
const passInput = $("#passcode");
const btnUnlock = $("#btnUnlock");
const btnLock = $("#btnLock");
const msg = $("#accessMsg");

const catFilter = $("#catFilter");
const gradeFilter = $("#gradeFilter");

const algoBody = $("#algoBody");
const mlBody = $("#mlBody");
const ooBody = $("#ooBody");

// Session token (kept in memory + sessionStorage)
function getToken(){ return sessionStorage.getItem('pd_token') || ''; }
function setToken(t){ if(t) sessionStorage.setItem('pd_token', t); else sessionStorage.removeItem('pd_token'); }

function unique(xs){ return [...new Set(xs)]; }

function setLocked(locked){
  appRoot.classList.toggle("locked", locked);
  lockPill.textContent = locked ? "Locked" : "Unlocked";
  lockPill.classList.toggle("meta-pill--lock", locked);
  lockPill.classList.toggle("meta-pill--ok", !locked);
}

function setMessage(text, tone="neutral"){
  msg.textContent = text;
  msg.style.color = tone === "bad" ? "#dc2626" : (tone === "ok" ? "#0ea5a4" : "#556070");
}

function gradeBadge(grade){
  const cls = grade === "A" ? "gradeA" : (grade === "B" ? "gradeB" : "gradeC");
  return `<span class="badge ${cls}"><span class="dot"></span>${escapeHtml(grade)}</span>`;
}

function escapeHtml(str){
  return String(str).replace(/[&<>"']/g, m => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
  }[m]));
}

function fmtMoney(x){
  if(x === null || x === undefined || Number.isNaN(x)) return "—";
  const n = Number(x);
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function priceCell(p){
  // p: {regular, pre, post, currency}
  if(!p) return `<div class="price"><div class="price__main">—</div><div class="price__sub">Pre — | Post —</div></div>`;
  const cur = p.currency ? ` ${escapeHtml(p.currency)}` : "";
  const main = p.regular != null ? `${fmtMoney(p.regular)}${cur}` : "—";
  const pre  = p.pre != null ? fmtMoney(p.pre) : "—";
  const post = p.post != null ? fmtMoney(p.post) : "—";
  return `<div class="price"><div class="price__main">${main}</div><div class="price__sub">Pre ${pre} | Post ${post}</div></div>`;
}

function filteredStocks(){
  const c = catFilter.value;
  const g = gradeFilter.value;
  return STOCKS.filter(s => (c === "ALL" || s.cat === c) && (g === "ALL" || s.grade === g));
}

function rowHTML(s, kind, secretData){
  const secret = secretData?.rows?.[s.ticker] || null;
  const p = secret?.price || null;
  const signal = secret?.signal?.[kind] ?? "TBD";
  const perf   = secret?.performance?.[kind] ?? "TBD";

  return `
    <tr>
      <td>${escapeHtml(s.name)}</td>
      <td class="mono">${escapeHtml(s.ticker)}</td>
      <td>${escapeHtml(s.cat)}</td>
      <td>${gradeBadge(s.grade)}</td>
      <td class="secret">${priceCell(p)}</td>
      <td class="secret">${escapeHtml(signal)}</td>
      <td class="secret mono">${escapeHtml(perf)}</td>
    </tr>
  `;
}

function render(secretData=null){
  const list = filteredStocks();
  algoBody.innerHTML = list.map(s => rowHTML(s, "algo", secretData)).join("");
  mlBody.innerHTML   = list.map(s => rowHTML(s, "ml", secretData)).join("");
  ooBody.innerHTML   = list.map(s => rowHTML(s, "oo", secretData)).join("");
}

function populateFilters(){
  unique(STOCKS.map(s => s.cat)).sort().forEach(c => {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    catFilter.appendChild(opt);
  });
  unique(STOCKS.map(s => s.grade)).sort().forEach(g => {
    const opt = document.createElement("option");
    opt.value = g;
    opt.textContent = g;
    gradeFilter.appendChild(opt);
  });
}

async function api(path, opts={}){
  const url = (API_BASE || '') + path;
  const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
  const t = getToken();
  if(opts.auth && t) headers["Authorization"] = `Bearer ${t}`;

  const r = await fetch(url, Object.assign({}, opts, { headers }));
  const ct = r.headers.get('content-type') || '';
  const body = ct.includes('application/json') ? await r.json().catch(()=>null) : await r.text().catch(()=>null);
  if(!r.ok){
    const detail = (body && body.detail) ? body.detail : (typeof body === 'string' ? body : `HTTP ${r.status}`);
    throw new Error(detail);
  }
  return body;
}

async function unlock(){
  const passcode = passInput.value || "";
  if(!passcode){ setMessage("Please enter a passcode.", "bad"); return; }

  btnUnlock.disabled = true;
  setMessage("Checking…");

  try{
    const out = await api('/api/login', {
      method: 'POST',
      body: JSON.stringify({ passcode })
    });

    if(!out || !out.token) throw new Error('Login failed');
    setToken(out.token);

    setLocked(false);
    passInput.value = "";
    setMessage("Access granted.", "ok");

    await refresh();
  }catch(err){
    const m = String(err?.message || err);
    if(m.includes('Failed to fetch') || m.includes('NetworkError')){
      setMessage("Backend not reachable. Deploy /server and set API_BASE in app.js.", "bad");
    }else{
      setMessage("Access denied.", "bad");
    }
    setToken('');
    setLocked(true);
    lastUpdatedEl.textContent = "Last updated: —";
    render(null);
  }finally{
    btnUnlock.disabled = false;
  }
}

async function refresh(){
  const t = getToken();
  if(!t){
    setLocked(true);
    render(null);
    return;
  }
  try{
    const data = await api('/api/data', { method:'GET', auth:true });
    const updated = data.last_updated ? new Date(data.last_updated) : new Date();
    lastUpdatedEl.textContent = `Last updated: ${updated.toLocaleString()}`;
    render(data);
  }catch(err){
    setMessage("Session expired. Unlock again.", "bad");
    setToken('');
    setLocked(true);
    lastUpdatedEl.textContent = "Last updated: —";
    render(null);
  }
}

async function lock(){
  setToken('');
  setLocked(true);
  setMessage("Locked.");
  lastUpdatedEl.textContent = "Last updated: —";
  render(null);
  // optional backend logout
  try{ await api('/api/logout', { method:'POST' }); }catch{}
}

(function init(){
  populateFilters();
  setLocked(true);
  render(null);

  catFilter.addEventListener('change', () => refresh());
  gradeFilter.addEventListener('change', () => refresh());

  btnUnlock.addEventListener('click', unlock);
  btnLock.addEventListener('click', lock);
  passInput.addEventListener('keydown', (e) => { if(e.key === 'Enter') unlock(); });

  // auto-refresh every 60s when unlocked
  setInterval(() => { if(getToken()) refresh(); }, 60000);
})();
