/* ================================================================
   ML Stock Tracker - Dashboard JavaScript
   ================================================================ */

const DATA_URL = "data/analysis.json";

let DATA = null;
let smaChart = null;
let signalChart = null;
let sentimentChart = null;
let rsiChart = null;
let corrHeatmap = null;

// ================================================================
// INIT
// ================================================================
document.addEventListener("DOMContentLoaded", async () => {
    setupTabs();
    setupFilters();
    await loadData();
});

async function loadData() {
    const overlay = document.getElementById("loading-overlay");
    try {
        const resp = await fetch(DATA_URL);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        DATA = await resp.json();
        renderAll();
    } catch (err) {
        console.error("Failed to load data:", err);
        overlay.innerHTML = `
            <p style="color:#c13737;font-weight:600;">Failed to load analysis data.</p>
            <p style="color:#6b7280;font-size:13px;margin-top:8px;">
                Run the GitHub Actions workflow first to generate data.<br>
                Error: ${escapeHtml(err.message)}
            </p>`;
        return;
    }
    overlay.classList.add("hidden");
}

// ================================================================
// RENDER ALL
// ================================================================
function renderAll() {
    renderMetrics();
    renderCombinedTable();
    renderSignalChart();
    renderMATable();
    renderSMAChart();
    renderSentimentTable();
    renderSentimentChart();
    renderSentimentDetail();
    renderFinRLTable();
    renderFinRLDetail();
    renderRSIChart();
    renderCorrelation();
    document.getElementById("last-updated").textContent = `Updated: ${DATA.generated_at}`;
}

// ================================================================
// TABS
// ================================================================
function setupTabs() {
    document.querySelectorAll(".nav-link").forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const tab = link.dataset.tab;
            document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
            link.classList.add("active");
            document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
            document.getElementById(`tab-${tab}`).classList.add("active");
        });
    });
}

// ================================================================
// FILTERS
// ================================================================
function setupFilters() {
    document.getElementById("search-input").addEventListener("input", applyFilters);
    document.getElementById("signal-filter").addEventListener("change", applyFilters);
    document.getElementById("sort-select").addEventListener("change", applyFilters);
}

function applyFilters() {
    if (!DATA) return;
    renderCombinedTable();
}

function getFilteredCombined() {
    let items = [...(DATA.combined || [])];
    const search = document.getElementById("search-input").value.trim().toUpperCase();
    const signal = document.getElementById("signal-filter").value;
    const sort = document.getElementById("sort-select").value;

    if (search) {
        items = items.filter(i => i.ticker.toUpperCase().includes(search));
    }
    if (signal !== "all") {
        items = items.filter(i => i.combined_signal === signal);
    }

    switch (sort) {
        case "score-desc": items.sort((a, b) => b.combined_score - a.combined_score); break;
        case "score-asc": items.sort((a, b) => a.combined_score - b.combined_score); break;
        case "change-desc": items.sort((a, b) => (b.change_pct || 0) - (a.change_pct || 0)); break;
        case "change-asc": items.sort((a, b) => (a.change_pct || 0) - (b.change_pct || 0)); break;
        case "ticker-asc": items.sort((a, b) => a.ticker.localeCompare(b.ticker)); break;
    }
    return items;
}

// ================================================================
// METRICS
// ================================================================
function renderMetrics() {
    const combined = DATA.combined || [];
    const prices = DATA.prices || [];

    document.getElementById("metric-total").textContent = combined.length;
    document.getElementById("metric-buy").textContent =
        combined.filter(c => c.combined_signal.includes("Buy")).length;
    document.getElementById("metric-hold").textContent =
        combined.filter(c => c.combined_signal === "Hold").length;
    document.getElementById("metric-sell").textContent =
        combined.filter(c => c.combined_signal.includes("Sell")).length;

    const changes = prices.map(p => p.change_pct).filter(v => v != null);
    if (changes.length) {
        const avg = changes.reduce((s, v) => s + v, 0) / changes.length;
        const el = document.getElementById("metric-avg-change");
        el.textContent = fmtPct(avg);
        el.className = `metric-value ${avg >= 0 ? "positive" : "negative"}`;
    }

    if (prices.length) {
        const best = prices.reduce((a, b) => (b.change_pct || -Infinity) > (a.change_pct || -Infinity) ? b : a);
        document.getElementById("metric-best").textContent =
            `${best.ticker} ${fmtPct(best.change_pct)}`;
    }
}

