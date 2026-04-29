"""
AI 에이전트 엔진
- Tier 1: claude-haiku-4-5  (빠른 판단, 매 사이클)
- Tier 2: claude-sonnet-4-6 (신뢰도 낮거나 고액 주문 시 재검토)
"""
import os
import asyncio
from datetime import datetime
from anthropic import AsyncAnthropic
from core.context_builder import build_context
from core.portfolio import Portfolio
from data.storage import add_trade
from data import storage

HAIKU  = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"

TIER2_THRESHOLD = int(os.getenv("TIER2_CONFIDENCE_THRESHOLD", 60))

_client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

# ── Tool 정의 ────────────────────────────────────────────────
TOOLS = [
    {
        "name": "buy",
        "description": (
            "지정 종목을 매수한다. "
            "확신이 있고(confidence≥60) 기술적 매수 근거가 명확할 때만 호출할 것. "
            "불확실하면 hold를 선택하라."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker":     {"type": "string",  "description": "종목코드 (예: 005930)"},
                "quantity":   {"type": "integer", "description": "매수 수량"},
                "confidence": {"type": "number",  "description": "판단 신뢰도 0~100"},
                "reason":     {"type": "string",  "description": "매수 근거 (한국어 2~3문장, 구체적 지표 수치 포함)"},
            },
            "required": ["ticker", "quantity", "confidence", "reason"],
        },
    },
    {
        "name": "sell",
        "description": "지정 종목을 매도한다. 보유 중일 때만 호출 가능.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker":     {"type": "string"},
                "quantity":   {"type": "integer"},
                "confidence": {"type": "number"},
                "reason":     {"type": "string"},
            },
            "required": ["ticker", "quantity", "confidence", "reason"],
        },
    },
    {
        "name": "hold",
        "description": "현재 포지션을 유지한다. 신호가 불명확하면 반드시 hold를 선택하라.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "유지 근거"},
            },
            "required": ["reason"],
        },
    },
]

SYSTEM_PROMPT = """당신은 한국 주식 시장 전문 트레이딩 에이전트입니다.

규칙:
1. 제공된 기술 지표와 포트폴리오 현황을 종합 분석하세요.
2. 반드시 buy / sell / hold 중 하나의 툴을 호출해 결정을 내리세요.
3. confidence가 60 미만이면 반드시 hold를 선택하세요.
4. reason은 구체적인 지표 수치를 포함한 한국어 2~3문장으로 작성하세요.
5. 단일 종목 비중이 총자산의 30%를 초과하지 않도록 수량을 조정하세요.
6. 장 시간(09:00~15:30) 외에는 hold를 선택하세요."""


# ── 에이전트 호출 ────────────────────────────────────────────
async def _call_agent(model: str, context: str) -> dict:
    resp = await _client.messages.create(
        model=model,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=[{"role": "user", "content": context}],
    )

    for block in resp.content:
        if block.type == "tool_use":
            return {
                "action":     block.name.upper(),   # BUY / SELL / HOLD
                "input":      block.input,
                "model":      model,
                "confidence": block.input.get("confidence", 0),
            }

    return {"action": "HOLD", "input": {"reason": "툴 미호출"}, "model": model, "confidence": 0}


async def run_agent(ticker: str, portfolio: Portfolio) -> dict:
    """
    단일 종목에 대해 Tier1 → 필요 시 Tier2 호출.
    반환: {action, ticker, quantity, confidence, reason, model, tier, ts}
    """
    context = build_context(ticker, portfolio)

    # Tier 1
    result = await _call_agent(HAIKU, context)
    tier   = 1

    # Tier 2: 신뢰도 낮음 or SELL (신중)
    if result["confidence"] < TIER2_THRESHOLD or result["action"] == "SELL":
        result2 = await _call_agent(SONNET, context)
        # Tier2 신뢰도가 더 높을 때만 채택
        if result2["confidence"] >= result["confidence"]:
            result = result2
            tier   = 2

    inp    = result["input"]
    action = result["action"]
    ts     = datetime.now().isoformat(timespec="seconds")

    decision = {
        "action":     action,
        "ticker":     ticker,
        "quantity":   inp.get("quantity", 0),
        "confidence": result["confidence"],
        "reason":     inp.get("reason", ""),
        "model":      result["model"],
        "tier":       tier,
        "ts":         ts,
    }

    # 주문 실행
    _execute(decision, portfolio)

    # 판단 로그 저장
    storage.set_state(
        f"agent_log_{ticker}_{ts}",
        decision,
    )

    return decision


def _execute(decision: dict, portfolio: Portfolio):
    action = decision["action"]
    ticker = decision["ticker"]
    qty    = decision["quantity"]

    if action == "BUY" and qty > 0:
        from data.fetcher import get_current_price
        price = get_current_price(ticker)
        portfolio.execute_buy(ticker, qty, price, strategy=f"agent_tier{decision['tier']}")

    elif action == "SELL" and qty > 0:
        from data.fetcher import get_current_price
        price = get_current_price(ticker)
        portfolio.execute_sell(ticker, qty, price, strategy=f"agent_tier{decision['tier']}")


# ── 감시 종목 전체 실행 ──────────────────────────────────────
async def run_all_agents(tickers: list[str], portfolio: Portfolio) -> list[dict]:
    tasks = [run_agent(t, portfolio) for t in tickers]
    return await asyncio.gather(*tasks, return_exceptions=False)
