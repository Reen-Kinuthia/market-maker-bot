"""
api/main.py — FastAPI backend for the Market Maker Dashboard.

Serves:
  GET  /api/status        - Bot running state
  GET  /api/snapshot      - Current full market snapshot
  POST /api/bot/start     - Start simulation
  POST /api/bot/stop      - Stop simulation
  POST /api/config        - Update config at runtime
  WS   /ws                - Real-time broadcast (1 msg/sec)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .simulator import MarketSimulator

log = logging.getLogger("api")
logging.basicConfig(level=logging.INFO)

# ────────────────────────────────────────────────────
#  Shared state
# ────────────────────────────────────────────────────

_sim = MarketSimulator(
    symbol="BTC/USDT",
    start_price=65000.0,
    spread_frac=0.002,
    levels=3,
    level_spacing=0.001,
    base_order_size=0.001,
    size_multiplier=1.5,
)

_connections: Set[WebSocket] = set()
_bot_running: bool = False
_tick_task: asyncio.Task | None = None

_config = {
    "symbol": "BTC/USDT",
    "spread": 0.002,
    "levels": 3,
    "order_size": 0.001,
    "level_size_multiplier": 1.5,
    "level_spacing": 0.001,
    "refresh_interval": 10,
    "target_price": None,
    "correlation_weight": 0.7,
    "volume_generation": False,
    "dry_run": True,
}


# ────────────────────────────────────────────────────
#  Background tick loop
# ────────────────────────────────────────────────────

async def _broadcast(data: dict) -> None:
    dead: Set[WebSocket] = set()
    payload = json.dumps(data)
    for ws in list(_connections):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    _connections.difference_update(dead)


async def _tick_loop() -> None:
    global _bot_running
    while _bot_running:
        try:
            snapshot = _sim.tick()
            snapshot["bot_running"] = _bot_running
            snapshot["config"] = _config
            await _broadcast(snapshot)
        except Exception as exc:
            log.error("Tick error: %s", exc)
        await asyncio.sleep(1.0)


# ────────────────────────────────────────────────────
#  App lifecycle
# ────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bot_running, _tick_task
    _bot_running = True
    _tick_task = asyncio.create_task(_tick_loop())
    yield
    _bot_running = False
    if _tick_task:
        _tick_task.cancel()


app = FastAPI(title="Market Maker Dashboard API", lifespan=lifespan)

_allowed_origin = os.getenv("ALLOWED_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_allowed_origin] if _allowed_origin != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ────────────────────────────────────────────────────
#  REST endpoints
# ────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    return {
        "running": _bot_running,
        "symbol": _sim.symbol,
        "cycle": _sim._cycle,
        "dry_run": _config["dry_run"],
    }


@app.get("/api/snapshot")
async def get_snapshot():
    snap = _sim._snapshot()
    snap["bot_running"] = _bot_running
    snap["config"] = _config
    return snap


@app.post("/api/bot/start")
async def start_bot():
    global _bot_running, _tick_task
    if _bot_running:
        return {"ok": False, "message": "Already running"}
    _bot_running = True
    _tick_task = asyncio.create_task(_tick_loop())
    return {"ok": True, "message": "Bot started"}


@app.post("/api/bot/stop")
async def stop_bot():
    global _bot_running, _tick_task
    _bot_running = False
    if _tick_task:
        _tick_task.cancel()
    return {"ok": True, "message": "Bot stopped"}


@app.post("/api/config")
async def update_config(body: dict):
    global _config, _sim
    _config.update(body)

    raw_target = _config.get("target_price")
    target_price = float(raw_target) if raw_target else None

    # If only target_price changed, update in place (no reset)
    if list(body.keys()) == ["target_price"]:
        _sim.set_target_price(target_price)
        return {"ok": True, "config": _config}

    # Full rebuild for other param changes
    symbol = _config.get("symbol", "BTC/USDT")
    current_mid = _sim._mid
    _sim = MarketSimulator(
        symbol=symbol,
        start_price=current_mid,
        spread_frac=float(_config.get("spread", 0.002)),
        levels=int(_config.get("levels", 3)),
        level_spacing=float(_config.get("level_spacing", 0.001)),
        base_order_size=float(_config.get("order_size", 0.001)),
        size_multiplier=float(_config.get("level_size_multiplier", 1.5)),
        target_price=target_price,
    )
    return {"ok": True, "config": _config}


@app.post("/api/target-price")
async def set_target_price(body: dict):
    """Quick endpoint — just update target price without full config rebuild."""
    global _config
    raw = body.get("price")
    price = float(raw) if raw else None
    _config["target_price"] = price
    _sim.set_target_price(price)
    return {"ok": True, "target_price": price}


# ────────────────────────────────────────────────────
#  WebSocket
# ────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _connections.add(ws)
    log.info("WS client connected. Total: %d", len(_connections))

    # Send immediate snapshot on connect
    try:
        snap = _sim._snapshot()
        snap["bot_running"] = _bot_running
        snap["config"] = _config
        await ws.send_text(json.dumps(snap))

        # Keep alive — data is pushed by tick loop
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                pass  # no-op ping keepalive
    except WebSocketDisconnect:
        pass
    finally:
        _connections.discard(ws)
        log.info("WS client disconnected. Total: %d", len(_connections))


# ────────────────────────────────────────────────────
#  Serve built React frontend (production)
# ────────────────────────────────────────────────────

_DIST = Path(__file__).parent.parent / "dashboard" / "dist"

if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        return FileResponse(_DIST / "index.html")
