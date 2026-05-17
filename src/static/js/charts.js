/**
 * Charts.js — Gráficos do dashboard
 *
 * Exports:
 *  - initPnlChart()        — linha de P&L acumulado
 *  - initWinRateChart()    — donut de win rate
 *  - initTradesPerHour()   — barras trades/hora
 *  - loadAgentPnlHistory() — histórico de P&L por agente
 *  - addPnlPoint()         — novo ponto em tempo real
 *  - updateWinRateChart()  — atualiza donut
 *  - updateTradesPerHour() — atualiza barras
 *  - removeAgentFromChart()
 *  - addTradeBar()         — (stub — compatibilidade)
 *  - updateTradeCountdown()— (stub — compatibilidade)
 *  - closeTradeBar()       — (stub — compatibilidade)
 */

// ─── Constantes ───────────────────────────────────────────────────────────────
const AGENT_COLORS = [
  '#58a6ff', '#3fb950', '#bc8cff', '#e3b341', '#f85149',
  '#39d353', '#ff7b72', '#79c0ff', '#d2a8ff', '#ffa657',
];

// ─── Estado global ────────────────────────────────────────────────────────────
let chartInst        = null;  // P&L line chart
let wrChartInst      = null;  // Win Rate donut
let tphChartInst     = null;  // Trades Per Hour bar

let colorCursor  = 0;
const agentColors   = {};   // { agentId: hex }
const agentDatasets = {}; // { agentId: datasetIndex }

// ─── Helpers ──────────────────────────────────────────────────────────────────
function agentColor(agentId) {
  if (!agentColors[agentId]) {
    agentColors[agentId] = AGENT_COLORS[colorCursor++ % AGENT_COLORS.length];
  }
  return agentColors[agentId];
}

function hexRgba(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

// ─── P&L Line Chart ───────────────────────────────────────────────────────────

export function initPnlChart(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) { console.warn(`[Charts] Canvas '${canvasId}' não encontrado.`); return null; }
  if (chartInst) { chartInst.destroy(); chartInst = null; }

  const ctx = canvas.getContext('2d');
  chartInst = new Chart(ctx, {
    type: 'line',
    data: { datasets: [] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          display: true, position: 'top', align: 'end',
          labels: {
            color: '#8b949e', font: { size: 11, weight: '600' },
            boxWidth: 14, padding: 12, usePointStyle: true, pointStyle: 'circle',
          },
        },
        tooltip: {
          backgroundColor: '#161b22', borderColor: '#30363d', borderWidth: 1,
          titleColor: '#e6edf3', bodyColor: '#8b949e', padding: 12,
          callbacks: {
            label(item) {
              const v = item.parsed.y;
              return `  ${item.dataset.label}: ${v >= 0 ? '+' : ''}$${v.toFixed(2)}`;
            },
          },
        },
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'hour', displayFormats: { minute: 'HH:mm', hour: 'HH:mm', day: 'dd/MM' }, tooltipFormat: 'dd/MM HH:mm' },
          ticks: { color: '#8b949e', font: { size: 10 }, maxTicksLimit: 8 },
          grid: { color: 'rgba(48,54,61,0.5)' },
        },
        y: {
          ticks: {
            color: '#8b949e', font: { size: 10 },
            callback(v) { return `${v >= 0 ? '+' : ''}$${v.toFixed(2)}`; },
          },
          grid: { color: 'rgba(48,54,61,0.5)' },
          afterBuildTicks(axis) {
            if (!axis.ticks.some(t => t.value === 0)) {
              axis.ticks.push({ value: 0 });
              axis.ticks.sort((a, b) => a.value - b.value);
            }
          },
        },
      },
    },
  });
  return chartInst;
}

export function loadAgentPnlHistory(agentId, agentName, dataPoints) {
  if (!chartInst) return;
  const color = agentColor(agentId);
  const points = (dataPoints || []).map(dp => ({ x: new Date(dp.timestamp), y: dp.cumulative_pnl }));

  if (agentId in agentDatasets) {
    const dsIndex = agentDatasets[agentId];
    if (chartInst.data.datasets[dsIndex]) {
      chartInst.data.datasets[dsIndex].data = points;
      chartInst.update('none');
      return;
    }
  }

  const dataset = {
    label: agentName,
    data: points,
    borderColor: color,
    backgroundColor: hexRgba(color, 0.08),
    borderWidth: 2,
    pointRadius: points.length <= 20 ? 3 : 0,
    pointHoverRadius: 5,
    pointBackgroundColor: color,
    tension: 0.3,
    fill: true,
  };

  const dsIndex = chartInst.data.datasets.length;
  agentDatasets[agentId] = dsIndex;
  chartInst.data.datasets.push(dataset);
  chartInst.update('none');
}

export function addPnlPoint(agentId, cumulativePnl, timestamp) {
  if (!chartInst || !(agentId in agentDatasets)) return;
  const ds = chartInst.data.datasets[agentDatasets[agentId]];
  if (!ds) return;
  ds.data.push({ x: new Date(timestamp || Date.now()), y: cumulativePnl });
  if (ds.data.length > 500) ds.data.shift();
  ds.pointRadius = ds.data.length <= 20 ? 3 : 0;
  chartInst.update('none');
}

export function removeAgentFromChart(agentId) {
  if (!chartInst || !(agentId in agentDatasets)) return;
  const dsIndex = agentDatasets[agentId];
  chartInst.data.datasets.splice(dsIndex, 1);
  delete agentDatasets[agentId];
  delete agentColors[agentId];
  Object.keys(agentDatasets).forEach(id => {
    if (agentDatasets[id] > dsIndex) agentDatasets[id]--;
  });
  chartInst.update('none');
}

