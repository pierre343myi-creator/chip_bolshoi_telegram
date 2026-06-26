"""
Command handlers for Telegram Bot webhook updates.

Telegram delivers a JSON Update for every interaction. The bot reacts to plain
text messages; commands are ordinary messages whose text starts with '/'.
When a user first opens the bot and presses "Start", Telegram simply sends a
message with the text "/start", so no special "bot started" event is needed.
"""
import logging
from datetime import timezone

from bot.notifications import send_to_user
from db import get_session
from db.repository import EventRepository, SubscriberRepository

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Команды бота:\n"
    "/подписаться (/subscribe) — подписаться на уведомления об открытии продаж\n"
    "/отписаться (/unsubscribe) — отписаться от уведомлений\n"
    "/расписание (/schedule) — ближайшие продажи по программе «Доступный Большой»\n"
    "/статус (/status) — проверить вашу подписку\n"
    "/помощь (/help) — это сообщение"
)


async def _handle_subscribe(user_id: int) -> None:
    async with get_session() as session:
        repo = SubscriberRepository(session)
        _, is_new = await repo.subscribe(user_id)
    if is_new:
        await send_to_user(
            user_id,
            "✅ Вы подписаны на уведомления!\n\n"
            "Я сообщу, когда откроется продажа льготных билетов "
            "по программе «Доступный Большой».",
        )
    else:
        await send_to_user(user_id, "Вы уже подписаны. Ожидайте уведомлений! 🎭")


async def _handle_unsubscribe(user_id: int) -> None:
    async with get_session() as session:
        repo = SubscriberRepository(session)
        was_active = await repo.unsubscribe(user_id)
    if was_active:
        await send_to_user(user_id, "❌ Вы отписались от уведомлений.")
    else:
        await send_to_user(user_id, "Вы и так не были подписаны.")


async def _handle_schedule(user_id: int) -> None:
    async with get_session() as session:
        repo = EventRepository(session)
        events = await repo.get_upcoming(limit=10)

    if not events:
        await send_to_user(
            user_id,
            "Пока новых объявлений не поступало.\n"
            "Подпишитесь и я сообщу, как только появятся новые билеты!",
        )
        return

    lines = ["📅 Предстоящие продажи по программе «Доступный Большой»:\n"]
    for i, ev in enumerate(events, 1):
        sale_str = "уточняется"
        if ev.sale_opens_at:
            sale_str = ev.sale_opens_at.strftime("%d.%m.%Y в %H:%M")
        price = ev.ticket_price or "уточняется"
        scene = ev.scene or "—"
        lines.append(
            f"{i}. {ev.title} — продажа {sale_str}\n"
            f"   💰 {price} руб. | {scene}"
        )

    await send_to_user(user_id, "\n".join(lines))


async def _handle_status(user_id: int) -> None:
    async with get_session() as session:
        repo = SubscriberRepository(session)
        sub = await repo.get(user_id)
    if sub and sub.active:
        since = sub.subscribed_at.strftime("%d.%m.%Y")
        await send_to_user(user_id, f"✅ Подписка активна (с {since}).")
    else:
        await send_to_user(
            user_id,
            "❌ Вы не подписаны.\nНапишите /подписаться, чтобы получать уведомления.",
        )


async def _handle_help(user_id: int) -> None:
    await send_to_user(user_id, HELP_TEXT)


_COMMAND_MAP = {
    # subscribe
    "/start": _handle_subscribe,
    "/подписаться": _handle_subscribe,
    "/subscribe": _handle_subscribe,
    # unsubscribe
    "/стоп": _handle_unsubscribe,
    "/отписаться": _handle_unsubscribe,
    "/unsubscribe": _handle_unsubscribe,
    "/stop": _handle_unsubscribe,
    # schedule
    "/расписание": _handle_schedule,
    "/schedule": _handle_schedule,
    # status
    "/статус": _handle_status,
    "/status": _handle_status,
    # help
    "/помощь": _handle_help,
    "/help": _handle_help,
}


async def dispatch(user_id: int, text: str) -> None:
    """Route incoming message text to the appropriate handler."""
    cmd = text.strip().split()[0].lower() if text.strip() else ""
    # In groups Telegram appends the bot username, e.g. "/start@MyBot".
    if "@" in cmd:
        cmd = cmd.split("@", 1)[0]
    handler = _COMMAND_MAP.get(cmd)
    if handler:
        try:
            await handler(user_id)
        except Exception:
            logger.exception("Handler error for user %s command '%s'", user_id, cmd)
            await send_to_user(user_id, "Произошла ошибка. Попробуйте позже.")
    else:
        await send_to_user(
            user_id,
            "Неизвестная команда. Напишите /помощь для списка команд.",
        )
