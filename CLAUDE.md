# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

```bash
# Install dependencies (activate venv first)
pip install -r requirements.txt

# Run bot
python -m bot.main

# Test parser without DB or notifications
python -m parser.scraper --test
python -m parser.scraper --test --url https://bolshoi.ru/news/obyavleniya/

# Database migrations
alembic upgrade head                                    # apply all
alembic revision --autogenerate -m "description"       # create new migration
alembic downgrade -1                                    # roll back one step
```

## Architecture

The bot has three independent concerns wired together in `bot/main.py`:

**1. Webhook server** (`bot/main.py` → aiohttp)
- `POST /webhook` receives MAX Bot API updates, dispatches to `bot/handlers.py`
- `GET /healthcheck` returns JSON status
- Webhook URL is registered with MAX API on startup via `bot/notifications.register_webhook()`

**2. Scheduler** (`bot/scheduler.py` → APScheduler `AsyncIOScheduler`)
- Every N hours: `_parse_and_notify()` — fetches bolshoi.ru, saves new events to DB, sends advance notifications
- Every 30 min: `_check_today_notifications()` — queries events whose `sale_opens_at` is within the next `NOTIFY_BEFORE_MINUTES` window, sends today notifications

**3. Parser pipeline** (`parser/`)
- `scraper.py` — HTTP fetching with 3 retries (30-min backoff). `_parse_list_page()` tries multiple CSS selectors for the news list; `fetch_announcements()` is the public async entry point
- `extractor.py` — pure HTML → `ExtractedEvent` dataclass. All regex/date parsing lives here. **If bolshoi.ru changes layout, this is the only file to update.**

## Database

Two tables: `events` and `subscribers`. Engine is lazily initialised — `db.init_engine()` must be called before any repository use (done in `bot/main.py`). Use `async with get_session() as session:` everywhere; never hold a session across `await` calls to external services.

Migrations live in `db/migrations/versions/`. Always generate via `alembic revision --autogenerate`, never edit the schema directly.

## MAX Bot API

Base URL: `https://botapi.max.ru` (TamTam-compatible protocol).  
Auth: `?access_token=TOKEN` query param on every request.  
Incoming webhook payload field: `update_type` — values `message_created` and `bot_started` are handled; others are silently ignored.  
Rate limit: 20 RPS — `bot/notifications.py` sends with `_SEND_DELAY = 0.06s` between messages.

## Configuration

`config.py` uses `pydantic-settings`. `Settings.database_url` builds the asyncpg connection string; `Settings.build_ssl_context()` returns an `ssl.SSLContext` for Yandex Managed PostgreSQL (port 6432, SSL required). SSL cert path is `DB_SSL_CA` in `.env`.

## Notification flow

New event found → `send_advance_notification(event)` → broadcast + `mark_notified_advance()`  
Sale day arrives → `send_today_notifications()` → broadcast + `mark_notified_today()`  
Both flags prevent double-sending across scheduler runs.

## Deployment

Target: Ubuntu 22.04, user `bolshoi-bot`, path `/home/bolshoi-bot/bolshoi-bot/`.  
Service file: `deploy/bolshoi-bot.service`. First deploy: `bash deploy/setup.sh`. Updates: `bash deploy/update.sh` (git pull → pip → alembic → systemctl restart).  
`bolshoi-bot` user has passwordless sudo only for `systemctl restart bolshoi-bot` and `systemctl status bolshoi-bot`.
