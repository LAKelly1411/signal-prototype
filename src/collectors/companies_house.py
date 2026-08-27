import logging
import time
from datetime import datetime, timedelta, timezone

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
        lookback_days: int | None = 365,
        categories: list[str] | None = None,
    ):
        self.api_key = api_key
        self.operators = operators
        self.items_per_page = items_per_page
        self.sleep_seconds = sleep_seconds
        # The API returns the most recent N filings regardless of age, so
        # without a date bound the first run back-fills a decade of routine
        # accounts and confirmation statements — each one paying for a scoring
        # call and padding out the company's cluster with nothing to report.
        self.lookback_days = lookback_days
        self.categories = {c.lower() for c in categories} if categories else None

    def _wanted(self, filing: dict, cutoff: datetime | None) -> bool:
        if self.categories and filing.get("category", "").lower() not in self.categories:
            return False
        if cutoff is None:
            return True
        date = filing.get("date")
        if not date:
            # No date to judge it by — keep it and let scoring decide.
            return True
        try:
            filed = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            logger.warning("Could not parse Companies House filing date %r", date)
            return True
        return filed >= cutoff

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
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
            if self.lookback_days
            else None
        )

        for operator in self.operators:
            company_number = operator.get("company_number")
            name = operator["name"]

            if not company_number:
                logger.info(
                    "Skipping %s — no company_number resolved yet", name
                )
                continue

            filings = self._fetch_filings(company_number)
            if not filings:
                logger.info("No filings returned for %s (%s)", name, company_number)

            for filing in filings:
                if not self._wanted(filing, cutoff):
                    continue

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
                        published_at_estimated=not date,
                        signal_type="corporate_filing",
                    )
                )

            time.sleep(self.sleep_seconds)

        return items
