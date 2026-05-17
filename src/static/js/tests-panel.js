/**
 * tests-panel.js — Painel Dev Unificado
 * Secções: Testes (com toggle de código + anotação) + Backlog (com prioridade)
 * Expõe: window.DevPanel  e  window.TestsPanel (alias de compatibilidade)
 */

// ═══════════════════════════════════════
// DEFINIÇÃO DAS SUITES DE TESTES
// ═══════════════════════════════════════

const TEST_SUITES = [
  {
    id: 'integration-agents',
    label: '🤖 Agentes',
    color: '#3fb950',
    tests: [
      {
        id: 'crud',
        name: 'CRUD — Criação e Edição',
        runFn: 'runAgentCrudTest',
        codeSnippet: `// Passo 1: Criar agente
const createResp = await fetch('/api/v1/agents', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ symbol: 'R_75', timeframe_minutes: 5,
                         stake: 1.0, strategy: 'rsi_ema' }),
});
const createData = await createResp.json();
if (!createResp.ok) throw new Error('Criar agente falhou');
createdId = createData.id;

// Passo 2: Verificar na listagem
const agents = await (await fetch('/api/v1/agents')).json();
if (!agents.find(a => a.id === createdId))
  throw new Error('Agente não aparece na listagem');

// Passo 3-4: Editar + verificar
await fetch('/api/v1/agents/' + createdId, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ name: 'Test Agent Edited', stake: 2.0 }),
});

// Passo 5-6: Deletar + confirmar 404
await fetch('/api/v1/agents/' + createdId, { method: 'DELETE' });`
      },
      {
        id: 'pause-resume',
        name: 'Pausar / Retomar',
        runFn: 'runPauseResumeTest',
        codeSnippet: `// Criar agente temporário
const { id } = await (await fetch('/api/v1/agents', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ symbol: 'R_75', timeframe_minutes: 5,
                         stake: 1.0, strategy: 'rsi_ema' }),
})).json();

// Pausar
await fetch('/api/v1/agents/' + id + '/pause', { method: 'POST' });
const afterPause = await (await fetch('/api/v1/agents/' + id)).json();
if (afterPause.status !== 'paused')
  throw new Error('Status não é "paused": ' + afterPause.status);

// Retomar
await fetch('/api/v1/agents/' + id + '/resume', { method: 'POST' });

// Cleanup
await fetch('/api/v1/agents/' + id, { method: 'DELETE' });`
      },
    ]
  },
  {
    id: 'integration-ws',
    label: '⚙️ WebSocket',
    color: '#58a6ff',
    tests: [
      {
        id: 'ws-connect',
        name: 'Conectar e receber full_state',
        runFn: 'runWsConnectTest',
        codeSnippet: `// Abrir WebSocket e aguardar mensagem full_state
const ws = new WebSocket('ws://' + location.host + '/ws');
const msg = await new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error('Timeout 5s')), 5000);
  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === 'full_state') {
      clearTimeout(timer);
      resolve(data);
    }
  };
  ws.onerror = () => reject(new Error('WebSocket erro'));
});
ws.close();
if (!Array.isArray(msg.agents))
  throw new Error('full_state.agents não é array');`
      },
    ]
  },
  {
    id: 'integration-api',
    label: '🔌 API REST',
    color: '#d2a8ff',
    tests: [
      {
        id: 'symbols',
        name: 'Listar Símbolos disponíveis',
        runFn: 'runSymbolsTest',
        codeSnippet: `// GET /api/v1/symbols
const resp = await fetch('/api/v1/symbols');
const data = await resp.json();
if (!resp.ok) throw new Error('HTTP ' + resp.status);

const symbols = data.categories || data;
let total = 0;
for (const cat of symbols) total += (cat.symbols || []).length;
if (total < 1) throw new Error('Nenhum símbolo retornado');`
      },
      {
        id: 'pnl-history',
        name: 'Histórico P&L carrega corretamente',
        runFn: 'runPnlHistoryTest',
        codeSnippet: `// Obter primeiro agente
const agents = await (await fetch('/api/v1/agents')).json();
if (!agents.length)
  return { status: 'skipped', error: 'Sem agentes' };

// GET /api/v1/trades/pnl-history
const resp = await fetch(
  '/api/v1/trades/pnl-history?limit=10&agent_id=' + agents[0].id
);
const data = await resp.json();
if (!resp.ok) throw new Error('HTTP ' + resp.status);
if (!Array.isArray(data))
  throw new Error('Resposta não é array: ' + typeof data);`
      },
      {
        id: 'strategies',
        name: 'Listar Estratégias disponíveis',
        runFn: 'runStrategiesTest',
        codeSnippet: `// GET /api/v1/strategies
const resp = await fetch('/api/v1/strategies');
const data = await resp.json();
if (!resp.ok) throw new Error('HTTP ' + resp.status);
if (!Array.isArray(data) || data.length < 1)
  throw new Error('Nenhuma estratégia retornada');
for (const item of data) {
  if (!item.id && !item.name && !item.strategy_id)
    throw new Error('Item sem id/name');
}`
      },
    ]
  },
  {
    id: 'trades-table',
    label: '🗂️ Tabela de Trades',
    color: '#ffa657',
    tests: [
      {
        id: 'api-structure',
        name: 'API /trades — estrutura da resposta',
        runFn: 'runTradesApiStructureTest',
        codeSnippet: `// GET /api/v1/trades — verifica envelope e campos obrigatórios
const resp = await fetch('/api/v1/trades?limit=20&include_open=true');
if (!resp.ok) throw new Error('HTTP ' + resp.status);
const data = await resp.json();

// Verificar envelope
if (typeof data.total !== 'number') throw new Error('Campo total ausente ou não-número');
if (!Array.isArray(data.trades))   throw new Error('Campo trades não é array');
if (typeof data.limit  !== 'number') throw new Error('Campo limit ausente');
if (typeof data.offset !== 'number') throw new Error('Campo offset ausente');

// Verificar campos em cada trade (se houver trades)
for (const t of data.trades) {
  if (t.result === undefined) throw new Error('Trade sem campo result: id=' + t.id);
  if (t.stake  === undefined) throw new Error('Trade sem campo stake: id='  + t.id);
  if (!t.opened_at)           throw new Error('Trade sem opened_at: id='    + t.id);
  if (!t.agent_id)            throw new Error('Trade sem agent_id: id='     + t.id);
}`
      },
      {
        id: 'result-values',
        name: 'Trades têm result válido (won/lost/pending)',
        runFn: 'runTradesResultValuesTest',
        codeSnippet: `// Garante que result seja sempre won | lost | pending | unknown
const data = await (await fetch('/api/v1/trades?limit=50')).json();
const allowed = new Set(['won', 'lost', 'pending', 'unknown']);
const bad = data.trades.filter(t => !allowed.has(t.result));
if (bad.length > 0)
  throw new Error(bad.length + ' trades com result inválido: ' +
    bad.map(t => t.id + '=' + t.result).join(', '));`
      },
      {
        id: 'pending-on-top',
        name: 'Trades pendentes chegam no topo com include_open',
        runFn: 'runTradesPendingOnTopTest',
        codeSnippet: `// Com include_open=true os pending devem preceder os finalizados
const data = await (await fetch('/api/v1/trades?limit=50&include_open=true')).json();
const trades = data.trades;
const firstNonPending = trades.findIndex(t => t.result !== 'pending');
// Se há algum pending depois de um não-pending → bug de ordenação
if (firstNonPending !== -1) {
  const pendingAfter = trades.slice(firstNonPending).filter(t => t.result === 'pending');
  if (pendingAfter.length > 0)
    throw new Error(pendingAfter.length + ' trade(s) pending após finalizados na lista');
}`
      },
      {
        id: 'filter-result',
        name: 'Filtro ?result=won retorna apenas wins',
        runFn: 'runTradesFilterResultTest',
        codeSnippet: `// Filtrar por result=won — todos devem ser won
const resp = await fetch('/api/v1/trades?result=won&limit=20');
if (!resp.ok) throw new Error('HTTP ' + resp.status);
const { trades } = await resp.json();
const notWon = trades.filter(t => t.result !== 'won');
if (notWon.length > 0)
  throw new Error(notWon.length + ' trades não-won no filtro ?result=won');

// Filtrar por result=lost — todos devem ser lost
const resp2 = await fetch('/api/v1/trades?result=lost&limit=20');
const { trades: tLost } = await resp2.json();
const notLost = tLost.filter(t => t.result !== 'lost');
if (notLost.length > 0)
  throw new Error(notLost.length + ' trades não-lost no filtro ?result=lost');`
      },
      {
        id: 'profit-field',
        name: 'Campo profit correto por resultado',
        runFn: 'runTradesProfitFieldTest',
        codeSnippet: `// Trades won devem ter profit > 0 (ou pelo menos != null)
// Trades lost devem ter profit < 0 (ou pelo menos != null)
// Trades pending podem ter profit null
const data = await (await fetch('/api/v1/trades?limit=50')).json();
const errors = [];
for (const t of data.trades) {
  if (t.result === 'won'  && t.profit != null && t.profit < 0)
    errors.push('Trade ' + t.id + ' won mas profit=' + t.profit);
  if (t.result === 'lost' && t.profit != null && t.profit > 0)
    errors.push('Trade ' + t.id + ' lost mas profit=' + t.profit);
}
if (errors.length) throw new Error(errors.join('; '));`
      },
      {
        id: 'direction-values',
        name: 'Direção é CALL, PUT, MULTUP ou MULTDOWN',
        runFn: 'runTradesDirectionValuesTest',
        codeSnippet: `// Verificar que direction tem valor válido em todos os trades
const data = await (await fetch('/api/v1/trades?limit=50')).json();
const allowed = new Set(['CALL','PUT','MULTUP','MULTDOWN']);
const bad = data.trades.filter(t => t.direction && !allowed.has(t.direction));
if (bad.length > 0)
  throw new Error(bad.length + ' trades com direction inválida: ' +
    [...new Set(bad.map(t => t.direction))].join(', '));`
      },
      {
        id: 'table-render',
        name: 'Tabela renderiza won/lost correctamente no DOM',
        runFn: 'runTradesTableRenderTest',
        codeSnippet: `// Verifica o DOM da tabela após carga inicial
const tbody = document.getElementById('recentTradesTbody');
if (!tbody) throw new Error('tbody#recentTradesTbody não encontrado');

const rows = [...tbody.querySelectorAll('tr.trade-row')];
if (rows.length === 0) return { status:'skipped', error:'Tabela vazia — sem trades' };

// Verificar que não há linhas win-row/loss-row a mostrar PENDING
const finishedRows = rows.filter(r => r.classList.contains('win-row') || r.classList.contains('loss-row'));
const stuckPending = finishedRows.filter(r => r.textContent.includes('EM CURSO') || r.textContent.includes('PENDING'));
if (stuckPending.length > 0)
  throw new Error(stuckPending.length + ' linhas won/lost exibem PENDING/EM CURSO incorretamente');

// Verificar colspan no placeholder (deve ser 6)
const placeholder = tbody.querySelector('td[colspan]');
if (placeholder) {
  const cs = parseInt(placeholder.getAttribute('colspan'), 10);
  if (cs !== 6) throw new Error('colspan do placeholder é ' + cs + ', esperado 6');
}`
      },
    ]
  }
];

