"""pykrx를 사용한 한국 주식 데이터 조회"""
import pandas as pd
from datetime import datetime, timedelta
from pykrx import stock as krx


def _today() -> str:
    return datetime.now().strftime("%Y%m%d")


def _from_date(days: int = 120) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")


def get_current_price(ticker: str) -> float:
    """현재가 조회 (당일 OHLCV의 종가)"""
    try:
        today = _today()
        df = krx.get_market_ohlcv_by_date(_from_date(5), today, ticker)
        if df.empty:
            return 0.0
        return float(df["종가"].iloc[-1])
    except Exception:
        return 0.0


def get_ohlcv(ticker: str, days: int = 120) -> pd.DataFrame:
    """OHLCV 데이터 조회"""
    df = krx.get_market_ohlcv_by_date(_from_date(days), _today(), ticker)
    df.index = pd.to_datetime(df.index)
    df.rename(columns={"시가": "open", "고가": "high", "저가": "low", "종가": "close", "거래량": "volume"}, inplace=True)
    return df[["open", "high", "low", "close", "volume"]]


def get_stock_name(ticker: str) -> str:
    try:
        return krx.get_market_ticker_name(ticker)
    except Exception:
        return ticker


def search_tickers(keyword: str, market: str = "ALL") -> pd.DataFrame:
    """종목명 또는 코드로 검색"""
    try:
        kospi = krx.get_market_ticker_list(market="KOSPI")
        kosdaq = krx.get_market_ticker_list(market="KOSDAQ")
        tickers = kospi + kosdaq if market == "ALL" else (
            kospi if market == "KOSPI" else kosdaq
        )
        results = []
        kw = keyword.upper()
        for t in tickers:
            name = krx.get_market_ticker_name(t)
            if kw in t or kw in name.upper():
                results.append({"ticker": t, "name": name})
                if len(results) >= 20:
                    break
        return pd.DataFrame(results)
    except Exception:
        return pd.DataFrame(columns=["ticker", "name"])


def get_market_tickers(market: str = "KOSPI") -> list[str]:
    return krx.get_market_ticker_list(market=market)
