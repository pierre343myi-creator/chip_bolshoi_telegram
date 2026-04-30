"""
Local parser script. Run on a machine with non-datacenter IP.
Schedule via Windows Task Scheduler every 6 hours.

Usage:
    python run_parser.py              # parse and save new events to DB
    python run_parser.py --dry-run    # parse only, print results, do not save
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import get_settings
from db import close_engine, get_session, init_engine
from db.repository import EventRepository
from parser.extractor import event_to_dict
from parser.scraper import fetch_announcements

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def run(dry_run: bool = False) -> None:
    settings = get_settings()

    if not dry_run:
        ssl_ctx = settings.build_ssl_context()
        init_engine(settings.database_url, ssl_context=ssl_ctx)

    logger.info("Fetching announcements from %s", settings.bolshoi_news_url)
    events = await fetch_announcements(settings.bolshoi_news_url)

    if not events:
        logger.info("No relevant announcements found")
        if not dry_run:
            await close_engine()
        return

    logger.info("Found %d announcement(s)", len(events))
    new_count = 0

    for ev in events:
        if dry_run:
            logger.info("[DRY RUN] %s", ev.title)
            logger.info("  Scene    : %s", ev.scene)
            logger.info("  Program  : %s", ev.program_type)
            logger.info("  Price    : %s", ev.ticket_price)
            logger.info("  Sale at  : %s", ev.sale_opens_at)
            logger.info("  URL      : %s", ev.source_url)
            continue

        async with get_session() as session:
            repo = EventRepository(session)
            existing = await repo.get_by_source_url(ev.source_url)
            if existing:
                logger.info("Already in DB: %s", ev.title)
                continue
            await repo.create(**event_to_dict(ev))
            logger.info("Saved: %s", ev.title)
            new_count += 1

    if not dry_run:
        logger.info("Done. %d new event(s) saved.", new_count)
        await close_engine()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Parse bolshoi.ru and save events to DB")
    ap.add_argument("--dry-run", action="store_true", help="Parse only, do not save to DB")
    args = ap.parse_args()
    asyncio.run(run(dry_run=args.dry_run))