// ═══════════════════════════════════════
// ESTADO GLOBAL
// ═══════════════════════════════════════

let suiteResults   = {};   // { suiteId: { testId: { status, error, duration, lastRun } } }
let suiteRunning   = null; // suiteId em execução
let suiteCollapsed = {};   // { suiteId: bool }
let errorExpanded  = {};   // { 'suiteId-testId': bool }
let codeExpanded   = {};   // { 'suiteId-testId': bool }
let annotationDraft = {};  // { 'suiteId-testId': string }
let devTasks       = [];   // tasks carregadas da API
let _currentTab    = 'tests';
let _panelOpen     = false;

const _store = (typeof AppStorage !== 'undefined')
  ? AppStorage.getNamespace('devPanel')
  : null;

// ═══════════════════════════════════════
// UTILITÁRIOS
// ═══════════════════════════════════════

function esc(s) {
  return String(s || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function relativeTime(iso) {
  if (!iso) return '—';
  try {
    const d = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (d < 5)    return 'agora';
    if (d < 60)   return d + 's';
    if (d < 3600) return Math.floor(d / 60) + 'min';
    if (d < 86400) return Math.floor(d / 3600) + 'h';
    return Math.floor(d / 86400) + 'd';
  } catch (_) { return '—'; }
}

function suiteStats(suite) {
  const res = suiteResults[suite.id] || {};
  let pass = 0, fail = 0, skip = 0, running = 0;
  for (const t of suite.tests) {
    const r = res[t.id];
    if (!r) continue;
    if (r.status === 'passed')  pass++;
    else if (r.status === 'failed')  fail++;
    else if (r.status === 'skipped') skip++;
    else if (r.status === 'running') running++;
  }
  return { pass, fail, skip, running, total: suite.tests.length };
}

function globalStats() {
  let pass = 0, fail = 0, skip = 0, total = 0;
  for (const s of TEST_SUITES) {
    const st = suiteStats(s);
    pass += st.pass; fail += st.fail; skip += st.skip; total += st.total;
  }
  return { pass, fail, skip, total };
}

function priorityMeta(p) {
  if (p === 'critical') return { label: '🔴 Crítica', cls: 'prio-critical' };
  if (p === 'low')      return { label: '⬇ Baixa',   cls: 'prio-low' };
  return                        { label: '● Normal',  cls: 'prio-normal' };
}

// ═══════════════════════════════════════
// RENDER — TESTES
// ═══════════════════════════════════════

function renderGlobalSummary() {
  const { pass, fail, skip, total } = globalStats();
  const ran  = pass + fail + skip;
  const pw   = ran > 0 ? ((pass / total) * 100).toFixed(1) : 0;
  const fw   = ran > 0 ? ((fail / total) * 100).toFixed(1) : 0;
  return `
    <div class="udp-summary">
      <span class="udp-sum-pass">${pass}✓</span>
      <span class="udp-sum-fail">${fail}✗</span>
      ${skip > 0 ? `<span class="udp-sum-skip">${skip}○</span>` : ''}
      <div class="udp-sum-bar">
        <div class="udp-sum-bar-pass" style="width:${pw}%"></div>
        <div class="udp-sum-bar-fail" style="width:${fw}%"></div>
      </div>
      <span class="udp-sum-total">${ran}/${total}</span>
    </div>`;
}

function renderCodeViewer(suite, test) {
  const key   = `${suite.id}-${test.id}`;
  const draft = annotationDraft[key] || '';
  const relatedTasks = devTasks.filter(
    t => t.suite_id === suite.id && t.test_id === test.id && t.status === 'open'
  );
  return `
    <div class="udp-code-viewer">
      <div class="udp-code-hdr"><span class="udp-code-lbl">📄 Código do teste</span></div>
      <pre class="udp-code-pre"><code>${esc(test.codeSnippet || '')}</code></pre>
      ${relatedTasks.length > 0 ? `
        <div class="udp-code-tasks">
          ${relatedTasks.map(t => `
            <span class="udp-code-task-badge${t.regression ? ' reg' : ''}">
              ${t.regression ? '🔄 ' : ''}${esc(t.title.substring(0, 50))}
            </span>`).join('')}
        </div>` : ''}
      <div class="udp-annotation">
        <div class="udp-ann-lbl">📋 Anotar problema</div>
        <textarea class="udp-ann-ta" rows="3"
          placeholder="Descreve o problema: comportamento esperado vs. obtido..."
          id="udp-draft-${esc(key)}"
          oninput="DevPanel._saveDraft('${esc(suite.id)}','${esc(test.id)}',this.value)"
        >${esc(draft)}</textarea>
        <div class="udp-ann-footer">
          <select class="udp-ann-prio" id="udp-prio-${esc(key)}">
            <option value="normal">Normal</option>
            <option value="critical">🔴 Crítica</option>
            <option value="low">⬇ Baixa</option>
          </select>
          <label class="udp-ann-reg">
            <input type="checkbox" id="udp-reg-${esc(key)}" /> 🔄 Regressão
          </label>
          <button class="udp-ann-btn"
            onclick="DevPanel._createTaskFromTest('${esc(suite.id)}','${esc(test.id)}')">
            + Criar Task
          </button>
        </div>
      </div>
    </div>`;
}

function renderTestRow(suite, test) {
  const result    = (suiteResults[suite.id] || {})[test.id];
  const status    = result ? result.status : 'idle';
  const key       = `${suite.id}-${test.id}`;
  const codeOpen  = !!codeExpanded[key];
  const errOpen   = !!errorExpanded[key];
  const hasError  = result && result.error;
  const openTasks = devTasks.filter(
    t => t.suite_id === suite.id && t.test_id === test.id && t.status === 'open'
  ).length;

  let icon = '<span style="color:#484f58">○</span>';
  if (status === 'passed')  icon = '<span style="color:#3fb950">✓</span>';
  if (status === 'failed')  icon = '<span style="color:#f85149">✗</span>';
  if (status === 'skipped') icon = '<span style="color:#8b949e">○</span>';
  if (status === 'running') icon = '<span style="color:#58a6ff;animation:tp-spin 1s linear infinite;display:inline-block">⟳</span>';

  let dur = '';
  if (result?.duration) dur = `<span class="udp-test-dur">${(result.duration/1000).toFixed(2)}s</span>`;

  const taskBadge = openTasks > 0
    ? `<span class="udp-test-tasks">${openTasks}📋</span>`
    : '';

  const codeBtn = test.codeSnippet
    ? `<button class="udp-code-btn${codeOpen ? ' active' : ''}"
         onclick="event.stopPropagation();DevPanel._toggleCode('${esc(suite.id)}','${esc(test.id)}')"
         title="${codeOpen ? 'Fechar código' : 'Ver código'}">&lt;/&gt;</button>`
    : '';

  return `
    <div class="udp-test-row">
      <div class="udp-test-main"
        style="cursor:${hasError ? 'pointer' : 'default'}"
        ${hasError ? `onclick="DevPanel._toggleErr('${esc(suite.id)}','${esc(test.id)}')"` : ''}>
        <span class="udp-test-icon">${icon}</span>
        <span class="udp-test-name">${esc(test.name)}</span>
        ${taskBadge}${dur}
        <span style="flex:1"></span>
        ${codeBtn}
      </div>
      ${hasError && errOpen ? `<div class="udp-test-err">${esc(result.error)}</div>` : ''}
      ${codeOpen ? renderCodeViewer(suite, test) : ''}
    </div>`;
}

function renderSuiteCard(suite) {
  const stats    = suiteStats(suite);
  const collapsed = !!suiteCollapsed[suite.id];
  const isRunning = suiteRunning === suite.id;
  const ran      = stats.pass + stats.fail + stats.skip;

  let dot = '#484f58';
  if (isRunning)           dot = '#58a6ff';
  else if (stats.fail > 0) dot = '#f85149';
  else if (ran > 0 && stats.pass === ran) dot = '#3fb950';
  else if (ran > 0)        dot = '#d29922';

  const pw = stats.total > 0 ? ((stats.pass / stats.total) * 100).toFixed(1) : 0;
  const fw = stats.total > 0 ? ((stats.fail / stats.total) * 100).toFixed(1) : 0;

  return `
    <div class="udp-suite${collapsed ? ' collapsed' : ''}" id="udp-suite-${esc(suite.id)}">
      <div class="udp-suite-hdr" onclick="DevPanel._toggleSuite('${esc(suite.id)}')">
        <span class="udp-suite-dot" style="background:${dot}${isRunning ? ';animation:tp-pulse 1s infinite' : ''}"></span>
        <span class="udp-suite-lbl">${esc(suite.label)}</span>
        <span class="udp-suite-counts">
          ${stats.pass > 0 ? `<span style="color:#3fb950">${stats.pass}✓</span>` : ''}
          ${stats.fail > 0 ? `<span style="color:#f85149">${stats.fail}✗</span>` : ''}
          ${stats.skip > 0 ? `<span style="color:#8b949e">${stats.skip}○</span>` : ''}
        </span>
        <span class="udp-suite-chevron">▼</span>
      </div>
      <div class="udp-suite-body">
        <div class="udp-suite-bar">
          <div class="udp-suite-bar-p" style="width:${pw}%"></div>
          <div class="udp-suite-bar-f" style="width:${fw}%"></div>
        </div>
        <div class="udp-suite-tests">
          ${suite.tests.map(t => renderTestRow(suite, t)).join('')}
        </div>
        <button class="udp-suite-run"
          style="color:${suite.color};border-color:${suite.color}"
          onclick="DevPanel._runSuite('${esc(suite.id)}')"
          ${suiteRunning ? 'disabled' : ''}>
          ${isRunning ? '⏳ A correr...' : '▶ Correr ' + suite.label}
        </button>
      </div>
    </div>`;
}

function renderTestsPane() {
  const el = document.getElementById('udpTestsBody');
  if (!el) return;
  el.innerHTML = renderGlobalSummary()
    + TEST_SUITES.map(s => renderSuiteCard(s)).join('');
}

// ═══════════════════════════════════════
// RENDER — BACKLOG
// ═══════════════════════════════════════

function renderBacklog() {
  const el     = document.getElementById('udpBacklogBody');
  const badge  = document.getElementById('udpBacklogBadge');
  if (!el) return;

  const filterSel = document.getElementById('udpBacklogFilter');
  const filter = filterSel ? filterSel.value : 'open';

  const filtered = filter === 'all'
    ? devTasks
    : devTasks.filter(t => t.status === filter);

  const openCount = devTasks.filter(t => t.status === 'open').length;
  if (badge) badge.textContent = openCount > 0 ? openCount : '';

  if (filtered.length === 0) {
    el.innerHTML = `<div class="udp-backlog-empty">
      ${filter === 'open' ? '🎉 Sem tasks abertas!' : 'Nenhuma task encontrada.'}
    </div>`;
    return;
  }

  el.innerHTML = filtered.map(task => {
    const suite   = TEST_SUITES.find(s => s.id === task.suite_id);
    const test    = suite ? suite.tests.find(t => t.id === task.test_id) : null;
    const context = task.component
      ? task.component
      : (suite && test ? `${suite.label} › ${test.name}` : (task.suite_id || '—'));
    const pm      = priorityMeta(task.priority || 'normal');

    return `
      <div class="udp-task${task.regression ? ' is-reg' : ''}${task.status === 'done' ? ' is-done' : ''}">
        <div class="udp-task-top">
          <span class="udp-prio-badge ${pm.cls}">${pm.label}</span>
          <span class="udp-task-title">${esc(task.title)}</span>
        </div>
        ${task.body ? `<div class="udp-task-body">${esc(task.body)}</div>` : ''}
        <div class="udp-task-foot">
          <span class="udp-task-ctx">📍 ${esc(context)}</span>
          ${task.regression ? '<span class="udp-task-reg-badge">🔄 Regressão</span>' : ''}
          <span class="udp-task-age">${relativeTime(task.created_at)} atrás</span>
          <div class="udp-task-actions">
            ${task.status === 'open' ? `
              <button class="udp-ta crit" title="Prioridade crítica"
                onclick="DevPanel._setPrio('${esc(task.id)}','critical')">🔴</button>
              <button class="udp-ta norm" title="Prioridade normal"
                onclick="DevPanel._setPrio('${esc(task.id)}','normal')">●</button>
              <button class="udp-ta low"  title="Prioridade baixa"
                onclick="DevPanel._setPrio('${esc(task.id)}','low')">⬇</button>
              ${!task.regression ? `
                <button class="udp-ta reg" title="Marcar como regressão"
                  onclick="DevPanel._setReg('${esc(task.id)}')">🔄</button>` : ''}
              <button class="udp-ta done" title="Marcar como resolvida"
                onclick="DevPanel._closeTask('${esc(task.id)}')">✓</button>` : `
              <button class="udp-ta reopen" title="Reabrir"
                onclick="DevPanel._reopenTask('${esc(task.id)}')">↩</button>`}
            <button class="udp-ta del" title="Apagar"
              onclick="DevPanel._deleteTask('${esc(task.id)}')">✕</button>
          </div>
        </div>
      </div>`;
  }).join('');
}

// ═══════════════════════════════════════
// BADGE DO NAV
// ═══════════════════════════════════════

function updateNavBadge() {
  // Badge antigo (navbar — pode não existir mais)
  const badge = document.getElementById('devNavBadge');
  // Badge novo (sidebar esquerda)
  const leftBadge = document.getElementById('leftDevBadge');

  const { pass, fail } = globalStats();
  const ran   = pass + fail;
  const open  = devTasks.filter(t => t.status === 'open').length;
  const crit  = devTasks.filter(t => t.status === 'open' && t.priority === 'critical').length;

  let text = '', cls = 'dev-nav-badge dev-badge-idle';

  if (suiteRunning) {
    text = '⟳'; cls = 'dev-nav-badge dev-badge-running';
  } else if (fail > 0) {
    text = fail + '✗'; cls = 'dev-nav-badge dev-badge-fail';
  } else if (crit > 0) {
    text = '🔴' + crit; cls = 'dev-nav-badge dev-badge-crit';
  } else if (open > 0) {
    text = open; cls = 'dev-nav-badge dev-badge-tasks';
  } else if (ran > 0 && fail === 0) {
    text = pass + '✓'; cls = 'dev-nav-badge dev-badge-pass';
  } else {
    text = ''; cls = 'dev-nav-badge dev-badge-idle';
  }

  if (badge) { badge.textContent = text || '—'; badge.className = cls; }

  // Sidebar badge
  if (leftBadge) {
    if (text) {
      leftBadge.textContent = text;
      leftBadge.style.display = 'inline';
    } else {
      leftBadge.style.display = 'none';
    }
  }
}

// ═══════════════════════════════════════
// API TASKS
// ═══════════════════════════════════════

async function _loadTasks() {
  try {
    const r = await fetch('/api/v1/dev/tasks');
    if (r.ok) devTasks = await r.json();
  } catch (_) { devTasks = []; }
}

// ═══════════════════════════════════════
// FUNÇÕES DE TESTE (runners)
// ═══════════════════════════════════════

async function runAgentCrudTest() {
  const start = Date.now(); let createdId = null;
  try {
    const cr = await fetch('/api/v1/agents', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ symbol:'R_75', timeframe_minutes:5, stake:1.0, strategy:'rsi_ema' }) });
    const cd = await cr.json();
    if (!cr.ok) throw new Error('Criar agente falhou HTTP ' + cr.status + ': ' + (cd.detail || JSON.stringify(cd)));
    createdId = cd.id;
    if (!createdId) throw new Error('Sem campo id na resposta: ' + JSON.stringify(cd));

    const lr = await fetch('/api/v1/agents');
    const ld = await lr.json();
    if (!lr.ok) throw new Error('Listar falhou HTTP ' + lr.status);
    const agents = Array.isArray(ld) ? ld : (ld.agents || []);
    if (!agents.find(a => a.id === createdId)) throw new Error('Agente não aparece na listagem');

    const pr = await fetch('/api/v1/agents/' + createdId, { method:'PUT',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ name:'Test Agent Edited', stake:2.0 }) });
    if (!pr.ok) throw new Error('PUT falhou HTTP ' + pr.status);

    const gr = await fetch('/api/v1/agents/' + createdId);
    const gd = await gr.json();
    if (!gr.ok) throw new Error('GET falhou HTTP ' + gr.status);
    if (gd.name !== 'Test Agent Edited') throw new Error('Nome não atualizado: ' + gd.name);

    const dr = await fetch('/api/v1/agents/' + createdId, { method:'DELETE' });
    if (!dr.ok) throw new Error('DELETE falhou HTTP ' + dr.status);
    createdId = null;
    return { status:'passed', error:null, duration: Date.now()-start };
  } catch(e) {
    if (createdId) { try { await fetch('/api/v1/agents/'+createdId, {method:'DELETE'}); } catch(_){} }
    return { status:'failed', error:e.message, duration: Date.now()-start };
  }
}

