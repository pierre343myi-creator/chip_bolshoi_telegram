"""
Command handlers for MAX Bot webhook updates.

MAX Bot API update_type values (TamTam-compatible):
  - message_created  — new message from user
  - bot_started      — user pressed Start or opened bot for first time
"""
import logging
from datetime import timezone

from bot.notifications import send_to_user
from db import get_session
from db.repository import EventRepository, SubscriberRepository

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Команды бота:\n"
    "/подписаться — подписаться на уведомления об открытии продаж\n"
    "/отписаться — отписаться от уведомлений\n"
    "/расписание — ближайшие продажи по программе «Доступный Большой»\n"
    "/статус — проверить вашу подписку\n"
    "/помощь — это сообщение"
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
    "/start": _handle_subscribe,
    "/подписаться": _handle_subscribe,
    "/стоп": _handle_unsubscribe,
    "/отписаться": _handle_unsubscribe,
    "/расписание": _handle_schedule,
    "/помощь": _handle_help,
    "/статус": _handle_status,
    "/help": _handle_help,
}


async def dispatch(user_id: int, text: str) -> None:
    """Route incoming message text to the appropriate handler."""
    cmd = text.strip().split()[0].lower() if text.strip() else ""
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
