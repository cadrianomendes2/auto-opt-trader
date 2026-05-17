"""
Cliente WebSocket para a Deriv API.
Gerencia conexão, autenticação, histórico de velas e execução de trades.
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

import websockets
import pandas as pd

logger = logging.getLogger(__name__)

DERIV_WS_URL = os.getenv("DERIV_WS_URL", "wss://ws.binaryws.com/websockets/v3")
DERIV_APP_ID = os.getenv("DERIV_APP_ID", "1")
DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN", "eYf2ydKTUpN2cgz")


class DerivClient:
    """Cliente WebSocket para a Deriv API com reconnect automático."""

    def __init__(self, token: Optional[str] = None, app_id: Optional[str] = None):
        self.token = token or DERIV_API_TOKEN
        self.app_id = app_id or DERIV_APP_ID
        self.ws_url = f"{DERIV_WS_URL}?app_id={self.app_id}"
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._request_id = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._receiver_task: Optional[asyncio.Task] = None
        self._keepalive_task: Optional[asyncio.Task] = None
        self._connected = False
        self._authorized = False
        self._reconnect_delay = 1

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def connect(self) -> None:
        """Conecta ao WebSocket da Deriv com exponential backoff."""
        retries = 0
        while True:
            try:
                logger.info(f"[Deriv] Conectando a {self.ws_url}...")
                self.ws = await websockets.connect(
                    self.ws_url,
                    ping_interval=None,  # gerenciamos manualmente
                    close_timeout=5,
                )
                self._connected = True
                self._reconnect_delay = 1
                logger.info("[Deriv] WebSocket conectado!")

                # Iniciar receiver em background
                if self._receiver_task:
                    self._receiver_task.cancel()
                self._receiver_task = asyncio.create_task(self._receiver_loop())

                # Autorizar
                await self.authorize(self.token)

                # Iniciar keepalive
                if self._keepalive_task:
                    self._keepalive_task.cancel()
                self._keepalive_task = asyncio.create_task(self._keepalive_loop())

                return

            except Exception as e:
                retries += 1
                delay = min(2 ** retries, 60)
                logger.warning(f"[Deriv] Falha na conexão (tentativa {retries}): {e}. Reconectando em {delay}s...")
                await asyncio.sleep(delay)

    async def disconnect(self) -> None:
        """Desconecta do WebSocket."""
        self._connected = False
        self._authorized = False

        if self._receiver_task:
            self._receiver_task.cancel()
        if self._keepalive_task:
            self._keepalive_task.cancel()

        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass

        # Cancela requests pendentes
        for req_id, future in self._pending.items():
            if not future.done():
                future.cancel()
        self._pending.clear()

        logger.info("[Deriv] Desconectado.")

    async def _receiver_loop(self) -> None:
        """Loop de recebimento de mensagens WebSocket."""
        try:
            async for raw_msg in self.ws:
                try:
                    msg = json.loads(raw_msg)
                    req_id = msg.get("req_id")
                    if req_id and req_id in self._pending:
                        future = self._pending.pop(req_id)
                        if not future.done():
                            if "error" in msg:
                                future.set_exception(
                                    Exception(f"Deriv error: {msg['error'].get('message', msg['error'])}")
                                )
                            else:
                                future.set_result(msg)
                except json.JSONDecodeError:
                    logger.warning(f"[Deriv] Mensagem inválida: {raw_msg[:100]}")
        except asyncio.CancelledError:
            pass
        except websockets.ConnectionClosed as e:
            logger.warning(f"[Deriv] Conexão fechada: {e}")
            self._connected = False
            self._authorized = False
        except Exception as e:
            logger.error(f"[Deriv] Erro no receiver: {e}")
            self._connected = False
            self._authorized = False

    async def _keepalive_loop(self) -> None:
        """Envia pings periódicos para manter a conexão ativa."""
        while True:
            try:
                await asyncio.sleep(30)
                if self._connected and self.ws:
                    await self._send_request({"ping": 1})
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[Deriv] Keepalive erro: {e}")

    async def _send_request(self, payload: Dict[str, Any],
                             timeout: float = 30.0) -> Dict[str, Any]:
        """Envia um request e aguarda a resposta."""
        if not self._connected or not self.ws:
            raise ConnectionError("[Deriv] Não conectado. Chame connect() primeiro.")

        req_id = self._next_id()
        payload["req_id"] = req_id

        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[req_id] = future

        await self.ws.send(json.dumps(payload))

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise TimeoutError(f"[Deriv] Timeout aguardando resposta para req_id={req_id}")

    async def authorize(self, token: str) -> Dict[str, Any]:
        """Autentica na API Deriv com o token fornecido."""
        response = await self._send_request({"authorize": token})
        self._authorized = True
        account = response.get("authorize", {})
        logger.info(f"[Deriv] Autenticado: {account.get('loginid', 'N/A')}")
        return response

    async def get_candles(self, symbol: str, granularity: int,
                           count: int = 200) -> pd.DataFrame:
        """
        Busca histórico de velas (OHLCV) para o símbolo.
        granularity: segundos por vela (120 = 2min, 300 = 5min, etc.)
        """
        if not self._authorized:
            await self.authorize(self.token)

        response = await self._send_request({
            "ticks_history": symbol,
            "style": "candles",
            "granularity": granularity,
            "count": count,
            "end": "latest",
            "adjust_start_time": 1,
        }, timeout=30.0)

        candles = response.get("candles", [])
        if not candles:
            return pd.DataFrame()

        df = pd.DataFrame(candles)
        df = df.rename(columns={
            "epoch": "time",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
        })
        df["time"] = pd.to_datetime(df["time"], unit="s")
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.sort_values("time").reset_index(drop=True)
        return df

    async def get_proposal(self, symbol: str, contract_type: str,
                            duration: int, duration_unit: str,
                            stake: float) -> Dict[str, Any]:
        """
        Solicita uma proposta de contrato da Deriv.
        contract_type: "CALL" | "PUT"
        duration: duração do contrato
        duration_unit: "m" (minutos), "s" (segundos), etc.
        """
        if not self._authorized:
            await self.authorize(self.token)

        response = await self._send_request({
            "proposal": 1,
            "amount": stake,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": "USD",
            "duration": duration,
            "duration_unit": duration_unit,
            "symbol": symbol,
        }, timeout=15.0)

        return response.get("proposal", {})

    async def get_proposal_multiplier(self, symbol: str, contract_type: str,
                                       stake: float,
                                       multiplier: int = 2) -> Dict[str, Any]:
        """
        Solicita proposta para contrato Multiplier (MULTUP/MULTDOWN).
        contract_type: "MULTUP" | "MULTDOWN"
        multiplier: fator de multiplicação (1-5 para conta virtual R_75)
        """
        if not self._authorized:
            await self.authorize(self.token)

        # take_profit e stop_loss baseados no stake para gestão de risco automática
        take_profit = round(stake * multiplier * 0.5, 2)   # 50% de ganho
        stop_loss = round(stake, 2)                          # perder apenas o stake

        response = await self._send_request({
            "proposal": 1,
            "amount": stake,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": "USD",
            "symbol": symbol,
            "multiplier": multiplier,
            "limit_order": {
                "take_profit": take_profit,
                "stop_loss": stop_loss,
            },
        }, timeout=15.0)

        return response.get("proposal", {})

    async def sell_contract(self, contract_id: int,
                             price: float = 0) -> Dict[str, Any]:
        """Vende (fecha) um contrato aberto pelo market price ou price especificado."""
        if not self._authorized:
            await self.authorize(self.token)

        response = await self._send_request({
            "sell": contract_id,
            "price": price,   # 0 = aceitar qualquer preço de mercado
        }, timeout=15.0)

        return response.get("sell", {})

    async def buy_contract(self, proposal_id: str, price: float) -> Dict[str, Any]:
        """Executa a compra de um contrato via proposal_id."""
        if not self._authorized:
            await self.authorize(self.token)

        response = await self._send_request({
            "buy": proposal_id,
            "price": price,
        }, timeout=15.0)

        return response.get("buy", {})

    async def get_contract_result(self, contract_id: int,
                                   timeout: float = 300.0,
                                   force_close_on_timeout: bool = True) -> Dict[str, Any]:
        """
        Aguarda o resultado de um contrato aberto via polling a cada 5 segundos.

        Para contratos Multiplier (MULTUP/MULTDOWN), o TP/SL pode demorar mais do que
        o timeout configurado. Se force_close_on_timeout=True (padrão), o contrato é
        fechado via sell() ao invés de lançar TimeoutError.
        """
        start_time = asyncio.get_event_loop().time()
        last_contract: Dict[str, Any] = {}

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                if force_close_on_timeout and last_contract:
                    logger.warning(
                        f"[Deriv] Timeout ({timeout:.0f}s) aguardando contrato {contract_id}. "
                        f"Forçando sell (fechamento manual)..."
                    )
                    try:
                        sell_result = await self.sell_contract(contract_id, price=0)
                        # Construir resultado sintético a partir do sell
                        sold_price = float(sell_result.get("sold_for", 0))
                        buy_price = float(last_contract.get("buy_price", 0)) or float(
                            last_contract.get("purchase_price", 0)
                        )
                        profit = round(sold_price - buy_price, 2)
                        logger.info(
                            f"[Deriv] Contrato {contract_id} fechado via sell forçado: "
                            f"sold_for={sold_price:.2f} buy_price={buy_price:.2f} profit={profit:.2f}"
                        )
                        # Atualizar last_contract com dados do sell
                        last_contract["status"] = "sold"
                        last_contract["profit"] = profit
                        last_contract["sell_price"] = sold_price
                        last_contract["exit_spot"] = sell_result.get("sold_for", 0)
                        return last_contract
                    except Exception as sell_err:
                        logger.error(
                            f"[Deriv] Falha ao fechar contrato {contract_id} via sell: {sell_err}"
                        )
                raise TimeoutError(
                    f"[Deriv] Timeout aguardando contrato {contract_id} após {timeout:.0f}s"
                )

            try:
                response = await self._send_request({
                    "proposal_open_contract": 1,
                    "contract_id": contract_id,
                }, timeout=15.0)

                contract = response.get("proposal_open_contract", {})
                status = contract.get("status", "open")

                # Guardar último estado conhecido para usar no sell forçado
                if contract:
                    last_contract = contract

                logger.debug(
                    f"[Deriv] Contrato {contract_id}: status={status} | "
                    f"profit={contract.get('profit', 'N/A')} | elapsed={elapsed:.0f}s/{timeout:.0f}s"
                )

                if status in ("won", "lost", "sold"):
                    return contract

            except Exception as e:
                logger.warning(f"[Deriv] Erro ao checar contrato {contract_id}: {e}")

            await asyncio.sleep(5)

    async def place_and_wait(self, symbol: str, contract_type: str,
                              duration: int, stake: float,
                              multiplier: int = 2,
                              duration_minutes: Optional[int] = None) -> Dict[str, Any]:
        """
        Fluxo completo usando contratos Multiplier (MULTUP/MULTDOWN):
        proposal → buy → monitorar via polling → fechar via TP/SL automático ou sell forçado.

        contract_type: "MULTUP" | "MULTDOWN"  (mapeado de "call"/"put" no BotTask)
        multiplier: 1-5 (conta virtual R_75 suporta até 5x)
        duration: duração em minutos para timeout de monitoramento
        duration_minutes: alias para duration (retrocompatibilidade)
        """
        opened_at = datetime.utcnow().isoformat() + "Z"

        # Mapear CALL/PUT legados para MULTUP/MULTDOWN
        mult_type = contract_type
        if contract_type == "CALL":
            mult_type = "MULTUP"
        elif contract_type == "PUT":
            mult_type = "MULTDOWN"

        # Resolver duração: aceitar ambos os parâmetros
        effective_duration = duration_minutes if duration_minutes is not None else duration

        # 1. Obter proposta multiplier
        proposal = await self.get_proposal_multiplier(
            symbol=symbol,
            contract_type=mult_type,
            stake=stake,
            multiplier=multiplier,
        )

        proposal_id = proposal.get("id")
        ask_price = float(proposal.get("ask_price", stake))

        if not proposal_id:
            raise ValueError(
                f"[Deriv] Proposta inválida para {mult_type}: sem ID. "
                f"Resposta: {proposal}"
            )

        # 2. Comprar contrato
        buy_result = await self.buy_contract(proposal_id, ask_price)

        contract_id = buy_result.get("contract_id")
        if not contract_id:
            raise ValueError("[Deriv] Falha na compra: sem contract_id")

        logger.info(
            f"[Deriv] Trade Multiplier aberto: {mult_type} {symbol} "
            f"x{multiplier} | stake={stake} | contract_id={contract_id}"
        )

        # 3. Aguardar resultado com sell forçado como fallback
        # Timeout = duração do timeframe do bot; mínimo 5 minutos, máximo 15 minutos
        # Evita esperar indefinidamente para contratos que não atingem TP/SL
        wait_timeout = min(max(effective_duration * 60, 300), 900)
        logger.info(
            f"[Deriv] Monitorando contrato {contract_id} por até {wait_timeout:.0f}s "
            f"(sell forçado se não fechar)"
        )

        contract = await self.get_contract_result(
            contract_id,
            timeout=wait_timeout,
            force_close_on_timeout=True,
        )

        profit = float(contract.get("profit", 0))
        result = "won" if profit > 0 else "lost"
        payout_final = float(contract.get("payout", 0))
        entry_price = float(contract.get("entry_spot", 0))
        exit_price = float(contract.get("exit_spot", 0))
        closed_at = datetime.utcnow().isoformat() + "Z"

        logger.info(
            f"[Deriv] Trade fechado: {result} | profit={profit:.2f} | "
            f"contract_id={contract_id}"
        )

        return {
            "contract_id": str(contract_id),
            "symbol": symbol,
            "direction": mult_type,
            "stake": stake,
            "ask_price": ask_price,
            "payout": payout_final,
            "result": result,
            "profit": profit,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "opened_at": opened_at,
            "closed_at": closed_at,
        }

    async def reconnect(self) -> None:
        """Reconnecta ao WebSocket após uma queda."""
        logger.info("[Deriv] Iniciando reconnect...")
        self._connected = False
        self._authorized = False

        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass

        await self.connect()

    @property
    def is_connected(self) -> bool:
        return self._connected and self._authorized