async function runPauseResumeTest() {
  const start = Date.now(); let createdId = null;
  try {
    const cr = await fetch('/api/v1/agents', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ symbol:'R_75', timeframe_minutes:5, stake:1.0, strategy:'rsi_ema' }) });
    const cd = await cr.json();
    if (!cr.ok) throw new Error('Criar falhou HTTP ' + cr.status);
    createdId = cd.id;

    const pauseR = await fetch('/api/v1/agents/' + createdId + '/pause', { method:'POST' });
    if (!pauseR.ok) throw new Error('Pause falhou HTTP ' + pauseR.status);

    const afterP = await (await fetch('/api/v1/agents/' + createdId)).json();
    if (afterP.status !== 'paused') throw new Error('Status após pause: ' + afterP.status);

    const resumeR = await fetch('/api/v1/agents/' + createdId + '/resume', { method:'POST' });
    if (!resumeR.ok) throw new Error('Resume falhou HTTP ' + resumeR.status);

    await fetch('/api/v1/agents/' + createdId, { method:'DELETE' });
    createdId = null;
    return { status:'passed', error:null, duration: Date.now()-start };
  } catch(e) {
    if (createdId) { try { await fetch('/api/v1/agents/'+createdId, {method:'DELETE'}); } catch(_){} }
    return { status:'failed', error:e.message, duration: Date.now()-start };
  }
}

