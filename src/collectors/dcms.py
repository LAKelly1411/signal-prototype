import logging
from datetime import datetime, timezone

import requests

from src.collectors.base import Collector, RawItem

SEARCH_URL = "https://www.gov.uk/api/search.json"
ORGANISATION_SLUG = "department-for-culture-media-and-sport"
SOURCE = "dcms"

logger = logging.getLogger(__name__)


class DCMSCollector(Collector):
    def __init__(self, keywords: list[str], user_agent: str, results_per_term: int = 20):
        self.keywords = keywords
        self.headers = {"User-Agent": user_agent}
        self.results_per_term = results_per_term

    def _search(self, term: str) -> list[dict]:
        params = {
            "q": term,
            "filter_organisations": ORGANISATION_SLUG,
            "count": self.results_per_term,
            "order": "-public_timestamp",
        }
        try:
            resp = requests.get(SEARCH_URL, params=params, headers=self.headers, timeout=20)
            resp.raise_for_status()
        except requests.RequestException:
            logger.warning(
                "Failed to query GOV.UK Search API for term %r", term, exc_info=True
            )
            return []
        return resp.json().get("results", [])

    def _parse_date(self, public_timestamp: str | None) -> str:
        if not public_timestamp:
            return datetime.now(timezone.utc).isoformat()
        try:
            dt = datetime.fromisoformat(public_timestamp.replace("Z", "+00:00"))
            return dt.isoformat()
        except ValueError:
            logger.warning("Could not parse DCMS date %r", public_timestamp)
            return datetime.now(timezone.utc).isoformat()

    def collect(self) -> list[RawItem]:
        seen_links: set[str] = set()
        items: list[RawItem] = []

        for term in self.keywords:
            results = self._search(term)
            if not results:
                logger.info("No DCMS results for term %r", term)

            for result in results:
                link = result.get("link")
                if not link or link in seen_links:
                    continue
                seen_links.add(link)

                title = result.get("title") or "Untitled"
                description = result.get("description") or ""
                fmt = result.get("format", "")
                published_at = self._parse_date(result.get("public_timestamp"))

                signal_type = "consultation" if "consultation" in fmt else "policy"

                items.append(
                    RawItem(
                        source=SOURCE,
                        source_url=f"https://www.gov.uk{link}",
                        title=title,
                        raw_summary=description,
                        published_at=published_at,
                        signal_type=signal_type,
                    )
                )

        return items
