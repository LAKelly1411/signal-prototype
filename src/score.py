import hashlib
import json
import logging
import os

import anthropic

from src.categories import TAXONOMY, canonical_category
from src.entities import canonicalise

logger = logging.getLogger(__name__)

_CATEGORY_LIST = "\n".join(f"  - {c}" for c in TAXONOMY)

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
    "The category must be exactly one of these, copied verbatim. Free-text "
    "themes fragment the cross-company pattern detection downstream, so pick "
    "the closest match rather than inventing a better label. Use 'Other' only "
    "when genuinely none applies:\n"
    f"{_CATEGORY_LIST}\n\n"
    "Return exactly this JSON shape, no prose, no markdown fences:\n"
    "{\n"
    '  "newsworthiness_score": 0-100,\n'
    '  "signal_type": "regulatory|enforcement|consultation|corporate_filing|insolvency|policy",\n'
    '  "entities": ["operator or company names mentioned"],\n'
    '  "category": "one value copied verbatim from the list above",\n'
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
    "Also judge the cluster itself. The signals were grouped mechanically, by "
    "shared company name, so some clusters are genuine developing stories and "
    "others are unrelated events that happen to name the same operator. Say "
    "which this is — marking a cluster incoherent is useful, not a failure.\n\n"
    "Return exactly this JSON shape, no prose, no markdown fences:\n"
    "{\n"
    '  "summary": "2-3 sentences, plain English, no more than 60 words",\n'
    '  "pattern_type": "escalation|wave|developing_story|routine|unrelated",\n'
    '  "coherent": true or false,\n'
    '  "significance": 0-100\n'
    "}\n\n"
    "pattern_type: 'escalation' where the signals show a situation worsening "
    "step by step; 'wave' where similar things are happening to several "
    "companies; 'developing_story' for one story unfolding across sources; "
    "'routine' for ordinary recurring filings with no story in them; "
    "'unrelated' where the signals have no real connection.\n"
    "coherent: false when the grouping is an artefact of a shared name rather "
    "than a real link.\n"
    "significance: how much a specialist gambling newsroom should care, "
    "independent of how many signals happen to be in the cluster."
)

# Tied to the prompt text so editing CLUSTER_SYSTEM_PROMPT automatically
# invalidates cached cluster_summary values from the old wording.
CLUSTER_SUMMARY_VERSION = hashlib.sha256(
    CLUSTER_SYSTEM_PROMPT.encode("utf-8")
).hexdigest()[:8]


def build_client() -> anthropic.Anthropic:
    """One client per run, reused across every call. max_retries covers the
    transient 429/529s that would otherwise leave a signal unscored until the
    next scheduled run."""
    return anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"], max_retries=5
    )


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def score_signal(
    signal: dict,
    client: anthropic.Anthropic | None = None,
    alias_map: dict[str, str] | None = None,
) -> dict:
    """Enrich a signal in place with score/entities/category/why_it_matters.
    On any failure, leaves the score null and flags it rather than dropping it."""
    client = client or build_client()
    # `or`, not a get() default: CI sets this from a repo variable, and an
    # undefined variable arrives as an empty string, which a default would
    # happily pass through to the API as the model name.
    model = os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-5"

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
        # Raw extraction stays as-is so it remains auditable; clustering and
        # the dashboard's company filter work off the canonical form.
        signal["canonical_entities"] = canonicalise(signal["entities"], alias_map)
        signal["category"] = parsed.get("category")
        # Belt and braces: the prompt constrains this, but a near-miss like
        # "AML enforcement" would silently split a theme, so map it anyway.
        signal["canonical_category"] = canonical_category(
            signal["category"], signal["title"], signal.get("signal_type")
        )
        signal["why_it_matters"] = parsed.get("why_it_matters")
        signal["status"] = "seen"
    except Exception:
        logger.warning("Scoring failed for signal %s", signal["id"], exc_info=True)
        # Leave status as "new" and score null so the next pipeline run retries it.

    return signal


def summarize_cluster(
    members: list[dict], client: anthropic.Anthropic | None = None
) -> dict | None:
    """Synthesise what a cluster of related signals means, and judge whether
    it's a real pattern at all. Returns None on failure so the pipeline
    retries next run rather than caching a blank.

    The judgement matters as much as the prose: clusters are formed
    mechanically on a shared company name, so some are genuine developing
    stories and some are coincidence. Only the model can tell them apart, and
    it is already being asked to read every member.
    """
    client = client or build_client()
    # `or`, not a get() default: CI sets this from a repo variable, and an
    # undefined variable arrives as an empty string, which a default would
    # happily pass through to the API as the model name.
    model = os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-5"

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
            max_tokens=500,
            system=CLUSTER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        text_block = next(b for b in response.content if b.type == "text")
        raw = _strip_fences(text_block.text)
        parsed = json.loads(raw)

        summary = parsed.get("summary")
        if not summary:
            return None

        significance = parsed.get("significance")
        return {
            "summary": summary,
            "pattern_type": parsed.get("pattern_type"),
            # Default to coherent: a missing field shouldn't silently hide a
            # cluster the model never actually rejected.
            "coherent": parsed.get("coherent", True) is not False,
            "significance": (
                max(0, min(100, int(significance)))
                if isinstance(significance, (int, float))
                else None
            ),
        }
    except Exception:
        logger.warning("Cluster summarisation failed", exc_info=True)
        return None
