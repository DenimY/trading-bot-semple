"""AI 에이전트에 넘길 컨텍스트 프롬프트 조립"""
import pandas as pd
import numpy as np
from market_stream import get_ohlcv_buffer, latest_price
from data.fetcher import get_ohlcv, get_stock_name
from core.portfolio import Portfolio


def _calc_indicators(closes: list[float]) -> dict:
    if len(closes) < 20:
        return {}
    s = pd.Series(closes)

    # RSI
    delta = s.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = float((100 - 100 / (1 + rs)).iloc[-1])

    # SMA
    sma5  = float(s.rolling(5).mean().iloc[-1])
    sma20 = float(s.rolling(20).mean().iloc[-1])

    # 볼린저
    mid   = sma20
    std   = float(s.rolling(20).std().iloc[-1])
    upper = mid + 2 * std
    lower = mid - 2 * std

    # 거래량 비율 (스트리밍 버퍼가 충분할 때만)
    return {
        "rsi":   round(rsi, 1),
        "sma5":  round(sma5),
        "sma20": round(sma20),
        "bb_upper": round(upper),
        "bb_mid":   round(mid),
        "bb_lower": round(lower),
    }


def build_context(ticker: str, portfolio: Portfolio) -> str:
    name = get_stock_name(ticker)

    # 1. 가격 데이터: WebSocket 버퍼 우선, 없으면 pykrx 폴백
    buf = get_ohlcv_buffer(ticker)
    if len(buf) >= 20:
        closes  = [c["close"] for c in buf]
        volumes = [c["volume"] for c in buf]
        cur     = closes[-1]
        vol     = volumes[-1]
    else:
        df = get_ohlcv(ticker, days=60)
        if df.empty:
            return f"{ticker} 데이터 없음"
        closes  = df["close"].tolist()
        volumes = df["volume"].tolist()
        cur     = latest_price.get(ticker) or closes[-1]
        vol     = volumes[-1]

    ind = _calc_indicators(closes)
    if not ind:
        return f"{ticker} 지표 계산 불가 (데이터 부족)"

    prev_close = closes[-2] if len(closes) >= 2 else cur
    change_pct = (cur - prev_close) / prev_close * 100

    vol_avg = float(pd.Series(volumes[-20:]).mean()) if len(volumes) >= 20 else vol
    vol_ratio = vol / vol_avg if vol_avg > 0 else 1.0

    # 2. 포트폴리오 현황
    snap     = portfolio.get_snapshot()
    holdings = {h["ticker"]: h for h in snap["holdings"]}
    h_info   = holdings.get(ticker)
    hold_txt = (
        f"보유 {h_info['quantity']}주 | 평균가 {h_info['avg_price']:,.0f}원 | "
        f"현재손익 {h_info['pnl_pct']:+.1f}%"
        if h_info else "미보유"
    )

    order_amount = int(__import__('os').getenv("ORDER_AMOUNT", 500000))
    max_qty      = order_amount // int(cur) if cur > 0 else 0

    # 3. 컨텍스트 문자열
    rsi_label = (
        "과매도 구간" if ind["rsi"] < 30
        else "과매수 구간" if ind["rsi"] > 70
        else "중립"
    )
    return f"""
## 종목: {name} ({ticker})

### 현재가
- 현재가: {cur:,.0f}원
- 전일 대비: {change_pct:+.2f}%

### 기술 지표
- RSI(14): {ind['rsi']} ({rsi_label})
- SMA5: {ind['sma5']:,}원 | SMA20: {ind['sma20']:,}원 | {'SMA5 > SMA20 (상승 추세)' if ind['sma5'] > ind['sma20'] else 'SMA5 < SMA20 (하락 추세)'}
- 볼린저 상단: {ind['bb_upper']:,} / 중선: {ind['bb_mid']:,} / 하단: {ind['bb_lower']:,}
- 현재가 위치: {'상단 돌파' if cur > ind['bb_upper'] else '하단 이탈' if cur < ind['bb_lower'] else '밴드 내'}
- 거래량: {vol:,} (20일 평균 대비 {vol_ratio:.1f}배)

### 포트폴리오 현황
- 총자산: {snap['total_assets']:,.0f}원 | 예수금: {snap['cash']:,.0f}원
- {ticker} 보유: {hold_txt}

### 주문 제약
- 최대 매수 수량: {max_qty}주 (1회 한도 {order_amount:,}원 기준)
""".strip()
