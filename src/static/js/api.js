/**
 * API client - Helpers para chamadas REST ao backend.
 */

const API_BASE = '/api/v1';

async function apiFetch(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const defaults = {
    headers: { 'Content-Type': 'application/json' },
  };
  const config = { ...defaults, ...options };
  if (config.body && typeof config.body === 'object') {
    config.body = JSON.stringify(config.body);
  }

  const response = await fetch(url, config);
  const data = await response.json();

  if (!response.ok) {
    const message = data.detail || data.message || `HTTP Error ${response.status}`;
    throw new Error(message);
  }
  return data;
}

// ─── Agentes ──────────────────────────────────────────────

export async function fetchAgents() {
  return apiFetch('/agents');
}

export async function fetchAgent(agentId) {
  return apiFetch(`/agents/${agentId}`);
}

export async function createAgent(agentData) {
  return apiFetch('/agents', { method: 'POST', body: agentData });
}

export async function updateAgent(agentId, agentData) {
  return apiFetch(`/agents/${agentId}`, { method: 'PUT', body: agentData });
}

export async function deleteAgent(agentId) {
  return apiFetch(`/agents/${agentId}`, { method: 'DELETE' });
}

export async function pauseAgent(agentId) {
  return apiFetch(`/agents/${agentId}/pause`, { method: 'POST' });
}

export async function resumeAgent(agentId) {
  return apiFetch(`/agents/${agentId}/resume`, { method: 'POST' });
}

export async function resetAgentStats(agentId) {
  return apiFetch(`/agents/${agentId}/reset-stats`, { method: 'POST' });
}

export async function fetchAgentTrades(agentId, limit = 20) {
  return apiFetch(`/agents/${agentId}/trades?limit=${limit}`);
}

// ─── Trades ───────────────────────────────────────────────

export async function fetchTrades(params = {}) {
  const query = new URLSearchParams();
  if (params.agent_id) query.set('agent_id', params.agent_id);
  if (params.result) query.set('result', params.result);
  if (params.limit) query.set('limit', params.limit);
  if (params.offset) query.set('offset', params.offset);
  return apiFetch(`/trades?${query.toString()}`);
}

export async function fetchTradeStats(agentId = null, period = 'all') {
  const query = new URLSearchParams({ period });
  if (agentId) query.set('agent_id', agentId);
  return apiFetch(`/trades/stats?${query.toString()}`);
}

export async function fetchPnlHistory(agentId = null, limit = 100) {
  const query = new URLSearchParams({ limit });
  if (agentId) query.set('agent_id', agentId);
  return apiFetch(`/trades/pnl-history?${query.toString()}`);
}

// ─── Sistema ──────────────────────────────────────────────

export async function fetchHealth() {
  return apiFetch('/health');
}

export async function fetchStrategies() {
  return apiFetch('/strategies');
}
