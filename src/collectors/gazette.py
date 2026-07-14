import logging
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from src.collectors.base import Collector, RawItem

BASE_URL = "https://www.thegazette.co.uk/all-notices/notice/data.json"
CORPORATE_INSOLVENCY_CATEGORY = "24"  # confirmed against TheGazette/DevDocs notice-taxonomy.md
SOURCE = "gazette"

logger = logging.getLogger(__name__)


def _strip_html(content: str) -> str:
    return BeautifulSoup(content, "html.parser").get_text(" ", strip=True)


class GazetteCollector(Collector):
    def __init__(
        self,
        search_terms: list[str],
        user_agent: str,
        results_per_term: int = 20,
        sleep_seconds: float = 1.0,
    ):
        self.search_terms = search_terms
        self.headers = {"User-Agent": user_agent}
        self.results_per_term = results_per_term
        self.sleep_seconds = sleep_seconds

    def _search(self, term: str) -> list[dict]:
        params = {
            "categorycode": CORPORATE_INSOLVENCY_CATEGORY,
            "text": term,
            "results-page-size": self.results_per_term,
            "sort-by": "latest-date",
        }
        try:
            resp = requests.get(BASE_URL, params=params, headers=self.headers, timeout=20)
            resp.raise_for_status()
        except requests.RequestException:
            logger.warning("Failed to query Gazette for term %r", term, exc_info=True)
            return []
        return resp.json().get("entry", [])

    def collect(self) -> list[RawItem]:
        seen_ids: set[str] = set()
        items: list[RawItem] = []

        for term in self.search_terms:
            entries = self._search(term)
            if not entries:
                logger.info("No Gazette results for term %r", term)

            for entry in entries:
                notice_id = entry["id"].rsplit("/", 1)[-1]
                if notice_id in seen_ids:
                    continue
                seen_ids.add(notice_id)

                title = entry.get("title") or "Untitled notice"
                category_term = entry.get("category", {}).get("@term", "")
                content = _strip_html(entry.get("content", ""))
                published = entry.get("published")

                published_at = (
                    datetime.fromisoformat(published)
                    .replace(tzinfo=timezone.utc)
                    .isoformat()
                    if published
                    else datetime.now(timezone.utc).isoformat()
                )

                raw_summary = f"{category_term}: {content}" if category_term else content

                items.append(
                    RawItem(
                        source=SOURCE,
                        source_id=notice_id,
                        source_url=f"https://www.thegazette.co.uk/notice/{notice_id}",
                        title=title,
                        raw_summary=raw_summary,
                        published_at=published_at,
                        signal_type="insolvency",
                    )
                )

            time.sleep(self.sleep_seconds)

        return items
