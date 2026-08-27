"""Entity canonicalisation.

Claude extracts entity names as they appear in the source text, so the same
company arrives under several spellings — "Entain", "Entain Holdings (UK)
Limited", "William Hill Organization Ltd". Clustering matches entities exactly,
so those never join and the pattern layer stays quiet. This module collapses
the variants down to one canonical name per company.

Two mechanisms, in order:

1. The watchlist. `config/watchlist.yaml` already carries an `aliases` list per
   operator ("bwin", "partypoker", "Gala" → Entain); that is editorial
   knowledge no amount of string manipulation would recover.
2. A legal-suffix stripper for everything off the watchlist, so the long tail
   of operators nobody has curated yet still collapses sensibly.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Trailing tokens that mark a legal entity rather than the company a journalist
# means. Deliberately conservative: only tokens that are near-meaningless on
# their own, so "Betfair Casino Limited" stays distinct from "Betfair Limited"
# while "William Hill Organization Ltd" collapses into "William Hill".
LEGAL_SUFFIXES = {
    "limited",
    "ltd",
    "ltd.",
    "plc",
    "plc.",
    "llp",
    "llc",
    "inc",
    "inc.",
    "incorporated",
    "corporation",
    "corp",
    "corp.",
    "company",
    "co",
    "co.",
    "holdings",
    "holding",
    "group",
    "organization",
    "organisation",
    "international",
    "worldwide",
    "uk",
    "gb",
}

# Trailing "(UK)", "(Gibraltar)", "(Malta)" and friends — jurisdiction markers
# on what is otherwise the same operator.
_TRAILING_PAREN = re.compile(r"\s*\([^()]*\)\s*$")

_PUNCT_EDGE = re.compile(r"^[\s,.;:\-–—]+|[\s,.;:\-–—]+$")


def _tokens(name: str) -> list[str]:
    return [t for t in re.split(r"\s+", name.strip()) if t]


def strip_legal_suffixes(name: str) -> str:
    """Drop trailing legal-entity noise, preserving the original casing so the
    result is still presentable in the dashboard. Returns the input unchanged
    if stripping would leave nothing behind."""
    current = _PUNCT_EDGE.sub("", name)

    while True:
        stripped = _TRAILING_PAREN.sub("", current)
        stripped = _PUNCT_EDGE.sub("", stripped)

        tokens = _tokens(stripped)
        if len(tokens) > 1 and tokens[-1].lower().strip(",.") in LEGAL_SUFFIXES:
            stripped = " ".join(tokens[:-1])
            stripped = _PUNCT_EDGE.sub("", stripped)

        if stripped == current or not stripped:
            break
        current = stripped

    # A name made entirely of suffix tokens ("The Group") would strip to
    # nothing useful — keep the original rather than inventing a blank entity.
    return current or _PUNCT_EDGE.sub("", name)


def match_key(name: str) -> str:
    """Lookup key for a name: suffix-stripped, lowercased, whitespace collapsed,
    and with a leading 'the' removed so 'The Rank Group' and 'Rank' agree."""
    key = " ".join(_tokens(strip_legal_suffixes(name))).lower()
    if key.startswith("the ") and len(key) > 4:
        key = key[4:]
    return key


def build_alias_map(operators: list[dict]) -> dict[str, str]:
    """Map every known spelling of a watchlist operator to its canonical name.

    Operator names are claimed first, then aliases, so an operator's own name
    always wins over another operator's alias — the seed watchlist lists
    "Ladbrokes" as an alias of both Entain and Ladbrokes Coral Group, and
    without that precedence the winner would depend on file order.
    """
    alias_map: dict[str, str] = {}

    for operator in operators:
        name = (operator.get("name") or "").strip()
        if not name:
            continue
        alias_map[match_key(name)] = name

    for operator in operators:
        name = (operator.get("name") or "").strip()
        if not name:
            continue
        for alias in operator.get("aliases") or []:
            alias = (alias or "").strip()
            if not alias:
                continue
            key = match_key(alias)
            if not key:
                continue
            existing = alias_map.get(key)
            if existing is None:
                alias_map[key] = name
            elif existing != name:
                logger.info(
                    "Alias %r already maps to %r — ignoring claim from %r",
                    alias, existing, name,
                )

    return alias_map


def canonical(name: str, alias_map: dict[str, str] | None = None) -> str:
    """Canonical display name for a single extracted entity."""
    key = match_key(name)
    if alias_map and key in alias_map:
        return alias_map[key]
    return strip_legal_suffixes(name)


def canonicalise(
    names: list[str], alias_map: dict[str, str] | None = None
) -> list[str]:
    """Canonicalise a signal's entity list, de-duplicated, order preserved."""
    seen: dict[str, str] = {}
    for name in names or []:
        if not name or not name.strip():
            continue
        resolved = canonical(name, alias_map)
        seen.setdefault(resolved.lower(), resolved)
    return list(seen.values())
