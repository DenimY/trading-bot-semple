"""
백그라운드 스케줄러
- 매 N초마다 AI 에이전트 실행
- 매일 09:00 일일 기준선 초기화
- FastAPI 서버와 함께 asyncio 루프에서 동작
"""
import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from data.storage import init_db
from core.portfolio import Portfolio
from core.agent_engine import run_all_agents
from core.risk_manager import RiskManager
from core.risk_guard import is_emergency_stop, check_daily_loss, reset_daily_baseline
from broker.paper import get_watchlist

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("scheduler")

INTERVAL      = int(os.getenv("AGENT_INTERVAL_SEC", 60))
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", 5.0))
TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", 10.0))


def _is_market_open() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:           # 주말
        return False
    t = now.hour * 100 + now.minute
    return 900 <= t <= 1530


async def agent_cycle(portfolio: Portfolio):
    if is_emergency_stop():
        log.warning("비상 정지 활성화 — 에이전트 실행 건너뜀")
        return

    if not _is_market_open():
        log.info("장 시간 외 — 에이전트 실행 건너뜀")
        return

    if check_daily_loss(portfolio):
        log.warning("일일 손실 한도 초과 — 비상 정지 설정")
        return

    tickers = get_watchlist()
    if not tickers:
        log.info("감시 종목 없음")
        return

    log.info(f"에이전트 실행: {tickers}")
    decisions = await run_all_agents(tickers, portfolio)
    for d in decisions:
        log.info(f"[{d['ticker']}] {d['action']} | 신뢰도 {d['confidence']} | Tier{d['tier']} | {d['reason'][:60]}...")

    # 손절/익절 체크
    rm   = RiskManager(STOP_LOSS_PCT, TAKE_PROFIT_PCT)
    logs = rm.check_and_execute(portfolio)
    for msg in logs:
        log.warning(msg)


async def scheduler_loop(portfolio: Portfolio):
    log.info(f"스케줄러 시작 (주기: {INTERVAL}초)")
    while True:
        try:
            await agent_cycle(portfolio)
        except Exception as e:
            log.error(f"에이전트 사이클 오류: {e}")
        await asyncio.sleep(INTERVAL)


# ── 단독 실행 모드 ────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    portfolio = Portfolio()

    async def main():
        from market_stream import start_stream
        tickers = get_watchlist()
        await asyncio.gather(
            start_stream(tickers),
            scheduler_loop(portfolio),
        )

    asyncio.run(main())
