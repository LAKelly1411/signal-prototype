import logging
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from src.collectors.base import Collector, RawItem

BASE_URL = "https://bettingandgamingcouncil.com/news/"
SOURCE = "bgc"

logger = logging.getLogger(__name__)


def _parse_date(date_text: str) -> str:
    try:
        dt = datetime.strptime(date_text.strip(), "%d %B %Y")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        logger.warning("Could not parse BGC news date %r", date_text)
        return datetime.now(timezone.utc).isoformat()


class BGCCollector(Collector):
    """Betting and Gaming Council press releases and policy commentary —
    the trade body's own line, often published ahead of or alongside the
    regulatory story itself."""

    def __init__(self, user_agent: str, pages: int = 2):
        self.headers = {"User-Agent": user_agent}
        self.pages = pages

    def _fetch_page(self, page_num: int) -> BeautifulSoup | None:
        url = BASE_URL if page_num == 1 else f"{BASE_URL}p{page_num}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=20)
            resp.raise_for_status()
        except requests.RequestException:
            logger.warning("Failed to fetch %s", url, exc_info=True)
            return None
        return BeautifulSoup(resp.text, "html.parser")

    def collect(self) -> list[RawItem]:
        items: list[RawItem] = []
        for page_num in range(1, self.pages + 1):
            soup = self._fetch_page(page_num)
            if soup is None:
                continue

            cards = soup.select("div.card-tile")
            if not cards:
                logger.warning(
                    "Zero BGC news items parsed from page %d — layout may have changed",
                    page_num,
                )
                continue

            for card in cards:
                title_tag = card.select_one("h4 a")
                if not title_tag or not title_tag.get("href"):
                    continue
                date_tag = card.select_one("small.date")
                summary_tag = card.select_one("div.summary")

                items.append(
                    RawItem(
                        source=SOURCE,
                        source_url=title_tag["href"],
                        title=title_tag.get_text(strip=True),
                        raw_summary=(
                            summary_tag.get_text(strip=True) if summary_tag else ""
                        ),
                        published_at=(
                            _parse_date(date_tag.get_text(strip=True))
                            if date_tag
                            else datetime.now(timezone.utc).isoformat()
                        ),
                        signal_type="policy",
                    )
                )
        return items
