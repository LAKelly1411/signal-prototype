import logging
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from src.collectors.base import Collector, RawItem

RULINGS_URL = "https://www.asa.org.uk/codes-and-rulings/rulings.html"
SOURCE = "asa"

_DATE_RE = re.compile(r"^\d{1,2} [A-Za-z]+ \d{4}$")

logger = logging.getLogger(__name__)


def _parse_date(date_text: str) -> str:
    try:
        dt = datetime.strptime(date_text, "%d %B %Y")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        logger.warning("Could not parse ASA ruling date %r", date_text)
        return datetime.now(timezone.utc).isoformat()


class ASACollector(Collector):
    """ASA rulings, filtered by keyword via the rulings page's own search
    (not the site-wide search, which matches "gamble" inside unrelated
    words like Procter & Gamble)."""

    def __init__(self, keywords: list[str], user_agent: str):
        self.keywords = keywords
        self.headers = {"User-Agent": user_agent}

    def _search(self, term: str) -> BeautifulSoup | None:
        params = {"q": term, "sort_order": "recent"}
        try:
            resp = requests.get(
                RULINGS_URL, params=params, headers=self.headers, timeout=20
            )
            resp.raise_for_status()
        except requests.RequestException:
            logger.warning("Failed to query ASA rulings for term %r", term, exc_info=True)
            return None
        return BeautifulSoup(resp.text, "html.parser")

    def collect(self) -> list[RawItem]:
        seen_urls: set[str] = set()
        items: list[RawItem] = []

        for term in self.keywords:
            soup = self._search(term)
            if soup is None:
                continue

            cards = soup.select("li.icon-listing-item")
            if not cards:
                logger.warning(
                    "Zero ASA rulings parsed for term %r — page layout may have changed",
                    term,
                )
                continue

            for card in cards:
                link = card.select_one("h4.heading a")
                if not link or not link.get("href"):
                    continue
                url = link["href"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                title = link.get_text(strip=True)
                captions = [
                    s.get_text(strip=True)
                    for s in card.select("ul.meta-listing span.caption")
                ]
                date_text = next((c for c in captions if _DATE_RE.match(c)), None)
                other_captions = [c for c in captions if c != date_text]

                summary_tag = card.find("p")
                summary = summary_tag.get_text(strip=True) if summary_tag else ""
                if other_captions:
                    summary = f"{' / '.join(other_captions)}: {summary}"

                items.append(
                    RawItem(
                        source=SOURCE,
                        source_url=url,
                        title=title,
                        raw_summary=summary,
                        published_at=(
                            _parse_date(date_text)
                            if date_text
                            else datetime.now(timezone.utc).isoformat()
                        ),
                        signal_type="enforcement",
                    )
                )

        return items
