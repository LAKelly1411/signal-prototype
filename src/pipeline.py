import hashlib
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml
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
from src.score import (
    CLUSTER_SUMMARY_VERSION,
    THEME_SUMMARY_VERSION,
    build_client,
    score_signal,
    summarize_cluster,
    summarize_theme,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

RUN_STATUS_PATH = Path("data/run_status.json")


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
                    lookback_days=ch_config.get("lookback_days", 365),
                    categories=ch_config.get("categories"),
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
                skip_titles=lse_config.get("skip_titles"),
            )
        )

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
    sources = load_sources()
    collectors = build_collectors(sources)
    alias_map = build_alias_map(load_watchlist())
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
        cache_key = f"{cluster_id}:{CLUSTER_SUMMARY_VERSION}"
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
        cache_key = f"{theme}:{members_hash}:{THEME_SUMMARY_VERSION}"
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
