#!/usr/bin/env python3
"""
run.py — Market Maker Bot entry point.

Usage
-----
    # Dry-run (safe, no real orders):
    python run.py

    # With a custom .env file:
    ENV_FILE=./production.env python run.py

    # Override single params inline:
    DRY_RUN=false SYMBOL=ETH/USDT SPREAD=0.003 python run.py
"""
import asyncio
import logging
import sys

from rich.logging import RichHandler

# ── Logging setup ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)],
)
log = logging.getLogger("market_maker")


def main() -> None:
    from market_maker import MarketMakerBot, load_config

    cfg = load_config()

    if cfg.dry_run:
        log.warning(
            "[yellow bold]DRY RUN mode[/] — no real orders will be placed. "
            "Set DRY_RUN=false in .env to trade live."
        )

    bot = MarketMakerBot(cfg)

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        log.info("Interrupted by user.")
    except Exception as exc:
        log.critical("Bot crashed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
