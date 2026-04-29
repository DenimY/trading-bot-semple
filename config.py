from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data_store"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "trading.db"

# 기본 설정
DEFAULT_INITIAL_CASH = 10_000_000  # 1천만원

# 지원 시장
MARKETS = ["KOSPI", "KOSDAQ"]

# 전략 파라미터 기본값
STRATEGY_DEFAULTS = {
    "sma_crossover": {"short_window": 5, "long_window": 20},
    "rsi": {"period": 14, "oversold": 30, "overbought": 70},
    "bollinger": {"window": 20, "num_std": 2.0},
}
