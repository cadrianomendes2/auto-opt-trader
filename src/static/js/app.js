/**
 * App.js - Controlador principal do dashboard de trading.
 */
import { WSClient } from './ws-client.js';
import {
  initPnlChart, loadAgentPnlHistory, addPnlPoint,
  removeAgentFromChart, addTradeBar, updateTradeCountdown, closeTradeBar,
  initWinRateChart, updateWinRateChart,
  initTradesPerHourChart, updateTradesPerHour,
} from './charts.js';
import {
  fetchAgents, createAgent, updateAgent, deleteAgent,
  pauseAgent, resumeAgent, fetchPnlHistory, fetchStrategies,
} from './api.js';

// ─── Estado da aplicação ────────────────────────────────
const state = {
  agents: {},           // { agentId: agentData }
  strategies: [],
  editingAgentId: null,
  modelsCache: {},      // { duration_minutes: [...models] }
  activeCountdowns: {}, // { agentId: { remaining, total, interval } }
  pendingTradeRows: {}, // { agentId: <tr element> } — linha em curso na tabela
  tableCountdowns: {},  // { contractId: { interval, expiresAt, trEl } } — countdowns na tabela
};

let wsClient = null;

// ─── Inicialização ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  initPnlChart('pnlChart');
  initWinRateChart('winRateChart');
  initTradesPerHourChart('tradesPerHourChart');
  bindUIEvents();
  await loadStrategies();
  await loadInitialData();
  // Restaurar countdowns ativos do localStorage (antes de conectar o WS)
  restoreCountdownsFromStorage();
  connectWebSocket();
  // Carregar trades históricos da API ao iniciar
  await loadRecentTradesFromAPI();

  // Atualizar textos de "última execução" a cada minuto
  setInterval(refreshLastExecutionTimes, 60_000);
  // Atualizar gráficos auxiliares a cada 5 minutos
  setInterval(refreshAuxCharts, 5 * 60_000);
});

async function loadStrategies() {
  try {
    const data = await fetchStrategies();
    // API retorna array diretamente: [...] ou objeto legado: { strategies: [...] }
    state.strategies = Array.isArray(data) ? data : (data.strategies || []);
    populateStrategySelect(state.strategies);
  } catch (e) {
    console.error('Erro ao carregar estratégias:', e);
  }
}

function populateStrategySelect(strategies) {
  const select = document.getElementById('agentStrategy');
  if (!select) return;
  select.innerHTML = '';
  strategies.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s.id;
    opt.textContent = s.name;
    select.appendChild(opt);
  });
}

async function loadInitialData() {
  try {
    const data = await fetchAgents();
    const agents = data.agents || [];

    agents.forEach(agent => {
      state.agents[agent.id] = agent;
    });

    // Carregar últimos trades de cada agente para exibir os quadradinhos
    await Promise.all(agents.map(agent => loadAgentRecentTrades(agent.id)));

    renderAgentCards();

    for (const agent of agents) {
      await loadAgentChart(agent.id, agent.name);
    }

  } catch (e) {
    console.error('Erro ao carregar agentes:', e);
    showToast('Erro', 'Não foi possível carregar os agentes.', 'error');
  }
}

async function loadAgentRecentTrades(agentId) {
  try {
    const resp = await fetch(`/api/v1/trades/recent?agent_id=${agentId}&limit=10`);
    if (!resp.ok) return;
    const data = await resp.json();
    if (state.agents[agentId]) {
      state.agents[agentId].last_trades = data.trades || [];
    }
  } catch (e) {
    console.warn(`Erro ao carregar trades recentes do agente ${agentId}:`, e);
  }
}

async function loadRecentTradesFromAPI() {
  try {
    const resp = await fetch('/api/v1/trades?limit=100&include_open=true');
    if (!resp.ok) return;
    const data = await resp.json();
    const trades = data.trades || [];
    // Separar pendentes (em curso) dos finalizados
    const pending = trades.filter(t => t.result === 'pending');
    const finished = trades.filter(t => t.result !== 'pending');
    // Ordenação: pendentes no topo, finalizados por data desc
    finished.sort((a, b) => {
      const ta = a.opened_at || a.closed_at || '';
      const tb = b.opened_at || b.closed_at || '';
      return tb.localeCompare(ta);
    });
    const sorted = [...pending, ...finished];
    // renderRecentTradesTable já inicia os countdowns e registra pendingTradeRows
    renderRecentTradesTable(sorted);
    // Atualizar timeline e gráficos auxiliares
    renderTradesTimeline(sorted);
    refreshAuxCharts(trades);
  } catch (e) {
    console.warn('Erro ao carregar trades históricos:', e);
  }
}

// ─── Timeline de Entradas ────────────────────────────────

// Estado da timeline
const timelineState = {
  cards: {},        // { trackingKey: { el, contractId, agentId, direction, openedAt, durationSecs } }
  countdowns: {},   // { trackingKey: intervalId }
};

/**
 * Renderiza a timeline de entradas a partir de um array de trades.
 * Mostra as entradas das últimas 6h, com os mais recentes à direita.
 */
function renderTradesTimeline(trades) {
  const track = document.getElementById('tradesTimelineTrack');
  if (!track) return;

  // Filtrar para últimas 6h
  const cutoff = Date.now() - 6 * 60 * 60 * 1000;
  const recent = (trades || [])
    .filter(t => {
      const ts = t.opened_at ? new Date(t.opened_at).getTime() : 0;
      return ts >= cutoff;
    })
    .sort((a, b) => {
      const ta = a.opened_at || '';
      const tb = b.opened_at || '';
      return ta.localeCompare(tb); // mais antigo primeiro (esq → dir)
    });

  // Parar countdowns antigos
  Object.values(timelineState.countdowns).forEach(clearInterval);
  timelineState.countdowns = {};
  timelineState.cards = {};

  track.innerHTML = '';

  if (recent.length === 0) {
    track.innerHTML = '<div class="trades-timeline-empty">Nenhuma entrada nas últimas 6h...</div>';
    return;
  }

  recent.forEach(t => {
    const card = _createTimelineCard(t);
    track.appendChild(card);
    // Scroll para o final (mais recentes à direita)
    track.scrollLeft = track.scrollWidth;
  });
}

/**
 * Adiciona um card de trade pendente no início da timeline (em tempo real).
 */
function prependTimelineCard(agentId, payload) {
  const track = document.getElementById('tradesTimelineTrack');
  if (!track) return;

  // Remover placeholder vazio se existir
  const empty = track.querySelector('.trades-timeline-empty');
  if (empty) empty.remove();

  const pseudoTrade = {
    id: payload.db_id,
    agent_id: agentId,
    direction: payload.direction,
    stake: payload.stake,
    result: 'pending',
    opened_at: payload.opened_at || new Date().toISOString(),
    contract_id: payload.contract_id,
    duration_seconds: payload.duration_seconds,
  };

  const card = _createTimelineCard(pseudoTrade);
  track.appendChild(card);
  // Scroll para o final
  track.scrollLeft = track.scrollWidth;

  // Limitar a 50 cards
  const cards = track.querySelectorAll('.tl-card');
  if (cards.length > 50) cards[0].remove();
}

/**
 * Resolve um card pendente da timeline (transforma em win/loss).
 */
function resolveTimelineCard(agentId, payload) {
  const dbKey = payload.db_id != null ? `db_${payload.db_id}` : null;
  const contractKey = payload.contract_id;

  let cardEl = null;
  if (dbKey && timelineState.cards[dbKey]) cardEl = timelineState.cards[dbKey].el;
  if (!cardEl && contractKey && timelineState.cards[contractKey]) cardEl = timelineState.cards[contractKey].el;
  if (!cardEl) {
    // Fallback: buscar por agentId
    const agentKey = `agent_${agentId}`;
    if (timelineState.cards[agentKey]) cardEl = timelineState.cards[agentKey].el;
  }

  if (!cardEl || !cardEl.isConnected) return;

  const isWin = payload.result === 'won';
  const profit = payload.profit || 0;
  const sign = profit >= 0 ? '+' : '';

  // Parar countdown
  if (dbKey && timelineState.countdowns[dbKey]) {
    clearInterval(timelineState.countdowns[dbKey]);
    delete timelineState.countdowns[dbKey];
  }

  // Atualizar card
  cardEl.className = `tl-card ${isWin ? 'win' : 'loss'}`;
  const resultEl = cardEl.querySelector('.tl-card-result');
  if (resultEl) {
    resultEl.className = `tl-card-result ${isWin ? 'win' : 'loss'}`;
    resultEl.textContent = `${isWin ? '✅' : '❌'} ${sign}$${Math.abs(profit).toFixed(2)}`;
  }

  // Atualizar tooltip
  _updateTimelineTooltip(cardEl, agentId, payload);

  // Flash
  cardEl.style.transform = 'scale(1.1)';
  setTimeout(() => { cardEl.style.transform = ''; }, 300);
}

/**
 * Cria um elemento card para a timeline.
 */
