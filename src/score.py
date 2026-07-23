import hashlib
import json
import logging
import os

import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a signal-scoring assistant for a B2B gambling-industry newsroom. "
    "You are given one item from a public, regulatory or corporate source. "
    "Assess how newsworthy it is to journalists covering the UK gambling and "
    "gaming sector. You do not write articles. You return structured JSON only.\n\n"
    "Score for a specialist B2B gambling audience, not a general newsdesk. A "
    "small operator's confirmation statement can matter here even if it would "
    "never make national news. Reward items that name operators, suppliers or "
    "affiliates, involve enforcement or money, or signal a regulatory or policy "
    "shift. Extract entity names carefully; these drive a downstream pattern-"
    "detection layer.\n\n"
    "Return exactly this JSON shape, no prose, no markdown fences:\n"
    "{\n"
    '  "newsworthiness_score": 0-100,\n'
    '  "signal_type": "regulatory|enforcement|consultation|corporate_filing|insolvency|policy",\n'
    '  "entities": ["operator or company names mentioned"],\n'
    "  \"category\": \"short theme tag, e.g. 'AML enforcement', 'licence change', 'accounts filing'\",\n"
    '  "why_it_matters": "one sentence, plain English, no more than 30 words"\n'
    "}"
)


CLUSTER_SYSTEM_PROMPT = (
    "You are a signal-analysis assistant for a B2B gambling-industry newsroom. "
    "You are given a cluster of signals that all name the same company, "
    "collected from public, regulatory or corporate sources. Synthesise the "
    "pattern behind them — what is actually going on — rather than "
    "restating the individual signals.\n\n"
    "The audience is always a specialist gambling-industry newsroom, so "
    "never state that explicitly and never address the reader directly. Do "
    "not say things like 'journalists should' or 'this means for reporters' "
    "and do not instruct anyone on what to do with the information — just "
    "describe the pattern and why it is significant.\n\n"
    "Return exactly this JSON shape, no prose, no markdown fences:\n"
    "{\n"
    '  "summary": "2-3 sentences, plain English, no more than 60 words"\n'
    "}"
)

# Tied to the prompt text so editing CLUSTER_SYSTEM_PROMPT automatically
# invalidates cached cluster_summary values from the old wording.
CLUSTER_SUMMARY_VERSION = hashlib.sha256(
    CLUSTER_SYSTEM_PROMPT.encode("utf-8")
).hexdigest()[:8]


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def score_signal(signal: dict, client: anthropic.Anthropic | None = None) -> dict:
    """Enrich a signal in place with score/entities/category/why_it_matters.
    On any failure, leaves the score null and flags it rather than dropping it."""
    client = client or _client()
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

    user_content = (
        f"Title: {signal['title']}\n"
        f"Source: {signal['source']}\n"
        f"Published: {signal['published_at']}\n"
        f"Extract: {signal['raw_summary']}"
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        text_block = next(b for b in response.content if b.type == "text")
        raw = _strip_fences(text_block.text)
        parsed = json.loads(raw)

        signal["newsworthiness_score"] = int(parsed["newsworthiness_score"])
        signal["signal_type"] = parsed.get("signal_type", signal["signal_type"])
        signal["entities"] = parsed.get("entities", [])
        signal["category"] = parsed.get("category")
        signal["why_it_matters"] = parsed.get("why_it_matters")
        signal["status"] = "seen"
    except Exception:
        logger.warning("Scoring failed for signal %s", signal["id"], exc_info=True)
        # Leave status as "new" and score null so the next pipeline run retries it.

    return signal


def summarize_cluster(
    members: list[dict], client: anthropic.Anthropic | None = None
) -> str | None:
    """Synthesise what a cluster of related signals means, for the Patterns
    feed. Returns None on failure so the pipeline retries next run rather
    than caching a blank."""
    client = client or _client()
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

    members_sorted = sorted(members, key=lambda m: m["published_at"])
    lines = [
        f"- [{m['published_at'][:10]}] {m['source']}: {m['title']} "
        f"({m.get('category') or m.get('signal_type')}) — {m.get('why_it_matters', '')}"
        for m in members_sorted
    ]
    user_content = "Signals in this cluster:\n" + "\n".join(lines)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=300,
            system=CLUSTER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        text_block = next(b for b in response.content if b.type == "text")
        raw = _strip_fences(text_block.text)
        parsed = json.loads(raw)
        return parsed.get("summary")
    except Exception:
        logger.warning("Cluster summarisation failed", exc_info=True)
        return None
