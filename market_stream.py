"""
KIS WebSocket 실시간 시세 수신기
- 체결 tick 수신 → 1분봉 OHLCV 버퍼 유지
- KIS API 미설정 시 pykrx fallback 모드 자동 전환
"""
import asyncio
import json
import time
from collections import defaultdict, deque
from datetime import datetime
import websockets
from broker.kis_client import KISClient


# ── 전역 데이터 버퍼 ─────────────────────────────────────────
# { ticker: deque([{ts, open, high, low, close, volume}, ...], maxlen=200) }
ohlcv_buffer: dict[str, deque] = defaultdict(lambda: deque(maxlen=200))

# { ticker: 현재가 }
latest_price: dict[str, float] = {}

# { ticker: 진행 중인 1분봉 임시 저장 }
_current_candle: dict[str, dict] = {}


def _minute_key(ts: float) -> int:
    """unix timestamp → 분 단위 정수 키"""
    return int(ts // 60)


def push_tick(ticker: str, price: float, volume: int, ts: float | None = None):
    """외부에서 tick을 밀어넣는 단일 진입점 (WebSocket 수신 + fallback 공용)"""
    ts = ts or time.time()
    latest_price[ticker] = price
    mk = _minute_key(ts)

    if ticker not in _current_candle or _current_candle[ticker]["mk"] != mk:
        # 이전 봉 확정
        if ticker in _current_candle:
            ohlcv_buffer[ticker].append(_current_candle[ticker]["candle"])
        # 새 봉 시작
        _current_candle[ticker] = {
            "mk": mk,
            "candle": {
                "ts":     datetime.fromtimestamp(mk * 60).isoformat(timespec="minutes"),
                "open":   price,
                "high":   price,
                "low":    price,
                "close":  price,
                "volume": volume,
            },
        }
    else:
        c = _current_candle[ticker]["candle"]
        c["high"]   = max(c["high"], price)
        c["low"]    = min(c["low"],  price)
        c["close"]  = price
        c["volume"] += volume


def get_ohlcv_buffer(ticker: str) -> list[dict]:
    """확정된 1분봉 리스트 반환 (최신순)"""
    buf = list(ohlcv_buffer[ticker])
    # 진행 중인 봉도 포함
    if ticker in _current_candle:
        buf.append(_current_candle[ticker]["candle"])
    return buf


# ── KIS WebSocket 수신 ────────────────────────────────────────
class KISMarketStream:
    def __init__(self, client: KISClient, tickers: list[str]):
        self.client  = client
        self.tickers = tickers
        self._running = False

    async def start(self):
        self._running = True
        approval_key = await self.client.get_ws_approval_key()
        uri = self.client.ws_url

        async with websockets.connect(uri, ping_interval=30) as ws:
            # 구독 등록
            for ticker in self.tickers:
                msg = {
                    "header": {
                        "approval_key": approval_key,
                        "custtype":     "P",
                        "tr_type":      "1",   # 등록
                        "content-type": "utf-8",
                    },
                    "body": {
                        "input": {
                            "tr_id":   "H0STCNT0",   # 주식 체결
                            "tr_key":  ticker,
                        }
                    },
                }
                await ws.send(json.dumps(msg))

            while self._running:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    self._parse(raw)
                except asyncio.TimeoutError:
                    await ws.ping()
                except websockets.ConnectionClosed:
                    break

    def _parse(self, raw: str):
        """KIS 체결 메시지 파싱 ("|" 구분 CSV 포맷)"""
        if raw.startswith("{"):   # JSON → 시스템 메시지, 무시
            return
        parts = raw.split("|")
        if len(parts) < 4:
            return
        # parts[3] = 데이터부 (^로 필드 구분)
        fields = parts[3].split("^")
        try:
            ticker = fields[0]
            price  = float(fields[2])
            volume = int(fields[12])
            # 체결시각: HHMMSS
            t_str  = fields[1]
            now    = datetime.now()
            ts     = now.replace(
                hour=int(t_str[0:2]),
                minute=int(t_str[2:4]),
                second=int(t_str[4:6]),
                microsecond=0,
            ).timestamp()
            push_tick(ticker, price, volume, ts)
        except (IndexError, ValueError):
            pass

    def stop(self):
        self._running = False


# ── pykrx fallback (KIS 미설정 시) ──────────────────────────
async def pykrx_fallback_loop(tickers: list[str], interval: int = 60):
    """pykrx로 현재가를 주기적으로 polling해서 버퍼에 push"""
    from data.fetcher import get_current_price
    print("[MarketStream] KIS 미설정 → pykrx fallback 모드")
    while True:
        for ticker in tickers:
            price = get_current_price(ticker)
            if price > 0:
                push_tick(ticker, price, 0)
        await asyncio.sleep(interval)


async def start_stream(tickers: list[str]):
    """진입점: KIS 설정 여부에 따라 WebSocket 또는 fallback 선택"""
    client = KISClient()
    if client.is_configured():
        print(f"[MarketStream] KIS WebSocket 시작 ({client.mode} 모드)")
        stream = KISMarketStream(client, tickers)
        await stream.start()
    else:
        await pykrx_fallback_loop(tickers)