function _createTimelineCard(trade) {
  const isPending = trade.result === 'pending';
  const isWin = trade.result === 'won';
  const isLoss = trade.result === 'lost';

  const agentId = trade.agent_id;
  const agentName = state.agents[agentId]?.name || agentId || '—';
  const agentShort = agentName.split(' ')[0] || agentName;

  const isCall = trade.direction === 'CALL' || trade.direction === 'MULTUP';
  const dirIcon = isPending ? '⏳' : isCall ? '▲' : '▼';
  const dirClass = isPending ? 'pending' : isCall ? 'call' : 'put';

  const timeStr = trade.opened_at
    ? new Date(trade.opened_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—';

  const profit = trade.profit;
  const sign = profit != null && profit >= 0 ? '+' : '';

  let resultContent = '';
  if (isPending) {
    const durationSecs = trade.duration_seconds
      || (state.agents[agentId]?.timeframe_minutes || 5) * 60;
    const remaining = _calcRemainingSeconds(trade.opened_at, durationSecs);
    resultContent = `<span class="tl-card-result countdown" id="tl-cd-${trade.id || agentId}">${formatCountdown(remaining)}</span>`;
  } else if (isWin) {
    resultContent = `<span class="tl-card-result win">✅ ${profit != null ? sign + '$' + Math.abs(profit).toFixed(2) : 'WIN'}</span>`;
  } else if (isLoss) {
    resultContent = `<span class="tl-card-result loss">❌ ${profit != null ? sign + '$' + Math.abs(profit).toFixed(2) : 'LOST'}</span>`;
  } else {
    resultContent = `<span class="tl-card-result" style="color:var(--text-muted)">—</span>`;
  }

  const card = document.createElement('div');
  card.className = `tl-card ${isPending ? 'pending' : isWin ? 'win' : isLoss ? 'loss' : ''}`;
  card.innerHTML = `
    <div class="tl-card-dir ${dirClass}">${dirIcon}</div>
    <div class="tl-card-agent">${escHtml(agentShort)}</div>
    <div class="tl-card-time">${timeStr}</div>
    ${resultContent}
    <div class="tl-card-stake">$${(trade.stake || 0).toFixed(2)}</div>
    <div class="tl-card-tooltip">
      <strong>${escHtml(agentName)}</strong><br>
      ${isCall ? '▲ CALL' : '▼ PUT'}<br>
      Stake: $${(trade.stake || 0).toFixed(2)}<br>
      ${trade.opened_at ? '⏰ ' + new Date(trade.opened_at).toLocaleString('pt-BR') : ''}
      ${profit != null ? '<br>' + (isWin ? '✅' : '❌') + ' ' + sign + '$' + Math.abs(profit).toFixed(2) : ''}
    </div>`;

  // Registrar no estado
  const trackingKey = trade.id != null ? `db_${trade.id}` : (trade.contract_id || `agent_${agentId}`);
  timelineState.cards[trackingKey] = { el: card, trade };

  // Iniciar countdown se pendente
  if (isPending) {
    const durationSecs = trade.duration_seconds
      || (state.agents[agentId]?.timeframe_minutes || 5) * 60;
    _startTimelineCountdown(trackingKey, trade.id || agentId, trade.opened_at, durationSecs);
  }

  return card;
}

function _updateTimelineTooltip(cardEl, agentId, payload) {
  const tip = cardEl.querySelector('.tl-card-tooltip');
  if (!tip) return;
  const agentName = state.agents[agentId]?.name || agentId || '—';
  const isCall = payload.direction === 'CALL' || payload.direction === 'MULTUP';
  const isWin = payload.result === 'won';
  const profit = payload.profit || 0;
  const sign = profit >= 0 ? '+' : '';
  tip.innerHTML = `
    <strong>${escHtml(agentName)}</strong><br>
    ${isCall ? '▲ CALL' : '▼ PUT'}<br>
    Stake: $${(payload.stake || 0).toFixed(2)}<br>
    ${payload.opened_at ? '⏰ ' + new Date(payload.opened_at).toLocaleString('pt-BR') : ''}
    <br>${isWin ? '✅' : '❌'} ${sign}$${Math.abs(profit).toFixed(2)}`;
}

function _startTimelineCountdown(trackingKey, elemKey, openedAt, durationSecs) {
  // Parar anterior se existir
  if (timelineState.countdowns[trackingKey]) {
    clearInterval(timelineState.countdowns[trackingKey]);
  }

  const tick = () => {
    const el = document.getElementById(`tl-cd-${elemKey}`);
    if (!el) {
      clearInterval(timelineState.countdowns[trackingKey]);
      delete timelineState.countdowns[trackingKey];
      return;
    }
    const remaining = _calcRemainingSeconds(openedAt, durationSecs);
    el.textContent = remaining > 0 ? formatCountdown(remaining) : '⌛';
    el.className = `tl-card-result countdown${remaining <= 15 ? ' urgent' : ''}`;
  };

  tick();
  timelineState.countdowns[trackingKey] = setInterval(tick, 1000);
}

// ─── Gráficos Auxiliares ─────────────────────────────────

/**
 * Atualiza Win Rate Donut e Trades/Hora com dados dos agentes ou trades fornecidos.
 */
function refreshAuxCharts(tradesOverride) {
  // Calcular wins/losses totais dos agentes
  const agents = Object.values(state.agents);
  const totalWins = agents.reduce((s, a) => s + (a.wins || 0), 0);
  const totalLosses = agents.reduce((s, a) => s + (a.losses || 0), 0);
  updateWinRateChart(totalWins, totalLosses);

  // Se temos trades da API, usar para o gráfico de trades/hora
  if (tradesOverride && Array.isArray(tradesOverride)) {
    updateTradesPerHour(tradesOverride);
  }
}

async function loadAgentChart(agentId, agentName) {
  try {
    const data = await fetchPnlHistory(agentId, 100);
    // API retorna array diretamente: [...] ou objeto legado: { data_points: [...] }
    const dataPoints = Array.isArray(data) ? data : (data.data_points || []);
    if (dataPoints.length > 0) {
      loadAgentPnlHistory(agentId, agentName, dataPoints);
    } else {
      loadAgentPnlHistory(agentId, agentName, [{
        timestamp: new Date().toISOString(),
        cumulative_pnl: 0,
      }]);
    }
  } catch (e) {
    console.warn(`Erro ao carregar P&L do agente ${agentId}:`, e);
  }
}

// ─── Modelos/Estratégias ────────────────────────────────
async function fetchModelsForTf(durationMinutes) {
  const cached = state.modelsCache[durationMinutes];
  if (cached) return cached;

  try {
    const resp = await fetch(`/api/v1/models/performance?duration_minutes=${durationMinutes}`);
    const data = await resp.json();
    const models = data.models || [];
    state.modelsCache[durationMinutes] = models;
    return models;
  } catch (e) {
    console.error('Erro ao carregar modelos:', e);
    return [];
  }
}

// Carrega modelos para um agente e injeta no card
async function loadModelsForAgent(agentId) {
  const agent = state.agents[agentId];
  if (!agent) return;

  const tf = agent.timeframe_minutes || 5;
  const models = await fetchModelsForTf(tf);
  renderStrategySelector(agentId, agent, models);
}

function renderStrategySelector(agentId, agent, models) {
  const container = document.getElementById(`strategy-selector-${agentId}`);
  if (!container) return;

  const currentStrategy = agent.strategy || 'rsi_ema';
  const sp = agent.strategy_params || {};
  const isAutoMode = sp.auto_select === true;

  const statusMap = { good: 'wr-good', ok: 'wr-ok', poor: 'wr-poor' };

  const modelItems = models.map(m => {
    const isSelected = m.name === currentStrategy;
    const wrClass = statusMap[m.status] || 'wr-ok';
    const wrPct = (m.win_rate * 100).toFixed(1);
    const warningIcon = m.status === 'poor' ? ' ⚠️' : '';
    const dotClass = `dot-${m.status}`;
    return `
      <div class="strategy-option ${isSelected ? 'selected' : ''}"
           onclick="handleSelectStrategy('${agentId}', '${m.name}')">
        <div class="strategy-option-left">
          <span class="strategy-dot ${dotClass}"></span>
          <span class="strategy-name">${escHtml(m.label)}${warningIcon}</span>
        </div>
        <span class="strategy-wr ${wrClass}">${wrPct}%</span>
      </div>`;
  }).join('');

  container.innerHTML = `
    <div class="strategy-section">
      <div class="strategy-header">
        <span class="strategy-label">Modelo</span>
        <div class="strategy-toggle">
          <button class="toggle-btn ${isAutoMode ? 'active-auto' : ''}"
                  onclick="handleAutoSelect('${agentId}')" title="Seleção automática do melhor modelo">
            🤖 Auto
          </button>
          <button class="toggle-btn ${!isAutoMode ? 'active-manual' : ''}"
                  onclick="handleManualToggle('${agentId}')">
            Manual
          </button>
        </div>
      </div>
      ${models.length > 0
        ? `<div class="strategy-list">${modelItems}</div>`
        : `<div class="strategy-loading">Carregando modelos...</div>`
      }
    </div>`;
}

window.handleSelectStrategy = async (agentId, strategyName) => {
  try {
    const resp = await fetch(`/api/v1/agents/${agentId}/strategy`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy: strategyName, auto_select: false }),
    });
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();

    if (state.agents[agentId]) {
      state.agents[agentId].strategy = strategyName;
      state.agents[agentId].strategy_params = {
        ...state.agents[agentId].strategy_params,
        auto_select: false,
      };
    }

    // Invalidar cache de modelos para recarregar is_current
    const tf = state.agents[agentId]?.timeframe_minutes || 5;
    delete state.modelsCache[tf];

    updateAgentCard(agentId);
    await loadModelsForAgent(agentId);
    showToast('✅ Estratégia Alterada', `${agentId}: ${strategyName}`, 'success');
  } catch (e) {
    showToast('❌ Erro', `Falha ao alterar estratégia: ${e.message}`, 'error');
  }
};

window.handleAutoSelect = async (agentId) => {
  showToast('🤖 Auto-Select', 'Analisando performance dos modelos...', 'info');
  try {
    const resp = await fetch(`/api/v1/agents/${agentId}/auto-select-strategy`, {
      method: 'POST',
    });
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();

    if (state.agents[agentId]) {
      state.agents[agentId].strategy = data.selected_strategy;
      state.agents[agentId].strategy_params = {
        ...state.agents[agentId].strategy_params,
        auto_select: true,
      };
    }

    const tf = state.agents[agentId]?.timeframe_minutes || 5;
    delete state.modelsCache[tf];

    updateAgentCard(agentId);
    await loadModelsForAgent(agentId);
    showToast(
      '🤖 Melhor Modelo Selecionado',
      `${data.selected_label} (${(data.win_rate * 100).toFixed(1)}% win rate)`,
      'success'
    );
  } catch (e) {
    showToast('❌ Erro', `Falha no auto-select: ${e.message}`, 'error');
  }
};

// ─── Auto-Select de Símbolo ─────────────────────────────
window.autoSelectSymbol = async (agentId) => {
  const agent = state.agents[agentId];
  if (!agent) return;

  const scoreEl = document.getElementById(`symbol-score-${agentId}`);
  const rankingsEl = document.getElementById(`symbol-rankings-${agentId}`);

  if (scoreEl) {
    scoreEl.textContent = '⏳ Calculando...';
    scoreEl.className = 'symbol-score-badge score-neutral';
  }
  if (rankingsEl) rankingsEl.innerHTML = '<div class="symbol-loading">Analisando símbolos...</div>';

  showToast('🎯 Auto-Select Símbolo', 'Calculando EV dos símbolos...', 'info');

  try {
    const resp = await fetch(`/api/v1/agents/${agentId}/auto-select-symbol`, {
      method: 'POST',
    });
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();

    // Atualizar estado local
    if (state.agents[agentId]) {
      state.agents[agentId].symbol = data.new_symbol;
    }

    // Atualizar UI do card
    updateAgentCard(agentId);

    // Renderizar mini-rankings
    const symRankEl = document.getElementById(`symbol-rankings-${agentId}`);
    if (symRankEl && data.rankings) {
      renderSymbolRankingsMini(symRankEl, data.rankings.slice(0, 3), data.new_symbol);
    }

    // Atualizar score badge
    const newScoreEl = document.getElementById(`symbol-score-${agentId}`);
    if (newScoreEl) {
      const evPct = data.ev_pct;
      newScoreEl.textContent = `EV: ${evPct >= 0 ? '+' : ''}${evPct.toFixed(1)}%`;
      newScoreEl.className = `symbol-score-badge ${evPct >= 8 ? 'score-good' : evPct >= 4 ? 'score-ok' : 'score-bad'}`;
    }

    const changeMsg = data.changed
      ? `${data.old_symbol} → ${data.new_symbol} (EV: +${data.ev_pct.toFixed(1)}%)`
      : `${data.new_symbol} mantido (já é o melhor, EV: +${data.ev_pct.toFixed(1)}%)`;

    showToast('🎯 Símbolo Selecionado', changeMsg, 'success');
  } catch (e) {
    if (scoreEl) {
      scoreEl.textContent = 'Erro';
      scoreEl.className = 'symbol-score-badge score-bad';
    }
    showToast('❌ Erro', `Falha no auto-select de símbolo: ${e.message}`, 'error');
  }
};

