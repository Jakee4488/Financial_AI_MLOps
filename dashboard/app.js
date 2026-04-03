/**
 * Financial AI — Performance Dashboard
 * Chart.js visualisations & data loading
 */

// ── Sample data (used when no JSON files are available) ──
const SAMPLE_DATA = {
    tournament: {
        winner: "xgboost",
        timestamp: new Date().toISOString(),
        results: [
            { model: "lightgbm", metrics: { pr_auc: 0.892, f1_score: 0.761, precision: 0.834, recall: 0.699 }, training_time_s: 12.3 },
            { model: "xgboost", metrics: { pr_auc: 0.915, f1_score: 0.783, precision: 0.851, recall: 0.724 }, training_time_s: 15.7 },
            { model: "random_forest", metrics: { pr_auc: 0.847, f1_score: 0.712, precision: 0.795, recall: 0.645 }, training_time_s: 8.2 },
            { model: "isolation_forest", metrics: { pr_auc: 0.821, f1_score: 0.689, precision: 0.743, recall: 0.642 }, training_time_s: 4.1 },
        ],
    },
    champion_history: {
        champion: { model_type: "xgboost", version: "12", metrics: { pr_auc: 0.908, f1_score: 0.775, precision: 0.842, recall: 0.717 } },
        challenger: { model_type: "xgboost", version: "13", metrics: { pr_auc: 0.915, f1_score: 0.783, precision: 0.851, recall: 0.724 } },
        decision: "PROMOTE",
        improvement: { pr_auc: 0.007, f1_score: 0.008, precision: 0.009, recall: 0.007 },
    },
    drift: {
        psi: 0.12,
        js_divergence: 0.06,
        overall_drift: false,
        drifted_features: [],
        psi_threshold: 0.20,
        js_threshold: 0.10,
    },
    performance_timeline: [
        { date: "2026-03-28", pr_auc: 0.901, f1_score: 0.758, precision: 0.831, recall: 0.696 },
        { date: "2026-03-29", pr_auc: 0.905, f1_score: 0.762, precision: 0.836, recall: 0.700 },
        { date: "2026-03-30", pr_auc: 0.908, f1_score: 0.775, precision: 0.842, recall: 0.717 },
        { date: "2026-03-31", pr_auc: 0.903, f1_score: 0.770, precision: 0.838, recall: 0.712 },
        { date: "2026-04-01", pr_auc: 0.910, f1_score: 0.779, precision: 0.845, recall: 0.721 },
        { date: "2026-04-02", pr_auc: 0.912, f1_score: 0.781, precision: 0.848, recall: 0.722 },
        { date: "2026-04-03", pr_auc: 0.915, f1_score: 0.783, precision: 0.851, recall: 0.724 },
    ],
    deployment_events: [
        { type: "deploy", version: "13", model: "xgboost", time: "2h ago", decision: "PROMOTE" },
        { type: "rollback", version: "11", model: "lightgbm", time: "1d ago", reason: "Performance degradation" },
        { type: "deploy", version: "12", model: "xgboost", time: "3d ago", decision: "PROMOTE" },
        { type: "retrain", version: "12", model: "xgboost", time: "3d ago", reason: "Data drift detected" },
        { type: "deploy", version: "10", model: "lightgbm", time: "7d ago", decision: "PROMOTE" },
    ],
};

// ── Chart instances ──
let radarChart = null;
let comparisonBarChart = null;
let trendChart = null;
let currentMetric = "pr_auc";

// ── Color palette ──
const COLORS = {
    lightgbm: { bg: "rgba(99, 102, 241, 0.2)", border: "#818cf8" },
    xgboost: { bg: "rgba(34, 211, 238, 0.2)", border: "#22d3ee" },
    random_forest: { bg: "rgba(52, 211, 153, 0.2)", border: "#34d399" },
    isolation_forest: { bg: "rgba(251, 191, 36, 0.2)", border: "#fbbf24" },
};

const CHART_DEFAULTS = {
    color: "#94a3b8",
    borderColor: "rgba(255,255,255,0.06)",
    font: { family: "'Inter', sans-serif" },
};

// ── Initialisation ──
document.addEventListener("DOMContentLoaded", () => {
    Chart.defaults.color = CHART_DEFAULTS.color;
    Chart.defaults.borderColor = CHART_DEFAULTS.borderColor;
    Chart.defaults.font.family = CHART_DEFAULTS.font.family;

    loadData(SAMPLE_DATA);

    document.getElementById("btn-refresh").addEventListener("click", () => loadData(SAMPLE_DATA));

    document.querySelectorAll(".chip[data-metric]").forEach((chip) => {
        chip.addEventListener("click", () => {
            document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
            chip.classList.add("active");
            currentMetric = chip.dataset.metric;
            updateTrendChart(SAMPLE_DATA.performance_timeline);
        });
    });
});