async function runWsConnectTest() {
  const start = Date.now();
  return new Promise(resolve => {
    const url = 'ws://' + location.host + '/ws';
    let ws, timer, done = false;
    const finish = r => {
      if (done) return; done = true;
      clearTimeout(timer);
      try { ws.close(); } catch(_) {}
      r.duration = Date.now() - start;
      resolve(r);
    };
    try {
      ws = new WebSocket(url);
      ws.onmessage = e => {
        try {
          const m = JSON.parse(e.data);
          if (m.type === 'full_state')
            finish(Array.isArray(m.agents)
              ? { status:'passed', error:null }
              : { status:'failed', error:'agents não é array' });
        } catch(e) { finish({ status:'failed', error:'Parse: ' + e.message }); }
      };
      ws.onerror = () => finish({ status:'failed', error:'WebSocket erro em ' + url });
      ws.onclose = e => { if (!done) finish({ status:'failed', error:'Fechado (code ' + e.code + ')' }); };
      timer = setTimeout(() => finish({ status:'failed', error:'Timeout 5s' }), 5000);
    } catch(e) { resolve({ status:'failed', error:e.message, duration: Date.now()-start }); }
  });
}

async function runSymbolsTest() {
  const start = Date.now();
  try {
    const r = await fetch('/api/v1/symbols');
    const d = await r.json();
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const cats = d.categories || d;
    let n = 0;
    if (Array.isArray(cats)) for (const c of cats) n += (c.symbols||[]).length;
    else if (typeof cats === 'object') n = Object.keys(cats).length;
    if (n < 1) throw new Error('Nenhum símbolo');
    return { status:'passed', error:null, duration: Date.now()-start };
  } catch(e) { return { status:'failed', error:e.message, duration: Date.now()-start }; }
}