// ================================================================
// COMBINED TABLE
// ================================================================
function renderCombinedTable() {
    const tbody = document.getElementById("combined-tbody");
    const items = getFilteredCombined();
    tbody.innerHTML = items.map(item => `
        <tr>
            <td>${tickerLink(item.ticker)}</td>
            <td>${item.price != null ? "$" + fmtNum(item.price) : "—"}</td>
            <td class="${changeClass(item.change_pct)}">${fmtPct(item.change_pct)}</td>
            <td>${signalBadge(item.combined_signal)}</td>
            <td>${scoreDisplay(item.combined_score)}</td>
            <td>${maBadge(item.ma_signal)}</td>
            <td>${sentimentBadge(item.sentiment_label)} <small class="text-neutral">${fmtScore(item.sentiment_score)}</small></td>
            <td>${signalBadge(item.finrl_signal)}</td>
        </tr>
    `).join("");
}

// ================================================================
// SIGNAL DISTRIBUTION CHART
// ================================================================
function renderSignalChart() {
    const combined = DATA.combined || [];
    const counts = {};
    combined.forEach(c => {
        counts[c.combined_signal] = (counts[c.combined_signal] || 0) + 1;
    });

    const labels = Object.keys(counts);
    const values = Object.values(counts);
    const colors = labels.map(signalColor);

    const ctx = document.getElementById("signal-chart").getContext("2d");
    if (signalChart) signalChart.destroy();
    signalChart = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels,
            datasets: [{ data: values, backgroundColor: colors, borderWidth: 2, borderColor: "#fff" }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "bottom", labels: { font: { size: 12 } } }
            }
        }
    });
}

// ================================================================
// MA CROSS TABLE
// ================================================================
function renderMATable() {
    const tbody = document.getElementById("ma-tbody");
    const items = DATA.ma_cross || [];
    tbody.innerHTML = items.map(item => `
        <tr>
            <td>${tickerLink(item.ticker)}</td>
            <td>${maBadge(item.signal)}</td>
            <td>${item.sma50 != null ? "$" + fmtNum(item.sma50) : "—"}</td>
            <td>${item.sma200 != null ? "$" + fmtNum(item.sma200) : "—"}</td>
        </tr>
    `).join("");

    // Populate SMA chart dropdown
    const sel = document.getElementById("sma-chart-ticker");
    sel.innerHTML = items.map(i => `<option value="${escapeHtml(i.ticker)}">${escapeHtml(i.ticker)}</option>`).join("");
    sel.addEventListener("change", () => renderSMAChart());
}

// ================================================================
// SMA CHART
// ================================================================
function renderSMAChart() {
    const ticker = document.getElementById("sma-chart-ticker").value;
    const item = (DATA.ma_cross || []).find(i => i.ticker === ticker);
    if (!item || !item.sma_history || !item.sma_history.length) return;

    const hist = item.sma_history;
    const labels = hist.map(h => h.date);
    const datasets = [
        {
            label: "Close",
            data: hist.map(h => h.close),
            borderColor: "#1f5aa6",
            backgroundColor: "rgba(31,90,166,0.08)",
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            borderWidth: 2,
        },
        {
            label: "SMA 50",
            data: hist.map(h => h.sma50),
            borderColor: "#d97706",
            borderDash: [5, 3],
            fill: false,
            tension: 0.3,
            pointRadius: 0,
            borderWidth: 2,
        },
        {
            label: "SMA 200",
            data: hist.map(h => h.sma200),
            borderColor: "#c13737",
            borderDash: [8, 4],
            fill: false,
            tension: 0.3,
            pointRadius: 0,
            borderWidth: 2,
        },
    ];

    const ctx = document.getElementById("sma-chart").getContext("2d");
    if (smaChart) smaChart.destroy();
    smaChart = new Chart(ctx, {
        type: "line",
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { position: "top", labels: { font: { size: 12 } } },
                title: { display: true, text: `${ticker} — Price & Moving Averages`, font: { size: 14 } }
            },
            scales: {
                x: { ticks: { maxTicksLimit: 12, font: { size: 11 } } },
                y: { ticks: { font: { size: 11 } } }
            }
        }
    });
}

