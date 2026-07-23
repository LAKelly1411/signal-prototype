import logging
import os
from collections import defaultdict

import yaml
from dotenv import load_dotenv

from src import cluster, store
from src.collectors.asa import ASACollector
from src.collectors.bgc import BGCCollector
from src.collectors.companies_house import CompaniesHouseCollector
from src.collectors.dcms import DCMSCollector
from src.collectors.gambling_commission import GamblingCommissionCollector
from src.collectors.gazette import GazetteCollector
from src.collectors.insolvency_service import InsolvencyServiceCollector
from src.collectors.lse_rns import LSERNSCollector
from src.collectors.parliament import ParliamentCollector
from src.normalise import to_signal
from src.score import score_signal, summarize_cluster

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def load_sources(path: str = "config/sources.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_operators_file(path: str) -> list[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        return []
    return (data or {}).get("operators", []) or []


def load_watchlist(
    seed_path: str = "config/watchlist.yaml",
    user_path: str = "config/user_watchlist.yaml",
) -> list[dict]:
    """Curated seed list, plus any self-service additions from the
    dashboard. The user file may not exist yet — that's fine, not an error."""
    return _load_operators_file(seed_path) + _load_operators_file(user_path)


def build_collectors(sources: dict) -> list:
    collectors = []
    watchlist = load_watchlist()

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
                    operators=watchlist,
                    items_per_page=ch_config.get("items_per_page", 25),
                    sleep_seconds=ch_config.get("sleep_seconds", 0.6),
                )
            )

    gz_config = sources.get("gazette", {})
    if gz_config.get("enabled"):
        watchlist_names = [op["name"] for op in watchlist]
        collectors.append(
            GazetteCollector(
                search_terms=gz_config.get("keywords", []) + watchlist_names,
                user_agent=gz_config["user_agent"],
                results_per_term=gz_config.get("results_per_term", 20),
                sleep_seconds=gz_config.get("sleep_seconds", 1.0),
            )
        )

    dcms_config = sources.get("dcms", {})
    if dcms_config.get("enabled"):
        collectors.append(
            DCMSCollector(
                keywords=dcms_config.get("keywords", []),
                user_agent=dcms_config["user_agent"],
                results_per_term=dcms_config.get("results_per_term", 20),
            )
        )

    parliament_config = sources.get("parliament", {})
    if parliament_config.get("enabled"):
        collectors.append(
            ParliamentCollector(
                keywords=parliament_config.get("keywords", []),
                user_agent=parliament_config["user_agent"],
                results_per_term=parliament_config.get("results_per_term", 20),
            )
        )

    asa_config = sources.get("asa", {})
    if asa_config.get("enabled"):
        collectors.append(
            ASACollector(
                keywords=asa_config.get("keywords", []),
                user_agent=asa_config["user_agent"],
            )
        )

    bgc_config = sources.get("bgc", {})
    if bgc_config.get("enabled"):
        collectors.append(
            BGCCollector(
                user_agent=bgc_config["user_agent"],
                pages=bgc_config.get("pages", 2),
            )
        )

    insolvency_config = sources.get("insolvency_service", {})
    if insolvency_config.get("enabled"):
        collectors.append(
            InsolvencyServiceCollector(
                keywords=insolvency_config.get("keywords", []),
                user_agent=insolvency_config["user_agent"],
                sleep_seconds=insolvency_config.get("sleep_seconds", 1.0),
            )
        )

    lse_config = sources.get("lse_rns", {})
    if lse_config.get("enabled"):
        collectors.append(
            LSERNSCollector(
                tickers=lse_config.get("tickers", {}),
                user_agent=lse_config["user_agent"],
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

    cluster.assign_clusters(merged)
    by_cluster = defaultdict(list)
    for s in merged:
        if s.get("cluster_id"):
            by_cluster[s["cluster_id"]].append(s)
    logger.info("%d clusters formed", len(by_cluster))

    for cluster_id, members in by_cluster.items():
        # Content-addressed cluster_id means membership changes invalidate the
        # cache automatically; skip re-summarising (and re-billing) otherwise.
        if any(m.get("cluster_summary_for") == cluster_id for m in members):
            continue
        summary = summarize_cluster(members)
        if summary:
            for m in members:
                m["cluster_summary"] = summary
                m["cluster_summary_for"] = cluster_id

    store.save(merged)
    logger.info("Store now holds %d signals total", len(merged))


if __name__ == "__main__":
    run()
