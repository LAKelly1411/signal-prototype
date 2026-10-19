// Port of src/entities.py (match_key and helpers), src/cluster.py (is_excluded)
// and the small name helpers in dashboard/app.py.
import type { SectorRules, Signal } from "@/lib/data/types";
import { PEOPLE, SOURCE_NAMES } from "@/lib/brand";

const LEGAL_SUFFIXES = new Set([
  "limited", "ltd", "ltd.", "plc", "plc.", "llp", "llc", "inc", "inc.", "incorporated",
  "corporation", "corp", "corp.", "company", "co", "co.", "holdings", "holding", "group",
  "organization", "organisation", "international", "worldwide", "uk", "gb",
]);

// Python's str \s also covers \x1c-\x1f; JS \s covers the rest of Unicode whitespace.
const WS = "\\s\\x1c-\\x1f";
const TRAILING_PAREN = new RegExp(`[${WS}]*\\([^()]*\\)[${WS}]*$`);
const PUNCT_EDGE = new RegExp(`^[${WS},.;:\\-–—]+|[${WS},.;:\\-–—]+$`, "g");
const SPLIT_WS = new RegExp(`[${WS}]+`);

/** Python str.strip() with no args. */
const pyStrip = (s: string) => s.replace(new RegExp(`^[${WS}]+|[${WS}]+$`, "g"), "");

function tokens(name: string): string[] {
  return pyStrip(name).split(SPLIT_WS).filter((t) => t);
}

const edge = (s: string) => s.replace(PUNCT_EDGE, "");

function stripLegalSuffixes(name: string): string {
  let current = edge(name);
  for (;;) {
    let stripped = edge(current.replace(TRAILING_PAREN, ""));
    const toks = tokens(stripped);
    if (toks.length > 1 && LEGAL_SUFFIXES.has(toks[toks.length - 1].toLowerCase().replace(/^[,.]+|[,.]+$/g, ""))) {
      stripped = edge(toks.slice(0, -1).join(" "));
    }
    if (stripped === current || !stripped) break;
    current = stripped;
  }
  return current || edge(name);
}

export function matchKey(name: string): string {
  let key = tokens(stripLegalSuffixes(name)).join(" ").toLowerCase();
  if (key.startsWith("the ") && key.length > 4) key = key.slice(4);
  return key;
}

export function signalEntities(signal: Signal): string[] {
  const resolved = signal.canonical_entities;
  if (resolved && resolved.length) return resolved;
  return signal.entities ?? [];
}

const SHARED_EXCLUDED = [
  "hmrc", "hm revenue & customs", "hm revenue and customs", "hm treasury", "treasury",
  "companies house", "the gazette", "gazette", "advertising standards authority", "asa", "cap",
  "committee of advertising practice", "insolvency service", "financial conduct authority", "fca",
  "parliament", "uk parliament", "house of commons", "house of lords", "government", "uk government",
  "cabinet office", "home office",
];

const sharedSet = new Set(SHARED_EXCLUDED);
const cache = new Map<string, Set<string>>();

function excludedEntities(rules: SectorRules | null): Set<string> {
  // Python's sector=None means the gambling sector; we have no rules to read
  // then, so only the shared list applies.
  if (!rules) return sharedSet;
  const key = JSON.stringify([rules.slug, rules.excludedBodies]);
  let set = cache.get(key);
  if (!set) {
    set = new Set([...SHARED_EXCLUDED, ...rules.excludedBodies.map((b) => pyStrip(b).toLowerCase())]);
    cache.set(key, set);
  }
  return set;
}

export function isExcluded(name: string, rules: SectorRules | null): boolean {
  const excluded = excludedEntities(rules);
  return excluded.has(matchKey(name)) || excluded.has(pyStrip(name).toLowerCase());
}

const PEOPLE_KEYS = new Set([...PEOPLE].map(matchKey));

export function isPerson(name: string): boolean {
  return PEOPLE_KEYS.has(matchKey(name));
}

export function sourceName(source: string): string {
  const hit = SOURCE_NAMES[source];
  if (hit) return hit[0];
  return source.replace(/_/g, " ").replace(/[A-Za-z]+('[A-Za-z]+)?/g, (w) => w[0].toUpperCase() + w.slice(1).toLowerCase());
}

export function initials(name: string): string {
  const words = name.replace(/\(/g, " ").split(SPLIT_WS).filter((w) => w && /^[\p{L}\p{N}]/u.test(w));
  const out = words.slice(0, 2).map((w) => [...w][0]).join("").toUpperCase();
  return out || "?";
}
