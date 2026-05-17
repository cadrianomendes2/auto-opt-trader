/**
 * test-countdown.js — Script de diagnóstico temporário para o bug de persistência do countdown.
 *
 * Como usar no console do browser:
 *   import('/static/js/test-countdown.js').then(m => m.runCountdownDiagnostic())
 *
 * Ou adicionar temporariamente ao index.html:
 *   <script type="module" src="/static/js/test-countdown.js"></script>
 *
 * REMOVA ESTE ARQUIVO APÓS O DIAGNÓSTICO.
 */

const COUNTDOWN_STORAGE_PREFIX = 'bot_countdown_';

export function runCountdownDiagnostic() {
  console.group('[DIAGNÓSTICO] Countdown Persistence Debug');

  // ── PASSO 1: Estado do localStorage ANTES do teste ──────────────────────
  console.group('PASSO 1 — localStorage ANTES do teste');
  const keysBefore = [];
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (k && k.startsWith(COUNTDOWN_STORAGE_PREFIX)) keysBefore.push(k);
  }
  console.log('Chaves de countdown existentes:', keysBefore);
  console.groupEnd();

  // ── PASSO 2: Identificar agentes no DOM ─────────────────────────────────
  console.group('PASSO 2 — Cards de agentes no DOM');
  const agentCards = document.querySelectorAll('[id^="agent-card-"]');
  console.log(`Cards encontrados no DOM: ${agentCards.length}`);
  agentCards.forEach(card => console.log(' •', card.id));
  if (agentCards.length === 0) {
    console.error('❌ NENHUM card de agente encontrado no DOM! renderAgentCards() ainda não foi chamado, ou falhou.');
    console.groupEnd();
    console.groupEnd();
    return;
  }
  console.groupEnd();

  // ── PASSO 3: Simular localStorage com um countdown para o 1º agente ────
  const firstCard = agentCards[0];
  const agentId = firstCard.id.replace('agent-card-', '');
  const key = `${COUNTDOWN_STORAGE_PREFIX}${agentId}`;
  const simulatedData = {
    direction: 'CALL',
    startedAt: Date.now() - 30000,   // começou há 30 segundos
    totalSeconds: 120,
  };

  console.group(`PASSO 3 — Inserindo countdown simulado para agente "${agentId}"`);
  try {
    localStorage.setItem(key, JSON.stringify(simulatedData));
    const readBack = localStorage.getItem(key);
    console.log('✅ localStorage.setItem funcionou. Valor lido de volta:', readBack);
  } catch (e) {
    console.error('❌ FALHA em localStorage.setItem:', e);
    console.groupEnd();
    console.groupEnd();
    return;
  }
  console.groupEnd();

  // ── PASSO 4: Chamar restoreCountdownsFromStorage (se acessível) ─────────
  console.group('PASSO 4 — Chamando restoreCountdownsFromStorage()');
  // A função não está exportada publicamente; vamos replicar sua lógica aqui para diagnóstico
  const keysToRestore = [];
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (k && k.startsWith(COUNTDOWN_STORAGE_PREFIX)) keysToRestore.push(k);
  }
  console.log('Chaves a restaurar:', keysToRestore);

  for (const k of keysToRestore) {
    const agId = k.slice(COUNTDOWN_STORAGE_PREFIX.length);
    console.group(`  Processando agente: ${agId}`);

    const cardEl = document.getElementById(`agent-card-${agId}`);
    console.log(`  Card no DOM (agent-card-${agId}):`, cardEl ? '✅ ENCONTRADO' : '❌ NÃO ENCONTRADO');

    if (!cardEl) {
      console.warn('  ⚠️ Card não encontrado → entrada órfã (seria removida)');
      console.groupEnd();
      continue;
    }

    try {
      const raw = localStorage.getItem(k);
      const { direction, startedAt, totalSeconds } = JSON.parse(raw);
      const elapsedSeconds = (Date.now() - startedAt) / 1000;
      const remaining = Math.round(totalSeconds - elapsedSeconds);
      console.log(`  Dados: direction=${direction}, startedAt=${new Date(startedAt).toISOString()}, totalSeconds=${totalSeconds}`);
      console.log(`  Tempo decorrido: ${elapsedSeconds.toFixed(1)}s, Restante: ${remaining}s`);

      if (remaining <= 0) {
        console.warn('  ⚠️ Countdown já expirou → seria ignorado');
        console.groupEnd();
        continue;
      }

      // Verificar se o strategy-selector existe (seletor usado no insertBefore)
      const stratSel = cardEl.querySelector(`#strategy-selector-${agId}`);
      console.log(`  #strategy-selector-${agId} dentro do card:`, stratSel ? '✅ ENCONTRADO' : '❌ NÃO ENCONTRADO — countdown seria appendado ao final');

      // Verificar se já existe countdown no card
      const existingCd = document.getElementById(`countdown-${agId}`);
      console.log(`  #countdown-${agId} já existe:`, existingCd ? '⚠️ SIM (seria removido antes de recriar)' : 'NÃO (será criado)');

      console.log(`  ✅ Countdown SERIA restaurado com ${remaining}s restantes`);
    } catch (e) {
      console.error('  ❌ Erro ao parsear dados do countdown:', e);
    }
    console.groupEnd();
  }
  console.groupEnd();

  // ── PASSO 5: Simular o que acontece quando full_state chega ─────────────
  console.group('PASSO 5 — Simulando o que acontece quando full_state (WS) chega');
  console.warn('⚠️ Quando o WebSocket conecta e recebe full_state, renderAgentCards() é chamado.');
  console.warn('⚠️ renderAgentCards() faz: container.innerHTML = "" → APAGA TODOS OS COUNTDOWN ELEMENTS.');
  console.warn('⚠️ O countdown restaurado no PASSO 4 seria DESTRUÍDO neste momento.');
  console.warn('⚠️ restoreCountdownsFromStorage() NÃO é chamada novamente após full_state.');

  // Verificar se os dados ainda estão no localStorage APÓS renderAgentCards seria chamado
  console.log('O localStorage AINDA tem os dados? (verificar manualmente após full_state chegar)');
  const keyAfter = localStorage.getItem(key);
  console.log(`  localStorage.getItem("${key}"):`, keyAfter ? '✅ SIM — dados preservados, mas DOM já foi destruído' : '❌ NÃO — dados foram removidos');
  console.groupEnd();

  // ── PASSO 6: Verificar updateAgentCard ───────────────────────────────────
  console.group('PASSO 6 — updateAgentCard também destrói countdowns?');
  console.warn('⚠️ updateAgentCard() faz: card.innerHTML = buildAgentCardHTML(agent)');
  console.warn('⚠️ Isso TAMBÉM apaga qualquer countdown ativo no card.');
  console.warn('⚠️ Eventos agent_update e agent_status_changed chamam updateAgentCard().');
  console.groupEnd();

  // ── RESUMO ───────────────────────────────────────────────────────────────
  console.group('RESUMO DO DIAGNÓSTICO');
  console.error('BUG #1 (PRINCIPAL): Handler full_state chama renderAgentCards() que destrói countdowns restaurados.');
  console.error('BUG #2 (SECUNDÁRIO): updateAgentCard() substitui card.innerHTML, apagando countdown ativo.');
  console.info('FIX #1: Chamar restoreCountdownsFromStorage() APÓS renderAgentCards() no handler full_state.');
  console.info('FIX #2: updateAgentCard() deve preservar e reinserir o countdown element se existir no estado.');
  console.groupEnd();

  // Limpar dado simulado do localStorage
  localStorage.removeItem(key);
  console.log(`[cleanup] Dado simulado "${key}" removido do localStorage.`);

  console.groupEnd();
}

// Auto-executar quando o DOM estiver pronto
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(runCountdownDiagnostic, 2000); // aguardar renderAgentCards
  });
} else {
  setTimeout(runCountdownDiagnostic, 2000);
}