async function runPnlHistoryTest() {
  const start = Date.now();
  try {
    const ar = await fetch('/api/v1/agents');
    if (!ar.ok) throw new Error('Listar agentes HTTP ' + ar.status);
    const agents = await ar.json();
    const list   = Array.isArray(agents) ? agents : (agents.agents || []);
    if (!list.length) return { status:'skipped', error:'Sem agentes', duration: Date.now()-start };
    const r = await fetch('/api/v1/trades/pnl-history?limit=10&agent_id=' + encodeURIComponent(list[0].id));
    const d = await r.json();
    if (!r.ok) throw new Error('HTTP ' + r.status);
    if (!Array.isArray(d)) throw new Error('Não é array: ' + typeof d);
    return { status:'passed', error:null, duration: Date.now()-start };
  } catch(e) { return { status:'failed', error:e.message, duration: Date.now()-start }; }
}

async function runStrategiesTest() {
  const start = Date.now();
  try {
    const r = await fetch('/api/v1/strategies');
    const d = await r.json();
    if (!r.ok) throw new Error('HTTP ' + r.status);
    if (!Array.isArray(d) || d.length < 1) throw new Error('Sem estratégias');
    for (const item of d) {
      if (!item.id && !item.name && !item.strategy_id)
        throw new Error('Item sem id/name: ' + JSON.stringify(item).substring(0, 60));
    }
    return { status:'passed', error:null, duration: Date.now()-start };
  } catch(e) { return { status:'failed', error:e.message, duration: Date.now()-start }; }
}

