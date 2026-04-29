"""
안전장치 레이어
- 일일 최대 손실 한도 초과 시 자동 중지
- 비상 정지 플래그
"""
import os
from data import storage
from core.portfolio import Portfolio


DAILY_LOSS_LIMIT_PCT = float(os.getenv("DAILY_LOSS_LIMIT_PCT", 3.0))


def is_emergency_stop() -> bool:
    return storage.get_state("emergency_stop", False)


def set_emergency_stop(flag: bool):
    storage.set_state("emergency_stop", flag)


def check_daily_loss(portfolio: Portfolio) -> bool:
    """
    일일 손실 한도 초과 여부 확인.
    초과 시 비상 정지 플래그 설정 후 True 반환.
    """
    snap        = portfolio.get_snapshot()
    initial     = storage.get_state("daily_start_assets", None)
    total       = snap["total_assets"]

    if initial is None:
        storage.set_state("daily_start_assets", total)
        return False

    loss_pct = (initial - total) / initial * 100
    if loss_pct >= DAILY_LOSS_LIMIT_PCT:
        set_emergency_stop(True)
        return True
    return False


def reset_daily_baseline(portfolio: Portfolio):
    snap = portfolio.get_snapshot()
    storage.set_state("daily_start_assets", snap["total_assets"])
    set_emergency_stop(False)
