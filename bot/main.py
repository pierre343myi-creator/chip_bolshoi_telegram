"""
Entry point for the Bolshoi Bot.

Starts:
  1. PostgreSQL connection pool
  2. aiohttp webhook server  (POST /webhook, GET /healthcheck)
  3. APScheduler (parse every N hours, check today-notifications every 30 min)
  4. Registers webhook URL with MAX Bot API

Run:
    python -m bot.main
"""
import asyncio
import json
import logging
import logging.handlers
import os
import sys

from aiohttp import web

from bot.handlers import dispatch
from bot.notifications import register_webhook
from bot.scheduler import create_scheduler
from config import get_settings
from db import close_engine, init_engine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Webhook HTTP handlers
# ---------------------------------------------------------------------------

async def handle_webhook(request: web.Request) -> web.Response:
    try:
        update = await request.json()
    except Exception:
        return web.Response(status=400, text="Bad JSON")

    update_type = update.get("update_type", "")

    if update_type in ("message_created", "bot_started"):
        message = update.get("message", {})
        sender = message.get("sender", {})
        user_id: int | None = sender.get("user_id")
        body = message.get("body", {})
        text: str = body.get("text", "") or ""

        if not user_id:
            return web.Response(status=200)

        # For bot_started treat as /start
        if update_type == "bot_started":
            text = "/start"

        asyncio.create_task(dispatch(user_id, text))

    return web.Response(status=200, text="ok")


async def handle_healthcheck(request: web.Request) -> web.Response:
    return web.Response(
        content_type="application/json",
        text=json.dumps({"status": "ok", "service": "bolshoi-bot"}),
    )


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/webhook", handle_webhook)
    app.router.add_get("/healthcheck", handle_healthcheck)
    return app


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(log_level: str, log_file: str) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s")
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if root.handlers:
        return  # already configured (e.g. double-call on restart)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_file)

    logger.info("Starting Bolshoi Bot")

    # Init DB
    ssl_ctx = settings.build_ssl_context()
    init_engine(settings.database_url, ssl_context=ssl_ctx)
    logger.info("Database engine initialised")

    # Register webhook
    await register_webhook(settings.webhook_url)

    # Start scheduler
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    # Start web server
    app = create_app()
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.webhook_port)
    await site.start()
    logger.info("Webhook server listening on port %d", settings.webhook_port)

    # Run the first parse immediately on startup
    from bot.scheduler import _parse_and_notify
    asyncio.create_task(_parse_and_notify())

    # Block forever
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        logger.info("Shutting down…")
        scheduler.shutdown(wait=False)
        await runner.cleanup()
        await close_engine()


if __name__ == "__main__":
    asyncio.run(main())
