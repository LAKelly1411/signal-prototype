import hashlib
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from src import cluster, store
from src.entities import build_alias_map
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
from src.sectors import Sector, load_sector
from src.score import (
    cluster_summary_version,
    theme_summary_version,
    build_client,
    score_signal,
    summarize_cluster,
    summarize_theme,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

RUN_STATUS_PATH = Path("data/run_status.json")


DEFAULT_USER_AGENT = "Signal-Prototype/0.1"


def _ua(settings: dict) -> str:
    return settings.get("user_agent", DEFAULT_USER_AGENT)


def _keywords(sector: Sector, settings: dict) -> list[str]:
    # A source's own keywords win; otherwise the sector's defaults.
    return list(settings.get("keywords", sector.keywords))


def _gambling_commission(sector, s):
    return GamblingCommissionCollector(listing_pages=s["listing_pages"], user_agent=_ua(s))


def _companies_house(sector, s):
    api_key = os.environ.get("COMPANIES_HOUSE_API_KEY")
    if not api_key:
        logger.warning("COMPANIES_HOUSE_API_KEY not set — skipping Companies House collector")
        return None
    return CompaniesHouseCollector(
        api_key=api_key,
        operators=sector.companies,
        items_per_page=s.get("items_per_page", 25),
        sleep_seconds=s.get("sleep_seconds", 0.6),
        lookback_days=s.get("lookback_days", 365),
        categories=s.get("categories"),
    )


def _gazette(sector, s):
    return GazetteCollector(
        search_terms=_keywords(sector, s) + [c["name"] for c in sector.companies],
        user_agent=_ua(s),
        results_per_term=s.get("results_per_term", 20),
        sleep_seconds=s.get("sleep_seconds", 1.0),
    )


def _dcms(sector, s):
    kwargs = {"organisation": s["organisation"]} if "organisation" in s else {}
    return DCMSCollector(
        keywords=_keywords(sector, s), user_agent=_ua(s),
        results_per_term=s.get("results_per_term", 20), **kwargs,
    )


def _parliament(sector, s):
    return ParliamentCollector(
        keywords=_keywords(sector, s), user_agent=_ua(s),
        results_per_term=s.get("results_per_term", 20),
    )


def _asa(sector, s):
    return ASACollector(keywords=_keywords(sector, s), user_agent=_ua(s))


def _bgc(sector, s):
    return BGCCollector(user_agent=_ua(s), pages=s.get("pages", 2))


def _insolvency_service(sector, s):
    return InsolvencyServiceCollector(
        keywords=_keywords(sector, s), user_agent=_ua(s),
        sleep_seconds=s.get("sleep_seconds", 1.0),
    )


def _lse_rns(sector, s):
    return LSERNSCollector(
        tickers=dict(s.get("tickers", sector.tickers)), user_agent=_ua(s),
        skip_titles=s.get("skip_titles"),
    )


# Build order matters: it sets the order raw items, and so new signals, arrive.
COLLECTORS = {
    "gambling_commission": _gambling_commission,
    "companies_house": _companies_house,
    "gazette": _gazette,
    "dcms": _dcms,
    "parliament": _parliament,
    "asa": _asa,
    "bgc": _bgc,
    "insolvency_service": _insolvency_service,
    "lse_rns": _lse_rns,
}


def build_collectors(sector: Sector) -> list:
    collectors = []
    for key, build in COLLECTORS.items():
        if key in sector.sources:
            collector = build(sector, sector.sources[key])
            if collector is not None:
                collectors.append(collector)
    return collectors


def write_run_status(status: dict, path: Path = RUN_STATUS_PATH) -> None:
    """Publish what the run actually did, so a silently broken scraper shows
    up in the dashboard instead of only in an Actions log nobody reads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)


def run() -> None:
    load_dotenv()
    started_at = datetime.now(timezone.utc)
    sector = load_sector("gambling")
    collectors = build_collectors(sector)
    alias_map = build_alias_map(sector.companies)
    client = build_client()

    raw_items = []
    source_status: dict[str, dict] = {}
    for collector in collectors:
        name = type(collector).__name__
        try:
            collected = collector.collect()
        except Exception:
            # One source's unexpected failure shouldn't take every other
            # source down with it — log it and move on.
            logger.exception(
                "Collector %s failed — skipping, other sources unaffected", name
            )
            source_status[name] = {"items": 0, "ok": False, "error": True}
            continue
        raw_items.extend(collected)
        # Zero items isn't an exception, but for a scraper it usually means
        # the page layout moved underneath us — flag it as unhealthy.
        source_status[name] = {
            "items": len(collected),
            "ok": bool(collected),
            "error": False,
        }
    logger.info("Collected %d raw items", len(raw_items))

    new_signals_by_id = {}
    for item in raw_items:
        signal = to_signal(item)
        new_signals_by_id[signal["id"]] = signal

    existing = store.load()
    merged, added = store.merge_new(
        existing, list(new_signals_by_id.values()), store.load_archived_ids()
    )

    unscored = [s for s in merged if s.get("newsworthiness_score") is None]
    logger.info(
        "%d new signals, %d unscored total (including retries of prior failures)",
        len(added), len(unscored),
    )

    for signal in unscored:
        score_signal(signal, client=client, alias_map=alias_map)

    cluster.assign_clusters(merged, alias_map=alias_map)
    cluster.assign_themes(merged, alias_map=alias_map)
    by_cluster = defaultdict(list)
    for s in merged:
        if s.get("cluster_id"):
            by_cluster[s["cluster_id"]].append(s)
    themes = {s["theme_id"] for s in merged if s.get("theme_id")}
    logger.info("%d clusters and %d themes formed", len(by_cluster), len(themes))

    for cluster_id, members in by_cluster.items():
        # Cache key covers both cluster membership and prompt wording, so
        # either changing invalidates it and triggers a re-summary.
        cache_key = f"{cluster_id}:{cluster_summary_version()}"
        if any(m.get("cluster_summary_for") == cache_key for m in members):
            continue
        verdict = summarize_cluster(members, client=client)
        if verdict:
            for m in members:
                m["cluster_summary"] = verdict["summary"]
                m["cluster_pattern_type"] = verdict["pattern_type"]
                m["cluster_coherent"] = verdict["coherent"]
                m["cluster_significance"] = verdict["significance"]
                m["cluster_summary_for"] = cache_key

    by_theme = defaultdict(list)
    for s in merged:
        if s.get("theme_id"):
            by_theme[s["theme_id"]].append(s)

    for theme, members in by_theme.items():
        # theme_id is stable, but membership isn't, so the cache key covers
        # who is in it as well as the prompt wording.
        members_hash = hashlib.sha256(
            "|".join(sorted(m["id"] for m in members)).encode("utf-8")
        ).hexdigest()[:12]
        cache_key = f"{theme}:{members_hash}:{theme_summary_version()}"
        if any(m.get("theme_summary_for") == cache_key for m in members):
            continue
        verdict = summarize_theme(theme, members, client=client)
        if verdict:
            for m in members:
                m["theme_summary"] = verdict["summary"]
                m["theme_key_points"] = verdict["key_points"]
                m["theme_direction"] = verdict["direction"]
                m["theme_summary_for"] = cache_key

    live = store.save(merged)
    logger.info(
        "Store now holds %d live signals (%d archived this run)",
        len(live), len(merged) - len(live),
    )

    write_run_status(
        {
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "sources": source_status,
            "healthy_sources": sum(1 for s in source_status.values() if s["ok"]),
            "total_sources": len(source_status),
            "raw_items": len(raw_items),
            "new_signals": len(added),
            "unscored": sum(
                1 for s in live if s.get("newsworthiness_score") is None
            ),
            "live_signals": len(live),
            "clusters": len(by_cluster),
        }
    )


if __name__ == "__main__":
    run()