// ================================================================
// SENTIMENT TABLE
// ================================================================
function renderSentimentTable() {
    const tbody = document.getElementById("sentiment-tbody");
    const items = DATA.sentiment || [];
    tbody.innerHTML = items.map(item => `
        <tr>
            <td>${tickerLink(item.ticker)}</td>
            <td>${sentimentBadge(item.label)}</td>
            <td class="${item.avg_score > 0 ? 'text-positive' : item.avg_score < 0 ? 'text-negative' : 'text-neutral'}">${fmtScore(item.avg_score)}</td>
            <td>${item.news_count}</td>
        </tr>
    `).join("");

    // Populate sentiment detail dropdown
    const sel = document.getElementById("sentiment-detail-ticker");
    sel.innerHTML = items
        .filter(i => i.news_count > 0)
        .map(i => `<option value="${escapeHtml(i.ticker)}">${escapeHtml(i.ticker)}</option>`)
        .join("");
    sel.addEventListener("change", () => renderSentimentDetail());
}

// ================================================================
// SENTIMENT DIST CHART
// ================================================================
function renderSentimentChart() {
    const items = DATA.sentiment || [];
    const counts = { Positive: 0, Neutral: 0, Negative: 0, "No News": 0 };
    items.forEach(i => { counts[i.label] = (counts[i.label] || 0) + 1; });

    const labels = Object.keys(counts).filter(k => counts[k] > 0);
    const values = labels.map(l => counts[l]);
    const colors = labels.map(l => {
        if (l === "Positive") return "#1f9d68";
        if (l === "Negative") return "#c13737";
        if (l === "No News") return "#d1d5db";
        return "#6366f1";
    });

    const ctx = document.getElementById("sentiment-chart").getContext("2d");
    if (sentimentChart) sentimentChart.destroy();
    sentimentChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [{ data: values, backgroundColor: colors, borderRadius: 4 }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, ticks: { stepSize: 1 } }
            }
        }
    });
}

// ================================================================
// SENTIMENT DETAIL (headlines)
// ================================================================
function renderSentimentDetail() {
    const ticker = document.getElementById("sentiment-detail-ticker").value;
    const item = (DATA.sentiment || []).find(i => i.ticker === ticker);
    const tbody = document.getElementById("headlines-tbody");
    if (!item || !item.headlines || !item.headlines.length) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#6b7280;">No headlines</td></tr>`;
        return;
    }
    tbody.innerHTML = item.headlines.map(h => `
        <tr>
            <td>${escapeHtml(h.date)}</td>
            <td>${escapeHtml(h.title)}</td>
            <td>${escapeHtml(h.publisher)}</td>
            <td>${sentimentBadge(h.sentiment)}</td>
            <td class="${h.score > 0 ? 'text-positive' : h.score < 0 ? 'text-negative' : 'text-neutral'}">${fmtScore(h.score)}</td>
        </tr>
    `).join("");
}

// ================================================================
// FINRL TABLE
// ================================================================
function renderFinRLTable() {
    const tbody = document.getElementById("finrl-tbody");
    const items = DATA.finrl || [];
    tbody.innerHTML = items.map(item => `
        <tr>
            <td>${tickerLink(item.ticker)}</td>
            <td>${signalBadge(item.signal)}</td>
            <td>${escapeHtml(item.confidence)}</td>
            <td>${scoreDisplay(item.composite_score)}</td>
            <td class="${changeClass(item.momentum_20d)}">${item.momentum_20d != null ? fmtPct(item.momentum_20d) : "—"}</td>
            <td>${item.rsi != null ? item.rsi.toFixed(1) : "—"}</td>
            <td>${item.macd != null ? item.macd.toFixed(4) : "—"}</td>
            <td>${item.volatility != null ? item.volatility.toFixed(3) : "—"}</td>
            <td>${item.sharpe != null ? item.sharpe.toFixed(2) : "—"}</td>
        </tr>
    `).join("");

    // Populate detail dropdown
    const sel = document.getElementById("finrl-detail-ticker");
    sel.innerHTML = items.map(i => `<option value="${escapeHtml(i.ticker)}">${escapeHtml(i.ticker)}</option>`).join("");
    sel.addEventListener("change", () => renderFinRLDetail());
}

