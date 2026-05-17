"""
Script para criar os 5 agentes padrão via API REST.
Execute com: python3 src/create_default_agents.py
"""
import asyncio
import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000/api/v1"

agents = [
    {
        "id": "r75-2min",
        "name": "R75 — 2min",
        "symbol": "R_75",
        "timeframe_minutes": 2,
        "stake": 2.0,
        "strategy": "rsi_ema",
        "api_token": "eYf2ydKTUpN2cgz",
        "status": "running",
    },
    {
        "id": "r75-5min",
        "name": "R75 — 5min",
        "symbol": "R_75",
        "timeframe_minutes": 5,
        "stake": 5.0,
        "strategy": "bb_squeeze",
        "api_token": "eYf2ydKTUpN2cgz",
        "status": "running",
    },
    {
        "id": "r75-10min",
        "name": "R75 — 10min",
        "symbol": "R_75",
        "timeframe_minutes": 10,
        "stake": 10.0,
        "strategy": "stochrsi",
        "api_token": "eYf2ydKTUpN2cgz",
        "status": "running",
    },
    {
        "id": "r75-15min",
        "name": "R75 — 15min",
        "symbol": "R_75",
        "timeframe_minutes": 15,
        "stake": 15.0,
        "strategy": "ema_pullback",
        "api_token": "eYf2ydKTUpN2cgz",
        "status": "running",
    },
    {
        "id": "r75-30min",
        "name": "R75 — 30min",
        "symbol": "R_75",
        "timeframe_minutes": 30,
        "stake": 30.0,
        "strategy": "rsi_ema",
        "api_token": "eYf2ydKTUpN2cgz",
        "status": "running",
    },
]


def post_agent(agent: dict) -> dict:
    payload = json.dumps(agent).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/agents",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return {"error": e.code, "detail": json.loads(body)}


def get_agents() -> dict:
    req = urllib.request.Request(f"{BASE_URL}/agents", method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    print("=" * 60)
    print("  Criando 5 agentes padrão via API")
    print("=" * 60)

    created = 0
    for agent in agents:
        print(f"\n→ Criando: {agent['name']} (id={agent['id']})...")
        result = post_agent(agent)
        if "error" in result:
            print(f"  ❌ Falha: {result}")
        else:
            print(f"  ✅ Criado: id={result.get('id')} | status={result.get('status')}")
            created += 1

    print(f"\n{'=' * 60}")
    print(f"  {created}/{len(agents)} agentes criados com sucesso")
    print("=" * 60)

    print("\n→ Verificando via GET /api/v1/agents...")
    data = get_agents()
    agents_list = data.get("agents", [])
    print(f"\n  Total de agentes no sistema: {len(agents_list)}")
    for a in agents_list:
        print(f"  • [{a.get('status','?')}] {a.get('name')} (id={a.get('id')}) | {a.get('symbol')} {a.get('timeframe_minutes')}min | stake=${a.get('stake')}")

    print("\n✅ Concluído! Acesse http://localhost:8000 para ver os agentes na UI.\n")


if __name__ == "__main__":
    main()
