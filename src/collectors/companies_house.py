import logging
import time
from datetime import datetime, timezone

import requests

from src.collectors.base import Collector, RawItem

API_BASE = "https://api.company-information.service.gov.uk"
PUBLIC_BASE = "https://find-and-update.company-information.service.gov.uk"
SOURCE = "companies_house"

logger = logging.getLogger(__name__)


def _humanise(text: str) -> str:
    return text.replace("-", " ").replace("_", " ").strip().capitalize()


class CompaniesHouseCollector(Collector):
    def __init__(
        self,
        api_key: str,
        operators: list[dict],
        items_per_page: int = 25,
        sleep_seconds: float = 0.6,
    ):
        self.api_key = api_key
        self.operators = operators
        self.items_per_page = items_per_page
        self.sleep_seconds = sleep_seconds

    def _fetch_filings(self, company_number: str) -> list[dict]:
        url = f"{API_BASE}/company/{company_number}/filing-history"
        try:
            resp = requests.get(
                url,
                auth=(self.api_key, ""),
                params={"items_per_page": self.items_per_page},
                timeout=20,
            )
            resp.raise_for_status()
        except requests.RequestException:
            logger.warning(
                "Failed to fetch filing history for %s", company_number, exc_info=True
            )
            return []
        return resp.json().get("items", [])

    def collect(self) -> list[RawItem]:
        items: list[RawItem] = []

        for operator in self.operators:
            company_number = operator["company_number"]
            name = operator["name"]

            filings = self._fetch_filings(company_number)
            if not filings:
                logger.info("No filings returned for %s (%s)", name, company_number)

            for filing in filings:
                transaction_id = filing.get("transaction_id")
                category = filing.get("category", "")
                filing_type = filing.get("type", "")
                date = filing.get("date")
                description = filing.get("description", "")

                label = _humanise(category) or _humanise(description) or "Filing"
                title = f"{name}: {label} filed"

                summary_parts = [
                    f"Type: {filing_type}" if filing_type else None,
                    f"Description: {_humanise(description)}" if description else None,
                ]
                raw_summary = " · ".join(p for p in summary_parts if p)

                published_at = (
                    f"{date}T00:00:00+00:00"
                    if date
                    else datetime.now(timezone.utc).isoformat()
                )

                if transaction_id:
                    source_url = (
                        f"{PUBLIC_BASE}/company/{company_number}"
                        f"/filing-history/{transaction_id}/document?format=pdf&download=0"
                    )
                else:
                    source_url = f"{PUBLIC_BASE}/company/{company_number}/filing-history"

                items.append(
                    RawItem(
                        source=SOURCE,
                        source_id=transaction_id,
                        source_url=source_url,
                        title=title,
                        raw_summary=raw_summary,
                        published_at=published_at,
                        signal_type="corporate_filing",
                    )
                )

            time.sleep(self.sleep_seconds)

        return items