function renderSymbolRankingsMini(container, rankings, currentSymbol) {
  const medals = ['🥇', '🥈', '🥉'];
  container.innerHTML = rankings.map((r, i) => {
    const evPct = r.ev_pct !== undefined ? r.ev_pct : (r.score * 100);
    const evClass = evPct >= 8 ? 'score-good' : evPct >= 4 ? 'score-ok' : 'score-bad';
    const isActive = r.symbol === currentSymbol ? ' active' : '';
    return `
      <div class="symbol-rank-item${isActive}">
        <span class="rank-medal">${medals[i] || (i + 1)}</span>
        <span class="rank-sym">${escHtml(r.symbol)}</span>
        <span class="symbol-score-badge ${evClass}">EV: ${evPct >= 0 ? '+' : ''}${evPct.toFixed(1)}%</span>
      </div>`;
  }).join('');
}

window.handleManualToggle = async (agentId) => {
  if (!state.agents[agentId]) return;
  state.agents[agentId].strategy_params = {
    ...state.agents[agentId].strategy_params,
    auto_select: false,
  };
  const tf = state.agents[agentId].timeframe_minutes || 5;
  delete state.modelsCache[tf];
  await loadModelsForAgent(agentId);
};

// ─── WebSocket ──────────────────────────────────────────
function connectWebSocket() {
  const wsUrl = `ws://${window.location.host}/ws`;
  wsClient = new WSClient(wsUrl);

  wsClient
    .on('_connected', () => updateWsStatus(true))
    .on('_disconnected', () => updateWsStatus(false))
    .on('full_state', (payload) => {
      const agents = payload.agents || [];
      // Preservar last_trades existentes antes de sobrescrever o estado
      const previousLastTrades = {};
      Object.entries(state.agents).forEach(([id, a]) => {
        if (a.last_trades && a.last_trades.length > 0) {
          previousLastTrades[id] = a.last_trades;
        }
      });
      state.agents = {};
      agents.forEach(a => {
        state.agents[a.id] = a;
        // Restaurar last_trades preservados se o payload não trouxer
        if (!a.last_trades || a.last_trades.length === 0) {
          if (previousLastTrades[a.id]) {
            state.agents[a.id].last_trades = previousLastTrades[a.id];
          }
        }
      });
      renderAgentCards();
      // BUG FIX #1: renderAgentCards() reconstrói todo o DOM e apaga os countdowns
      // restaurados do localStorage. Re-restaurar após cada renderização completa.
      restoreCountdownsFromStorage();
    })
    .on('agent_update', (payload) => {
      if (state.agents[payload.agent_id]) {
        const agent = state.agents[payload.agent_id];
        Object.assign(agent, {
          status: payload.status,
          total_trades: payload.total_trades,
          wins: payload.wins,
          losses: payload.losses,
          total_pnl: payload.total_pnl,
          win_rate: payload.win_rate,
          consecutive_losses: payload.consecutive_losses,
          last_trade_at: payload.last_trade_at,
        });
        // Atualizar linha do gráfico P&L com o novo ponto acumulado
        if (payload.total_pnl != null && payload.last_trade_at) {
          addPnlPoint(payload.agent_id, payload.total_pnl, payload.last_trade_at);
        }
        updateAgentCard(payload.agent_id);
        updateOverviewStats();
      }
    })
    .on('trade_closed', (payload) => {
      const agentId = payload.agent_id;
      // Limpar countdown ao fechar o trade (no card)
      clearCountdownUI(agentId);
      // Parar countdown da tabela pelo db_id (mais confiável que contract_id)
      if (payload.db_id != null) {
        _stopTableCountdown(`db_${payload.db_id}`);
      }
      if (payload.contract_id) {
        _stopTableCountdown(payload.contract_id);
      }
      if (state.agents[agentId]) {
        // Resolver card na timeline de entradas
        resolveTimelineCard(agentId, payload);

        const card = document.getElementById(`agent-card-${agentId}`);
        if (card) {
          card.classList.remove('flash-win', 'flash-loss');
          void card.offsetWidth;
          card.classList.add(payload.result === 'won' ? 'flash-win' : 'flash-loss');
        }

        // Atualizar last_trades do agente para os quadradinhos
        const agent = state.agents[agentId];
        if (!agent.last_trades) agent.last_trades = [];
        agent.last_trades.push({
          direction: payload.direction,
          result: payload.result,
          profit: payload.profit,
          opened_at: payload.opened_at || new Date().toISOString(),
        });
        // Manter apenas os últimos 10
        if (agent.last_trades.length > 10) {
          agent.last_trades = agent.last_trades.slice(-10);
        }
        // Atualizar quadradinhos no card sem re-renderizar tudo
        updateTradeHistoryDots(agentId);

        // ── Resolver linha pendente (actualiza in-place) ou inserir nova ──
        resolveTradeRow(agentId, payload);

        const sign = payload.profit >= 0 ? '+' : '';
        const emoji = payload.result === 'won' ? '✅' : '❌';
        showToast(
          `${emoji} ${state.agents[agentId]?.name || agentId}`,
          `${payload.result === 'won' ? 'Ganhou' : 'Perdeu'} ${sign}$${(payload.profit || 0).toFixed(2)}`,
          payload.result === 'won' ? 'success' : 'error'
        );

        // Atualizar gráficos auxiliares (win rate)
        refreshAuxCharts();
      }
    })
    .on('trade_executed', (payload) => {
      const agentId = payload.agent_id;
      // Iniciar countdown visual no card
      if (payload.duration_seconds && agentId) {
        startCountdownUI(agentId, payload.duration_seconds, payload.direction);
      }
      // Adicionar card na timeline de entradas
      if (agentId) {
        prependTimelineCard(agentId, payload);
      }
      // ── Inserir linha pendente na tabela de trades ──
      if (agentId) {
        prependPendingTradeRow(agentId, payload);
      }
    })
    .on('trade_countdown', (payload) => {
      updateCountdownUI(payload.agent_id, payload.remaining_seconds, payload.total_seconds, payload.progress_pct);
      // Atualizar countdown na barra do gráfico
      if (payload.contract_id) {
        updateTradeCountdown(payload.contract_id, payload.remaining_seconds);
      }
    })
    .on('agent_created', () => { loadInitialData(); })
    .on('agent_deleted', (payload) => {
      const agentId = payload.agent_id;
      delete state.agents[agentId];
      removeAgentFromChart(agentId);
      const card = document.getElementById(`agent-card-${agentId}`);
      if (card) card.remove();
      checkEmptyState();
    })
    .on('agent_status_changed', (payload) => {
      if (state.agents[payload.agent_id]) {
        state.agents[payload.agent_id].status = payload.new_status;
        updateAgentCard(payload.agent_id);
      }
    })
    .on('error', (payload) => {
      showToast('Erro do Sistema', payload.message || 'Erro desconhecido', 'error');
    })
    .on('pong', () => { /* keepalive ok */ })
    .on('reload', (payload) => {
      const files = (payload.files || []).join(', ');
      console.log(`[HotReload] Arquivos alterados: ${files || '?'} → recarregando...`);
      // Aguarda 150 ms para garantir que o servidor já serviu os novos arquivos
      setTimeout(() => window.location.reload(), 150);
    })
    .on('bot_tasks_update', (payload) => {
      renderBotTasks(payload.tasks || []);
    });

  wsClient.connect();
}

function updateWsStatus(connected) {
  const dot = document.getElementById('wsDot');
  const text = document.getElementById('wsText');
  if (dot) dot.className = 'ws-dot ' + (connected ? 'connected' : 'disconnected');
  if (text) text.textContent = connected ? 'Conectado' : 'Reconectando...';
}

// ─── Bot Diagnostics ────────────────────────────────────
/**
 * Renderiza as tarefas de diagnóstico automático do bot
 * no painel #botDiagnosticsSection da sidebar de Backlog.
 */
function renderBotTasks(tasks) {
  const section = document.getElementById('botDiagnosticsSection');
  const list    = document.getElementById('botDiagnosticsList');
  const tsEl    = document.getElementById('botDiagTimestamp');
  if (!section || !list) return;

  section.style.display = tasks.length > 0 ? '' : 'none';
  if (tsEl) {
    const now = new Date();
    tsEl.textContent = `Atualizado ${now.toLocaleTimeString('pt-BR')}`;
  }

  const prioLabel = { high: '🔴 Alta', medium: '🟡 Média', low: '🟢 OK' };

  list.innerHTML = tasks.map(t => `
    <div class="bot-diag-item prio-${t.priority || 'low'}">
      <div class="bot-diag-item-top">
        <span class="bot-diag-badge ${t.priority || 'low'}">${prioLabel[t.priority] || t.priority}</span>
        <span class="bot-diag-item-title">${escHtml(t.title)}</span>
      </div>
      ${t.description ? `<div class="bot-diag-item-desc">${escHtml(t.description)}</div>` : ''}
    </div>`).join('');

  // Atualizar badge da sidebar com tarefas críticas/médias
  const alerts = tasks.filter(t => t.priority === 'high' || t.priority === 'medium');
  const badge  = document.getElementById('leftDevBadge');
  if (badge) {
    if (alerts.length > 0) {
      badge.textContent = alerts.length;
      badge.style.display = '';
    } else {
      badge.style.display = 'none';
    }
  }
}

// ─── Overview Stats ─────────────────────────────────────
function updateOverviewStats() {
  const agents = Object.values(state.agents);
  const running = agents.filter(a => a.status === 'running').length;
  const totalPnl = agents.reduce((s, a) => s + (a.total_pnl || 0), 0);
  const totalTrades = agents.reduce((s, a) => s + (a.total_trades || 0), 0);
  const totalWins = agents.reduce((s, a) => s + (a.wins || 0), 0);
  const winRate = totalTrades > 0 ? (totalWins / totalTrades * 100).toFixed(1) : '0.0';

  const pnlEl = document.getElementById('overviewPnl');
  const wrEl = document.getElementById('overviewWinRate');
  const tradesEl = document.getElementById('overviewTrades');
  const agentsEl = document.getElementById('overviewAgents');

  if (pnlEl) {
    const sign = totalPnl >= 0 ? '+' : '';
    pnlEl.textContent = `${sign}$${Math.abs(totalPnl).toFixed(2)}`;
    pnlEl.style.color = totalPnl >= 0 ? 'var(--color-profit)' : 'var(--color-loss)';
  }
  if (wrEl) wrEl.textContent = `${winRate}%`;
  if (tradesEl) tradesEl.textContent = totalTrades;
  if (agentsEl) agentsEl.textContent = `${running} / ${agents.length}`;
}

// ─── Renderização dos Cards ─────────────────────────────
function renderAgentCards() {
  const container = document.getElementById('agentsList');
  if (!container) return;

  container.innerHTML = '';
  const agents = Object.values(state.agents);

  if (agents.length === 0) {
    container.innerHTML = `
      <div class="agent-card-add" onclick="document.getElementById('btnNewAgent').click()">
        <span class="agent-card-add-icon">➕</span>
        <span class="agent-card-add-label">Novo Agente</span>
      </div>`;
    updateOverviewStats();
    return;
  }

  agents.forEach(agent => {
    container.appendChild(createAgentCardElement(agent));
    // Carregar modelos em background
    loadModelsForAgent(agent.id);
  });

  // Card "Novo Agente" no final do grid
  const addCard = document.createElement('div');
  addCard.className = 'agent-card-add';
  addCard.onclick = () => document.getElementById('btnNewAgent').click();
  addCard.innerHTML = `
    <span class="agent-card-add-icon">➕</span>
    <span class="agent-card-add-label">Novo Agente</span>`;
  container.appendChild(addCard);

  updateOverviewStats();
  // Atualizar dev panel se estiver aberto
  window.refreshDevPanel?.();
}

