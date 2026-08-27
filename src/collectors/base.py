from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RawItem:
    source: str
    source_url: str
    title: str
    raw_summary: str
    published_at: str  # ISO 8601
    signal_type: str
    source_id: str | None = None
    # Set when the source gave no usable date and published_at is a "now"
    # fallback. Without this an unparseable date looks like breaking news at
    # the top of the feed.
    published_at_estimated: bool = False


class Collector(ABC):
    @abstractmethod
    def collect(self) -> list[RawItem]:
        """Fetch and return the current set of raw items from this source."""
