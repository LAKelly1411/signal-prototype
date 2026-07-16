import logging
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from src.collectors.base import Collector, RawItem

BASE_URL = "https://www.investegate.co.uk/company/"
SOURCE = "lse_rns"

logger = logging.getLogger(__name__)


def _parse_datetime(date_text: str, time_text: str) -> str:
    try:
        dt = datetime.strptime(
            f"{date_text.strip()} {time_text.strip()}", "%d %b %Y %I:%M %p"
        )
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        logger.warning("Could not parse RNS date/time %r %r", date_text, time_text)
        return datetime.now(timezone.utc).isoformat()


class LSERNSCollector(Collector):
    """Regulatory News Service (RNS) announcements for LSE-listed gambling
    operators, via Investegate's per-company announcement feed (LSE's own
    site is a JS-rendered SPA, not scrapeable with a plain HTTP GET).
    Companies House filings are backward-looking (annual accounts); this
    catches trading updates, M&A and board changes as they're announced."""

    def __init__(self, tickers: dict[str, str], user_agent: str):
        self.tickers = tickers  # {"ENT": "Entain", ...}
        self.headers = {"User-Agent": user_agent}

    def _fetch(self, ticker: str) -> BeautifulSoup | None:
        try:
            resp = requests.get(
                f"{BASE_URL}{ticker}", headers=self.headers, timeout=20
            )
            resp.raise_for_status()
        except requests.RequestException:
            logger.warning(
                "Failed to fetch Investegate page for %s", ticker, exc_info=True
            )
            return None
        return BeautifulSoup(resp.text, "html.parser")

    def collect(self) -> list[RawItem]:
        items: list[RawItem] = []
        for ticker, company_name in self.tickers.items():
            soup = self._fetch(ticker)
            if soup is None:
                continue

            rows = [r for r in soup.select("table.table-investegate tr") if r.find("td")]
            if not rows:
                logger.warning(
                    "Zero RNS announcements parsed for %s — layout may have changed",
                    ticker,
                )
                continue

            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue
                link = cells[3].find("a", class_="announcement-link")
                if not link or not link.get("href"):
                    continue

                title = link.get_text(strip=True)
                date_text = cells[0].get_text(strip=True)
                time_text = cells[1].get_text(strip=True)

                items.append(
                    RawItem(
                        source=SOURCE,
                        source_url=link["href"],
                        title=f"{company_name}: {title}",
                        raw_summary=f"RNS announcement from {company_name} ({ticker}).",
                        published_at=_parse_datetime(date_text, time_text),
                        signal_type="corporate_filing",
                    )
                )
        return items
