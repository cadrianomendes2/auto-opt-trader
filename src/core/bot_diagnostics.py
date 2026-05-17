"""
Bot Diagnostics — analisa periodicamente o desempenho dos agentes e gera
uma lista de tarefas/sugestões que são transmitidas ao dashboard via WebSocket.
Cada tarefa tem: id, prioridade (high/medium/low), categoria, título, descrição.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

# Intervalo entre rodadas de diagnóstico (segundos)
DIAG_INTERVAL = 60

# Thresholds configuráveis
_THRESHOLDS = {
    "min_win_rate": 0.45,          # abaixo disso → alerta
    "max_consecutive_losses": 3,   # acima disso → alerta
    "min_trades_for_eval": 10,     # mínimo de trades para avaliar win rate
    "idle_minutes": 30,            # tempo sem trade antes de alertar
    "max_pnl_drawdown": -20.0,     # PnL abaixo disso → alerta crítico
}


def _generate_tasks(agents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Gera lista de tarefas/alertas com base no estado dos agentes."""
    tasks: List[Dict[str, Any]] = []
    now = datetime.now(tz=timezone.utc)

    if not agents:
        tasks.append({
            "id": "no_agents",
            "priority": "medium",
            "category": "setup",
            "title": "Nenhum agente configurado",
            "description": "Crie pelo menos um agente para começar a operar.",
        })
        return tasks

    running = [a for a in agents if a.get("status") == "running"]
    stopped = [a for a in agents if a.get("status") not in ("running", "paused")]

    # ── Agentes parados ─────────────────────────────────────
    for a in stopped:
        tasks.append({
            "id": f"stopped_{a['id']}",
            "priority": "medium",
            "category": "status",
            "title": f"Agente '{a['name']}' está parado",
            "description": (
                f"O agente '{a['name']}' ({a.get('symbol', '?')}) não está em execução. "
                "Verifique a configuração ou inicie manualmente."
            ),
        })

    for a in agents:
        name = a.get("name", a["id"])
        total = a.get("total_trades", 0)
        wins = a.get("wins", 0)
        losses = a.get("losses", 0)
        pnl = a.get("total_pnl", 0.0)
        consec = a.get("consecutive_losses", 0)
        win_rate = a.get("win_rate", 0.0)
        last_trade_at_raw = a.get("last_trade_at")

        # ── PnL muito negativo ───────────────────────────────
        if pnl < _THRESHOLDS["max_pnl_drawdown"]:
            tasks.append({
                "id": f"drawdown_{a['id']}",
                "priority": "high",
                "category": "risk",
                "title": f"Drawdown crítico em '{name}'",
                "description": (
                    f"PnL acumulado de ${pnl:.2f}. Considere pausar o agente, "
                    "revisar a estratégia ou reduzir o stake."
                ),
            })

        # ── Win rate baixo ───────────────────────────────────
        if total >= _THRESHOLDS["min_trades_for_eval"] and win_rate < _THRESHOLDS["min_win_rate"]:
            tasks.append({
                "id": f"winrate_{a['id']}",
                "priority": "high" if win_rate < 0.35 else "medium",
                "category": "performance",
                "title": f"Win rate baixo em '{name}' ({win_rate:.0%})",
                "description": (
                    f"{wins}W / {losses}L em {total} trades. "
                    "Considere trocar a estratégia, ajustar os parâmetros RSI/EMA "
                    "ou selecionar um símbolo diferente."
                ),
            })

        # ── Perdas consecutivas ──────────────────────────────
        if consec >= _THRESHOLDS["max_consecutive_losses"]:
            tasks.append({
                "id": f"consec_{a['id']}",
                "priority": "high",
                "category": "risk",
                "title": f"{consec} perdas consecutivas em '{name}'",
                "description": (
                    f"O agente '{name}' acumulou {consec} perdas seguidas. "
                    "Verifique se o mercado está em tendência contra a estratégia."
                ),
            })

        # ── Agente rodando mas sem trades recentes ───────────
        if a.get("status") == "running" and last_trade_at_raw:
            try:
                last_dt = datetime.fromisoformat(
                    last_trade_at_raw.replace("Z", "+00:00")
                )
                idle_min = (now - last_dt).total_seconds() / 60
                if idle_min > _THRESHOLDS["idle_minutes"]:
                    tasks.append({
                        "id": f"idle_{a['id']}",
                        "priority": "low",
                        "category": "status",
                        "title": f"'{name}' ocioso há {idle_min:.0f} min",
                        "description": (
                            "O agente está rodando mas não gerou trades nos últimos "
                            f"{idle_min:.0f} minutos. Pode ser sinal fraco ou erro silencioso."
                        ),
                    })
            except Exception:
                pass

    # ── Tudo OK ─────────────────────────────────────────────
    if not tasks and running:
        tasks.append({
            "id": "all_ok",
            "priority": "low",
            "category": "info",
            "title": "Todos os agentes operando normalmente",
            "description": (
                f"{len(running)} agente(s) em execução sem alertas. "
                "Continue monitorando o desempenho."
            ),
        })

    # Ordenar: high → medium → low
    priority_order = {"high": 0, "medium": 1, "low": 2}
    tasks.sort(key=lambda t: priority_order.get(t["priority"], 9))
    return tasks


async def run_diagnostics_loop(
    get_agents_fn: Callable[[], List[Dict[str, Any]]],
    broadcast_fn: Callable,
) -> None:
    """
    Loop de diagnóstico contínuo.
    A cada DIAG_INTERVAL segundos analisa os agentes e transmite as tarefas.
    """
    logger.info("[Diagnostics] Loop de diagnóstico iniciado.")
    while True:
        await asyncio.sleep(DIAG_INTERVAL)
        try:
            agents = get_agents_fn()
            tasks = _generate_tasks(agents)
            await broadcast_fn({
                "type": "bot_tasks_update",
                "payload": {
                    "tasks": tasks,
                    "generated_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            })
            logger.debug(f"[Diagnostics] {len(tasks)} tarefa(s) transmitida(s).")
        except Exception as exc:
            logger.warning(f"[Diagnostics] Erro no loop: {exc}")
