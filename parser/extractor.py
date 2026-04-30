"""
Extract structured event data from a bolshoi.ru announcement page.

The site renders HTML server-side; selectors are based on observed structure.
If the site layout changes, only this file needs updating.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup, Tag
from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)

MONTH_RU = {
    "января": "01", "февраля": "02", "марта": "03", "апреля": "04",
    "мая": "05", "июня": "06", "июля": "07", "августа": "08",
    "сентября": "09", "октября": "10", "ноября": "11", "декабря": "12",
}

PROGRAM_KEYWORDS = {
    "Доступный Большой": "Доступный Большой",
    "Места низкой ценовой категории": "Места низкой ценовой категории",
    "60 плюс": "60 плюс",
    "Молодёжный": "Молодёжный",
    "специальные программы": "специальные программы",
}

SCENE_KEYWORDS = {
    "историческая": "Историческая сцена",
    "историческом": "Историческая сцена",
    "новая": "Новая сцена",
    "новом": "Новая сцена",
    "бетховенский": "Бетховенский зал",
}


@dataclass
class ExtractedEvent:
    title: str
    source_url: str
    scene: str | None = None
    show_dates: list[str] = field(default_factory=list)
    program_type: str | None = None
    ticket_price: str | None = None
    sale_opens_at: datetime | None = None
    ticket_url: str | None = None


def _normalise_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _extract_program_type(text: str) -> str | None:
    for kw, label in PROGRAM_KEYWORDS.items():
        if kw.lower() in text.lower():
            return label
    return None


def _extract_scene(text: str) -> str | None:
    lower = text.lower()
    for kw, label in SCENE_KEYWORDS.items():
        if kw in lower:
            return label
    return None


def _parse_russian_date(text: str) -> datetime | None:
    """Parse dates like '14 апреля 2026 в 20:00' or '14.04.2026 в 20:00'."""
    # Replace Russian month names with numbers
    for ru, num in MONTH_RU.items():
        text = re.sub(ru, num, text, flags=re.IGNORECASE)

    # Try to find date + time patterns
    patterns = [
        r"(\d{1,2})[.\s](\d{1,2})[.\s](\d{4})\s*(?:в|at)?\s*(\d{1,2}):(\d{2})",
        r"(\d{1,2})[.\s](\d{1,2})[.\s](\d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            groups = m.groups()
            try:
                if len(groups) == 5:
                    day, month, year, hour, minute = groups
                    dt = datetime(int(year), int(month), int(day), int(hour), int(minute))
                else:
                    day, month, year = groups
                    dt = datetime(int(year), int(month), int(day), 20, 0)
                return dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

    # Fallback: let dateutil try
    try:
        return dateutil_parser.parse(text, dayfirst=True).replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _extract_sale_date(text: str) -> datetime | None:
    """Find the sale opening datetime from announcement body text."""
    patterns = [
        r"(?:продажа|продаж[аи])\s+(?:открывается|открывается|начнётся|стартует)[^\d]*(\d[\d\s.апреляфевралямартаапрелямаяиюняиюляавгустасентябряоктябряноябрядекабряи:]+)",
        r"(?:с\s+)?(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4})[^\d]*(?:в\s+)?(\d{1,2}[:.]\d{2})",
        r"(\d{1,2}[./]\d{1,2}[./]\d{2,4})[^\d]*(?:в\s+)?(\d{1,2}[:.]\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            candidate = " ".join(g for g in m.groups() if g)
            dt = _parse_russian_date(candidate)
            if dt:
                return dt
    return None


def _extract_price(text: str) -> str | None:
    m = re.search(r"(\d[\d\s]*)\s*(?:руб|₽|рублей)", text, flags=re.IGNORECASE)
    if m:
        price = re.sub(r"\s+", "", m.group(1))
        return f"от {price}"
    return None


def _extract_ticket_url(soup: BeautifulSoup, base_url: str = "https://bolshoi.ru") -> str | None:
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        text = a.get_text(strip=True).lower()
        if any(kw in text for kw in ("купить", "билет", "приобрести", "заказать")):
            return href if href.startswith("http") else base_url + href
    return None


def _extract_show_dates(text: str) -> list[str]:
    """Extract individual show date strings from announcement text."""
    dates: list[str] = []
    # Pattern: "14 апреля в 19:00", "15 апреля (воскресенье) в 18:00" etc.
    pattern = r"\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)(?:\s+\d{4})?(?:\s*\([^)]+\))?(?:\s+в\s+\d{1,2}[:.]\d{2})?"
    for m in re.finditer(pattern, text, flags=re.IGNORECASE):
        dates.append(_normalise_spaces(m.group(0)))
    return dates


def extract_event(html: str, source_url: str) -> ExtractedEvent | None:
    soup = BeautifulSoup(html, "lxml")

    # --- Title ---
    title_el = (
        soup.select_one("h1.article-title")
        or soup.select_one("h1.news-title")
        or soup.select_one("h1")
    )
    if not title_el:
        logger.warning("No title found in %s", source_url)
        return None
    title = _normalise_spaces(title_el.get_text())

    # --- Body text ---
    body_el = (
        soup.select_one("div.article-body")
        or soup.select_one("div.news-body")
        or soup.select_one("div.content")
        or soup.select_one("main")
    )
    body_text = _normalise_spaces(body_el.get_text(" ")) if body_el else ""

    full_text = f"{title} {body_text}"

    return ExtractedEvent(
        title=title,
        source_url=source_url,
        scene=_extract_scene(full_text),
        show_dates=_extract_show_dates(body_text),
        program_type=_extract_program_type(full_text),
        ticket_price=_extract_price(body_text),
        sale_opens_at=_extract_sale_date(body_text),
        ticket_url=_extract_ticket_url(soup),
    )


def event_to_dict(event: ExtractedEvent) -> dict[str, Any]:
    return {
        "title": event.title,
        "source_url": event.source_url,
        "scene": event.scene,
        "show_dates": event.show_dates,
        "program_type": event.program_type,
        "ticket_price": event.ticket_price,
        "sale_opens_at": event.sale_opens_at,
        "ticket_url": event.ticket_url,
        "notified_advance": False,
        "notified_today": False,
    }
