"""
FastAPI 서버
- REST API: 포트폴리오, 거래내역, 감시종목
- WebSocket: 실시간 시세/에이전트 이벤트 push
- 스케줄러 및 WebSocket 스트리머를 같은 루프에서 실행
"""
import os
import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from data.storage import init_db
from core.portfolio import Portfolio
from core.risk_guard import is_emergency_stop, set_emergency_stop, reset_daily_baseline
from broker.paper import get_watchlist, set_watchlist
from data.storage import get_trades
from market_stream import latest_price, get_ohlcv_buffer
from scheduler import scheduler_loop
from market_stream import start_stream

# ── WebSocket 연결 관리 ─────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.append(ws)

    def disconnect(self, ws: WebSocket):
        self.clients.remove(ws)

    async def broadcast(self, data: dict):
        msg = json.dumps(data, ensure_ascii=False)
        dead = []
        for ws in self.clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.remove(ws)


manager = ConnectionManager()
portfolio = Portfolio()


# ── 실시간 push 루프 (가격 + AI 이벤트) ────────────────────
async def push_loop():
    """보유 종목 + 감시 종목 현재가를 1초마다 broadcast"""
    while True:
        tickers = list(set(
            [h["ticker"] for h in portfolio.get_holdings()] + get_watchlist()
        ))
        for t in tickers:
            price = latest_price.get(t)
            if price:
                await manager.broadcast({
                    "type":   "price",
                    "ticker": t,
                    "price":  price,
                    "ts":     datetime.now().isoformat(timespec="seconds"),
                })
        await asyncio.sleep(1)


# ── 에이전트 결정을 WebSocket으로 broadcast ─────────────────
async def patched_scheduler_loop(port: Portfolio):
    """스케줄러 결과를 WS로 중계"""
    from core.agent_engine import run_all_agents
    from core.risk_guard import is_emergency_stop, check_daily_loss
    from core.risk_manager import RiskManager

    interval = int(os.getenv("AGENT_INTERVAL_SEC", 60))
    stop_loss = float(os.getenv("STOP_LOSS_PCT", 5.0))
    take_profit = float(os.getenv("TAKE_PROFIT_PCT", 10.0))

    def _is_market_open():
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        t = now.hour * 100 + now.minute
        return 900 <= t <= 1530

    while True:
        await asyncio.sleep(interval)
        if is_emergency_stop() or not _is_market_open():
            continue
        if check_daily_loss(port):
            await manager.broadcast({"type": "emergency", "message": "일일 손실 한도 초과 — 봇 정지"})
            continue

        tickers = get_watchlist()
        if not tickers:
            continue

        try:
            decisions = await run_all_agents(tickers, port)
            for d in decisions:
                await manager.broadcast({"type": "agent_decision", **d})
        except Exception as e:
            await manager.broadcast({"type": "error", "message": str(e)})

        rm = RiskManager(stop_loss, take_profit)
        logs = rm.check_and_execute(port)
        for msg in logs:
            await manager.broadcast({"type": "risk_action", "message": msg})


# ── FastAPI 앱 ───────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    tickers = get_watchlist()
    asyncio.create_task(start_stream(tickers))
    asyncio.create_task(push_loop())
    asyncio.create_task(patched_scheduler_loop(portfolio))
    yield


app = FastAPI(title="Trading Bot API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3005", "http://127.0.0.1:3005"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
async def root():
    return FileResponse("frontend/index.html")


# ── REST API ─────────────────────────────────────────────────
@app.get("/api/portfolio")
async def api_portfolio():
    return portfolio.get_snapshot()


@app.get("/api/trades")
async def api_trades(limit: int = 100):
    return get_trades(limit)


@app.get("/api/watchlist")
async def api_watchlist():
    return {"tickers": get_watchlist()}


@app.post("/api/watchlist")
async def api_add_watchlist(body: dict):
    ticker = body.get("ticker", "").strip()
    if not ticker:
        return {"error": "ticker 필요"}
    wl = get_watchlist()
    if ticker not in wl:
        wl.append(ticker)
        set_watchlist(wl)
    return {"tickers": wl}


@app.delete("/api/watchlist/{ticker}")
async def api_del_watchlist(ticker: str):
    wl = get_watchlist()
    wl = [t for t in wl if t != ticker]
    set_watchlist(wl)
    return {"tickers": wl}


@app.get("/api/candles/{ticker}")
async def api_candles(ticker: str):
    return {"ticker": ticker, "candles": get_ohlcv_buffer(ticker)}


@app.post("/api/emergency-stop")
async def api_emergency_stop(body: dict):
    flag = body.get("active", True)
    set_emergency_stop(flag)
    if not flag:
        reset_daily_baseline(portfolio)
    return {"emergency_stop": flag}


@app.get("/api/status")
async def api_status():
    return {
        "emergency_stop": is_emergency_stop(),
        "watchlist":      get_watchlist(),
        "market_open":    _is_market_open_simple(),
        "mode":           os.getenv("TRADING_MODE", "paper"),
    }


def _is_market_open_simple() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 100 + now.minute
    return 900 <= t <= 1530


# ── WebSocket ────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    # 접속 즉시 현재 상태 전송
    snap = portfolio.get_snapshot()
    await ws.send_text(json.dumps({"type": "snapshot", **snap}, ensure_ascii=False))
    try:
        while True:
            await ws.receive_text()   # keep-alive ping 처리
    except WebSocketDisconnect:
        manager.disconnect(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8006, reload=False)
