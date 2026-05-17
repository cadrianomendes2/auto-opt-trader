"""
AgentManager - Singleton que gerencia todos os bots de trading.
"""
import asyncio
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.core.bot_task import BotTask
from src.db import trade_repository

logger = logging.getLogger(__name__)

AGENTS_JSON_PATH = Path(__file__).parent.parent / "state" / "agents.json"


class AgentManager:
    """
    Singleton que gerencia todos os bots de trading.
    Responsável por criar, pausar, retomar e deletar bots.
    """
    _instance: Optional["AgentManager"] = None

    def __new__(cls) -> "AgentManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.agents: Dict[str, Dict[str, Any]] = {}
        self.bot_instances: Dict[str, BotTask] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self._json_lock = asyncio.Lock()
        self._broadcast_fn = None
        self._start_time = datetime.utcnow()

    def set_broadcast_fn(self, fn) -> None:
        """Define a função de broadcast para comunicação WebSocket."""
        self._broadcast_fn = fn

    async def _broadcast(self, message: Dict[str, Any]) -> None:
        """Envia broadcast para os clientes WebSocket."""
        if self._broadcast_fn:
            try:
                await self._broadcast_fn(message)
            except Exception as e:
                logger.error(f"Erro no broadcast: {e}")

    async def load_from_disk(self) -> None:
        """Carrega agentes do arquivo agents.json na inicialização."""
        if not AGENTS_JSON_PATH.exists():
            logger.info("agents.json não encontrado. Criando arquivo vazio...")
            AGENTS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
            await self._write_json({
                "version": "1.0",
                "last_updated": datetime.utcnow().isoformat() + "Z",
                "agents": []
            })
            return

        try:
            config = self._read_json()
            agents_list = config.get("agents", [])
            logger.info(f"Carregando {len(agents_list)} agentes do disco...")

            for agent_cfg in agents_list:
                self.agents[agent_cfg["id"]] = agent_cfg

                # Registrar no banco de dados
                try:
                    await trade_repository.insert_agent(
                        agent_id=agent_cfg["id"],
                        name=agent_cfg["name"],
                        symbol=agent_cfg.get("symbol", "R_75"),
                        timeframe=agent_cfg.get("timeframe_minutes", 5),
                        stake=agent_cfg.get("stake", 5.0),
                        strategy=agent_cfg.get("strategy", "rsi_ema"),
                    )
                except Exception as e:
                    logger.warning(f"Erro ao registrar agente {agent_cfg['id']} no DB: {e}")

                # Iniciar bots que estavam running
                status = agent_cfg.get("status", "stopped")
                if agent_cfg.get("enabled", True) and status in ("running", "paused"):
                    await self._start_bot(agent_cfg)

        except json.JSONDecodeError as e:
            logger.error(f"agents.json corrompido: {e}. Tentando backup...")
            backup = AGENTS_JSON_PATH.with_suffix(".bak")
            if backup.exists():
                try:
                    shutil.copy2(backup, AGENTS_JSON_PATH)
                    await self.load_from_disk()
                except Exception as backup_err:
                    logger.error(f"Falha ao restaurar backup: {backup_err}")
            else:
                logger.error("Sem backup disponível. Iniciando com lista vazia.")

    async def _start_bot(self, agent_config: Dict[str, Any]) -> None:
        """Cria e inicia uma BotTask para um agente."""
        agent_id = agent_config["id"]

        if agent_id in self.tasks:
            task = self.tasks[agent_id]
            if not task.done():
                logger.warning(f"Bot {agent_id} já está rodando.")
                return

        bot = BotTask(
            config=agent_config,
            broadcast_fn=self._broadcast,
            save_config_fn=self.save_to_disk,
        )
        self.bot_instances[agent_id] = bot

        task = asyncio.create_task(
            bot.run(),
            name=f"bot-{agent_id}"
        )
        self.tasks[agent_id] = task

        task.add_done_callback(
            lambda t: asyncio.ensure_future(self._on_task_done(agent_id, t))
        )
        logger.info(f"Bot {agent_id} iniciado.")

    async def _on_task_done(self, agent_id: str, task: asyncio.Task) -> None:
        """Callback chamado quando uma task de bot termina."""
        if task.cancelled():
            logger.info(f"Bot {agent_id} cancelado.")
            return

        exc = task.exception() if not task.cancelled() else None
        if exc:
            logger.error(f"Bot {agent_id} terminou com erro: {exc}")
            if agent_id in self.agents:
                self.agents[agent_id]["status"] = "error"
                runtime = self.agents[agent_id].get("runtime", {})
                runtime["error_message"] = str(exc)
                self.agents[agent_id]["runtime"] = runtime
                await self.save_to_disk()

        # Limpar referências
        self.tasks.pop(agent_id, None)
        self.bot_instances.pop(agent_id, None)

    async def create_agent(self, agent_config: Dict[str, Any]) -> None:
        """Cria um novo agente e inicia seu bot."""
        agent_id = agent_config["id"]

        if agent_id in self.agents:
            raise ValueError(f"Agente '{agent_id}' já existe")

        # Configurar runtime inicial
        now = datetime.utcnow().isoformat() + "Z"
        agent_config["status"] = "running"
        agent_config["enabled"] = True
        agent_config.setdefault("runtime", {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl": 0.0,
            "consecutive_losses": 0,
            "last_trade_at": None,
            "started_at": now,
            "paused_at": None,
            "error_message": None,
        })

        self.agents[agent_id] = agent_config

        # Registrar no banco
        await trade_repository.insert_agent(
            agent_id=agent_id,
            name=agent_config["name"],
            symbol=agent_config.get("symbol", "R_75"),
            timeframe=agent_config.get("timeframe_minutes", 5),
            stake=agent_config.get("stake", 5.0),
            strategy=agent_config.get("strategy", "rsi_ema"),
        )

        await self.save_to_disk()
        await self._start_bot(agent_config)

        await self._broadcast({
            "type": "agent_created",
            "payload": {
                "agent_id": agent_id,
                "name": agent_config["name"],
                "status": "running",
            }
        })

    async def update_agent(self, agent_id: str,
                            updates: Dict[str, Any]) -> None:
        """Atualiza a configuração de um agente e reinicia seu bot."""
        if agent_id not in self.agents:
            raise ValueError(f"Agente '{agent_id}' não encontrado")

        # Parar bot atual
        await self._stop_bot(agent_id)

        # Aplicar atualizações
        self.agents[agent_id].update(updates)
        self.agents[agent_id]["status"] = "running"

        await self.save_to_disk()

        # Reiniciar bot
        await self._start_bot(self.agents[agent_id])

    async def delete_agent(self, agent_id: str) -> None:
        """Para e remove um agente."""
        if agent_id not in self.agents:
            raise ValueError(f"Agente '{agent_id}' não encontrado")

        await self._stop_bot(agent_id)
        del self.agents[agent_id]
        await self.save_to_disk()

        await self._broadcast({
            "type": "agent_deleted",
            "payload": {"agent_id": agent_id}
        })

    async def _stop_bot(self, agent_id: str) -> None:
        """Para o bot de um agente."""
        if agent_id in self.tasks:
            task = self.tasks[agent_id]
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

        self.tasks.pop(agent_id, None)
        self.bot_instances.pop(agent_id, None)

    async def pause_agent(self, agent_id: str) -> None:
        """Pausa um agente em execução."""
        if agent_id not in self.agents:
            raise ValueError(f"Agente '{agent_id}' não encontrado")

        if agent_id in self.bot_instances:
            await self.bot_instances[agent_id].pause()

        self.agents[agent_id]["status"] = "paused"
        await self.save_to_disk()

    async def resume_agent(self, agent_id: str) -> None:
        """Retoma um agente pausado."""
        if agent_id not in self.agents:
            raise ValueError(f"Agente '{agent_id}' não encontrado")

        if agent_id in self.bot_instances:
            await self.bot_instances[agent_id].resume()
        else:
            # Bot não está rodando — reiniciar
            self.agents[agent_id]["status"] = "running"
            await self._start_bot(self.agents[agent_id])

        self.agents[agent_id]["status"] = "running"
        await self.save_to_disk()

    async def reset_stats(self, agent_id: str) -> None:
        """Zera as estatísticas de runtime de um agente."""
        if agent_id not in self.agents:
            raise ValueError(f"Agente '{agent_id}' não encontrado")

        now = datetime.utcnow().isoformat() + "Z"
        self.agents[agent_id]["runtime"] = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl": 0.0,
            "consecutive_losses": 0,
            "last_trade_at": None,
            "started_at": now,
            "paused_at": None,
            "error_message": None,
        }

        if agent_id in self.bot_instances:
            bot = self.bot_instances[agent_id]
            bot.total_trades = 0
            bot.wins = 0
            bot.losses = 0
            bot.total_pnl = 0.0
            bot.consecutive_losses = 0
            bot.risk_mgr.reset_daily()

        await self.save_to_disk()

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Retorna a configuração completa de um agente."""
        agent = self.agents.get(agent_id)
        if not agent:
            return None

        # Sincronizar stats do bot em execução
        if agent_id in self.bot_instances:
            bot = self.bot_instances[agent_id]
            agent_copy = agent.copy()
            agent_copy["status"] = bot.status
            runtime = agent_copy.get("runtime", {}).copy()
            runtime.update({
                "total_trades": bot.total_trades,
                "wins": bot.wins,
                "losses": bot.losses,
                "total_pnl": bot.total_pnl,
                "consecutive_losses": bot.consecutive_losses,
                "last_trade_at": bot.last_trade_at,
            })
            agent_copy["runtime"] = runtime
            return agent_copy

        return agent

    def get_all_agents(self) -> List[Dict[str, Any]]:
        """Retorna lista de todos os agentes com stats atualizadas."""
        return [self.get_agent(aid) for aid in self.agents.keys()]

    def get_agent_summary(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Retorna um resumo do agente para exibição no dashboard."""
        agent = self.get_agent(agent_id)
        if not agent:
            return None

        runtime = agent.get("runtime", {})
        total_trades = runtime.get("total_trades", 0)
        wins = runtime.get("wins", 0)

        return {
            "id": agent["id"],
            "name": agent["name"],
            "symbol": agent.get("symbol", "R_75"),
            "timeframe_minutes": agent.get("timeframe_minutes", 5),
            "stake": agent.get("stake", 5.0),
            "strategy": agent.get("strategy", "rsi_ema"),
            "strategy_params": agent.get("strategy_params", {}),
            "status": agent.get("status", "stopped"),
            "total_trades": total_trades,
            "wins": wins,
            "losses": runtime.get("losses", 0),
            "total_pnl": runtime.get("total_pnl", 0.0),
            "win_rate": round(wins / total_trades, 4) if total_trades > 0 else 0.0,
            "consecutive_losses": runtime.get("consecutive_losses", 0),
            "last_trade_at": runtime.get("last_trade_at"),
        }

    def get_full_state(self) -> Dict[str, Any]:
        """Retorna o estado completo de todos os agentes."""
        return {
            "agents": [self.get_agent_summary(aid) for aid in self.agents.keys()]
        }

    async def stop_all(self) -> None:
        """Para todos os bots graciosamente (shutdown)."""
        logger.info("Parando todos os bots...")
        for agent_id in list(self.tasks.keys()):
            await self._stop_bot(agent_id)
        await self.save_to_disk()
        logger.info("Todos os bots parados.")

    def _read_json(self) -> Dict[str, Any]:
        """Lê o arquivo agents.json."""
        with open(AGENTS_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    async def _write_json(self, data: Dict[str, Any]) -> None:
        """Escreve o arquivo agents.json atomicamente."""
        tmp_path = AGENTS_JSON_PATH.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        tmp_path.replace(AGENTS_JSON_PATH)

    async def save_to_disk(self) -> None:
        """Salva o estado atual dos agentes no arquivo agents.json."""
        async with self._json_lock:
            # Backup do arquivo atual
            if AGENTS_JSON_PATH.exists():
                backup = AGENTS_JSON_PATH.with_suffix(".bak")
                shutil.copy2(AGENTS_JSON_PATH, backup)

            # Sincronizar stats dos bots em execução
            agents_list = []
            for agent_id, agent_cfg in self.agents.items():
                agent_data = agent_cfg.copy()

                if agent_id in self.bot_instances:
                    bot = self.bot_instances[agent_id]
                    agent_data["status"] = bot.status
                    runtime = agent_data.get("runtime", {}).copy()
                    runtime.update(bot.get_runtime_dict())
                    agent_data["runtime"] = runtime

                agents_list.append(agent_data)

            config = {
                "version": "1.0",
                "last_updated": datetime.utcnow().isoformat() + "Z",
                "agents": agents_list,
            }

            await self._write_json(config)


# Instância singleton
agent_manager = AgentManager()
