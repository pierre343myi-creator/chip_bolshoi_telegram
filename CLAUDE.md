# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

This is a Telegram bot that notifies subscribers when discounted-ticket sales open
under the Bolshoi Theatre's "Доступный Большой" program (parsed from bolshoi.ru).

## Common commands

```bash
# Install dependencies (activate venv first)
pip install -r requirements.txt
python -m camoufox fetch                                # one-time browser download for the parser

# Run bot (webhook server + scheduler)
python -m bot.main

# Run the parser standalone (writes new events to the DB)
python run_parser.py                                    # parse + save
python run_parser.py --dry-run                          # parse + print, no DB writes

# Test parser without DB or notifications
python -m parser.scraper --test
python -m parser.scraper --test --url https://bolshoi.ru/news/obyavleniya/

# Database migrations
alembic upgrade head                                    # apply all
alembic revision --autogenerate -m "description"        # create new migration
alembic downgrade -1                                    # roll back one step
```

## Architecture

There are two processes that share one PostgreSQL database:

1. **The bot server** (`python -m bot.main`) — webhook server + scheduler + notifications.
2. **The parser** (`python run_parser.py`) — runs separately (see "Parser" below) and
   writes events into the DB. The bot server itself never scrapes bolshoi.ru.

### Bot server (`bot/main.py`)

**Webhook server** (aiohttp)
- `POST /webhook` receives Telegram `Update` objects, extracts `message`/`edited_message`,
  and dispatches `(chat_id, text)` to `bot/handlers.py`.
- `GET /healthcheck` returns JSON status.
- The webhook URL is registered with Telegram on startup via
  `bot/notifications.register_webhook()` (calls Telegram's `setWebhook`).
- On startup `main()` also fires `_send_pending_advance_notifications()` once, so any
  events the parser already saved get their advance notification immediately instead of
  waiting for the first scheduler tick.

**Scheduler** (`bot/scheduler.py` → APScheduler `AsyncIOScheduler`)
- `_send_pending_advance_notifications()` — every 30 min: finds events with
  `notified_advance = False` and sends the advance notification.
- `_check_today_notifications()` — every 30 min: finds events whose `sale_opens_at` is
  within the next `NOTIFY_BEFORE_MINUTES` window and sends the "sale opens today"
  notification.

### Parser pipeline (`parser/`)
- `scraper.py` — uses **Camoufox** (a fingerprint-resistant Firefox via Playwright) to
  bypass bolshoi.ru's QRATOR anti-bot protection. `_fetch_page()` retries up to
  `MAX_RETRIES` (3) with a 30-minute backoff (`RETRY_DELAY_SECONDS`).
  `_parse_list_page()` extracts candidate announcements; `fetch_announcements()` is the
  public async entry point.
- `extractor.py` — pure HTML → `ExtractedEvent` dataclass. All regex/date parsing lives
  here (`_parse_russian_date`, `_extract_sale_date`, `_extract_price`, etc.).
  **If bolshoi.ru changes layout, this is the only file to update.**

> Because most VPS/datacenter IPs get blocked by QRATOR, the parser is designed to run
> from a non-datacenter IP (e.g. a home machine on a schedule) and write to the same DB
> the bot reads from. If the bot's host is not blocked, the parser can run there too.

## Database

Two tables: `events` and `subscribers`. The subscriber primary key is `telegram_user_id`
and **must be `BigInteger`** — Telegram user/chat IDs exceed the 32-bit `Integer` range.

The engine is lazily initialised — `db.init_engine()` must be called before any
repository use (done in `bot/main.py` and `run_parser.py`). Use
`async with get_session() as session:` everywhere; never hold a session across `await`
calls to external services.

Migrations live in `db/migrations/versions/`. Always generate via
`alembic revision --autogenerate`, never edit the schema directly.

## Telegram Bot API

- Base URL: `https://api.telegram.org/bot<TOKEN>/<METHOD>` (built by
  `config.Settings.telegram_api_base`). Auth is the token in the URL path — no query param.
- Sending: `bot/notifications._post_message()` calls `sendMessage` with JSON
  `{chat_id, text}`. It honours HTTP 429 by sleeping for the `retry_after` value Telegram
  returns.
- Incoming updates: a plain text message arrives as `update.message.text`; the reply
  target is `update.message.chat.id` (in a 1-on-1 chat this equals the user id). When a
  user first presses "Start", Telegram simply sends a `/start` message — there is no
  separate "bot started" event.
- Commands are ordinary messages starting with `/`. `handlers.dispatch()` strips an
  optional `@botname` suffix (added in groups) and maps both Russian and Latin aliases.
- Rate limit: bulk sends are capped ~30 msg/sec; `bot/notifications.py` uses
  `_SEND_DELAY = 0.06s` (~16 msg/sec) between messages.
- Webhooks require HTTPS on port 443/80/88/8443, so in production nginx terminates TLS on
  443 and proxies to the aiohttp server on `WEBHOOK_PORT` (8080).

## Configuration

`config.py` uses `pydantic-settings`. Key fields: `telegram_bot_token`, `webhook_url`,
`webhook_port`, the `db_*` group, and `notify_before_minutes`.
`Settings.database_url` builds the asyncpg connection string.
`Settings.build_ssl_context()` returns an `ssl.SSLContext` **only if `DB_SSL_CA` is set**,
otherwise `None` — for a local PostgreSQL on the same VPS, leave `DB_SSL_CA` empty.

## Notification flow

New event found → `send_advance_notification(event)` → `broadcast()` + `mark_notified_advance()`
Sale day arrives → `send_today_notifications()` → `broadcast()` + `mark_notified_today()`
Both flags prevent double-sending across scheduler runs.

## Deployment

Target: a classic Ubuntu VPS (22.04/24.04), user `bolshoi-bot`, path
`/home/bolshoi-bot/chip_bolshoi_telegram/`, with a locally installed PostgreSQL and
nginx + Let's Encrypt (certbot) in front of the webhook server.

Service file: `deploy/bolshoi-bot.service`. First deploy: `bash deploy/setup.sh`
(venv → pip → camoufox fetch → alembic). Updates: `bash deploy/update.sh`
(git pull → pip → alembic → `systemctl restart`).

See `README.md` for the full step-by-step VPS guide (PostgreSQL, nginx, certbot, systemd).