// ─── Runners da suite: Tabela de Trades ─────────────────────────────────────

async function runTradesApiStructureTest() {
  const start = Date.now();
  try {
    const resp = await fetch('/api/v1/trades?limit=20&include_open=true');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();

    if (typeof data.total !== 'number') throw new Error('Campo total ausente ou não-número (tipo: ' + typeof data.total + ')');
    if (!Array.isArray(data.trades))   throw new Error('Campo trades não é array (tipo: ' + typeof data.trades + ')');
    if (typeof data.limit  !== 'number') throw new Error('Campo limit ausente (tipo: ' + typeof data.limit + ')');
    if (typeof data.offset !== 'number') throw new Error('Campo offset ausente (tipo: ' + typeof data.offset + ')');

    const REQUIRED = ['result', 'stake', 'opened_at', 'agent_id'];
    for (const t of data.trades) {
      for (const field of REQUIRED) {
        if (t[field] === undefined)
          throw new Error('Trade id=' + t.id + ' sem campo obrigatório "' + field + '"');
      }
    }
    return { status: 'passed', error: null, duration: Date.now() - start };
  } catch(e) { return { status: 'failed', error: e.message, duration: Date.now() - start }; }
}

async function runTradesResultValuesTest() {
  const start = Date.now();
  try {
    const resp = await fetch('/api/v1/trades?limit=50');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const { trades } = await resp.json();
    const ALLOWED = new Set(['won', 'lost', 'pending', 'unknown']);
    const bad = trades.filter(t => !ALLOWED.has(t.result));
    if (bad.length > 0)
      throw new Error(bad.length + ' trade(s) com result inválido: ' +
        bad.map(t => 'id=' + t.id + ' result="' + t.result + '"').join(', '));
    return { status: 'passed', error: null, duration: Date.now() - start };
  } catch(e) { return { status: 'failed', error: e.message, duration: Date.now() - start }; }
}

async function runTradesPendingOnTopTest() {
  const start = Date.now();
  try {
    const resp = await fetch('/api/v1/trades?limit=50&include_open=true');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const { trades } = await resp.json();
    if (trades.length === 0) return { status: 'skipped', error: 'Sem trades para verificar', duration: Date.now() - start };

    const firstNonPending = trades.findIndex(t => t.result !== 'pending');
    if (firstNonPending !== -1) {
      const pendingAfter = trades.slice(firstNonPending).filter(t => t.result === 'pending');
      if (pendingAfter.length > 0)
        throw new Error(pendingAfter.length + ' trade(s) pending aparecem após trades finalizados na lista');
    }
    return { status: 'passed', error: null, duration: Date.now() - start };
  } catch(e) { return { status: 'failed', error: e.message, duration: Date.now() - start }; }
}

async function runTradesFilterResultTest() {
  const start = Date.now();
  try {
    // Filtro won
    const rWon = await fetch('/api/v1/trades?result=won&limit=20');
    if (!rWon.ok) throw new Error('HTTP ' + rWon.status + ' no filtro ?result=won');
    const { trades: tWon } = await rWon.json();
    const notWon = tWon.filter(t => t.result !== 'won');
    if (notWon.length > 0) throw new Error(notWon.length + ' trades não-won no filtro ?result=won');

    // Filtro lost
    const rLost = await fetch('/api/v1/trades?result=lost&limit=20');
    if (!rLost.ok) throw new Error('HTTP ' + rLost.status + ' no filtro ?result=lost');
    const { trades: tLost } = await rLost.json();
    const notLost = tLost.filter(t => t.result !== 'lost');
    if (notLost.length > 0) throw new Error(notLost.length + ' trades não-lost no filtro ?result=lost');

    // Filtro pending
    const rPend = await fetch('/api/v1/trades?result=pending&limit=20');
    if (!rPend.ok) throw new Error('HTTP ' + rPend.status + ' no filtro ?result=pending');
    const { trades: tPend } = await rPend.json();
    const notPend = tPend.filter(t => t.result !== 'pending');
    if (notPend.length > 0) throw new Error(notPend.length + ' trades não-pending no filtro ?result=pending');

    return { status: 'passed', error: null, duration: Date.now() - start };
  } catch(e) { return { status: 'failed', error: e.message, duration: Date.now() - start }; }
}

async function runTradesProfitFieldTest() {
  const start = Date.now();
  try {
    const resp = await fetch('/api/v1/trades?limit=50');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const { trades } = await resp.json();
    if (trades.length === 0) return { status: 'skipped', error: 'Sem trades para verificar', duration: Date.now() - start };

    const errors = [];
    for (const t of trades) {
      if (t.result === 'won'  && t.profit != null && t.profit < 0)
        errors.push('Trade ' + t.id + ': won mas profit=' + t.profit);
      if (t.result === 'lost' && t.profit != null && t.profit > 0)
        errors.push('Trade ' + t.id + ': lost mas profit=' + t.profit);
    }
    if (errors.length > 0) throw new Error(errors.join('; '));

    const finishedNullProfit = trades.filter(
      t => (t.result === 'won' || t.result === 'lost') && t.profit == null
    );
    if (finishedNullProfit.length > 0)
      throw new Error(finishedNullProfit.length + ' trade(s) finalizado(s) com profit=null: ids=' +
        finishedNullProfit.map(t => t.id).join(','));

    return { status: 'passed', error: null, duration: Date.now() - start };
  } catch(e) { return { status: 'failed', error: e.message, duration: Date.now() - start }; }
}

