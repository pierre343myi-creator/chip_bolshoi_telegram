import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import get_settings

logger = logging.getLogger(__name__)


async def _parse_and_notify() -> None:
    """Fetch new announcements and send advance notifications for new events."""
    from parser.scraper import fetch_announcements
    from parser.extractor import event_to_dict
    from db import get_session
    from db.repository import EventRepository
    from bot.notifications import send_advance_notification

    settings = get_settings()
    logger.info("Scheduled parse started")

    events = await fetch_announcements(settings.bolshoi_news_url)
    new_count = 0

    for ev in events:
        async with get_session() as session:
            repo = EventRepository(session)
            existing = await repo.get_by_source_url(ev.source_url)
            if existing:
                continue
            db_event = await repo.create(**event_to_dict(ev))

        await send_advance_notification(db_event)
        new_count += 1

    logger.info("Parse complete: %d new event(s)", new_count)


async def _check_today_notifications() -> None:
    from bot.notifications import send_today_notifications
    logger.debug("Checking today notifications")
    await send_today_notifications()


def create_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        _parse_and_notify,
        trigger=IntervalTrigger(hours=settings.parse_interval_hours),
        id="parse_announcements",
        name="Parse bolshoi.ru announcements",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=600,
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
