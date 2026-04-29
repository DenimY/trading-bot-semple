"""종목 차트 페이지 (캔들 + 전략 지표)"""
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from data.fetcher import get_ohlcv, search_tickers
from strategies.sma_crossover import SMACrossoverStrategy
from strategies.rsi import RSIStrategy
from strategies.bollinger import BollingerStrategy
from config import STRATEGY_DEFAULTS


STRATEGY_MAP = {
    "SMA 교차": SMACrossoverStrategy,
    "RSI": RSIStrategy,
    "볼린저 밴드": BollingerStrategy,
}


def render():
    st.markdown("## 차트 분석")

    col_search, col_strategy = st.columns([3, 2])

    with col_search:
        keyword = st.text_input("종목 검색 (종목명 또는 코드)", placeholder="삼성전자 / 005930")

    with col_strategy:
        strategy_name = st.selectbox("전략 오버레이", list(STRATEGY_MAP.keys()))

    ticker = None
    if keyword:
        results = search_tickers(keyword)
        if results.empty:
            st.warning("검색 결과가 없습니다.")
            return
        options = {f"{r['name']} ({r['ticker']})": r["ticker"] for _, r in results.iterrows()}
        selected = st.selectbox("종목 선택", list(options.keys()))
        ticker = options[selected]

    if not ticker:
        st.info("종목을 검색하세요.")
        return

    period = st.select_slider("기간", options=[30, 60, 90, 120], value=90)
    ohlcv = get_ohlcv(ticker, days=period + 30)

    if ohlcv.empty:
        st.error("데이터를 불러올 수 없습니다.")
        return

    ohlcv = ohlcv.iloc[-period:]

    # 전략별 지표 계산
    cls = STRATEGY_MAP[strategy_name]
    if strategy_name == "SMA 교차":
        p = STRATEGY_DEFAULTS["sma_crossover"]
        strategy = cls(p["short_window"], p["long_window"])
    elif strategy_name == "RSI":
        p = STRATEGY_DEFAULTS["rsi"]
        strategy = cls(p["period"], p["oversold"], p["overbought"])
    else:
        p = STRATEGY_DEFAULTS["bollinger"]
        strategy = cls(p["window"], p["num_std"])

    df = strategy.compute_indicators(ohlcv)
    signal = strategy.generate_signal(ohlcv)

    signal_color = {"BUY": "green", "SELL": "red", "HOLD": "gray"}
    st.markdown(
        f"### 현재 신호: <span style='color:{signal_color[signal]};font-size:1.3em;font-weight:bold'>{signal}</span>",
        unsafe_allow_html=True,
    )

    # ── 캔들 + 지표 차트 ─────────────────────────────────────
    has_rsi = "rsi" in df.columns
    rows = 2 if has_rsi else 1
    row_heights = [0.7, 0.3] if has_rsi else [1.0]

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=row_heights)

    # 캔들스틱
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="가격",
        increasing_line_color="#e84040", decreasing_line_color="#4488ff",
    ), row=1, col=1)

    # SMA
    if "sma_short" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["sma_short"], name=f"SMA{strategy.short_window}",
                                 line=dict(color="orange", width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["sma_long"], name=f"SMA{strategy.long_window}",
                                 line=dict(color="purple", width=1.5)), row=1, col=1)

    # 볼린저
    if "upper" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["upper"], name="상단",
                                 line=dict(color="gray", dash="dot", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["mid"], name="중선",
                                 line=dict(color="gray", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["lower"], name="하단",
                                 line=dict(color="gray", dash="dot", width=1),
                                 fill="tonexty", fillcolor="rgba(128,128,128,0.08)"), row=1, col=1)

    # RSI
    if has_rsi:
        fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], name="RSI",
                                 line=dict(color="royalblue", width=1.5)), row=2, col=1)
        fig.add_hline(y=strategy.overbought, line=dict(color="red", dash="dash", width=1), row=2, col=1)
        fig.add_hline(y=strategy.oversold, line=dict(color="green", dash="dash", width=1), row=2, col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)

    fig.update_layout(
        height=520, xaxis_rangeslider_visible=False,
        margin=dict(t=20, b=20, l=10, r=10),
        legend=dict(orientation="h", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)