async function runTradesDirectionValuesTest() {
  const start = Date.now();
  try {
    const resp = await fetch('/api/v1/trades?limit=50');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const { trades } = await resp.json();
    if (trades.length === 0) return { status: 'skipped', error: 'Sem trades para verificar', duration: Date.now() - start };

    const ALLOWED_DIRS = new Set(['CALL', 'PUT', 'MULTUP', 'MULTDOWN']);
    const bad = trades.filter(t => t.direction && !ALLOWED_DIRS.has(t.direction));
    if (bad.length > 0)
      throw new Error(bad.length + ' trade(s) com direction inválida: ' +
        [...new Set(bad.map(t => t.direction))].join(', '));

    const nullDirFinished = trades.filter(
      t => !t.direction && (t.result === 'won' || t.result === 'lost')
    );
    if (nullDirFinished.length > 0)
      throw new Error(nullDirFinished.length + ' trade(s) finalizado(s) sem campo direction');

    return { status: 'passed', error: null, duration: Date.now() - start };
  } catch(e) { return { status: 'failed', error: e.message, duration: Date.now() - start }; }
}

async function runTradesTableRenderTest() {
  const start = Date.now();
  try {
    const tbody = document.getElementById('recentTradesTbody');
    if (!tbody) throw new Error('tbody#recentTradesTbody não encontrado no DOM');

    // Verificar colspan do placeholder (deve ser 6, não 7)
    const placeholder = tbody.querySelector('td[colspan]');
    if (placeholder) {
      const cs = parseInt(placeholder.getAttribute('colspan'), 10);
      if (cs !== 6) throw new Error('colspan do placeholder é ' + cs + ', esperado 6 (a tabela tem 6 colunas: Hora, Agente, Direção, Stake, Resultado, Lucro)');
    }

    const rows = [...tbody.querySelectorAll('tr.trade-row')];
    if (rows.length === 0) return { status: 'skipped', error: 'Tabela vazia — sem trades visíveis no DOM', duration: Date.now() - start };

    // Linhas won/lost não devem exibir "EM CURSO" ou "PENDING"
    const finishedRows = rows.filter(r =>
      r.classList.contains('win-row') || r.classList.contains('loss-row')
    );
    const stuckPending = finishedRows.filter(r =>
      r.textContent.includes('EM CURSO') || r.textContent.includes('PENDING')
    );
    if (stuckPending.length > 0)
      throw new Error(stuckPending.length + ' linha(s) won/lost exibindo "EM CURSO"/"PENDING" incorretamente');

    // Linhas pending não devem mostrar resultado won/lost
    const pendingRows = rows.filter(r => r.classList.contains('trade-row-pending'));
    const pendingWithResult = pendingRows.filter(r =>
      r.querySelector('.result-won') || r.querySelector('.result-lost')
    );
    if (pendingWithResult.length > 0)
      throw new Error(pendingWithResult.length + ' linha(s) pending exibindo resultado won/lost');

    // Linhas won devem ter lucro ≥ 0 na célula de lucro (col 6)
    const wonNegative = finishedRows.filter(r => {
      if (!r.classList.contains('win-row')) return false;
      const cells = r.querySelectorAll('td');
      const profitCell = cells[5];
      return profitCell && profitCell.textContent.trim().startsWith('-');
    });
    if (wonNegative.length > 0)
      throw new Error(wonNegative.length + ' linha(s) won exibindo lucro negativo');

    // Linhas lost devem ter lucro < 0 na célula de lucro (col 6)
    const lostPositive = finishedRows.filter(r => {
      if (!r.classList.contains('loss-row')) return false;
      const cells = r.querySelectorAll('td');
      const profitCell = cells[5];
      return profitCell && profitCell.textContent.trim().startsWith('+');
    });
    if (lostPositive.length > 0)
      throw new Error(lostPositive.length + ' linha(s) lost exibindo lucro positivo');

    return {
      status: 'passed', error: null, duration: Date.now() - start,
    };
  } catch(e) { return { status: 'failed', error: e.message, duration: Date.now() - start }; }
}

// ═══════════════════════════════════════
// DEV PANEL — OBJETO PÚBLICO
// ═══════════════════════════════════════