// ================================================================
// FINRL DETAIL (reasons)
// ================================================================
function renderFinRLDetail() {
    const ticker = document.getElementById("finrl-detail-ticker").value;
    const item = (DATA.finrl || []).find(i => i.ticker === ticker);
    const container = document.getElementById("finrl-reasons");
    if (!item || !item.reasons || !item.reasons.length) {
        container.innerHTML = `<p class="text-neutral">No reasoning available</p>`;
        return;
    }
    container.innerHTML = `
        <div style="margin-bottom:12px;">
            <strong>${escapeHtml(item.ticker)}</strong> — 
            ${signalBadge(item.signal)} 
            <span class="text-neutral">(${escapeHtml(item.confidence)} confidence, score: ${item.composite_score})</span>
        </div>
        ${item.reasons.map(r => `
            <div class="reason-item">
                <span class="reason-bullet"></span>
                <span>${escapeHtml(r)}</span>
            </div>
        `).join("")}
    `;
}

// ================================================================
// RSI CHART
// ================================================================
function renderRSIChart() {
    const items = (DATA.finrl || []).filter(i => i.rsi != null);
    items.sort((a, b) => a.rsi - b.rsi);

    const labels = items.map(i => i.ticker);
    const values = items.map(i => i.rsi);
    const colors = values.map(v => {
        if (v < 30) return "#1f9d68";
        if (v > 70) return "#c13737";
        return "#6366f1";
    });

    const ctx = document.getElementById("rsi-chart").getContext("2d");
    if (rsiChart) rsiChart.destroy();
    rsiChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [{ data: values, backgroundColor: colors, borderRadius: 3 }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: "y",
            plugins: {
                legend: { display: false },
                annotation: {}
            },
            scales: {
                x: {
                    min: 0, max: 100,
                    ticks: { font: { size: 11 } }
                },
                y: {
                    ticks: { font: { size: 10 } }
                }
            }
        }
    });
}

// ================================================================
// CORRELATION
// ================================================================
function renderCorrelation() {
    const corr = DATA.correlation || {};

    // Top positive correlations table
    const posBody = document.getElementById("corr-pos-tbody");
    const posPairs = corr.top_positive || [];
    posBody.innerHTML = posPairs.length
        ? posPairs.map(p => `
            <tr>
                <td>${escapeHtml(p.pair)}</td>
                <td><span class="text-positive">${p.correlation.toFixed(3)}</span></td>
            </tr>
        `).join("")
        : `<tr><td colspan="2" class="text-neutral">No strongly correlated pairs</td></tr>`;

    // Top negative correlations table
    const negBody = document.getElementById("corr-neg-tbody");
    const negPairs = corr.top_negative || [];
    negBody.innerHTML = negPairs.length
        ? negPairs.map(p => `
            <tr>
                <td>${escapeHtml(p.pair)}</td>
                <td><span class="text-negative">${p.correlation.toFixed(3)}</span></td>
            </tr>
        `).join("")
        : `<tr><td colspan="2" class="text-neutral">No inversely correlated pairs</td></tr>`;

    // Heatmap
    renderCorrHeatmap(corr);
}