// ── Data loading ──
function loadData(data) {
    updateKPIs(data);
    renderRadarChart(data.tournament);
    renderComparisonBar(data.champion_history);
    updateComparisonCard(data.champion_history);
    updateModelTable(data.tournament);
    updateDriftGauges(data.drift);
    renderTimeline(data.deployment_events);
    updateTrendChart(data.performance_timeline);

    document.querySelector("#last-updated span").textContent = new Date().toLocaleTimeString();
    document.getElementById("tournament-date").textContent = new Date().toLocaleDateString();
}

// ── KPI Cards ──
function updateKPIs(data) {
    const latest = data.tournament.results.find((r) => r.model === data.tournament.winner);
    if (!latest) return;

    const m = latest.metrics;
    document.getElementById("val-prauc").textContent = m.pr_auc.toFixed(3);
    document.getElementById("val-f1").textContent = m.f1_score.toFixed(3);
    document.getElementById("val-precision").textContent = m.precision.toFixed(3);
    document.getElementById("val-recall").textContent = m.recall.toFixed(3);
    document.getElementById("val-champion").textContent = data.tournament.winner.toUpperCase();

    // Trends from improvement
    const imp = data.champion_history.improvement || {};
    setTrend("trend-prauc", imp.pr_auc);
    setTrend("trend-f1", imp.f1_score);
    setTrend("trend-precision", imp.precision);
    setTrend("trend-recall", imp.recall);
    document.getElementById("trend-champion").textContent = `v${data.champion_history.challenger?.version || "?"}`;
}

function setTrend(id, value) {
    const el = document.getElementById(id);
    if (value === undefined) return;
    const sign = value >= 0 ? "+" : "";
    el.textContent = `${sign}${(value * 100).toFixed(2)}%`;
    el.className = `kpi-trend ${value >= 0 ? "up" : "down"}`;
}

// ── Radar Chart ──
function renderRadarChart(tournament) {
    const ctx = document.getElementById("radarChart").getContext("2d");
    if (radarChart) radarChart.destroy();

    const labels = ["PR-AUC", "F1 Score", "Precision", "Recall", "Accuracy"];
    const datasets = tournament.results.map((r) => ({
        label: r.model,
        data: [r.metrics.pr_auc, r.metrics.f1_score, r.metrics.precision, r.metrics.recall, r.metrics.accuracy || 0.85],
        backgroundColor: COLORS[r.model]?.bg || "rgba(148,163,184,0.2)",
        borderColor: COLORS[r.model]?.border || "#94a3b8",
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: COLORS[r.model]?.border || "#94a3b8",
    }));

    radarChart = new Chart(ctx, {
        type: "radar",
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    beginAtZero: false,
                    min: 0.5,
                    max: 1.0,
                    ticks: { stepSize: 0.1, font: { size: 10 } },
                    grid: { color: "rgba(255,255,255,0.05)" },
                    angleLines: { color: "rgba(255,255,255,0.05)" },
                    pointLabels: { font: { size: 11, weight: "500" } },
                },
            },
            plugins: {
                legend: { position: "bottom", labels: { padding: 16, usePointStyle: true, font: { size: 11 } } },
            },
        },
    });
}

// ── Comparison Bar Chart ──
function renderComparisonBar(comparison) {
    const ctx = document.getElementById("comparisonBar").getContext("2d");
    if (comparisonBarChart) comparisonBarChart.destroy();

    if (!comparison.champion || !comparison.challenger) return;

    const metrics = ["pr_auc", "f1_score", "precision", "recall"];
    const labels = ["PR-AUC", "F1 Score", "Precision", "Recall"];

    comparisonBarChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [
                {
                    label: `Champion (v${comparison.champion.version})`,
                    data: metrics.map((m) => comparison.champion.metrics[m] || 0),
                    backgroundColor: "rgba(251,191,36,0.3)",
                    borderColor: "#fbbf24",
                    borderWidth: 1,
                    borderRadius: 4,
                },
                {
                    label: `Challenger (v${comparison.challenger.version})`,
                    data: metrics.map((m) => comparison.challenger.metrics[m] || 0),
                    backgroundColor: "rgba(34,211,238,0.3)",
                    borderColor: "#22d3ee",
                    borderWidth: 1,
                    borderRadius: 4,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: false, min: 0.5, grid: { color: "rgba(255,255,255,0.04)" } },
                x: { grid: { display: false } },
            },
            plugins: {
                legend: { position: "bottom", labels: { usePointStyle: true, font: { size: 11 } } },
            },
        },
    });
}

