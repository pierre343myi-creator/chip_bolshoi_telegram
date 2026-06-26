"""
Telegram Bot API client and notification broadcast logic.

All requests go to https://api.telegram.org/bot<TOKEN>/<METHOD>.
Docs: https://core.telegram.org/bots/api
"""
import asyncio
import logging
from datetime import datetime, timezone

import aiohttp

from config import get_settings
from db import get_session
from db.models import Event
from db.repository import EventRepository, SubscriberRepository

logger = logging.getLogger(__name__)

# Telegram limit for bulk notifications is ~30 messages/sec overall.
# 0.06s delay → ~16 msg/sec, comfortably under the limit.
_SEND_DELAY = 0.06
_RETRY_DELAY = 3            # seconds between retries on transient errors
_MAX_SEND_RETRIES = 2


def _fmt_dates(dates: list[str] | None) -> str:
    if not dates:
        return "уточняется"
    return ", ".join(dates)


def _fmt_sale_time(dt: datetime | None) -> tuple[str, str]:
    """Return (date_str, time_str) for sale_opens_at."""
    if not dt:
        return "уточняется", ""
    local = dt  # stored as UTC; format as-is (server is UTC+3, but we store naive-UTC)
    return local.strftime("%d.%m.%Y"), local.strftime("%H:%M")


def build_advance_message(event: Event) -> str:
    sale_date, sale_time = _fmt_sale_time(event.sale_opens_at)
    dates_str = _fmt_dates(event.show_dates)
    price = event.ticket_price or "уточняется"
    program = event.program_type or "Доступный Большой"
    scene = event.scene or "уточняется"

    lines = [
        "🎭 Большой театр | Доступный Большой",
        "",
        "📢 Открывается продажа льготных билетов!",
        "",
        f"🎬 Спектакль: {event.title}",
        f"🏛 Сцена: {scene}",
        f"📅 Дата показа: {dates_str}",
        f"💰 Цена по программе «{program}»: {price} руб.",
        "",
        f"🗓 Продажа открывается: {sale_date} в {sale_time}",
        "   (на сайте: bolshoi.ru)",
        "",
        "🔔 Я напомню вам в день открытия продаж!",
    ]
    return "\n".join(lines)


def build_today_message(event: Event) -> str:
    _, sale_time = _fmt_sale_time(event.sale_opens_at)
    dates_str = _fmt_dates(event.show_dates)
    price = event.ticket_price or "уточняется"
    program = event.program_type or "Доступный Большой"
    scene = event.scene or "уточняется"
    ticket_url = event.ticket_url or "https://bolshoi.ru"

    lines = [
        "🎟 СЕГОДНЯ открывается продажа билетов!",
        "",
        f"🎭 {event.title}",
        f"🏛 {scene}, {dates_str}",
        f"💰 {price} руб. по программе «{program}»",
        "",
        f"⏰ Продажа открывается в {sale_time} на bolshoi.ru",
        "   Билеты разбирают быстро — успейте купить!",
        "",
        f"👉 Купить билет: {ticket_url}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Low-level API call
# ---------------------------------------------------------------------------

async def _post_message(
    session: aiohttp.ClientSession,
    chat_id: int,
    text: str,
    base: str,
) -> bool:
    url = f"{base}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": False}
    for attempt in range(1, _MAX_SEND_RETRIES + 2):
        try:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    return True

                try:
                    data = await resp.json()
                except Exception:
                    data = {"raw": await resp.text()}

                # Honour Telegram's "Too Many Requests" back-off hint.
                if resp.status == 429:
                    retry_after = int(
                        (data.get("parameters") or {}).get("retry_after", _RETRY_DELAY)
                    )
                    logger.warning(
                        "Telegram 429 for chat %s (attempt %d): retry after %ss",
                        chat_id, attempt, retry_after,
                    )
                    if attempt <= _MAX_SEND_RETRIES:
                        await asyncio.sleep(retry_after)
                    continue

                logger.warning(
                    "Telegram API %s for chat %s (attempt %d): %s",
                    resp.status, chat_id, attempt, data,
                )
        except aiohttp.ClientError as e:
            logger.warning("Send error for chat %s (attempt %d): %s", chat_id, attempt, e)
        if attempt <= _MAX_SEND_RETRIES:
            await asyncio.sleep(_RETRY_DELAY)
    return False


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------

async def broadcast(text: str) -> int:
    """Send text to all active subscribers. Returns number of successful sends."""
    settings = get_settings()
    sent = 0

    async with get_session() as db_session:
        repo = SubscriberRepository(db_session)
        subscribers = await repo.get_active()

    if not subscribers:
        logger.info("No active subscribers — nothing to broadcast")
        return 0

    async with aiohttp.ClientSession() as http:
        for sub in subscribers:
            ok = await _post_message(
                http, sub.telegram_user_id, text, settings.telegram_api_base
            )
            if ok:
                sent += 1
            await asyncio.sleep(_SEND_DELAY)

    logger.info("Broadcast complete: %d/%d delivered", sent, len(subscribers))
    return sent


async def send_to_user(user_id: int, text: str) -> bool:
    settings = get_settings()
    async with aiohttp.ClientSession() as http:
        return await _post_message(http, user_id, text, settings.telegram_api_base)


# ---------------------------------------------------------------------------
# Notification tasks (called by scheduler)
# ---------------------------------------------------------------------------

async def send_advance_notification(event: Event) -> None:
    text = build_advance_message(event)
    await broadcast(text)
    async with get_session() as session:
        repo = EventRepository(session)
        await repo.mark_notified_advance(event.id)
    logger.info("Advance notification sent for event %d '%s'", event.id, event.title)


async def send_today_notifications() -> None:
    settings = get_settings()
    async with get_session() as session:
        repo = EventRepository(session)
        events = await repo.get_pending_today_notifications(settings.notify_before_minutes)

    for event in events:
        text = build_today_message(event)
        await broadcast(text)
        async with get_session() as session:
            repo = EventRepository(session)
            await repo.mark_notified_today(event.id)
        logger.info("Today notification sent for event %d '%s'", event.id, event.title)


# ---------------------------------------------------------------------------
# Webhook registration
# ---------------------------------------------------------------------------

async def register_webhook(webhook_url: str) -> None:
    settings = get_settings()
    url = f"{settings.telegram_api_base}/setWebhook"
    payload = {"url": webhook_url, "allowed_updates": ["message", "edited_message"]}
    async with aiohttp.ClientSession() as http:
        try:
            async with http.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                body = await resp.json()
                if resp.status == 200 and body.get("ok"):
                    logger.info("Webhook registered: %s", webhook_url)
                else:
                    logger.error("Failed to register webhook (HTTP %s): %s", resp.status, body)
        except aiohttp.ClientError as e:
            logger.error("Webhook registration error: %s", e)
