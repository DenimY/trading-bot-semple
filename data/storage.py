"""SQLite 기반 로컬 데이터 저장소"""
import sqlite3
import json
from datetime import datetime
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY,
                cash REAL NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS holdings (
                ticker TEXT PRIMARY KEY,
                name TEXT,
                quantity INTEGER NOT NULL,
                avg_price REAL NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                name TEXT,
                side TEXT NOT NULL,      -- BUY / SELL
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                strategy TEXT,
                executed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        # 포트폴리오 초기화 (없으면)
        row = conn.execute("SELECT id FROM portfolio LIMIT 1").fetchone()
        if row is None:
            from config import DEFAULT_INITIAL_CASH
            conn.execute(
                "INSERT INTO portfolio (cash, updated_at) VALUES (?, ?)",
                (DEFAULT_INITIAL_CASH, _now()),
            )


def _now():
    return datetime.now().isoformat(timespec="seconds")


# ── 포트폴리오 ──────────────────────────────────────────────
def get_cash() -> float:
    with get_conn() as conn:
        row = conn.execute("SELECT cash FROM portfolio ORDER BY id LIMIT 1").fetchone()
        return row["cash"] if row else 0.0


def set_cash(amount: float):
    with get_conn() as conn:
        conn.execute("UPDATE portfolio SET cash=?, updated_at=?", (amount, _now()))


def reset_portfolio(initial_cash: float):
    with get_conn() as conn:
        conn.execute("UPDATE portfolio SET cash=?, updated_at=?", (initial_cash, _now()))
        conn.execute("DELETE FROM holdings")
        conn.execute("DELETE FROM trades")


# ── 보유 종목 ────────────────────────────────────────────────
def get_holdings() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM holdings").fetchall()
        return [dict(r) for r in rows]


def upsert_holding(ticker: str, name: str, quantity: int, avg_price: float):
    with get_conn() as conn:
        if quantity <= 0:
            conn.execute("DELETE FROM holdings WHERE ticker=?", (ticker,))
        else:
            conn.execute(
                """INSERT INTO holdings (ticker, name, quantity, avg_price, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(ticker) DO UPDATE SET
                     name=excluded.name,
                     quantity=excluded.quantity,
                     avg_price=excluded.avg_price,
                     updated_at=excluded.updated_at""",
                (ticker, name, quantity, avg_price, _now()),
            )


# ── 거래 내역 ────────────────────────────────────────────────
def add_trade(ticker: str, name: str, side: str, quantity: int, price: float, strategy: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO trades (ticker, name, side, quantity, price, strategy, executed_at) VALUES (?,?,?,?,?,?,?)",
            (ticker, name, side, quantity, price, strategy, _now()),
        )


def get_trades(limit: int = 200) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY executed_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── 봇 상태 ─────────────────────────────────────────────────
def get_state(key: str, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM bot_state WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default


def set_state(key: str, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO bot_state (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )
