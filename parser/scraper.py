"""
Scraper for bolshoi.ru/news/obyavleniya/.

Run in test mode (no DB writes, no notifications):
    python -m parser.scraper --test
"""
import argparse
import asyncio
import json
import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup

from parser.extractor import ExtractedEvent, extract_event

logger = logging.getLogger(__name__)

BASE_URL = "https://bolshoi.ru"

KEYWORDS = [
    "Доступный Большой",
    "Места низкой ценовой категории",
    "60 плюс",
    "Молодёжный",
    "специальные программы",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

RETRY_DELAY_SECONDS = 1800  # 30 minutes between retries
MAX_RETRIES = 3


async def _fetch(url: str, client: httpx.AsyncClient, retries: int = MAX_RETRIES) -> str | None:
    for attempt in range(1, retries + 1):
        try:
            resp = await client.get(url, timeout=30)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPStatusError as e:
            logger.warning("[%d/%d] HTTP %s for %s", attempt, retries, e.response.status_code, url)
        except httpx.RequestError as e:
            logger.warning("[%d/%d] Request error for %s: %s", attempt, retries, url, e)
        if attempt < retries:
            logger.info("Retrying %s in 30 minutes…", url)
            await asyncio.sleep(RETRY_DELAY_SECONDS)
    logger.error("Failed to fetch %s after %d attempts", url, retries)
    return None


def _is_relevant(title: str, text: str) -> bool:
    combined = (title + " " + text).lower()
    return any(kw.lower() in combined for kw in KEYWORDS)


def _parse_list_page(html: str) -> list[dict[str, str]]:
    """Return list of {title, url} dicts from the announcements list page."""
    soup = BeautifulSoup(html, "lxml")
    items: list[dict[str, str]] = []

    # bolshoi.ru uses various structures; try multiple selectors in order of specificity
    candidates: list[Any] = (
        soup.select("article.news-item")
        or soup.select("div.news-item")
        or soup.select("li.news-item")
        or soup.select("article")
        or soup.select(".news-list__item")
        or soup.select(".b-news-list__item")
    )

    for el in candidates:
        link = el.select_one("a[href]")
        heading = el.select_one("h2, h3, h4, .title, .news-title, .item-title")
        if not link:
            continue

        href: str = link.get("href", "")
        if not href:
            continue

        title = heading.get_text(strip=True) if heading else link.get_text(strip=True)
        full_url = href if href.startswith("http") else BASE_URL + href
        snippet = el.get_text(" ", strip=True)

        if _is_relevant(title, snippet):
            items.append({"title": title, "url": full_url})

    logger.info("Found %d relevant items on list page", len(items))
    return items


async def fetch_announcements(news_url: str) -> list[ExtractedEvent]:
    """Fetch and parse all relevant announcements. Returns list of ExtractedEvent."""
    events: list[ExtractedEvent] = []

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        html = await _fetch(news_url, client)
        if not html:
            return events

        items = _parse_list_page(html)
        if not items:
            logger.info("No relevant announcements found")
            return events

        for item in items:
            article_html = await _fetch(item["url"], client)
            if not article_html:
                continue
            event = extract_event(article_html, item["url"])
            if event:
                events.append(event)
            # Small polite delay between article requests
            await asyncio.sleep(1)

    return events


# ---------------------------------------------------------------------------
# Test mode
# ---------------------------------------------------------------------------

async def _run_test(news_url: str) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(f"\n=== TEST MODE — fetching {news_url} ===\n")
    events = await fetch_announcements(news_url)
    if not events:
        print("No events found.")
        return
    for i, ev in enumerate(events, 1):
        print(f"--- Event {i} ---")
        print(f"  Title       : {ev.title}")
        print(f"  URL         : {ev.source_url}")
        print(f"  Scene       : {ev.scene}")
        print(f"  Program     : {ev.program_type}")
        print(f"  Price       : {ev.ticket_price}")
        print(f"  Sale opens  : {ev.sale_opens_at}")
        print(f"  Show dates  : {json.dumps(ev.show_dates, ensure_ascii=False)}")
        print(f"  Ticket URL  : {ev.ticket_url}")
        print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Test bolshoi.ru scraper")
    ap.add_argument("--test", action="store_true", help="Run in test mode (no DB, no notifications)")
    ap.add_argument(
        "--url",
        default="https://bolshoi.ru/news/obyavleniya/",
        help="Override news list URL",
    )
    args = ap.parse_args()

    if args.test:
        asyncio.run(_run_test(args.url))
    else:
        ap.print_help()