export function getChart() { return chartInst; }

// ─── Win Rate Donut ───────────────────────────────────────────────────────────

export function initWinRateChart(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;
  if (wrChartInst) { wrChartInst.destroy(); wrChartInst = null; }

  const ctx = canvas.getContext('2d');
  wrChartInst = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Wins', 'Losses'],
      datasets: [{
        data: [0, 1],
        backgroundColor: ['#3fb950', '#f85149'],
        borderColor: ['#3fb950', '#f85149'],
        borderWidth: 1,
        hoverOffset: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '72%',
      animation: { duration: 500 },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#161b22',
          borderColor: '#30363d',
          borderWidth: 1,
          callbacks: {
            label(item) {
              const total = item.dataset.data.reduce((a, b) => a + b, 0);
              const pct = total > 0 ? ((item.parsed / total) * 100).toFixed(1) : '0.0';
              return `${item.label}: ${item.parsed} (${pct}%)`;
            },
          },
        },
      },
    },
  });
  return wrChartInst;
}

export function updateWinRateChart(wins, losses) {
  if (!wrChartInst) return;
  const total = wins + losses;
  wrChartInst.data.datasets[0].data = total > 0 ? [wins, losses] : [0, 1];
  wrChartInst.update('none');

  // Atualizar texto central
  const pct = total > 0 ? ((wins / total) * 100).toFixed(1) : '0.0';
  const el = document.getElementById('donutWinRate');
  if (el) {
    el.textContent = `${pct}%`;
    el.style.color = parseFloat(pct) >= 55 ? '#3fb950' : parseFloat(pct) >= 45 ? '#e3b341' : '#f85149';
  }
  const subtitle = document.getElementById('wrChartSubtitle');
  if (subtitle) subtitle.textContent = `${wins}W / ${losses}L`;
}

// ─── Trades Per Hour Bar Chart ────────────────────────────────────────────────

export function initTradesPerHourChart(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;
  if (tphChartInst) { tphChartInst.destroy(); tphChartInst = null; }

  // Gerar labels para as últimas 12 horas
  const labels = [];
  const now = new Date();
  for (let i = 11; i >= 0; i--) {
    const h = new Date(now);
    h.setHours(h.getHours() - i, 0, 0, 0);
    labels.push(h.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }));
  }

  const ctx = canvas.getContext('2d');
  tphChartInst = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Wins',
          data: new Array(12).fill(0),
          backgroundColor: 'rgba(63,185,80,0.6)',
          borderColor: '#3fb950',
          borderWidth: 1,
          borderRadius: 3,
        },
        {
          label: 'Losses',
          data: new Array(12).fill(0),
          backgroundColor: 'rgba(248,81,73,0.6)',
          borderColor: '#f85149',
          borderWidth: 1,
          borderRadius: 3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      interaction: { mode: 'index' },
      plugins: {
        legend: {
          display: true, position: 'top', align: 'end',
          labels: { color: '#8b949e', font: { size: 10 }, boxWidth: 10, padding: 8 },
        },
        tooltip: {
          backgroundColor: '#161b22', borderColor: '#30363d', borderWidth: 1,
          titleColor: '#e6edf3', bodyColor: '#8b949e', padding: 10,
        },
      },
      scales: {
        x: {
          stacked: true,
          ticks: { color: '#8b949e', font: { size: 9 }, maxRotation: 45 },
          grid: { display: false },
        },
        y: {
          stacked: true,
          ticks: { color: '#8b949e', font: { size: 9 }, stepSize: 1 },
          grid: { color: 'rgba(48,54,61,0.5)' },
          beginAtZero: true,
        },
      },
    },
  });
  return tphChartInst;
}

/**
 * Atualiza o gráfico de trades por hora com dados dos últimos trades.
 * @param {Array} trades - array de trades com opened_at, result
 */
export function updateTradesPerHour(trades) {
  if (!tphChartInst) return;

  const now = new Date();
  const wins  = new Array(12).fill(0);
  const losses = new Array(12).fill(0);

  const labels = [];
  const hourBuckets = [];
  for (let i = 11; i >= 0; i--) {
    const h = new Date(now);
    h.setHours(h.getHours() - i, 0, 0, 0);
    hourBuckets.push(h);
    labels.push(h.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }));
  }

  (trades || []).forEach(t => {
    if (!t.opened_at) return;
    const tDate = new Date(t.opened_at);
    for (let i = 0; i < 12; i++) {
      const bucketStart = hourBuckets[i];
      const bucketEnd = new Date(bucketStart);
      bucketEnd.setHours(bucketEnd.getHours() + 1);
      if (tDate >= bucketStart && tDate < bucketEnd) {
        if (t.result === 'won') wins[i]++;
        else if (t.result === 'lost') losses[i]++;
        break;
      }
    }
  });

  tphChartInst.data.labels = labels;
  tphChartInst.data.datasets[0].data = wins;
  tphChartInst.data.datasets[1].data = losses;
  tphChartInst.update('none');
}

// ─── Stubs de compatibilidade ─────────────────────────────────────────────────

/** @deprecated stub de compatibilidade */
export function addTradeBar(agentId, agentName, trade) {
  void agentId; void agentName; void trade;
}

/** @deprecated stub de compatibilidade */
export function updateTradeCountdown(contractId, remainingSeconds) {
  void contractId; void remainingSeconds;
}

/** @deprecated stub de compatibilidade */
export function closeTradeBar(contractId, result, profit) {
  void contractId; void result; void profit;
}
