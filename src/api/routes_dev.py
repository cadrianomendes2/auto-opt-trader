"""
routes_dev.py — Endpoints de desenvolvimento: sistema de tasks anotadas
no painel dev unificado (Testes + Experimentos + Backlog).
"""
import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dev", tags=["dev"])

# ─── Prioridade ──────────────────────────────────────────────────────────────

PRIORITY_ORDER = {"critical": 0, "normal": 1, "low": 2}

# ─── Persistência ────────────────────────────────────────────────────────────

TASKS_FILE = Path("src/state/tasks.json")


def _load_tasks() -> List[dict]:
    try:
        if TASKS_FILE.exists():
            return json.loads(TASKS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Erro ao carregar tasks: {e}")
    return []


def _save_tasks(tasks: List[dict]) -> None:
    try:
        TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        TASKS_FILE.write_text(
            json.dumps(tasks, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        logger.error(f"Erro ao salvar tasks: {e}")
        raise


def _sort_tasks(tasks: List[dict]) -> List[dict]:
    """Ordena por prioridade (critical → normal → low) e depois por data desc."""
    return sorted(
        tasks,
        key=lambda t: (
            PRIORITY_ORDER.get(t.get("priority", "normal"), 1),
            # Inverter data: mais recente primeiro dentro da mesma prioridade
            -(datetime.fromisoformat(
                t.get("created_at", "2000-01-01T00:00:00+00:00")
                 .replace("Z", "+00:00")
            ).timestamp() if t.get("created_at") else 0),
        )
    )


# ─── Schemas ─────────────────────────────────────────────────────────────────


class TaskCreate(BaseModel):
    suite_id: Optional[str] = ""
    test_id: Optional[str] = ""
    component: Optional[str] = ""       # nome livre do componente/área
    title: str
    body: Optional[str] = ""
    regression: Optional[bool] = False
    priority: Optional[str] = "normal"  # "critical" | "normal" | "low"


class TaskPatch(BaseModel):
    status: Optional[str] = None        # "open" | "done" | "wont_fix"
    regression: Optional[bool] = None
    priority: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/tasks")
async def list_tasks(status: Optional[str] = None):
    """Lista todas as tasks, ordenadas por prioridade."""
    tasks = _load_tasks()
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    return _sort_tasks(tasks)


@router.post("/tasks", status_code=201)
async def create_task(payload: TaskCreate):
    """Cria uma nova task a partir de anotação no painel dev."""
    allowed_prio = {"critical", "normal", "low"}
    priority = payload.priority if payload.priority in allowed_prio else "normal"

    tasks = _load_tasks()
    task = {
        "id": str(uuid.uuid4()),
        "suite_id": (payload.suite_id or "").strip(),
        "test_id": (payload.test_id or "").strip(),
        "component": (payload.component or "").strip(),
        "title": payload.title.strip(),
        "body": (payload.body or "").strip(),
        "status": "open",
        "regression": payload.regression or False,
        "priority": priority,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    tasks.append(task)
    _save_tasks(tasks)
    logger.info(f"[DEV] Task criada [{priority}]: {task['id']} — {task['title']}")
    return task


@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, payload: TaskPatch):
    """Atualiza status, prioridade, regressão, título ou corpo de uma task."""
    tasks = _load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            if payload.status is not None:
                allowed = {"open", "done", "wont_fix"}
                if payload.status not in allowed:
                    raise HTTPException(400, f"status deve ser um de: {allowed}")
                t["status"] = payload.status
            if payload.priority is not None:
                allowed_p = {"critical", "normal", "low"}
                if payload.priority not in allowed_p:
                    raise HTTPException(400, f"priority deve ser um de: {allowed_p}")
                t["priority"] = payload.priority
            if payload.regression is not None:
                t["regression"] = payload.regression
            if payload.title is not None:
                t["title"] = payload.title.strip()
            if payload.body is not None:
                t["body"] = payload.body.strip()
            t["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_tasks(tasks)
            return t
    raise HTTPException(404, f"Task '{task_id}' não encontrada")


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str):
    """Remove permanentemente uma task."""
    tasks = _load_tasks()
    new_tasks = [t for t in tasks if t["id"] != task_id]
    if len(new_tasks) == len(tasks):
        raise HTTPException(404, f"Task '{task_id}' não encontrada")
    _save_tasks(new_tasks)