function renderCorrHeatmap(corr) {
    const tickers = corr.tickers || [];
    const matrix = corr.matrix || [];
    if (!tickers.length || !matrix.length) return;

    // Build dataset for scatter-style heatmap
    const dataPoints = [];
    for (let i = 0; i < tickers.length; i++) {
        for (let j = 0; j < tickers.length; j++) {
            const val = matrix[i] && matrix[i][j] != null ? matrix[i][j] : 0;
            dataPoints.push({ x: j, y: i, v: val });
        }
    }

    const ctx = document.getElementById("corr-heatmap").getContext("2d");
    if (corrHeatmap) corrHeatmap.destroy();

    // Use a simple bubble chart approach for the heatmap
    corrHeatmap = new Chart(ctx, {
        type: "scatter",
        data: {
            datasets: [{
                data: dataPoints.map(p => ({ x: p.x, y: p.y })),
                backgroundColor: dataPoints.map(p => corrColor(p.v)),
                pointRadius: Math.max(4, Math.min(16, 200 / tickers.length)),
                pointStyle: "rect",
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const idx = context.dataIndex;
                            const p = dataPoints[idx];
                            return `${tickers[p.y]} / ${tickers[p.x]}: ${p.v.toFixed(3)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: "linear",
                    min: -0.5,
                    max: tickers.length - 0.5,
                    ticks: {
                        stepSize: 1,
                        callback: (val) => tickers[val] || "",
                        font: { size: 9 },
                        maxRotation: 90,
                        minRotation: 45,
                    }
                },
                y: {
                    type: "linear",
                    min: -0.5,
                    max: tickers.length - 0.5,
                    reverse: true,
                    ticks: {
                        stepSize: 1,
                        callback: (val) => tickers[val] || "",
                        font: { size: 9 },
                    }
                }
            }
        }
    });
}

function corrColor(val) {
    if (val == null) return "rgba(200,200,200,0.3)";
    // Red for negative, blue for positive, white for zero
    if (val > 0) {
        const intensity = Math.min(val, 1);
        return `rgba(31, 90, 166, ${0.15 + intensity * 0.75})`;
    } else {
        const intensity = Math.min(Math.abs(val), 1);
        return `rgba(193, 55, 55, ${0.15 + intensity * 0.75})`;
    }
}

// ================================================================
// HELPERS
// ================================================================
function escapeHtml(str) {
    if (str == null) return "";
    const div = document.createElement("div");
    div.textContent = String(str);
    return div.innerHTML;
}

function tickerLink(ticker) {
    const encoded = encodeURIComponent(ticker);
    return `<a href="https://finance.yahoo.com/quote/${encoded}" target="_blank" rel="noopener" class="ticker-link">${escapeHtml(ticker)}</a>`;
}

function fmtNum(val) {
    if (val == null) return "—";
    return Number(val).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPct(val) {
    if (val == null) return "—";
    const prefix = val >= 0 ? "+" : "";
    return `${prefix}${val.toFixed(2)}%`;
}

function fmtScore(val) {
    if (val == null) return "—";
    const prefix = val >= 0 ? "+" : "";
    return `${prefix}${Number(val).toFixed(3)}`;
}

function changeClass(val) {
    if (val == null) return "text-neutral";
    return val >= 0 ? "text-positive" : "text-negative";
}

function signalBadge(signal) {
    if (!signal) return `<span class="badge badge-neutral">N/A</span>`;
    const cls = signalBadgeClass(signal);
    return `<span class="badge ${cls}">${escapeHtml(signal)}</span>`;
}

function signalBadgeClass(signal) {
    const s = (signal || "").toLowerCase();
    if (s === "strong buy") return "badge-strong-buy";
    if (s === "buy") return "badge-buy";
    if (s === "hold") return "badge-hold";
    if (s === "sell") return "badge-sell";
    if (s === "strong sell") return "badge-strong-sell";
    return "badge-neutral";
}

function maBadge(signal) {
    if (!signal) return `<span class="badge badge-neutral">N/A</span>`;
    const s = signal.toLowerCase();
    let cls = "badge-neutral";
    if (s.includes("golden")) cls = "badge-golden";
    else if (s.includes("death")) cls = "badge-death";
    else if (s.includes("bullish")) cls = "badge-bullish";
    else if (s.includes("bearish")) cls = "badge-bearish";
    else if (s.includes("insufficient")) cls = "badge-insufficient";
    return `<span class="badge ${cls}">${escapeHtml(signal)}</span>`;
}

function sentimentBadge(label) {
    if (!label) return `<span class="badge badge-neutral">N/A</span>`;
    const l = label.toLowerCase();
    let cls = "badge-neutral";
    if (l === "positive") cls = "badge-positive";
    else if (l === "negative") cls = "badge-negative";
    return `<span class="badge ${cls}">${escapeHtml(label)}</span>`;
}

function signalColor(signal) {
    const s = (signal || "").toLowerCase();
    if (s === "strong buy") return "#166534";
    if (s === "buy") return "#1f9d68";
    if (s === "hold") return "#6366f1";
    if (s === "sell") return "#c13737";
    if (s === "strong sell") return "#991b1b";
    return "#9ca3af";
}

function scoreDisplay(score) {
    if (score == null) return "—";
    const color = score > 0 ? "#1f9d68" : score < 0 ? "#c13737" : "#6366f1";
    const maxScore = 10;
    const pct = Math.min(Math.abs(score) / maxScore * 100, 100);
    return `
        <div class="score-bar">
            <span style="color:${color};font-weight:600;min-width:38px;">${score > 0 ? "+" : ""}${score.toFixed(1)}</span>
            <div class="score-bar-track">
                <div class="score-bar-fill" style="width:${pct}%;background:${color};"></div>
            </div>
        </div>
    `;
}