window.DevPanel = {

  // ── Painel ──────────────────────────
  open() {
    // Tentar abrir no sidebar esquerdo (novo layout)
    const sidebar = document.getElementById('leftDevSidebar');
    if (sidebar && sidebar.classList.contains('collapsed')) {
      window.LeftDev?.toggle();
    }
    // Mudar para a tab de testes
    window.LeftDev?.switchTab(_currentTab || 'tests');
    _panelOpen = true;
    // Também suportar painel antigo UDP se ainda existir
    document.getElementById('udp')?.classList.add('open');
    document.getElementById('udpOverlay')?.classList.add('open');
    if (_currentTab === 'tests') renderTestsPane();
    else renderBacklog();
  },

  close() {
    // Painel antigo
    document.getElementById('udp')?.classList.remove('open');
    document.getElementById('udpOverlay')?.classList.remove('open');
    _panelOpen = false;
  },

  switchTab(tab) {
    _currentTab = tab;
    // Sincronizar com sidebar esquerdo
    window.LeftDev?.switchTab(tab === 'tests' ? 'tests' : tab === 'backlog' ? 'backlog' : tab);
    // Tabs antigas do UDP (retrocompatibilidade)
    document.querySelectorAll('.udp-tab').forEach(b => {
      b.classList.toggle('active', b.dataset.tab === tab);
    });
    document.querySelectorAll('.udp-pane').forEach(p => {
      p.classList.toggle('hidden', !p.id.endsWith(tab));
    });
    if (tab === 'tests')   renderTestsPane();
    if (tab === 'backlog') renderBacklog();
  },

  // ── Testes ──────────────────────────
  _toggleSuite(id) { suiteCollapsed[id] = !suiteCollapsed[id]; renderTestsPane(); },
  _toggleErr(sId, tId) {
    const k = sId + '-' + tId; errorExpanded[k] = !errorExpanded[k]; renderTestsPane();
  },
  _toggleCode(sId, tId) {
    const k = sId + '-' + tId; codeExpanded[k] = !codeExpanded[k]; renderTestsPane();
  },
  _saveDraft(sId, tId, v) { annotationDraft[sId + '-' + tId] = v; },

  async _runSuite(suiteId) {
    const suite = TEST_SUITES.find(s => s.id === suiteId);
    if (!suite || suiteRunning) return;
    suiteRunning = suiteId;
    updateNavBadge(); renderTestsPane();

    for (const test of suite.tests) {
      if (!suiteResults[suiteId]) suiteResults[suiteId] = {};
      suiteResults[suiteId][test.id] = { status:'running', error:null, duration:0, lastRun: new Date().toISOString() };
      renderTestsPane();
      const start = Date.now();
      let result = { status:'failed', error:'Função não encontrada', duration:0 };
      try {
        const fn = window[test.runFn];
        if (typeof fn === 'function') result = await fn();
        else result = { status:'failed', error: `"${test.runFn}" não encontrada`, duration:0 };
      } catch(e) { result = { status:'failed', error:e.message||String(e), duration: Date.now()-start }; }
      if (!result.duration) result.duration = Date.now() - start;
      result.lastRun = new Date().toISOString();
      suiteResults[suiteId][test.id] = result;
    }

    suiteRunning = null;
    if (_store) _store.set('results-' + suiteId, suiteResults[suiteId]);
    updateNavBadge(); renderTestsPane();
  },

  async _createTaskFromTest(suiteId, testId) {
    const key  = suiteId + '-' + testId;
    const body = (annotationDraft[key] || '').trim();
    const ta   = document.getElementById('udp-draft-' + key);
    if (!body) {
      if (ta) { ta.style.borderColor = '#f85149';
        setTimeout(() => ta.style.borderColor = '', 2000); }
      return;
    }
    const title    = body.split('\n')[0].substring(0, 80);
    const prioEl   = document.getElementById('udp-prio-' + key);
    const regEl    = document.getElementById('udp-reg-' + key);
    const priority = prioEl ? prioEl.value : 'normal';
    const regression = regEl ? regEl.checked : false;

    try {
      const r = await fetch('/api/v1/dev/tasks', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ suite_id:suiteId, test_id:testId, title, body, priority, regression }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const task = await r.json();
      devTasks.unshift(task);
      annotationDraft[key] = '';
      codeExpanded[key] = false;
      renderTestsPane();
      renderBacklog();
      updateNavBadge();
    } catch(e) { alert('Erro ao criar task: ' + e.message); }
  },

  // ── Backlog ──────────────────────────
  renderBacklog,

  async quickAddTask() {
    const titleEl = document.getElementById('udpQaTitle');
    const bodyEl  = document.getElementById('udpQaBody');
    const prioEl  = document.getElementById('udpQaPriority');
    const regEl   = document.getElementById('udpQaReg');
    const title   = (titleEl?.value || '').trim();
    if (!title) { if(titleEl) { titleEl.style.borderColor='#f85149'; setTimeout(()=>titleEl.style.borderColor='',2000); } return; }
    try {
      const r = await fetch('/api/v1/dev/tasks', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title, body: bodyEl?.value || '',
          priority: prioEl?.value || 'normal',
          regression: regEl?.checked || false,
          component: 'Manual',
        }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const task = await r.json();
      devTasks.unshift(task);
      if (titleEl) titleEl.value = '';
      if (bodyEl)  bodyEl.value  = '';
      renderBacklog();
      updateNavBadge();
    } catch(e) { alert('Erro: ' + e.message); }
  },

  async _setPrio(id, prio) {
    try {
      const r = await fetch('/api/v1/dev/tasks/' + id, {
        method:'PATCH', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ priority: prio }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const u = await r.json();
      const i = devTasks.findIndex(t => t.id === id);
      if (i >= 0) devTasks[i] = u;
      renderBacklog(); updateNavBadge();
    } catch(e) { alert('Erro: ' + e.message); }
  },

  async _setReg(id) {
    try {
      const r = await fetch('/api/v1/dev/tasks/' + id, {
        method:'PATCH', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ regression: true }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const u = await r.json();
      const i = devTasks.findIndex(t => t.id === id);
      if (i >= 0) devTasks[i] = u;
      renderBacklog();
    } catch(e) { alert('Erro: ' + e.message); }
  },

  async _closeTask(id) {
    try {
      const r = await fetch('/api/v1/dev/tasks/' + id, {
        method:'PATCH', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ status:'done' }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const u = await r.json();
      const i = devTasks.findIndex(t => t.id === id);
      if (i >= 0) devTasks[i] = u;
      renderBacklog(); updateNavBadge();
    } catch(e) { alert('Erro: ' + e.message); }
  },

  async _reopenTask(id) {
    try {
      const r = await fetch('/api/v1/dev/tasks/' + id, {
        method:'PATCH', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ status:'open' }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const u = await r.json();
      const i = devTasks.findIndex(t => t.id === id);
      if (i >= 0) devTasks[i] = u;
      renderBacklog(); updateNavBadge();
    } catch(e) { alert('Erro: ' + e.message); }
  },

  async _deleteTask(id) {
    if (!confirm('Apagar task permanentemente?')) return;
    try {
      const r = await fetch('/api/v1/dev/tasks/' + id, { method:'DELETE' });
      if (r.status !== 204 && !r.ok) throw new Error('HTTP ' + r.status);
      devTasks = devTasks.filter(t => t.id !== id);
      renderBacklog(); renderTestsPane(); updateNavBadge();
    } catch(e) { alert('Erro: ' + e.message); }
  },

  // ── Init ────────────────────────────
  async init() {
    // Restaurar resultados persistidos
    if (_store) {
      for (const suite of TEST_SUITES) {
        const saved = _store.get('results-' + suite.id, null);
        if (saved) suiteResults[suite.id] = saved;
      }
    }
    await _loadTasks();
    updateNavBadge();
  }
};

// Exposição de runners globais (chamados via window[runFn])
window.runAgentCrudTest           = runAgentCrudTest;
window.runPauseResumeTest         = runPauseResumeTest;
window.runWsConnectTest           = runWsConnectTest;
window.runSymbolsTest             = runSymbolsTest;
window.runPnlHistoryTest          = runPnlHistoryTest;
window.runStrategiesTest          = runStrategiesTest;
// Tabela de Trades
window.runTradesApiStructureTest  = runTradesApiStructureTest;
window.runTradesResultValuesTest  = runTradesResultValuesTest;
window.runTradesPendingOnTopTest  = runTradesPendingOnTopTest;
window.runTradesFilterResultTest  = runTradesFilterResultTest;
window.runTradesProfitFieldTest   = runTradesProfitFieldTest;
window.runTradesDirectionValuesTest = runTradesDirectionValuesTest;
window.runTradesTableRenderTest   = runTradesTableRenderTest;

// Alias retrocompatibilidade
window.TestsPanel = {
  render:         () => renderTestsPane(),
  runSuite:       id => DevPanel._runSuite(id),
  toggleCollapse: id => DevPanel._toggleSuite(id),
  toggleError:    (s, t) => DevPanel._toggleErr(s, t),
  init:           () => DevPanel.init(),
};

// Auto-init quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
  DevPanel.init();
});
