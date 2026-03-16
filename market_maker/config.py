"""
config.py — Centralised configuration loaded from environment / .env file.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env from the directory containing this file (or project root)
_env_path = Path(__file__).parent / ".env"
if not _env_path.exists():
    _env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _getf(key: str, default: float = 0.0) -> float:
    try:
        return float(_get(key, str(default)))
    except ValueError:
        return default


def _geti(key: str, default: int = 0) -> int:
    try:
        return int(_get(key, str(default)))
    except ValueError:
        return default


def _getb(key: str, default: bool = False) -> bool:
    val = _get(key, str(default)).lower()
    return val in ("1", "true", "yes", "on")


@dataclass
class ExchangeConfig:
    exchange_id: str
    api_key: str
    api_secret: str
    passphrase: str = ""
    sandbox: bool = False


@dataclass
class StrategyConfig:
    symbol: str
    spread: float           # fractional, e.g. 0.002 = 0.2%
    order_size: float       # base currency per level
    levels: int             # number of levels per side
    level_size_multiplier: float   # size growth per level
    level_spacing: float    # extra spread per level
    refresh_interval: float # seconds between order refreshes
    target_price: Optional[float]  # None → use reference exchange
    inventory_skew: bool    # skew orders based on inventory
    max_position_base: float
    max_position_quote: float


@dataclass
class CorrelationConfig:
    weight: float           # 0.0–1.0 weight toward reference price
    max_deviation: float    # halt if price deviates more than this fraction


@dataclass
class VolumeConfig:
    enabled: bool
    interval: float         # seconds between volume trades
    min_size: float
    max_size: float


@dataclass
class BotConfig:
    primary: ExchangeConfig
    reference: ExchangeConfig
    strategy: StrategyConfig
    correlation: CorrelationConfig
    volume: VolumeConfig
    dry_run: bool


def load_config() -> BotConfig:
    primary = ExchangeConfig(
        exchange_id=_get("PRIMARY_EXCHANGE", "binance"),
        api_key=_get("PRIMARY_API_KEY"),
        api_secret=_get("PRIMARY_API_SECRET"),
        passphrase=_get("PRIMARY_PASSPHRASE"),
    )

    reference = ExchangeConfig(
        exchange_id=_get("REFERENCE_EXCHANGE", "kraken"),
        api_key=_get("REFERENCE_API_KEY"),
        api_secret=_get("REFERENCE_API_SECRET"),
    )

    raw_target = _get("TARGET_PRICE")
    target_price: Optional[float] = float(raw_target) if raw_target else None

    strategy = StrategyConfig(
        symbol=_get("SYMBOL", "BTC/USDT"),
        spread=_getf("SPREAD", 0.002),
        order_size=_getf("ORDER_SIZE", 0.001),
        levels=_geti("LEVELS", 3),
        level_size_multiplier=_getf("LEVEL_SIZE_MULTIPLIER", 1.5),
        level_spacing=_getf("LEVEL_SPACING", 0.001),
        refresh_interval=_getf("REFRESH_INTERVAL", 10.0),
        target_price=target_price,
        inventory_skew=_getb("INVENTORY_SKEW", True),
        max_position_base=_getf("MAX_POSITION_BASE", 0.1),
        max_position_quote=_getf("MAX_POSITION_QUOTE", 5000.0),
    )

    correlation = CorrelationConfig(
        weight=_getf("CORRELATION_WEIGHT", 0.7),
        max_deviation=_getf("MAX_PRICE_DEVIATION", 0.05),
    )

    volume = VolumeConfig(
        enabled=_getb("VOLUME_GENERATION", False),
        interval=_getf("VOLUME_INTERVAL", 30.0),
        min_size=_getf("VOLUME_MIN_SIZE", 0.0001),
        max_size=_getf("VOLUME_MAX_SIZE", 0.0005),
    )

    return BotConfig(
        primary=primary,
        reference=reference,
        strategy=strategy,
        correlation=correlation,
        volume=volume,
        dry_run=_getb("DRY_RUN", True),
    )
