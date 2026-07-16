import logging
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup, Tag

from src.collectors.base import Collector, RawItem

BASE_URL = "https://www.insolvencydirect.bis.gov.uk/IESdatabase"
LISTING_URL = f"{BASE_URL}/viewdirectorsummary-new-sub.asp?surname="
SOURCE = "insolvency_service"

logger = logging.getLogger(__name__)


def _text_after(tag: Tag) -> str:
    sibling = tag.next_sibling
    return sibling.strip().replace("\xa0", " ") if isinstance(sibling, str) else ""


def _parse_date(date_text: str, fmt: str) -> str:
    try:
        dt = datetime.strptime(date_text.strip(), fmt)
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        logger.warning("Could not parse Insolvency Service date %r", date_text)
        return datetime.now(timezone.utc).isoformat()


class InsolvencyServiceCollector(Collector):
    """Director disqualification register. It's a weekly-published, rolling
    3-month list covering every industry with no server-side search or
    per-record HTML wrapper — just five <b> label/value pairs in a row for
    each entry — so this fetches the whole listing and filters client-side
    by company name keyword. Complements the Gazette's insolvency notices
    with the director-level accountability angle: who was banned, and why."""

    def __init__(self, keywords: list[str], user_agent: str, sleep_seconds: float = 1.0):
        self.keywords = [k.lower() for k in keywords]
        self.headers = {"User-Agent": user_agent}
        self.sleep_seconds = sleep_seconds

    def _fetch(self, url: str) -> BeautifulSoup | None:
        try:
            resp = requests.get(url, headers=self.headers, timeout=20)
            resp.raise_for_status()
        except requests.RequestException:
            logger.warning("Failed to fetch %s", url, exc_info=True)
            return None
        resp.encoding = "windows-1252"
        return BeautifulSoup(resp.text, "html.parser")

    def _is_relevant(self, company_name: str) -> bool:
        name = company_name.lower()
        return any(k in name for k in self.keywords)

    def _fetch_conduct(self, detail_url: str) -> tuple[str, str]:
        soup = self._fetch(detail_url)
        if soup is None:
            return "", ""
        fields = {b.get_text(strip=True).rstrip(":"): _text_after(b) for b in soup.find_all("b")}
        return fields.get("Conduct", ""), fields.get("Date Order Starts", "")

    def collect(self) -> list[RawItem]:
        soup = self._fetch(LISTING_URL)
        if soup is None:
            return []

        all_labels = soup.find_all("b")
        if not all_labels or len(all_labels) % 5 != 0:
            logger.warning(
                "Insolvency Service listing tag count not a multiple of 5 (%d) "
                "— page layout may have changed",
                len(all_labels),
            )
            return []

        items: list[RawItem] = []
        for i in range(0, len(all_labels), 5):
            name_tag, company_tag, length_tag, details_tag, submitted_tag = all_labels[i:i + 5]

            company_name = _text_after(company_tag)
            if not self._is_relevant(company_name):
                continue

            name = _text_after(name_tag)
            length = _text_after(length_tag)
            date_submitted = _text_after(submitted_tag)
            link = details_tag.find_next("a")
            detail_href = link["href"] if link and link.get("href") else None

            conduct, date_order_starts = "", ""
            if detail_href:
                conduct, date_order_starts = self._fetch_conduct(f"{BASE_URL}/{detail_href}")
                time.sleep(self.sleep_seconds)

            summary = f"Disqualified for {length}." + (f" {conduct}" if conduct else "")
            date_text, fmt = (
                (date_order_starts, "%d / %m / %Y")
                if date_order_starts
                else (date_submitted, "%d-%m-%Y")
            )

            items.append(
                RawItem(
                    source=SOURCE,
                    source_id=detail_href,
                    source_url=f"{BASE_URL}/{detail_href}" if detail_href else LISTING_URL,
                    title=f"{name} disqualified as director — {company_name}",
                    raw_summary=summary,
                    published_at=(
                        _parse_date(date_text, fmt)
                        if date_text
                        else datetime.now(timezone.utc).isoformat()
                    ),
                    signal_type="insolvency",
                )
            )

        return items