function createAgentCardElement(agent) {
  const div = document.createElement('div');
  div.id = `agent-card-${agent.id}`;
  div.className = `agent-card status-${agent.status}`;
  div.innerHTML = buildAgentCardHTML(agent);
  return div;
}

function buildAgentCardHTML(agent) {
  const pnl = agent.total_pnl || 0;
  const winRate = ((agent.win_rate || 0) * 100).toFixed(1);
  const pnlClass = pnl >= 0 ? 'profit' : 'loss';
  const pnlSign = pnl >= 0 ? '+' : '';
  const statusLabel = {
    running:   '🟢 RUNNING',
    paused:    '🟡 PAUSED',
    stopped:   '⚫ STOPPED',
    error:     '🔴 ERROR',
    limit_hit: '🟠 LIMIT HIT',
  }[agent.status] || agent.status;

  const badgeClass = `badge-${agent.status}`;
  const recentDots = buildTradeHistoryHTML(agent.last_trades || [], agent);

  const isPaused = agent.status === 'paused';
  const isRunning = agent.status === 'running';

  // Botão pause/resume inline no header
  const toggleBtn = isRunning
    ? `<button class="btn btn-warning btn-sm btn-icon btn-pause" onclick="handlePauseAgent('${agent.id}')" title="Pausar">⏸</button>`
    : isPaused
    ? `<button class="btn btn-success btn-sm btn-icon btn-pause" onclick="handleResumeAgent('${agent.id}')" title="Retomar">▶</button>`
    : '';

  // ── PROBLEMA 1: Tempo relativo da última execução ──────────────
  // Exibido na área do countdown quando agente não está running.
  // Usa last_trade_at do agente ou o opened_at do trade mais recente.
  let lastExecHTML = '';
  if (!isRunning) {
    const lastAt = agent.last_trade_at
      || (agent.last_trades?.length > 0
          ? (agent.last_trades[agent.last_trades.length - 1]?.closed_at
            || agent.last_trades[agent.last_trades.length - 1]?.opened_at)
          : null);
    const relTime = lastAt ? relativeTime(lastAt) : null;
    const label = relTime
      ? `⏱ Última execução: ${relTime}`
      : '⏱ Sem execuções registradas';
    lastExecHTML = `<div class="last-execution-info" data-agent-id="${escHtml(agent.id)}" data-last-at="${escHtml(lastAt || '')}">${escHtml(label)}</div>`;
  }

  return `
    <div class="agent-card-header">
      <div class="agent-card-header-left">
        <div class="agent-name">${escHtml(agent.name)}</div>
        <div class="agent-meta">${escHtml(agent.symbol)} · ${agent.timeframe_minutes}min · ${escHtml(agent.strategy || 'rsi_ema')}</div>
      </div>
      <div class="agent-card-header-actions">
        <span class="agent-status-badge ${badgeClass}">${statusLabel}</span>
        ${toggleBtn}
        <button class="btn btn-secondary btn-sm btn-icon btn-edit" onclick="handleEditAgent('${agent.id}')" title="Editar">✏️</button>
        <button class="btn btn-danger btn-sm btn-icon btn-delete" onclick="handleDeleteAgent('${agent.id}')" title="Deletar">🗑️</button>
      </div>
    </div>
    <div class="agent-stats">
      <div class="stat-item">
        <div class="stat-label">P&L Total</div>
        <div class="stat-value ${pnlClass}">${pnlSign}$${Math.abs(pnl).toFixed(2)}</div>
      </div>
      <div class="stat-item">
        <div class="stat-label">Win Rate</div>
        <div class="stat-value">${winRate}%</div>
      </div>
      <div class="stat-item">
        <div class="stat-label">Trades</div>
        <div class="stat-value">${agent.total_trades || 0}</div>
      </div>
      <div class="stat-item">
        <div class="stat-label">Stake</div>
        <div class="stat-value">$${(agent.stake || 0).toFixed(2)}</div>
      </div>
    </div>
    ${lastExecHTML}
    <div id="strategy-selector-${agent.id}">
      <div class="strategy-section">
        <div class="strategy-header">
          <span class="strategy-label">Modelo</span>
        </div>
        <div class="strategy-loading">Carregando modelos...</div>
      </div>
    </div>
    <div id="symbol-selector-${agent.id}">
      <div class="symbol-section">
        <div class="symbol-section-header">
          <span class="strategy-label">Símbolo</span>
          <button class="toggle-btn" onclick="autoSelectSymbol('${agent.id}')" title="Selecionar símbolo com maior EV automaticamente">
            🎯 Auto
          </button>
        </div>
        <div class="symbol-current">
          <span class="symbol-name-badge">${escHtml(agent.symbol || 'R_75')}</span>
          <span class="symbol-score-badge score-neutral" id="symbol-score-${agent.id}">Calcular EV</span>
        </div>
        <div class="symbol-rankings-mini" id="symbol-rankings-${agent.id}"></div>
      </div>
    </div>
    <div class="trade-history-section" id="trade-history-${agent.id}">
      <div class="trade-history-label">Histórico</div>
      <div class="trade-history">
        ${recentDots}
      </div>
    </div>`;
}

function buildTradeHistoryHTML(trades, agent) {
  // Preencher com até 10 slots: trades reais + placeholders vazios
  const slots = [];
  const filled = (trades || []).slice(-10); // últimos 10, mais recente no final
  // Preencher placeholders à esquerda se necessário
  const emptyCount = 10 - filled.length;
  for (let i = 0; i < emptyCount; i++) {
    slots.push('<div class="trade-sq empty" title="Sem trade"></div>');
  }
  filled.forEach(t => {
    const cls = t.result === 'won' ? 'win' : t.result === 'lost' ? 'loss' : 'empty';
    const titleStr = buildTradeTooltip(t, agent);
    slots.push(`<div class="trade-sq ${cls}" title="${escHtml(titleStr)}"></div>`);
  });
  return slots.join('');
}

/**
 * Monta o texto de tooltip para um quadradinho de trade.
 * Formato multi-linha compatível com o atributo title nativo do HTML.
 * @param {object} t   - trade object (result, direction, profit, opened_at, stake, strategy, symbol)
 * @param {object} [a] - agente (para preencher strategy/symbol se não vier no trade)
 */
function buildTradeTooltip(t, a) {
  const lines = [];

  // 📅 Data/hora completa
  if (t.opened_at || t.closed_at) {
    const dt = new Date(t.opened_at || t.closed_at);
    const dateStr = dt.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
    const timeStr = dt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    lines.push(`📅 ${dateStr} ${timeStr}`);
  }

  // 📊 Estratégia
  const strategy = t.strategy || a?.strategy;
  if (strategy) lines.push(`📊 Estratégia: ${strategy}`);

  // 🪙 Símbolo
  const symbol = t.symbol || a?.symbol;
  if (symbol) lines.push(`🪙 Símbolo: ${symbol}`);

  // ↕ Direção
  if (t.direction) {
    const isCall = t.direction === 'CALL' || t.direction === 'MULTUP';
    lines.push(`${isCall ? '▲' : '▼'} Direção: ${t.direction}`);
  }

  // 💰 Stake
  const stake = t.stake != null ? t.stake : a?.stake;
  if (stake != null) lines.push(`💰 Stake: $${Number(stake).toFixed(2)}`);

  // ✅/❌ Resultado
  if (t.result) {
    const isWon = t.result === 'won';
    const resultLabel = isWon ? 'WIN' : 'LOST';
    const profitStr = t.profit != null
      ? ` (${t.profit >= 0 ? '+' : ''}$${Math.abs(t.profit).toFixed(2)})`
      : '';
    lines.push(`${isWon ? '✅' : '❌'} Resultado: ${resultLabel}${profitStr}`);
  }

  return lines.length > 0 ? lines.join('\n') : 'Sem dados';
}

function updateTradeHistoryDots(agentId) {
  const agent = state.agents[agentId];
  if (!agent) return;
  const section = document.getElementById(`trade-history-${agentId}`);
  if (!section) return;
  const container = section.querySelector('.trade-history');
  if (!container) return;

  const trades = agent.last_trades || [];
  const filled = trades.slice(-10);

  // Se o container está vazio ou tem apenas placeholders, fazer rebuild completo
  const existingSquares = container.querySelectorAll('.trade-sq');
  if (existingSquares.length === 0) {
    container.innerHTML = buildTradeHistoryHTML(trades, agent);
    return;
  }

  // Animação: remover o mais antigo e adicionar o novo no final
  const firstEl = container.querySelector('.trade-sq');
  if (firstEl) {
    firstEl.style.transition = 'opacity 0.2s, transform 0.2s';
    firstEl.style.opacity = '0';
    firstEl.style.transform = 'scale(0.5)';
    setTimeout(() => firstEl.remove(), 200);
  }

  // Adicionar novo quadradinho ao final com tooltip enriquecido
  if (filled.length > 0) {
    const lastTrade = filled[filled.length - 1];
    const cls = lastTrade.result === 'won' ? 'win' : lastTrade.result === 'lost' ? 'loss' : 'empty';
    const titleStr = buildTradeTooltip(lastTrade, agent);

    const newSq = document.createElement('div');
    newSq.className = `trade-sq ${cls} new-trade`;
    newSq.title = titleStr;
    container.appendChild(newSq);

    // Remover classe de animação após concluir
    setTimeout(() => newSq.classList.remove('new-trade'), 400);
  }
}

function updateAgentCard(agentId) {
  const agent = state.agents[agentId];
  if (!agent) return;

  const card = document.getElementById(`agent-card-${agentId}`);
  if (!card) return;

  card.className = `agent-card status-${agent.status}`;
  card.innerHTML = buildAgentCardHTML(agent);
  loadModelsForAgent(agentId);

  // BUG FIX #2: card.innerHTML sobrescreve todo o conteúdo do card, apagando
  // o elemento de countdown ativo. Re-inserir se houver um countdown no localStorage.
  _reinsertCountdownForAgent(agentId);
}

// ─── Countdown UI ────────────────────────────────────────
/**
 * Chave usada no localStorage para cada agente: bot_countdown_<agentId>
 * Valor armazenado: { direction, startedAt (ms epoch), totalSeconds }
 */
const COUNTDOWN_STORAGE_PREFIX = 'bot_countdown_';

