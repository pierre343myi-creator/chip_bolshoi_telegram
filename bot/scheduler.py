import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import get_settings

logger = logging.getLogger(__name__)


async def _send_pending_advance_notifications() -> None:
    """Send advance notifications for events saved by the local parser."""
    from db import get_session
    from db.repository import EventRepository
    from bot.notifications import send_advance_notification

    async with get_session() as session:
        repo = EventRepository(session)
        events = await repo.get_pending_advance_notifications()

    for event in events:
        await send_advance_notification(event)
        logger.info("Advance notification sent for event %d '%s'", event.id, event.title)


async def _check_today_notifications() -> None:
    from bot.notifications import send_today_notifications
    logger.debug("Checking today notifications")
    await send_today_notifications()


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        _send_pending_advance_notifications,
        trigger=IntervalTrigger(minutes=30),
        id="advance_notifications",
        name="Send advance notifications for new events",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    scheduler.add_job(
        _check_today_notifications,
        trigger=IntervalTrigger(minutes=30),
        id="today_notifications",
        name="Check and send today sale notifications",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    return scheduler