// ── Comparison Card ──
function updateComparisonCard(comparison) {
    const badge = document.getElementById("comparison-decision");
    if (comparison.decision === "PROMOTE") {
        badge.textContent = "✅ PROMOTED";
        badge.className = "card-badge promoted";
    } else {
        badge.textContent = "❌ REJECTED";
        badge.className = "card-badge rejected";
    }

    const grid = document.getElementById("comparison-grid");
    if (!comparison.champion || !comparison.challenger) return;

    grid.innerHTML = `
        <div class="comparison-side">
            <h3>🛡️ Champion v${comparison.champion.version}</h3>
            ${Object.entries(comparison.champion.metrics).map(([k, v]) => `
                <div class="metric-row"><span>${k}</span><span class="metric-val">${v.toFixed(4)}</span></div>
            `).join("")}
        </div>
        <div class="comparison-side">
            <h3>⚔️ Challenger v${comparison.challenger.version}</h3>
            ${Object.entries(comparison.challenger.metrics).map(([k, v]) => `
                <div class="metric-row"><span>${k}</span><span class="metric-val">${v.toFixed(4)}</span></div>
            `).join("")}
        </div>
    `;
}

// ── Model Table ──
function updateModelTable(tournament) {
    const tbody = document.getElementById("model-table-body");
    tbody.innerHTML = tournament.results
        .sort((a, b) => (b.metrics.pr_auc || 0) - (a.metrics.pr_auc || 0))
        .map((r, i) => `
            <tr class="${i === 0 ? "winner" : ""}">
                <td>${i === 0 ? "🏆 " : ""}${r.model}</td>
                <td>${(r.metrics.pr_auc || 0).toFixed(4)}</td>
                <td>${(r.metrics.f1_score || 0).toFixed(4)}</td>
                <td>${(r.metrics.precision || 0).toFixed(4)}</td>
                <td>${(r.metrics.recall || 0).toFixed(4)}</td>
                <td>${(r.training_time_s || 0).toFixed(1)}</td>
            </tr>
        `)
        .join("");
}

// ── Drift Gauges ──
function updateDriftGauges(drift) {
    const psiPct = Math.min((drift.psi / drift.psi_threshold) * 100, 100);
    const jsPct = Math.min((drift.js_divergence / drift.js_threshold) * 100, 100);

    const psiFill = document.getElementById("psi-fill");
    psiFill.style.width = `${psiPct}%`;
    psiFill.className = `gauge-fill ${psiPct > 80 ? "danger" : psiPct > 50 ? "warning" : "ok"}`;
    document.getElementById("psi-value").textContent = drift.psi.toFixed(2);

    const jsFill = document.getElementById("js-fill");
    jsFill.style.width = `${jsPct}%`;
    jsFill.className = `gauge-fill ${jsPct > 80 ? "danger" : jsPct > 50 ? "warning" : "ok"}`;
    document.getElementById("js-value").textContent = drift.js_divergence.toFixed(2);

    const featuresDiv = document.getElementById("drifted-features");
    if (drift.overall_drift) {
        featuresDiv.innerHTML = `<p class="drift-status danger">⚠️ Drift detected: ${drift.drifted_features.join(", ")}</p>`;
    } else {
        featuresDiv.innerHTML = `<p class="drift-status ok">✅ No features drifted</p>`;
    }
}

// ── Trend Chart ──
function updateTrendChart(timeline) {
    const ctx = document.getElementById("trendChart").getContext("2d");
    if (trendChart) trendChart.destroy();

    trendChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: timeline.map((t) => t.date),
            datasets: [
                {
                    label: currentMetric.replace("_", " ").toUpperCase(),
                    data: timeline.map((t) => t[currentMetric] || 0),
                    borderColor: "#818cf8",
                    backgroundColor: "rgba(99,102,241,0.1)",
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointBackgroundColor: "#818cf8",
                    borderWidth: 2,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: false, grid: { color: "rgba(255,255,255,0.04)" } },
                x: { grid: { display: false } },
            },
            plugins: {
                legend: { display: false },
                tooltip: { backgroundColor: "rgba(17,24,39,0.95)", borderColor: "#818cf8", borderWidth: 1 },
            },
        },
    });
}

// ── Deployment Timeline ──
function renderTimeline(events) {
    const container = document.getElementById("deployment-timeline");
    if (!events || events.length === 0) {
        container.innerHTML = '<div class="timeline-empty">No deployment events yet</div>';
        return;
    }

    const icons = { deploy: "🚀", rollback: "⏪", retrain: "🔄" };
    container.innerHTML = events
        .map((e) => `
            <div class="timeline-item">
                <div class="timeline-icon ${e.type}">${icons[e.type] || "•"}</div>
                <div class="timeline-content">
                    <div class="timeline-title">${e.type === "deploy" ? `Deployed v${e.version} (${e.model})` : e.type === "rollback" ? `Rolled back to v${e.version}` : `Retrained → v${e.version}`}</div>
                    <div class="timeline-meta">${e.time}${e.reason ? ` · ${e.reason}` : ""}${e.decision ? ` · ${e.decision}` : ""}</div>
                </div>
            </div>
        `)
        .join("");
}