function startCountdownUI(agentId, totalSeconds, direction) {
  // Criar ou atualizar o elemento de countdown no card
  const card = document.getElementById(`agent-card-${agentId}`);
  if (!card) return;

  // Remover countdown anterior se existir
  clearCountdownUI(agentId);

  // Criar elemento de countdown
  const cdEl = document.createElement('div');
  cdEl.id = `countdown-${agentId}`;
  cdEl.className = 'trade-countdown';
  const dirClass = direction === 'CALL' ? 'countdown-call' : 'countdown-put';
  const dirIcon = direction === 'CALL' ? '▲' : '▼';
  cdEl.innerHTML = `
    <div class="countdown-inner ${dirClass}">
      <span class="countdown-icon">${dirIcon} ${direction}</span>
      <span class="countdown-timer" id="countdown-timer-${agentId}">
        ${formatCountdown(totalSeconds)}
      </span>
      <div class="countdown-bar-wrap">
        <div class="countdown-bar" id="countdown-bar-${agentId}" style="width:0%"></div>
      </div>
    </div>`;

  // Inserir antes do selector de estratégia
  const stratSel = card.querySelector(`#strategy-selector-${agentId}`);
  if (stratSel) {
    card.insertBefore(cdEl, stratSel);
  } else {
    card.appendChild(cdEl);
  }

  state.activeCountdowns[agentId] = { total: totalSeconds };

  // Persistir no localStorage para sobreviver ao reload da página
  try {
    localStorage.setItem(
      `${COUNTDOWN_STORAGE_PREFIX}${agentId}`,
      JSON.stringify({
        direction,
        startedAt: Date.now(),
        totalSeconds,
      })
    );
  } catch (e) {
    console.warn('[countdown] Falha ao salvar no localStorage:', e);
  }
}

function updateCountdownUI(agentId, remaining, total, progressPct) {
  const timerEl = document.getElementById(`countdown-timer-${agentId}`);
  const barEl = document.getElementById(`countdown-bar-${agentId}`);

  if (timerEl) timerEl.textContent = formatCountdown(remaining);
  if (barEl) barEl.style.width = `${progressPct || 0}%`;

  // Mudar cor quando próximo do fim
  const cdEl = document.getElementById(`countdown-${agentId}`);
  if (cdEl && remaining <= 10) {
    cdEl.querySelector('.countdown-inner')?.classList.add('countdown-urgent');
  }
}

function clearCountdownUI(agentId) {
  const cdEl = document.getElementById(`countdown-${agentId}`);
  if (cdEl) cdEl.remove();
  delete state.activeCountdowns[agentId];

  // Remover do localStorage para não restaurar um trade já encerrado
  try {
    localStorage.removeItem(`${COUNTDOWN_STORAGE_PREFIX}${agentId}`);
  } catch (e) {
    console.warn('[countdown] Falha ao remover do localStorage:', e);
  }
}

/**
 * Re-insere o elemento de countdown no card de um agente específico,
 * lendo o estado salvo no localStorage. Usado tanto no restore inicial
 * quanto após reconstruções do card (updateAgentCard, full_state).
 *
 * NÃO chama startCountdownUI para não sobrescrever o startedAt original.
 */
function _reinsertCountdownForAgent(agentId) {
  const key = `${COUNTDOWN_STORAGE_PREFIX}${agentId}`;
  const raw = localStorage.getItem(key);
  if (!raw) return;

  const card = document.getElementById(`agent-card-${agentId}`);
  if (!card) {
    // Card não existe no DOM — entrada órfã, remover
    try { localStorage.removeItem(key); } catch (_) { /* noop */ }
    return;
  }

  try {
    const { direction, startedAt, totalSeconds } = JSON.parse(raw);
    const elapsedSeconds = (Date.now() - startedAt) / 1000;
    const remaining = Math.round(totalSeconds - elapsedSeconds);

    if (remaining <= 0) {
      // Contrato já expirou — limpar silenciosamente
      localStorage.removeItem(key);
      delete state.activeCountdowns[agentId];
      return;
    }

    // Remover countdown anterior se existir (pode ter ficado de uma renderização anterior)
    const existingCd = document.getElementById(`countdown-${agentId}`);
    if (existingCd) existingCd.remove();

    const cdEl = document.createElement('div');
    cdEl.id = `countdown-${agentId}`;
    cdEl.className = 'trade-countdown';
    const dirClass = direction === 'CALL' ? 'countdown-call' : 'countdown-put';
    const dirIcon = direction === 'CALL' ? '▲' : '▼';
    const progressPct = Math.min(100, ((totalSeconds - remaining) / totalSeconds) * 100);
    cdEl.innerHTML = `
      <div class="countdown-inner ${dirClass}${remaining <= 10 ? ' countdown-urgent' : ''}">
        <span class="countdown-icon">${dirIcon} ${direction}</span>
        <span class="countdown-timer" id="countdown-timer-${agentId}">
          ${formatCountdown(remaining)}
        </span>
        <div class="countdown-bar-wrap">
          <div class="countdown-bar" id="countdown-bar-${agentId}" style="width:${progressPct.toFixed(1)}%"></div>
        </div>
      </div>`;

    const stratSel = card.querySelector(`#strategy-selector-${agentId}`);
    if (stratSel) {
      card.insertBefore(cdEl, stratSel);
    } else {
      card.appendChild(cdEl);
    }

    // Registrar no estado para que updateCountdownUI funcione normalmente
    state.activeCountdowns[agentId] = { total: totalSeconds };

    console.info(`[countdown] Reinserido para agente ${agentId}: ${remaining}s restantes`);
  } catch (e) {
    console.warn(`[countdown] Erro ao reinserir countdown de ${agentId}:`, e);
    try { localStorage.removeItem(key); } catch (_) { /* noop */ }
  }
}

/**
 * Restaura countdowns ativos do localStorage ao recarregar a página
 * (ou após qualquer renderização completa dos cards).
 * Deve ser chamado APÓS renderAgentCards().
 * Entradas expiradas ou órfãs são removidas do localStorage silenciosamente.
 */
function restoreCountdownsFromStorage() {
  // Coletar chaves primeiro para evitar problemas ao modificar localStorage durante iteração
  const keys = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && key.startsWith(COUNTDOWN_STORAGE_PREFIX)) {
      keys.push(key);
    }
  }

  for (const key of keys) {
    const agentId = key.slice(COUNTDOWN_STORAGE_PREFIX.length);
    _reinsertCountdownForAgent(agentId);
  }
}

