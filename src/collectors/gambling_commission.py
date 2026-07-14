import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.collectors.base import Collector, RawItem

BASE_URL = "https://www.gamblingcommission.gov.uk"
SOURCE = "gambling_commission"

logger = logging.getLogger(__name__)


def _parse_news_cards(soup: BeautifulSoup) -> list[tuple[str, str, str, str]]:
    """Layout used by /news: <li class="gcweb-card"> with a category tag,
    title (h2 for the featured item, else a <p role="heading">), a summary
    paragraph, and a trailing date paragraph."""
    items = []
    for li in soup.select("li.gcweb-card"):
        a = li.find("a")
        if not a or not a.get("href"):
            continue
        title_tag = li.find("h2") or li.find("p", attrs={"role": "heading"})
        title = title_tag.get_text(strip=True) if title_tag else None

        summary_tag = li.find(
            "p", class_=lambda c: bool(c) and "news-font-text" in c
        )
        summary = summary_tag.get_text(strip=True) if summary_tag else ""

        date_tag = None
        for p in li.find_all("p", class_="gc-card__description"):
            if p is title_tag:
                continue
            classes = p.get("class") or []
            if any("news-font-text" in c for c in classes):
                continue
            date_tag = p
        date_text = date_tag.get_text(strip=True) if date_tag else None

        if title and date_text:
            items.append((title, a["href"], date_text, summary))
    return items


def _parse_enforcement_cards(soup: BeautifulSoup) -> list[tuple[str, str, str, str]]:
    """Layout used by /news/enforcement-action: <li class="card"> with a
    date paragraph and an <h3> title, no separate summary."""
    items = []
    for li in soup.select("li.card"):
        a = li.find("a")
        if not a or not a.get("href"):
            continue
        title_tag = li.find("h3")
        title = title_tag.get_text(strip=True) if title_tag else None
        date_tag = li.find("p", class_="gc-card__description")
        date_text = date_tag.get_text(strip=True) if date_tag else None
        if title and date_text:
            items.append((title, a["href"], date_text, ""))
    return items


def _parse_date(date_text: str) -> str:
    try:
        dt = datetime.strptime(date_text.strip(), "%d %B %Y")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        logger.warning("Could not parse Gambling Commission date %r", date_text)
        return datetime.now(timezone.utc).isoformat()


class GamblingCommissionCollector(Collector):
    def __init__(self, listing_pages: list[dict], user_agent: str):
        self.listing_pages = listing_pages
        self.headers = {"User-Agent": user_agent}

    def _fetch(self, url: str) -> BeautifulSoup | None:
        try:
            resp = requests.get(url, headers=self.headers, timeout=20)
            resp.raise_for_status()
        except requests.RequestException:
            logger.warning("Failed to fetch %s", url, exc_info=True)
            return None
        return BeautifulSoup(resp.text, "html.parser")

    def collect(self) -> list[RawItem]:
        items: list[RawItem] = []
        for page in self.listing_pages:
            url = page["url"]
            signal_type = page["signal_type"]

            soup = self._fetch(url)
            if soup is None:
                continue

            parsed = _parse_news_cards(soup) or _parse_enforcement_cards(soup)
            if not parsed:
                logger.warning(
                    "Zero items parsed from %s — page layout may have changed", url
                )
                continue

            for title, href, date_text, summary in parsed:
                items.append(
                    RawItem(
                        source=SOURCE,
                        source_url=urljoin(BASE_URL, href),
                        title=title,
                        raw_summary=summary,
                        published_at=_parse_date(date_text),
                        signal_type=signal_type,
                    )
                )
        return items
