"""
BotTask - Loop principal de cada bot de trading individual.
"""
import asyncio
import logging
from collections import deque
from datetime import datetime
from typing import Dict, Any, Callable, Optional, List

from src.core.deriv_client import DerivClient
from src.core.risk_manager import RiskManager
from src.core.signal_generator import generate_signal
from src.db import trade_repository

logger = logging.getLogger(__name__)


class BotTask:
    """
    Representa um bot de trading individual.
    Gerencia o loop de operação, execução de trades e tratamento de erros.
    """

    def __init__(self, config: Dict[str, Any], broadcast_fn: Callable,
                 save_config_fn: Callable):
        self.config = config
        self.agent_id = config["id"]
        self.broadcast_fn = broadcast_fn
        self.save_config_fn = save_config_fn

        self.paused = config.get("status") == "paused"
        self._status = config.get("status", "stopped")

        # Runtime stats
        runtime = config.get("runtime", {})
        self.total_trades = runtime.get("total_trades", 0)
        self.wins = runtime.get("wins", 0)
        self.losses = runtime.get("losses", 0)
        self.total_pnl = runtime.get("total_pnl", 0.0)
        self.consecutive_losses = runtime.get("consecutive_losses", 0)
        self.last_trade_at: Optional[str] = runtime.get("last_trade_at")

        # Coin flip: rolling log dos últimos 3 resultados (para debug panel)
        self._countdown_log: deque = deque(maxlen=3)

        # Cliente Deriv
        token = config.get("api_token") or None
        self.deriv = DerivClient(token=token)

        # Gerenciador de risco
        risk_config = config.get("risk", {})
        self.risk_mgr = RiskManager(risk_config)
        self.risk_mgr.consecutive_losses = self.consecutive_losses

        # Controle de erros consecutivos
        self._error_count = 0
        self._max_errors = 5

    @property
    def status(self) -> str:
        return self._status

    async def run(self) -> None:
        """Loop principal do bot."""
        logger.info(f"[{self.agent_id}] Bot iniciando...")
        self._status = "running"
        self.paused = False

        granularity_seconds = self.config.get("timeframe_minutes", 5) * 60

        try:
            await self.deriv.connect()
        except Exception as e:
            logger.error(f"[{self.agent_id}] Falha ao conectar ao Deriv: {e}")
            await self._set_status("error", str(e))
            return

        await self.broadcast_fn({
            "type": "agent_status_changed",
            "payload": {
                "agent_id": self.agent_id,
                "old_status": "stopped",
                "new_status": "running",
                "reason": "Bot iniciado",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        })

        while True:
            try:
                if self.paused:
                    await asyncio.sleep(5)
                    continue

                # Buscar velas
                df = await self.deriv.get_candles(
                    symbol=self.config.get("symbol", "R_75"),
                    granularity=granularity_seconds,
                    count=200,
                )

                if df.empty:
                    logger.warning(f"[{self.agent_id}] Sem velas recebidas. Aguardando...")
                    await asyncio.sleep(10)
                    continue

                # Gerar sinal
                strategy = self.config.get("strategy", "rsi_ema")
                strategy_params = self.config.get("strategy_params", {})
                signal = generate_signal(df, strategy, strategy_params)

                logger.info(f"[{self.agent_id}] Signal gerado: {signal} | Candles: {len(df)} | Estratégia: {strategy}")

                if signal != "wait":
                    can_trade, reason = self.risk_mgr.can_trade()
                    if can_trade:
                        await self._execute_trade(signal)
                        self._error_count = 0
                    else:
                        logger.info(f"[{self.agent_id}] Trade bloqueado pelo risco: {reason}")
                        if "limit" in reason.lower() or "consecutiv" in reason.lower():
                            await self._set_status("limit_hit", reason)
                            return

                # ── Timing: coin_flip usa intervalos fixos por duração ──────
                # 2min → 120s | 5min → 300s | outros → mín 300s
                duration_minutes = self.config.get("timeframe_minutes", 5)
                if strategy == "coin_flip":
                    if duration_minutes == 2:
                        sleep_time = 120
                    elif duration_minutes == 5:
                        sleep_time = 300
                    else:
                        sleep_time = 300  # mínimo 5 minutos para outros timeframes
                    logger.debug(
                        f"[{self.agent_id}] CoinFlip sleep: {sleep_time}s "
                        f"(timeframe={duration_minutes}min)"
                    )
                else:
                    # Aguardar próxima vela pelo alinhamento de granularidade
                    sleep_time = self._seconds_to_next_candle(granularity_seconds)

                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                logger.info(f"[{self.agent_id}] Bot cancelado.")
                await self.deriv.disconnect()
                raise

            except Exception as e:
                self._error_count += 1
                logger.error(f"[{self.agent_id}] Erro #{self._error_count}: {e}")

                if self._error_count >= self._max_errors:
                    logger.error(f"[{self.agent_id}] Muitos erros consecutivos. Parando bot.")
                    await self._set_status("error", str(e))
                    await self.deriv.disconnect()
                    return

                # Tentar reconectar se a conexão caiu
                if not self.deriv.is_connected:
                    try:
                        await self.deriv.reconnect()
                    except Exception as reconnect_err:
                        logger.error(f"[{self.agent_id}] Falha no reconnect: {reconnect_err}")

                await asyncio.sleep(10)

    async def _execute_trade(self, signal: str) -> None:
        """Executa um trade completo: proposal → buy → wait result.

        Fluxo corrigido (definitivo):
          1. Insere o registro como 'pending' NO BANCO antes de enviar à Deriv
          2. Emite trade_executed com db_id para o frontend adicionar na tabela
          3. Aguarda o resultado (place_and_wait)
          4. Finaliza o registro no banco (finalize_trade)
          5. Emite trade_closed com db_id para o frontend atualizar a linha existente
        """
        stake = self.config.get("stake", 5.0)
        contract_type = "CALL" if signal == "call" else "PUT"
        symbol = self.config.get("symbol", "R_75")
        duration = self.config.get("timeframe_minutes", 5)
        strategy = self.config.get("strategy", "rsi_ema")

        opened_at = datetime.utcnow().isoformat() + "Z"
        # Calcular timestamp esperado de fechamento
        from datetime import timezone
        opened_ts = datetime.utcnow().replace(tzinfo=timezone.utc)
        expected_close_ts = opened_ts.timestamp() + duration * 60
        expected_close_at = datetime.utcfromtimestamp(expected_close_ts).isoformat() + "Z"

        # ── PASSO 1: Inserir IMEDIATAMENTE no banco como 'pending' ──────────
        # Isso garante que o trade apareça na API /trades?include_open=true
        # antes mesmo de a Deriv confirmar a abertura do contrato.
        db_id = await trade_repository.insert_pending_trade(
            agent_id=self.agent_id,
            symbol=symbol,
            direction=contract_type,
            stake=stake,
            strategy=strategy,
            opened_at=opened_at,
        )

        # ── PASSO 2: Registrar no log rolling (máx 3 entradas) ──────────────
        self._countdown_log.append({
            "direction": contract_type,
            "opened_at": opened_at,
            "expected_close_at": expected_close_at,
            "duration_seconds": duration * 60,
        })

        # ── PASSO 3: Notificar o frontend via WS com db_id ──────────────────
        # O frontend usa db_id como chave estável para rastrear esta linha
        # na tabela de trades durante toda a duração do contrato.
        await self.broadcast_fn({
            "type": "trade_executed",
            "payload": {
                "agent_id": self.agent_id,
                "db_id": db_id,          # chave estável para tracking no frontend
                "symbol": symbol,
                "direction": contract_type,
                "stake": stake,
                "strategy": strategy,
                "opened_at": opened_at,
                "duration_minutes": duration,
                "duration_seconds": duration * 60,
                "expected_close_at": expected_close_at,
            }
        })

        # ── PASSO 4: Iniciar countdown a cada segundo ────────────────────────
        asyncio.ensure_future(self._broadcast_countdown(
            duration_seconds=duration * 60,
            expected_close_at=expected_close_at,
            db_id=db_id,
        ))

        try:
            # ── PASSO 5: Executar trade na Deriv (bloqueante até fechar) ────
            result = await self.deriv.place_and_wait(
                symbol=symbol,
                contract_type=contract_type,
                duration=duration,
                stake=stake,
            )

            profit = result.get("profit", 0.0)
            trade_result = result.get("result", "lost")

            # ── PASSO 6: Finalizar o registro no banco ───────────────────────
            # Atualiza o registro 'pending' criado no Passo 1 com o resultado real.
            await trade_repository.finalize_trade(
                rowid=db_id,
                contract_id=result.get("contract_id"),
                result=trade_result,
                profit=profit,
                payout=result.get("payout"),
                ask_price=result.get("ask_price"),
                entry_price=result.get("entry_price"),
                exit_price=result.get("exit_price"),
                closed_at=result.get("closed_at"),
            )

            # Atualizar stats de runtime
            self._update_runtime(profit, trade_result)

            # Atualizar risk manager
            self.risk_mgr.update(profit, trade_result)

            # Salvar estado no agents.json
            await self.save_config_fn()

            # ── PASSO 7: Notificar frontend que o trade fechou ───────────────
            # db_id permite ao frontend localizar e atualizar a linha existente
            # na tabela (sem criar duplicata).
            await self.broadcast_fn({
                "type": "trade_closed",
                "payload": {
                    "agent_id": self.agent_id,
                    "db_id": db_id,          # chave para resolver linha pendente
                    "contract_id": result.get("contract_id"),
                    "symbol": symbol,
                    "direction": contract_type,
                    "stake": stake,
                    "result": trade_result,
                    "profit": profit,
                    "payout": result.get("payout"),
                    "entry_price": result.get("entry_price"),
                    "exit_price": result.get("exit_price"),
                    "opened_at": opened_at,
                    "closed_at": result.get("closed_at"),
                    "cumulative_pnl": self.total_pnl,
                    "win_rate": self._calc_win_rate(),
                }
            })

            # Broadcast: atualização do agente
            await self.broadcast_fn({
                "type": "agent_update",
                "payload": self._get_stats_payload(),
            })

        except asyncio.CancelledError:
            # Bot cancelado durante trade ativo — marcar como unknown para recovery
            try:
                await trade_repository.mark_trade_unknown_by_id(db_id)
            except Exception:
                pass
            raise
        except Exception as e:
            logger.error(f"[{self.agent_id}] Erro ao executar trade: {e}")
            # Marcar o registro pendente como unknown para não ficar orphan
            try:
                await trade_repository.mark_trade_unknown_by_id(db_id)
            except Exception:
                pass
            raise

    async def _broadcast_countdown(self, duration_seconds: int, expected_close_at: str,
                                    db_id: Optional[int] = None) -> None:
        """Emite mensagens de countdown a cada segundo até o fechamento do trade.
        O payload inclui 'recent_countdowns': lista rolling dos últimos 3 countdowns
        iniciados por este agente (sem sobrescrever entradas anteriores).
        db_id é incluído no payload para que o frontend associe o countdown
        à linha correta na tabela de trades.
        """
        remaining = duration_seconds
        interval = 1  # segundos entre cada broadcast

        # Para durações longas (>60s) usar intervalos maiores para economizar bandwidth
        if duration_seconds > 300:
            interval = 10
        elif duration_seconds > 60:
            interval = 5

        try:
            while remaining > 0:
                await self.broadcast_fn({
                    "type": "trade_countdown",
                    "payload": {
                        "agent_id": self.agent_id,
                        "db_id": db_id,
                        "remaining_seconds": remaining,
                        "total_seconds": duration_seconds,
                        "expected_close_at": expected_close_at,
                        "progress_pct": round((1 - remaining / duration_seconds) * 100, 1),
                        # Rolling log: lista dos últimos 3 countdowns iniciados (não sobrescreve)
                        "recent_countdowns": list(self._countdown_log),
                    }
                })
                await asyncio.sleep(interval)
                remaining = max(0, remaining - interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"[{self.agent_id}] Erro no countdown broadcast: {e}")

    def get_countdown_log(self) -> List[Dict[str, Any]]:
        """Retorna os últimos 3 countdowns registrados (para debug/API)."""
        return list(self._countdown_log)

    def _update_runtime(self, profit: float, result: str) -> None:
        """Atualiza as estatísticas de runtime."""
        self.total_trades += 1
        self.total_pnl = round(self.total_pnl + profit, 2)
        self.last_trade_at = datetime.utcnow().isoformat() + "Z"

        if result == "won":
            self.wins += 1
            self.consecutive_losses = 0
        else:
            self.losses += 1
            self.consecutive_losses += 1

    def _calc_win_rate(self) -> float:
        """Calcula o win rate atual."""
        if self.total_trades == 0:
            return 0.0
        return round(self.wins / self.total_trades, 4)

    def _get_stats_payload(self) -> Dict[str, Any]:
        """Retorna o payload de stats para broadcast."""
        return {
            "agent_id": self.agent_id,
            "status": self._status,
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "total_pnl": self.total_pnl,
            "win_rate": self._calc_win_rate(),
            "consecutive_losses": self.consecutive_losses,
            "last_trade_at": self.last_trade_at,
        }

    def get_runtime_dict(self) -> Dict[str, Any]:
        """Retorna o runtime como dicionário para persistência."""
        return {
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "total_pnl": self.total_pnl,
            "consecutive_losses": self.consecutive_losses,
            "last_trade_at": self.last_trade_at,
            "started_at": self.config.get("runtime", {}).get("started_at"),
            "paused_at": self.config.get("runtime", {}).get("paused_at"),
            "error_message": None,
        }

    async def pause(self) -> None:
        """Pausa o bot (mantém o loop rodando, mas pula execuções)."""
        self.paused = True
        self._status = "paused"
        await self.broadcast_fn({
            "type": "agent_status_changed",
            "payload": {
                "agent_id": self.agent_id,
                "old_status": "running",
                "new_status": "paused",
                "reason": "Pausado manualmente",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        })

    async def resume(self) -> None:
        """Retoma o bot após uma pausa."""
        self.paused = False
        self._status = "running"
        await self.broadcast_fn({
            "type": "agent_status_changed",
            "payload": {
                "agent_id": self.agent_id,
                "old_status": "paused",
                "new_status": "running",
                "reason": "Retomado manualmente",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        })

    async def _set_status(self, new_status: str, reason: str = "") -> None:
        """Muda o status do bot e notifica via broadcast."""
        old_status = self._status
        self._status = new_status

        await self.broadcast_fn({
            "type": "agent_status_changed",
            "payload": {
                "agent_id": self.agent_id,
                "old_status": old_status,
                "new_status": new_status,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        })

        await self.save_config_fn()

    def _seconds_to_next_candle(self, granularity_seconds: int) -> float:
        """
        Calcula quantos segundos faltam para a próxima vela ser fechada.
        Alinha com o início do próximo período de granularidade.
        """
        now = datetime.utcnow()
        current_timestamp = int(now.timestamp())
        seconds_into_period = current_timestamp % granularity_seconds
        seconds_to_next = granularity_seconds - seconds_into_period

        # Adicionar pequeno buffer para garantir que a vela esteja fechada
        return max(seconds_to_next + 2, 10)
