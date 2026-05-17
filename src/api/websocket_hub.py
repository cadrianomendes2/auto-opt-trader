"""
WebSocket Hub - Gerencia conexões WebSocket dos clientes do dashboard.
"""
import asyncio
import json
import logging
from typing import List, Dict, Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Gerencia as conexões WebSocket ativas dos clientes do dashboard."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Aceita a conexão e envia o estado completo inicial."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"[WS] Nova conexão. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a conexão da lista de ativos."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"[WS] Conexão encerrada. Total: {len(self.active_connections)}")

    async def send_personal(self, message: Dict[str, Any],
                             websocket: WebSocket) -> None:
        """Envia uma mensagem para um cliente específico."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"[WS] Erro ao enviar mensagem pessoal: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Envia uma mensagem para todos os clientes conectados."""
        if not self.active_connections:
            return

        dead_connections = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"[WS] Falha ao enviar para cliente: {e}")
                dead_connections.append(ws)

        # Remove conexões mortas
        for ws in dead_connections:
            self.disconnect(ws)

    async def send_full_state(self, websocket: WebSocket) -> None:
        """Envia o estado completo de todos os agentes na conexão inicial."""
        from src.core.agent_manager import agent_manager
        state = agent_manager.get_full_state()
        # "agents" é enviado tanto na raiz (para compatibilidade com testes diretos
        # via new WebSocket) quanto em "payload" (para o ws-client.js do dashboard).
        await self.send_personal({
            "type": "full_state",
            "agents": state.get("agents", []),
            "payload": state,
        }, websocket)


# Instância singleton do manager
connection_manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """Endpoint principal do WebSocket."""
    await connection_manager.connect(websocket)

    # Enviar estado completo ao conectar
    try:
        await connection_manager.send_full_state(websocket)
    except Exception as e:
        logger.error(f"[WS] Erro ao enviar full_state: {e}")

    try:
        while True:
            # Receber mensagens do cliente
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=60.0
                )
                msg = json.loads(data)
                msg_type = msg.get("type")

                if msg_type == "ping":
                    await connection_manager.send_personal(
                        {"type": "pong", "payload": {}},
                        websocket
                    )

                elif msg_type == "subscribe_agent":
                    agent_id = msg.get("payload", {}).get("agent_id")
                    if agent_id:
                        from src.core.agent_manager import agent_manager
                        summary = agent_manager.get_agent_summary(agent_id)
                        if summary:
                            await connection_manager.send_personal({
                                "type": "agent_update",
                                "payload": summary,
                            }, websocket)

            except asyncio.TimeoutError:
                # Timeout sem mensagem — enviar ping para verificar conexão
                try:
                    await websocket.send_json({"type": "ping", "payload": {}})
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info("[WS] Cliente desconectou normalmente.")
    except Exception as e:
        logger.error(f"[WS] Erro no endpoint: {e}")
    finally:
        connection_manager.disconnect(websocket)
