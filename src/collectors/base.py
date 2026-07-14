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


class Collector(ABC):
    @abstractmethod
    def collect(self) -> list[RawItem]:
        """Fetch and return the current set of raw items from this source."""
