"""
Teste de conexão com a Deriv API.
Verifica autenticação, saldo e busca velas do R_75.
"""

import asyncio
import websockets
import json

DERIV_WS_URL = "wss://ws.binaryws.com/websockets/v3?app_id=1"
API_TOKEN = "eYf2ydKTUpN2cgz"


async def test_connection():
    print("🔌 Conectando à Deriv API...")

    async with websockets.connect(DERIV_WS_URL) as ws:
        # 1. Autenticar
        await ws.send(json.dumps({"authorize": API_TOKEN}))
        auth_resp = json.loads(await ws.recv())

        if "error" in auth_resp:
            print(f"❌ Erro de autenticação: {auth_resp['error']['message']}")
            return

        account = auth_resp["authorize"]
        print(f"✅ Autenticado com sucesso!")
        print(f"   Login ID   : {account.get('loginid', 'N/A')}")
        print(f"   Email      : {account.get('email', 'N/A')}")
        print(f"   Saldo      : {account.get('balance', 'N/A')} {account.get('currency', '')}")
        print(f"   Tipo conta : {account.get('account_type', 'N/A')}")

        # 2. Buscar velas do Volatility 75 Index
        print("\n📊 Buscando últimas 5 velas do R_75 (Volatility 75 Index)...")
        await ws.send(json.dumps({
            "ticks_history": "R_75",
            "adjust_start_time": 1,
            "count": 5,
            "end": "latest",
            "granularity": 60,   # 1 minuto
            "style": "candles"
        }))

        candles_resp = json.loads(await ws.recv())

        if "error" in candles_resp:
            print(f"❌ Erro ao buscar velas: {candles_resp['error']['message']}")
        else:
            candles = candles_resp.get("candles", [])
            print(f"   Recebidas {len(candles)} velas:")
            for c in candles:
                print(f"   O:{c['open']:.4f}  H:{c['high']:.4f}  L:{c['low']:.4f}  C:{c['close']:.4f}")

        # 3. Ping
        await ws.send(json.dumps({"ping": 1}))
        ping_resp = json.loads(await ws.recv())
        if ping_resp.get("ping") == "pong":
            print("\n🏓 Ping/Pong OK — conexão estável.")

        print("\n✅ Teste concluído com sucesso!")


if __name__ == "__main__":
    asyncio.run(test_connection())
