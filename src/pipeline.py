import logging
import os

import yaml
from dotenv import load_dotenv

from src import store
from src.collectors.companies_house import CompaniesHouseCollector
from src.collectors.gambling_commission import GamblingCommissionCollector
from src.normalise import to_signal
from src.score import score_signal

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def load_sources(path: str = "config/sources.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_watchlist(path: str = "config/watchlist.yaml") -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("operators", [])


def build_collectors(sources: dict) -> list:
    collectors = []

    gc_config = sources.get("gambling_commission", {})
    if gc_config.get("enabled"):
        collectors.append(
            GamblingCommissionCollector(
                listing_pages=gc_config["listing_pages"],
                user_agent=gc_config["user_agent"],
            )
        )

    ch_config = sources.get("companies_house", {})
    if ch_config.get("enabled"):
        api_key = os.environ.get("COMPANIES_HOUSE_API_KEY")
        if not api_key:
            logger.warning(
                "COMPANIES_HOUSE_API_KEY not set — skipping Companies House collector"
            )
        else:
            collectors.append(
                CompaniesHouseCollector(
                    api_key=api_key,
                    operators=load_watchlist(),
                    items_per_page=ch_config.get("items_per_page", 25),
                    sleep_seconds=ch_config.get("sleep_seconds", 0.6),
                )
            )

    return collectors


def run() -> None:
    load_dotenv()
    sources = load_sources()
    collectors = build_collectors(sources)

    raw_items = []
    for collector in collectors:
        raw_items.extend(collector.collect())
    logger.info("Collected %d raw items", len(raw_items))

    new_signals_by_id = {}
    for item in raw_items:
        signal = to_signal(item)
        new_signals_by_id[signal["id"]] = signal

    existing = store.load()
    merged, added = store.merge_new(existing, list(new_signals_by_id.values()))

    unscored = [s for s in merged if s.get("newsworthiness_score") is None]
    logger.info(
        "%d new signals, %d unscored total (including retries of prior failures)",
        len(added), len(unscored),
    )

    for signal in unscored:
        score_signal(signal)

    store.save(merged)
    logger.info("Store now holds %d signals total", len(merged))


if __name__ == "__main__":
    run()
