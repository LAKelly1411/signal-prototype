import hashlib
from datetime import datetime, timezone

from src.collectors.base import RawItem


def make_id(source: str, stable_key: str) -> str:
    return hashlib.sha256(f"{source}:{stable_key}".encode("utf-8")).hexdigest()


def to_signal(item: RawItem) -> dict:
    stable_key = item.source_id or item.source_url
    return {
        "id": make_id(item.source, stable_key),
        "source": item.source,
        "source_id": item.source_id,
        "source_url": item.source_url,
        "title": item.title,
        "raw_summary": item.raw_summary,
        "published_at": item.published_at,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "signal_type": item.signal_type,
        "entities": [],
        "newsworthiness_score": None,
        "why_it_matters": None,
        "category": None,
        "cluster_id": None,
        "status": "new",
    }
