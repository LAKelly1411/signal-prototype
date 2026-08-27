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


# Shared by the cluster and theme prompts. Both were producing filing-clerk
# prose — "This cluster documents...", "...marking real corporate
# developments worth tracking" — which is both dull and, in the second case,
# telling the newsroom what to do with the story.
_HOUSE_STYLE = (
    "How to write it:\n"
    "- Open with what happened or what changed. Never open with, or refer to, "
    "the grouping itself: no 'This cluster...', 'These signals...', 'This "
    "group...', 'The signals show...'. The reader can see the signals; write "
    "about the companies and the events.\n"
    "- Be concrete and specific. Name the operator, the regulator, the sum of "
    "money, the date, the stage a process has reached. Specifics are what "
    "make it interesting; abstraction is what makes it dull.\n"
    "- Where the signals form a sequence, convey the direction of travel — "
    "what has moved, and where it has got to.\n"
    "- Plain, active, confident English. No hedging, no throat-clearing, no "
    "words like 'notable', 'significant', 'various' or 'a number of'.\n\n"
    "What never to include:\n"
    "- Never suggest a story, angle, follow-up or line of enquiry, and never "
    "say anything is 'worth tracking', 'worth watching', 'one to watch', "
    "'bears monitoring' or similar. State what is happening; the newsroom "
    "decides what to do about it.\n"
    "- Never address the reader or mention journalists, reporters, the "
    "newsroom or the audience.\n"
    "- Do not editorialise about how important something is. If it matters, "
    "the facts will carry it."
)


CLUSTER_SYSTEM_PROMPT = (
    "You are a signal-analysis assistant for a B2B gambling-industry newsroom. "
    "You are given a cluster of signals that all name the same company, "
    "collected from public, regulatory or corporate sources. Say what is "
    "happening to the company, in the voice of a well-informed trade "
    "reporter briefing a colleague.\n\n"
    + _HOUSE_STYLE
    + "\n\n"
    "Also judge the grouping itself. The signals were grouped mechanically, by "
    "shared company name, so some are genuine developing stories and others "
    "are unrelated events that happen to name the same operator. Say which "
    "this is — marking one incoherent is useful, not a failure.\n\n"
    "Return exactly this JSON shape, no prose, no markdown fences:\n"
    "{\n"
    '  "summary": "2-3 sentences, no more than 60 words",\n'
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

THEME_SYSTEM_PROMPT = (
    "You are a signal-analysis assistant for a B2B gambling-industry newsroom. "
    "You are given signals of the same kind — the same sort of event — "
    "affecting several different companies across the UK gambling sector "
    "over the past few months.\n\n"
    "This is a sector trend, not a company story. No single one of these "
    "events is necessarily worth reporting on its own; the shape of them "
    "together is the point. Say what that shape is: how widespread it is, "
    "who it is reaching, whether it is building or easing, and which "
    "individual cases stand out from the rest.\n\n"
    + _HOUSE_STYLE
    + "\n\n"
    "Return exactly this JSON shape, no prose, no markdown fences:\n"
    "{\n"
    '  "summary": "2-3 sentences on the trend, no more than 60 words",\n'
    '  "key_points": ["3 to 4 short findings, one line each, no more than 20 '
    'words each"],\n'
    '  "direction": "building|steady|easing"\n'
    "}\n\n"
    "key_points: each should carry something concrete the summary doesn't — a "
    "named company, a figure, a date, a cluster of similar cases, an outlier. "
    "Do not restate the summary in shorter words.\n"
    "direction: judge from the dates, not from the wording of any one signal."
)


def _version(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


# Tied to the prompt text so editing a prompt automatically invalidates the
# summaries cached under the old wording.
CLUSTER_SUMMARY_VERSION = _version(CLUSTER_SYSTEM_PROMPT)
THEME_SUMMARY_VERSION = _version(THEME_SYSTEM_PROMPT)


def build_client() -> anthropic.Anthropic:
    """One client per run, reused across every call. max_retries covers the
    transient 429/529s that would otherwise leave a signal unscored until the
    next scheduled run."""
    return anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"], max_retries=5
    )


# These models run adaptive thinking by default, and thinking is billed
# against max_tokens before any text is produced. A tight cap therefore
# truncates the JSON mid-string — or, when thinking uses the whole budget,
# returns no text block at all — which surfaces only as a parse failure and a
# silent retry next run. The JSON payloads here are a few hundred tokens; the
# ceiling only needs to be generous, and unused capacity costs nothing.
MAX_TOKENS = 8000


def _response_json(response, what: str) -> dict | None:
    """Parse a JSON response, distinguishing truncation from bad JSON so a
    too-low token ceiling can't hide as a mystery parse error again."""
    block = next((b for b in response.content if b.type == "text"), None)
    if block is None:
        logger.warning(
            "%s: no text block in response (stop_reason=%s, output_tokens=%s) — "
            "thinking consumed the whole token budget",
            what, response.stop_reason, response.usage.output_tokens,
        )
        return None
    try:
        return json.loads(_strip_fences(block.text))
    except json.JSONDecodeError:
        if response.stop_reason == "max_tokens":
            logger.warning(
                "%s: response truncated at the token ceiling (%s) — raise "
                "MAX_TOKENS", what, response.usage.output_tokens,
            )
        else:
            logger.warning("%s: response was not valid JSON", what, exc_info=True)
        return None


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
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        parsed = _response_json(response, f"Scoring {signal['id']}")
        if parsed is None:
            return signal

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
            max_tokens=MAX_TOKENS,
            system=CLUSTER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        parsed = _response_json(response, "Cluster summarisation")
        if not parsed:
            return None

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


def summarize_theme(
    theme: str, members: list[dict], client: anthropic.Anthropic | None = None
) -> dict | None:
    """Read a sector-wide trend: what is happening across the companies it
    touches, and whether it is building or easing.

    Different job from summarize_cluster. A cluster is one company's story; a
    theme is dozens of separate events whose only connection is being the same
    kind of thing. The reader can already see the monthly counts, so the value
    here is what the counts don't show — who is being caught up in it, and
    which cases are unlike the others.
    """
    client = client or build_client()
    model = os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-5"

    members_sorted = sorted(members, key=lambda m: m["published_at"])
    lines = [
        f"- [{m['published_at'][:10]}] {m['source']}: {m['title']} "
        f"(score {m.get('newsworthiness_score')}) — {m.get('why_it_matters') or ''}"
        for m in members_sorted
    ]
    companies = sorted(
        {e for m in members for e in (m.get("canonical_entities") or [])}
    )
    user_content = (
        f"Theme: {theme}\n"
        f"Companies involved ({len(companies)}): {', '.join(companies[:40])}\n\n"
        "Signals:\n" + "\n".join(lines)
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=THEME_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        parsed = _response_json(response, f"Theme summarisation ({theme})")
        if not parsed:
            return None

        summary = parsed.get("summary")
        if not summary:
            return None

        key_points = parsed.get("key_points") or []
        if not isinstance(key_points, list):
            key_points = []

        return {
            "summary": summary,
            "key_points": [str(p) for p in key_points if p],
            "direction": parsed.get("direction"),
        }
    except Exception:
        logger.warning("Theme summarisation failed for %s", theme, exc_info=True)
        return None