function formatCountdown(seconds) {
  if (seconds <= 0) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function checkEmptyState() {
  if (Object.keys(state.agents).length === 0) {
    renderAgentCards();
  }
}

// ─── Tempo Relativo ──────────────────────────────────────
/**
 * Retorna uma string de tempo relativo a partir de um ISO string.
 * < 60s    → "agora"
 * < 60min  → "Xm atrás"
 * < 24h    → "Xh atrás"
 * >= 24h   → "Xd atrás"
 */
function relativeTime(isoString) {
  if (!isoString) return null;
  const diffMs = Date.now() - new Date(isoString).getTime();
  if (diffMs < 0) return 'agora';
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return 'agora';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m atrás`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h atrás`;
  const diffDay = Math.floor(diffHour / 24);
  return `${diffDay}d atrás`;
}

/**
 * Atualiza todos os elementos .last-execution-info no DOM
 * recalculando o tempo relativo com base no atributo data-last-at.
 * Chamado pelo setInterval a cada minuto.
 */
function refreshLastExecutionTimes() {
  document.querySelectorAll('.last-execution-info[data-last-at]').forEach(el => {
    const lastAt = el.dataset.lastAt;
    const relTime = lastAt ? relativeTime(lastAt) : null;
    el.textContent = relTime
      ? `⏱ Última execução: ${relTime}`
      : '⏱ Sem execuções registradas';
  });
}

// ─── Helpers de direção e resultado ─────────────────────
function formatDirection(direction) {
  // Mapeia MULTUP/MULTDOWN → CALL/PUT
  if (!direction) return { label: '—', cls: '' };
  const isCall = direction === 'CALL' || direction === 'MULTUP';
  return {
    label: isCall ? '▲ CALL' : '▼ PUT',
    cls: isCall ? 'direction-call' : 'direction-put',
  };
}

function formatResult(result) {
  if (result === 'won')  return { label: 'WIN ✓',  cls: 'result-won' };
  if (result === 'lost') return { label: 'LOST ✗', cls: 'result-lost' };
  return { label: 'PENDING', cls: 'result-pending' };
}

function formatProfit(profit) {
  if (profit == null) return { label: '—', cls: '' };
  const sign = profit >= 0 ? '+' : '-';
  return {
    label: `${sign}$${Math.abs(profit).toFixed(2)}`,
    cls: profit >= 0 ? 'profit-positive' : 'profit-negative',
  };
}

// ─── Tabela de Últimas Operações ────────────────────────
/**
 * Renderiza a tabela de últimas operações a partir de um array de trades.
 * Para trades pendentes (em curso), usa t.id (db_id) como chave de rastreamento
 * para que trade_closed possa localizar e atualizar a linha correta sem duplicatas.
 */
function renderRecentTradesTable(trades) {
  const tbody = document.getElementById('recentTradesTbody');
  if (!tbody) return;

  // Parar todos os countdowns da tabela antes de re-renderizar
  _clearAllTableCountdowns();
  tbody.innerHTML = '';

  if (!trades || trades.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-muted" style="text-align:center;padding:24px;">
        Aguardando operações...
      </td></tr>`;
    return;
  }

  trades.slice(0, 20).forEach(t => {
    const isPending = t.result === 'pending';
    const tr = document.createElement('tr');
    tr.className = isPending ? 'trade-row trade-row-pending' : 'trade-row';
    if (t.result === 'won')  tr.classList.add('win-row');
    if (t.result === 'lost') tr.classList.add('loss-row');
    if (isPending && t.agent_id) tr.dataset.pendingAgent = t.agent_id;
    // Guardar db_id no elemento DOM para referência futura
    if (t.id != null) tr.dataset.dbId = String(t.id);

    const dir = formatDirection(t.direction);
    const agentObj = state.agents[t.agent_id];
    const agentName = agentObj?.name || t.agent_id;
    const timeStr = t.opened_at
      ? new Date(t.opened_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      : '';
    const stake = (t.stake || 0).toFixed(2);

    if (isPending) {
      // Calcular countdown para operação em curso
      const durationSecs = (agentObj?.timeframe_minutes || 5) * 60;
      const remaining = _calcRemainingSeconds(t.opened_at, durationSecs);

      // Usar db_id (t.id) como chave de tracking — mais confiável que contract_id
      // pois o db_id existe desde a inserção pendente, antes da Deriv confirmar
      const trackingKey = t.id != null ? `db_${t.id}` : (t.contract_id || t.agent_id);
      const countdownId = `tbl-cd-${trackingKey}`;

      tr.innerHTML = `
        <td class="text-secondary text-sm">${timeStr}</td>
        <td>${escHtml(agentName)}</td>
        <td><span class="direction-badge ${dir.cls}">${dir.label}</span></td>
        <td class="text-secondary">$${stake}</td>
        <td class="result-pending">
          <span class="trade-pending-pulse"></span> EM CURSO
          <span class="table-trade-countdown${remaining <= 15 ? ' countdown-urgent' : ''}" id="${countdownId}">
            ${remaining > 0 ? formatCountdown(remaining) : '⌛'}
          </span>
        </td>
        <td class="text-muted">—</td>`;
      tbody.appendChild(tr);

      // Registrar linha pendente no estado usando db_id (prioridade) e agentId (fallback)
      if (t.id != null) state.pendingTradeRows[`db_${t.id}`] = tr;
      if (t.agent_id) state.pendingTradeRows[t.agent_id] = tr;

      // Iniciar countdown na tabela usando trackingKey
      _startTableCountdown(trackingKey, t.opened_at, durationSecs, countdownId);
    } else {
      const res = formatResult(t.result);
      const pft = formatProfit(t.profit);
      const pctStr = t.profit != null && t.stake
        ? ` (${t.profit >= 0 ? '+' : ''}${((t.profit / t.stake) * 100).toFixed(0)}%)`
        : '';
      tr.title = buildTradeTooltip(t, agentObj);
      tr.innerHTML = `
        <td class="text-secondary text-sm">${timeStr}</td>
        <td>${escHtml(agentName)}</td>
        <td><span class="direction-badge ${dir.cls}">${dir.label}</span></td>
        <td class="text-secondary">$${stake}</td>
        <td class="${res.cls}">${res.label}</td>
        <td class="${pft.cls}">${pft.label}<span class="text-muted text-sm">${pctStr}</span></td>`;
      tbody.appendChild(tr);
    }
  });
}

// ─── Linha pendente (trade em curso) ────────────────────
/**
 * Insere uma linha "em curso" no topo da tabela global de trades
 * quando o evento trade_executed chega.
 *
 * CHAVE DE RASTREAMENTO: db_id (rowid do banco) — fornecido pelo backend antes
 * da Deriv confirmar o contrato. Isso garante que o frontend possa localizar
 * exatamente a linha correta para atualizar quando trade_closed chegar,
 * mesmo que múltiplos agentes tenham trades abertos simultaneamente.
 */
function prependPendingTradeRow(agentId, payload) {
  const tbody = document.getElementById('recentTradesTbody');
  if (!tbody) return;

  // Remover placeholder "Aguardando operações..."
  const emptyRow = tbody.querySelector('td[colspan]');
  if (emptyRow) tbody.innerHTML = '';

  const dir = formatDirection(payload.direction);
  const agentName = state.agents[agentId]?.name || agentId;
  const timeStr = payload.opened_at
    ? new Date(payload.opened_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const stake = (payload.stake || 0).toFixed(2);

  // Calcular duração em segundos para o countdown
  const durationSecs = payload.duration_seconds
    || (state.agents[agentId]?.timeframe_minutes || 5) * 60;

  // Preferir db_id como chave de countdown — mais estável que contract_id
  // (db_id existe desde a abertura; contract_id pode não vir no trade_executed)
  const trackingKey = payload.db_id != null ? `db_${payload.db_id}` : (payload.contract_id || agentId);
  const countdownId = `tbl-cd-${trackingKey}`;

  const tr = document.createElement('tr');
  tr.className = 'trade-row trade-row-pending';
  tr.dataset.pendingAgent = agentId;
  if (payload.db_id != null) tr.dataset.dbId = String(payload.db_id);

  tr.innerHTML = `
    <td class="text-secondary text-sm">${timeStr}</td>
    <td>${escHtml(agentName)}</td>
    <td><span class="direction-badge ${dir.cls}">${dir.label}</span></td>
    <td class="text-secondary">$${stake}</td>
    <td class="result-pending">
      <span class="trade-pending-pulse"></span> EM CURSO
      <span class="table-trade-countdown" id="${countdownId}">${formatCountdown(durationSecs)}</span>
    </td>
    <td class="text-muted">—</td>`;

  tbody.insertBefore(tr, tbody.firstChild);

  // Guardar referência usando db_id como chave primária (mais confiável)
  // Fallback para agentId para compatibilidade
  if (payload.db_id != null) {
    state.pendingTradeRows[`db_${payload.db_id}`] = tr;
  }
  // Também manter por agentId como fallback (pode ser sobrescrito em trades consecutivos,
  // mas garante compatibilidade com código legado)
  state.pendingTradeRows[agentId] = tr;

  // Iniciar countdown na tabela usando trackingKey
  _startTableCountdown(trackingKey, payload.opened_at || new Date().toISOString(), durationSecs, countdownId);

  // Limitar tabela a 20 linhas
  while (tbody.children.length > 20) {
    tbody.removeChild(tbody.lastChild);
  }
}

/**
 * Quando trade_closed chega:
 * 1. Busca a linha pendente por db_id (chave mais confiável)
 * 2. Fallback para agentId (compatibilidade)
 * 3. Se não encontrar linha pendente → insere nova linha no topo
 */
function resolveTradeRow(agentId, payload) {
  // Parar countdown da tabela pelos dois possíveis identificadores
  const dbKey = payload.db_id != null ? `db_${payload.db_id}` : null;
  if (dbKey) _stopTableCountdown(dbKey);
  if (payload.contract_id) _stopTableCountdown(payload.contract_id);

  // Buscar linha pendente: db_id tem prioridade sobre agentId
  let pendingRow = dbKey ? state.pendingTradeRows[dbKey] : null;
  if (!pendingRow || !pendingRow.isConnected) {
    pendingRow = state.pendingTradeRows[agentId];
  }

  if (pendingRow && pendingRow.isConnected) {
    // Atualizar a linha existente in-place
    const dir = formatDirection(payload.direction);
    const res = formatResult(payload.result);
    const pft = formatProfit(payload.profit || 0);
    const agentName = state.agents[agentId]?.name || agentId;
    const timeStr = payload.opened_at
      ? new Date(payload.opened_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      : new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const stake = (payload.stake || 0).toFixed(2);
    const profit = payload.profit || 0;
    const pctStr = payload.stake
      ? ` (${profit >= 0 ? '+' : ''}${((profit / payload.stake) * 100).toFixed(0)}%)`
      : '';

    // Remover classe pendente, adicionar classe de resultado com animação
    pendingRow.classList.remove('trade-row-pending');
    pendingRow.classList.add(
      payload.result === 'won' ? 'win-row' : 'loss-row',
      payload.result === 'won' ? 'flash-win' : 'flash-loss'
    );

    pendingRow.innerHTML = `
      <td class="text-secondary text-sm">${timeStr}</td>
      <td>${escHtml(agentName)}</td>
      <td><span class="direction-badge ${dir.cls}">${dir.label}</span></td>
      <td class="text-secondary">$${stake}</td>
      <td class="${res.cls}">${res.label}</td>
      <td class="${pft.cls}">${pft.label}<span class="text-muted text-sm">${pctStr}</span></td>`;

    // Limpar referências
    if (dbKey) delete state.pendingTradeRows[dbKey];
    delete state.pendingTradeRows[agentId];
  } else {
    // Nenhuma linha pendente encontrada: inserir nova (fallback)
    prependTradeToTable(agentId, payload);
  }
}

function prependTradeToTable(agentId, tradePayload) {
  const tbody = document.getElementById('recentTradesTbody');
  if (!tbody) return;

  const emptyRow = tbody.querySelector('td[colspan]');
  if (emptyRow) tbody.innerHTML = '';

  const dir = formatDirection(tradePayload.direction);
  const res = formatResult(tradePayload.result);
  const pft = formatProfit(tradePayload.profit || 0);
  const agentName = state.agents[agentId]?.name || agentId;
  const timeStr = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const stake = (tradePayload.stake || 0).toFixed(2);
  const profit = tradePayload.profit || 0;
  const pctStr = tradePayload.stake
    ? ` (${profit >= 0 ? '+' : ''}${((profit / tradePayload.stake) * 100).toFixed(0)}%)`
    : '';

  const tr = document.createElement('tr');
  // Classe permanente de resultado + animação flash
  tr.className = 'trade-row';
  if (tradePayload.result === 'won')  tr.classList.add('win-row',  'flash-win');
  if (tradePayload.result === 'lost') tr.classList.add('loss-row', 'flash-loss');

  tr.innerHTML = `
    <td class="text-secondary text-sm">${timeStr}</td>
    <td>${escHtml(agentName)}</td>
    <td><span class="direction-badge ${dir.cls}">${dir.label}</span></td>
    <td class="text-secondary">$${stake}</td>
    <td class="${res.cls}">${res.label}</td>
    <td class="${pft.cls}">${pft.label}<span class="text-muted text-sm">${pctStr}</span></td>`;

  tbody.insertBefore(tr, tbody.firstChild);

  while (tbody.children.length > 20) {
    tbody.removeChild(tbody.lastChild);
  }
}

// ─── Helpers para o formulário de agente ────────────────

/**
 * Gera o nome sugerido no formato "{SÍMBOLO_CURTO} — {TF}min"
 * ex: "R75 — 2min", "BOOM500 — 5min"
 */
function _buildSuggestedAgentName(symbol, timeframeMin) {
  if (!symbol) return '';
  // Tentar usar display_name curto — senão usar o próprio symbol
  let shortName = symbol;
  if (window._symbolsCache) {
    for (const cat of window._symbolsCache) {
      const found = cat.symbols?.find(s => s.symbol === symbol);
      if (found) {
        // Ex: "Volatility 75 Index" → "R75"   "BOOM 500 Index" → "BOOM500"
        const dn = found.display_name || symbol;
        // Extrair partes numéricas + prefixo curto
        const m = dn.match(/(\d+)/);
        if (m) {
          const num = m[1];
          if (symbol.startsWith('R_'))       shortName = `R${num}`;
          else if (symbol.startsWith('1HZ'))  shortName = `HZ${num}`;
          else if (symbol.startsWith('BOOM')) shortName = `BOOM${num}`;
          else if (symbol.startsWith('CRASH'))shortName = `CRASH${num}`;
          else if (symbol.startsWith('JD'))   shortName = `JD${num}`;
          else shortName = symbol;
        } else {
          shortName = symbol;
        }
        break;
      }
    }
  }
  return `${shortName} — ${timeframeMin}min`;
}

/**
 * Verifica se já existe agente com mesmo símbolo + timeframe + modelo (strategy).
 * Ignora o agente sendo editado.
 */
function _findDuplicateAgent(symbol, timeframeMin, strategy, excludeId) {
  return Object.values(state.agents).find(a =>
    a.id !== excludeId &&
    a.symbol === symbol &&
    a.timeframe_minutes === Number(timeframeMin) &&
    a.strategy === strategy
  ) || null;
}

/** Atualiza o nome sugerido e mostra/oculta o aviso de duplicado */
function _updateModalNameAndWarning() {
  if (state.editingAgentId) return; // só aplica na criação
  const symbolSel = document.getElementById('agentSymbol');
  const tfSel = document.getElementById('agentTimeframe');
  const strategySel = document.getElementById('agentStrategy');
  const nameInput = document.getElementById('agentName');
  const warningEl = document.getElementById('duplicateWarning');
  if (!symbolSel || !tfSel || !strategySel || !nameInput) return;

  const symbol = symbolSel.value;
  const tf = tfSel.value;
  const strategy = strategySel.value;

  // Auto-preencher nome SE estiver vazio ou for o valor sugerido anterior
  const suggested = _buildSuggestedAgentName(symbol, tf);
  const current = nameInput.value.trim();
  // Preencher se vazio ou se o valor atual parece um nome sugerido (contém " — ")
  if (!current || current.includes(' — ')) {
    nameInput.value = suggested;
  }

  // Verificar duplicata
  const dup = _findDuplicateAgent(symbol, tf, strategy, null);
  if (warningEl) {
    warningEl.style.display = dup ? 'inline-flex' : 'none';
  }
}

// ─── Modal de Criação/Edição ─────────────────────────────
function bindUIEvents() {
  document.getElementById('btnNewAgent')?.addEventListener('click', openCreateModal);
  document.getElementById('modalClose')?.addEventListener('click', closeModal);
  document.getElementById('agentForm')?.addEventListener('submit', handleFormSubmit);
  document.getElementById('modalOverlay')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeModal();
  });
  document.getElementById('confirmCancel')?.addEventListener('click', closeConfirm);
  document.getElementById('confirmOverlay')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeConfirm();
  });

  // Listeners para auto-preencher nome e checar duplicados no formulário
  ['agentSymbol', 'agentTimeframe', 'agentStrategy'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', _updateModalNameAndWarning);
  });
}

function openCreateModal() {
  state.editingAgentId = null;
  document.getElementById('modalTitle').textContent = '+ Novo Agente';
  document.getElementById('agentForm').reset();
  // Ocultar campo ID (não é necessário na criação)
  document.getElementById('agentIdGroup').style.display = 'none';
  document.getElementById('agentId').disabled = false;
  // Ocultar aviso de duplicado ao abrir
  const warningEl = document.getElementById('duplicateWarning');
  if (warningEl) warningEl.style.display = 'none';
  // Carregar dropdown de símbolos da API Deriv
  if (typeof window.loadSymbolsIntoDropdown === 'function') {
    const spinner = document.getElementById('symbolLoadingSpinner');
    if (spinner) spinner.style.display = 'inline';
    window.loadSymbolsIntoDropdown('R_75').then(() => {
      // Após carregar símbolos, sugerir nome inicial
      _updateModalNameAndWarning();
    });
  } else {
    _updateModalNameAndWarning();
  }
  openModal();
}

window.handleEditAgent = async (agentId) => {
  state.editingAgentId = agentId;
  const agent = state.agents[agentId];
  if (!agent) return;

  document.getElementById('modalTitle').textContent = `✏️ Editar: ${agent.name}`;
  document.getElementById('agentIdGroup').style.display = 'none';
  document.getElementById('agentId').disabled = true;

  const form = document.getElementById('agentForm');
  form.agentId.value = agent.id;
  form.agentName.value = agent.name || '';
  form.agentTimeframe.value = agent.timeframe_minutes || 5;
  form.agentStake.value = agent.stake || 5;
  form.agentStrategy.value = agent.strategy || 'rsi_ema';
  form.agentToken.value = agent.api_token || '';

  // Carregar dropdown de símbolos e pré-selecionar o símbolo do agente
  if (typeof window.loadSymbolsIntoDropdown === 'function') {
    const spinner = document.getElementById('symbolLoadingSpinner');
    if (spinner) spinner.style.display = 'inline';
    await window.loadSymbolsIntoDropdown(agent.symbol || 'R_75');
  } else {
    form.agentSymbol.value = agent.symbol || 'R_75';
  }

  openModal();
};

async function handleFormSubmit(e) {
  e.preventDefault();
  const form = e.target;

  const name = form.agentName.value.trim();  // pode ser vazio — backend gera default
  const agentId = form.agentId.value.trim() || undefined;  // undefined = auto-gerado no backend

  const symbol = form.agentSymbol.value.trim();
  const timeframeMin = parseInt(form.agentTimeframe.value);
  const strategy = form.agentStrategy.value;

  const agentData = {
    symbol,
    timeframe_minutes: timeframeMin,
    stake: parseFloat(form.agentStake.value),
    strategy,
  };

  // Incluir id e name apenas se preenchidos
  if (agentId) agentData.id = agentId;
  if (name) agentData.name = name;

  const token = form.agentToken.value.trim();
  if (token) agentData.api_token = token;

  // Verificar duplicação (só na criação)
  if (!state.editingAgentId) {
    const dup = _findDuplicateAgent(symbol, timeframeMin, strategy, null);
    if (dup) {
      // Criar em estado pausado para não conflitar com o agente existente
      agentData.initial_status = 'paused';
    }
  }

  // O botão de submit fica fora do <form> (no modal-footer), por isso
  // form.querySelector() retornaria null. Buscar pelo atributo form="agentForm"
  // ou diretamente no modal-footer.
  const submitBtn = document.querySelector('button[type="submit"][form="agentForm"]')
    || form.querySelector('button[type="submit"]');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Salvando...';
  }

  try {
    if (state.editingAgentId) {
      await updateAgent(state.editingAgentId, agentData);
      const displayName = agentData.name || state.agents[state.editingAgentId]?.name || state.editingAgentId;
      showToast('✅ Agente Atualizado', `${displayName} foi atualizado.`, 'success');
      if (state.agents[state.editingAgentId]) {
        Object.assign(state.agents[state.editingAgentId], agentData);
        updateAgentCard(state.editingAgentId);
      }
    } else {
      const result = await createAgent(agentData);
      const createdId = result?.id || agentData.id || 'novo';
      if (agentData.initial_status === 'paused') {
        showToast('⏸ Agente Criado (Pausado)', `Agente ${createdId} criado em modo pausado — configuração duplicada detectada.`, 'warning');
      } else {
        showToast('✅ Agente Criado', `Agente ${createdId} foi criado e iniciado.`, 'success');
      }
      await loadInitialData();
    }
    closeModal();
  } catch (err) {
    showToast('❌ Erro', err.message || 'Falha ao salvar agente.', 'error');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Salvar';
    }
  }
}

window.handlePauseAgent = async (agentId) => {
  try {
    await pauseAgent(agentId);
    if (state.agents[agentId]) {
      state.agents[agentId].status = 'paused';
      updateAgentCard(agentId);
    }
    showToast('⏸ Agente Pausado', `${state.agents[agentId]?.name || agentId} foi pausado.`, 'info');
  } catch (err) {
    showToast('❌ Erro', err.message, 'error');
  }
};

window.handleResumeAgent = async (agentId) => {
  try {
    await resumeAgent(agentId);
    if (state.agents[agentId]) {
      state.agents[agentId].status = 'running';
      updateAgentCard(agentId);
    }
    showToast('▶ Agente Retomado', `${state.agents[agentId]?.name || agentId} está operando novamente.`, 'success');
  } catch (err) {
    showToast('❌ Erro', err.message, 'error');
  }
};

let _confirmResolve = null;

window.handleDeleteAgent = (agentId) => {
  const agentName = state.agents[agentId]?.name || agentId;
  showConfirm(
    'Deletar Agente',
    `Tem certeza que deseja deletar "${agentName}"? O histórico de trades será preservado.`,
    async () => {
      try {
        await deleteAgent(agentId);
        delete state.agents[agentId];
        removeAgentFromChart(agentId);
        const card = document.getElementById(`agent-card-${agentId}`);
        if (card) card.remove();
        checkEmptyState();
        showToast('🗑️ Agente Deletado', `${agentName} foi removido.`, 'info');
      } catch (err) {
        showToast('❌ Erro', err.message, 'error');
      }
    }
  );
};

// ─── Modal helpers ──────────────────────────────────────
function openModal() {
  document.getElementById('modalOverlay').classList.add('open');
}

function closeModal() {
  document.getElementById('modalOverlay').classList.remove('open');
  state.editingAgentId = null;
}

// ─── Confirm Dialog ─────────────────────────────────────
function showConfirm(title, message, onConfirm) {
  document.getElementById('confirmTitle').textContent = title;
  document.getElementById('confirmMessage').textContent = message;
  document.getElementById('confirmOk').onclick = async () => {
    closeConfirm();
    await onConfirm();
  };
  document.getElementById('confirmOverlay').classList.add('open');
}

function closeConfirm() {
  document.getElementById('confirmOverlay').classList.remove('open');
}

// ─── Toast ──────────────────────────────────────────────
function showToast(title, message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
    <div class="toast-content">
      <div class="toast-title">${escHtml(title)}</div>
      <div class="toast-message">${escHtml(message)}</div>
    </div>`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ─── Countdowns na Tabela ────────────────────────────────

/**
 * Calcula os segundos restantes de um trade com base em opened_at + durationSecs.
 */
function _calcRemainingSeconds(openedAt, durationSecs) {
  if (!openedAt) return durationSecs;
  const elapsed = (Date.now() - new Date(openedAt).getTime()) / 1000;
  return Math.max(0, Math.round(durationSecs - elapsed));
}

/**
 * Inicia um countdown regressivo em um elemento da tabela.
 * @param {string} contractId  - ID do contrato (chave de estado)
 * @param {string} openedAt    - ISO string do momento de abertura
 * @param {number} durationSecs - Duração total em segundos
 * @param {string} [elemId]    - ID do elemento DOM onde exibir (tbl-cd-<contractId> por padrão)
 */
function _startTableCountdown(contractId, openedAt, durationSecs, elemId) {
  if (!contractId) return;
  const key = String(contractId);
  const domId = elemId || `tbl-cd-${key}`;

  // Parar countdown anterior para o mesmo contrato se existir
  _stopTableCountdown(key);

  const tick = () => {
    const el = document.getElementById(domId);
    if (!el) {
      _stopTableCountdown(key);
      return;
    }
    const remaining = _calcRemainingSeconds(openedAt, durationSecs);
    el.textContent = remaining > 0 ? formatCountdown(remaining) : '⌛';
    if (remaining <= 15) {
      el.classList.add('countdown-urgent');
    } else {
      el.classList.remove('countdown-urgent');
    }
  };

  tick(); // executar imediatamente
  const interval = setInterval(tick, 1000);
  state.tableCountdowns[key] = { interval, domId };
}

function _stopTableCountdown(contractId) {
  const key = String(contractId);
  if (state.tableCountdowns[key]) {
    clearInterval(state.tableCountdowns[key].interval);
    delete state.tableCountdowns[key];
  }
}

function _clearAllTableCountdowns() {
  Object.keys(state.tableCountdowns).forEach(k => {
    clearInterval(state.tableCountdowns[k].interval);
  });
  state.tableCountdowns = {};
}

// ─── Utilitários ────────────────────────────────────────
function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

window.showToast = showToast;
window._updateModalNameAndWarning = _updateModalNameAndWarning;

// ════════════════════════════════════════════════════════════
//  DEV DEBUG PANEL — Painel deslizante de Coin Flip
//  TEMPORÁRIO — será removido na versão final de produção
// ════════════════════════════════════════════════════════════

const devPanel = (() => {
  // ── Namespace de persistência (AppStorage deve estar carregado antes de app.js) ──
  const storage = window.AppStorage
    ? window.AppStorage.getNamespace('devPanel')
    : { get: (k, d) => d, set: () => {}, remove: () => {} }; // fallback seguro

  // Estado interno do painel — restaurado do localStorage quando possível
  const _state = {
    open: false,
    history: storage.get('history', []),  // restaurar do localStorage
    autoInterval: null,                   // setInterval para testes automáticos
    autoMode: null,                       // 'once' | 'minute' | null
    maxHistory: 50,
  };

  // ── Abrir/Fechar ────────────────────────────────────────
  function openPanel() {
    _state.open = true;
    storage.set('isOpen', true);
    // Novo: garantir que a sidebar esquerda está expandida
    const sidebar = document.getElementById('leftDevSidebar');
    if (sidebar && sidebar.classList.contains('collapsed')) {
      window.LeftDev?.toggle();
    }
    // Ir para tab coinflip
    window.LeftDev?.switchTab('coinflip');
    renderAgentsList();
    renderHistory();
  }

  function closePanel() {
    _state.open = false;
    storage.set('isOpen', false);
    // Não fechar a sidebar — o utilizador pode fechar com o toggle
  }

  function togglePanel() {
    // Agora usa o toggle da sidebar esquerda
    window.LeftDev?.toggle();
    _state.open = !_state.open;
    storage.set('isOpen', _state.open);
  }

  // ── Renderizar lista de agentes ─────────────────────────
  function renderAgentsList() {
    const container = document.getElementById('devAgentsList');
    const manualSection = document.getElementById('devManualSection');
    const autoSelect = document.getElementById('devAutoAgentSelect');
    if (!container) return;

    const agents = Object.values(state.agents);
    if (agents.length === 0) {
      container.innerHTML = '<div class="dev-empty-msg">Nenhum agente carregado.</div>';
      return;
    }

    // Atualizar select de agentes no modo automático
    if (autoSelect) {
      // Prioridade: valor atual do DOM → valor salvo no storage → 'all'
      const prev = autoSelect.value || storage.get('autoTarget', 'all');
      autoSelect.innerHTML = '<option value="all">Todos os agentes</option>';
      agents.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a.id;
        opt.textContent = `${a.name} (${a.timeframe_minutes}min)`;
        if (opt.value === prev) opt.selected = true;
        autoSelect.appendChild(opt);
      });
    }

    // Seção de status dos agentes
    container.innerHTML = agents.map(agent => {
      const isCoinFlip = agent.strategy === 'coin_flip';
      const history = _getAgentHistory(agent.id);
      const dotsHtml = _buildCfDotsHtml(history);
      const tfLabel = `${agent.timeframe_minutes}min`;
      const sleepLabel = agent.timeframe_minutes === 2 ? '120s' : '300s';

      return `
        <div class="dev-agent-row" id="dev-agent-row-${escHtml(agent.id)}">
          <span class="dev-agent-name">${escHtml(agent.name)}</span>
          <span class="dev-agent-tf" title="Timeframe">${escHtml(tfLabel)}</span>
          ${isCoinFlip
            ? `<span style="font-size:0.68rem;color:#9a6deb;flex-shrink:0;">🪙 flip/${escHtml(sleepLabel)}</span>`
            : `<span style="font-size:0.68rem;color:var(--text-muted);flex-shrink:0;">${escHtml(agent.strategy || '—')}</span>`
          }
          <div class="dev-coinflip-history">${dotsHtml}</div>
          <button class="dev-btn-reset" onclick="window.devPanel.resetAgent('${escHtml(agent.id)}')" title="Reiniciar bot">↺ Reset</button>
        </div>`;
    }).join('');

    // Seção de testes manuais
    if (manualSection) {
      manualSection.innerHTML = agents.map(agent => `
        <div class="dev-agent-row">
          <span class="dev-agent-name">${escHtml(agent.name)}</span>
          <span class="dev-agent-tf">${agent.timeframe_minutes}min</span>
          <button class="dev-btn-flip"
                  id="dev-flip-btn-${escHtml(agent.id)}"
                  onclick="window.devPanel.runFlip('${escHtml(agent.id)}')">
            🪙 Flip
          </button>
        </div>`
      ).join('');
    }
  }

  // ── Histórico por agente (últimos 5 resultados) ─────────
  function _getAgentHistory(agentId) {
    return _state.history
      .filter(h => h.agentId === agentId)
      .slice(-5);
  }

  function _buildCfDotsHtml(history) {
    const slots = [];
    const filled = history.slice(-5);
    for (let i = filled.length; i < 5; i++) {
      slots.push('<div class="dev-cf-dot empty"></div>');
    }
    filled.forEach(h => {
      const cls = h.result === 'CALL' ? 'call' : 'put';
      const lbl = h.result === 'CALL' ? 'C' : 'P';
      slots.push(`<div class="dev-cf-dot ${cls}" title="${h.result} @ ${h.timestamp}">${lbl}</div>`);
    });
    return slots.join('');
  }

  // ── Executar flip manual ────────────────────────────────
  async function runFlip(agentId) {
    const btn = document.getElementById(`dev-flip-btn-${agentId}`);
    if (btn) { btn.disabled = true; btn.textContent = '⏳'; }

    try {
      const res = await fetch(`/api/v1/agents/${agentId}/coin-flip-test`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      const entry = {
        timestamp: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        agentId: data.agent_id,
        agentName: data.agent_name || agentId,
        result: data.result,   // 'CALL' ou 'PUT'
        log: `${data.symbol} | ${data.timeframe_minutes}min | ${data.note || ''}`,
      };

      _state.history.push(entry);
      if (_state.history.length > _state.maxHistory) {
        _state.history = _state.history.slice(-_state.maxHistory);
      }
      // Persistir histórico imediatamente após cada execução
      storage.set('history', _state.history);

      // Atualizar UI
      renderAgentsList();
      renderHistory();

      showToast(
        `🪙 ${entry.result}`,
        `${entry.agentName}: ${entry.result}`,
        entry.result === 'CALL' ? 'success' : 'error'
      );

    } catch (e) {
      showToast('❌ Flip Error', e.message, 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '🪙 Flip'; }
    }
  }

  // ── Reset de agente ─────────────────────────────────────
  async function resetAgent(agentId) {
    const agentName = state.agents[agentId]?.name || agentId;
    const btn = document.querySelector(`#dev-agent-row-${agentId} .dev-btn-reset`);
    if (btn) { btn.disabled = true; btn.textContent = '⏳'; }

    try {
      const res = await fetch(`/api/v1/agents/${agentId}/restart`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      showToast('↺ Agente Reiniciado', `${agentName} foi reiniciado com sucesso.`, 'success');
    } catch (e) {
      showToast('❌ Reset Error', e.message, 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '↺ Reset'; }
    }
  }

  // ── Renderizar histórico ────────────────────────────────
  function renderHistory() {
    const container = document.getElementById('devHistoryList');
    if (!container) return;

    if (_state.history.length === 0) {
      container.innerHTML = '<div class="dev-empty-msg">Nenhuma execução ainda.</div>';
      return;
    }

    // Exibir do mais recente para o mais antigo
    const items = [..._state.history].reverse().slice(0, 30);
    container.innerHTML = items.map(h => {
      const cls = h.result === 'CALL' ? 'call' : 'put';
      const icon = h.result === 'CALL' ? '▲' : '▼';
      return `
        <div class="dev-history-item">
          <span class="dev-history-time">${escHtml(h.timestamp)}</span>
          <span class="dev-history-agent">${escHtml(h.agentName)}</span>
          <span class="dev-result-badge ${cls}">${icon} ${escHtml(h.result)}</span>
          ${h.log ? `<div class="dev-history-log" style="width:100%;">${escHtml(h.log)}</div>` : ''}
        </div>`;
    }).join('');
  }

  // ── Limpar histórico ────────────────────────────────────
  function clearHistory() {
    _state.history = [];
    storage.remove('history');
    renderHistory();
    renderAgentsList();
  }

  // ── Testes automáticos ──────────────────────────────────
  function _stopAutoTest() {
    if (_state.autoInterval) {
      clearInterval(_state.autoInterval);
      _state.autoInterval = null;
    }
    _state.autoMode = null;
    storage.set('autoMode', null);
    _updateAutoStatus('');
    _setAutoButtonsActive(null);
  }

  async function _runAutoOnce() {
    const selectEl = document.getElementById('devAutoAgentSelect');
    const agentId = selectEl?.value || 'all';

    const agents = agentId === 'all'
      ? Object.keys(state.agents)
      : [agentId];

    for (const id of agents) {
      await runFlip(id);
    }
  }

  function startAutoOnce() {
    _stopAutoTest();
    _state.autoMode = 'once';
    storage.set('autoMode', 'once');
    _setAutoButtonsActive('once');
    _updateAutoStatus('Executando uma vez...');
    _runAutoOnce().then(() => {
      _updateAutoStatus('✅ Concluído.');
      _state.autoMode = null;
      storage.set('autoMode', null);
      _setAutoButtonsActive(null);
    });
  }

  function startAutoMinute() {
    _stopAutoTest();
    _state.autoMode = 'minute';
    storage.set('autoMode', 'minute');
    _setAutoButtonsActive('minute');
    let count = 0;
    const tick = async () => {
      count++;
      _updateAutoStatus(`🔄 Execução #${count}...`);
      await _runAutoOnce();
      _updateAutoStatus(`✅ Execução #${count} concluída. Próxima em 60s.`);
    };
    tick();
    _state.autoInterval = setInterval(tick, 60000);
  }

  function stopAuto() {
    _stopAutoTest();
    showToast('⏹ Auto-Teste', 'Testes automáticos pausados.', 'info');
  }

  function _updateAutoStatus(msg) {
    const el = document.getElementById('devAutoStatus');
    if (el) el.textContent = msg;
  }

  function _setAutoButtonsActive(mode) {
    const btnOnce = document.getElementById('devAutoOnce');
    const btnMin = document.getElementById('devAutoMinute');
    if (btnOnce) btnOnce.classList.toggle('active', mode === 'once');
    if (btnMin) btnMin.classList.toggle('active', mode === 'minute');
  }

  // ── Inicialização ───────────────────────────────────────
  function init() {
    // Botões de teste automático (novo sidebar)
    document.getElementById('devAutoOnce')?.addEventListener('click', startAutoOnce);
    document.getElementById('devAutoMinute')?.addEventListener('click', startAutoMinute);
    document.getElementById('devAutoStop')?.addEventListener('click', stopAuto);

    // Persistir agente-alvo selecionado sempre que o usuário mudar o select
    document.getElementById('devAutoAgentSelect')?.addEventListener('change', (e) => {
      storage.set('autoTarget', e.target.value);
    });

    // Renderizar lista de agentes no sidebar (sempre visível)
    renderAgentsList();
    renderHistory();

    // Restaurar estado visual do autoMode
    const savedAutoMode = storage.get('autoMode', null);
    if (savedAutoMode) {
      _state.autoMode = savedAutoMode;
      _setAutoButtonsActive(savedAutoMode);
    }
  }

  // ── API pública ─────────────────────────────────────────
  return {
    init,
    openPanel,
    closePanel,
    togglePanel,
    runFlip,
    resetAgent,
    clearHistory,
    renderAgentsList,
  };
})();

// Registrar globalmente
window.devPanel = devPanel;

// Inicializar painel quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
  devPanel.init();
});

// Re-renderizar a lista de agentes sempre que o estado de agentes muda
const _patchDevPanelRefresh = () => {
  devPanel.renderAgentsList();
};

// Exportar para ser chamado pelo WebSocket handler quando state.agents muda
window.refreshDevPanel = _patchDevPanelRefresh;
