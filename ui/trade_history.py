"""거래 내역 페이지"""
import streamlit as st
import pandas as pd
from data.storage import get_trades


def render():
    st.markdown("## 거래 내역")
    trades = get_trades(limit=200)

    if not trades:
        st.info("거래 내역이 없습니다.")
        return

    df = pd.DataFrame(trades)
    df["executed_at"] = pd.to_datetime(df["executed_at"])
    df = df.sort_values("executed_at", ascending=False)

    # 요약
    buys = df[df["side"] == "BUY"]
    sells = df[df["side"] == "SELL"]
    col1, col2, col3 = st.columns(3)
    col1.metric("전체 거래", f"{len(df)}건")
    col2.metric("매수", f"{len(buys)}건")
    col3.metric("매도", f"{len(sells)}건")

    st.divider()

    # 필터
    side_filter = st.radio("필터", ["전체", "매수", "매도"], horizontal=True)
    if side_filter == "매수":
        df = df[df["side"] == "BUY"]
    elif side_filter == "매도":
        df = df[df["side"] == "SELL"]

    # 테이블
    display = df[["executed_at", "name", "ticker", "side", "quantity", "price", "strategy"]].copy()
    display.columns = ["체결시각", "종목명", "코드", "구분", "수량", "체결가", "전략"]
    display["체결가"] = display["체결가"].map("{:,.0f}원".format)
    display["거래금액"] = (df["price"] * df["quantity"]).map("{:,.0f}원".format)
    display["구분"] = display["구분"].map({"BUY": "🔴 매수", "SELL": "🔵 매도"})
    display["체결시각"] = display["체결시각"].dt.strftime("%Y-%m-%d %H:%M:%S")

    st.dataframe(display, use_container_width=True, hide_index=True)
