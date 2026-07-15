import logging
from datetime import datetime, timezone

import requests

from src.collectors.base import Collector, RawItem

DEBATES_URL = "https://hansard-api.parliament.uk/search/debates.json"
WRITTEN_QUESTIONS_URL = (
    "https://questions-statements-api.parliament.uk/api/writtenquestions/questions"
)
HANSARD_BASE = "https://hansard.parliament.uk"
QUESTIONS_BASE = "https://questions-statements.parliament.uk"
SOURCE = "parliament"

logger = logging.getLogger(__name__)


def _slugify(title: str) -> str:
    return "".join(c for c in title if c.isalnum()) or "Debate"


def _to_iso(date_str: str) -> str:
    dt = datetime.fromisoformat(date_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class ParliamentCollector(Collector):
    """Hansard debates (title-level — precise, on-topic) plus written
    questions (full Q&A text). Deliberately skips the Hansard contributions
    endpoint: it matches any speech mentioning "gambling" in passing, which
    is far noisier than debates actually about the topic."""

    def __init__(
        self, keywords: list[str], user_agent: str, results_per_term: int = 20
    ):
        self.keywords = keywords
        self.headers = {"User-Agent": user_agent}
        self.results_per_term = results_per_term

    def _fetch_debates(self, term: str) -> list[dict]:
        params = {
            "queryParameters.searchTerm": term,
            "queryParameters.take": self.results_per_term,
        }
        try:
            resp = requests.get(
                DEBATES_URL, params=params, headers=self.headers, timeout=20
            )
            resp.raise_for_status()
        except requests.RequestException:
            logger.warning(
                "Failed to query Hansard debates for term %r", term, exc_info=True
            )
            return []
        return resp.json().get("Results", [])

    def _fetch_written_questions(self, term: str) -> list[dict]:
        params = {"searchTerm": term, "take": self.results_per_term}
        try:
            resp = requests.get(
                WRITTEN_QUESTIONS_URL, params=params, headers=self.headers, timeout=20
            )
            resp.raise_for_status()
        except requests.RequestException:
            logger.warning(
                "Failed to query written questions for term %r", term, exc_info=True
            )
            return []
        return [r["value"] for r in resp.json().get("results", [])]

    def collect(self) -> list[RawItem]:
        seen_ids: set[str] = set()
        items: list[RawItem] = []

        for term in self.keywords:
            for debate in self._fetch_debates(term):
                ext_id = debate.get("DebateSectionExtId")
                if not ext_id or ext_id in seen_ids:
                    continue
                seen_ids.add(ext_id)

                title = " ".join(debate.get("Title", "Untitled debate").split())
                house = debate.get("House", "Commons")
                sitting_date = debate.get("SittingDate")
                date_part = sitting_date[:10] if sitting_date else ""

                items.append(
                    RawItem(
                        source=SOURCE,
                        source_id=ext_id,
                        source_url=(
                            f"{HANSARD_BASE}/{house}/{date_part}/debates/"
                            f"{ext_id}/{_slugify(title)}"
                        ),
                        title=title,
                        raw_summary=(
                            f"{debate.get('DebateSection', '')} debate, "
                            f"{house}: {title}"
                        ),
                        published_at=(
                            _to_iso(sitting_date)
                            if sitting_date
                            else datetime.now(timezone.utc).isoformat()
                        ),
                        signal_type="policy",
                    )
                )

            for question in self._fetch_written_questions(term):
                q_id = str(question.get("id") or "")
                if not q_id or q_id in seen_ids:
                    continue
                seen_ids.add(q_id)

                uin = question.get("uin", "")
                date_tabled = question.get("dateTabled")
                date_part = date_tabled[:10] if date_tabled else ""
                heading = question.get("heading") or question.get("questionText", "")[:100]
                question_text = question.get("questionText", "")
                answer_text = question.get("answerText") or "(not yet answered)"

                items.append(
                    RawItem(
                        source=SOURCE,
                        source_id=q_id,
                        source_url=(
                            f"{QUESTIONS_BASE}/written-questions/detail/"
                            f"{date_part}/{uin}"
                        ),
                        title=f"Written question: {heading}",
                        raw_summary=f"Q: {question_text}\nA: {answer_text}",
                        published_at=(
                            _to_iso(date_tabled)
                            if date_tabled
                            else datetime.now(timezone.utc).isoformat()
                        ),
                        signal_type="policy",
                    )
                )

        return items
