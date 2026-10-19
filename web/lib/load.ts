import { cache } from "react";
import { notFound } from "next/navigation";
import { DataError, isSlug } from "@/lib/data/errors";
import { getDataSource, type DataSource } from "@/lib/data/source";
import type { RunStatus, SectorEntry, SectorRules, Signal } from "@/lib/data/types";

export type SectorView =
  | { state: "ready"; sector: SectorEntry; sectors: SectorEntry[]; signals: Signal[]; status: RunStatus | null; rules: SectorRules | null; now: Date; notice: "update_failed" | null }
  | { state: "setting_up" | "empty" | "error_empty"; sector: SectorEntry; sectors: SectorEntry[]; status: RunStatus | null }
  | { state: "unavailable"; sectors: SectorEntry[] };

export { TABS } from "@/lib/tabs";

const GAMBLING = "gambling";

/** Gambling first (the original sector), then alphabetical by slug; entries without a valid slug are dropped. */
export function orderSectors(entries: SectorEntry[]): SectorEntry[] {
  return entries
    .filter((e) => e && isSlug(e.slug))
    .sort((a, b) => Number(a.slug !== GAMBLING) - Number(b.slug !== GAMBLING) || (a.slug < b.slug ? -1 : a.slug > b.slug ? 1 : 0));
}

/** The muted note beside a sector in the switcher. */
export function sectorNote(entry: SectorEntry): string {
  if (entry.status === "setting_up") return "Setting up…";
  if (entry.status === "error") return "Update failed";
  return entry.signal_count != null ? String(entry.signal_count) : "";
}

/**
 * Where "/" lands: the first ready sector's feed (else the first sector's),
 * or null when there are no sectors or the index can't be read.
 */
export async function homePath(src: DataSource = getDataSource()): Promise<string | null> {
  try {
    const sectors = orderSectors(await src.listSectors());
    const target = (sectors.find((s) => s.status === "ready") ?? sectors[0])?.slug;
    return target ? `/${target}/feed` : null;
  } catch {
    return null;
  }
}

const orNull = async <T,>(p: Promise<T>): Promise<T | null> => {
  try {
    return await p;
  } catch {
    return null;
  }
};

/** One sector's view. Wrapped in React's cache() so the layout and the page share one load per request. */
export const loadSector = cache(async function loadSector(slug: string, src: DataSource = getDataSource()): Promise<SectorView> {
  if (!isSlug(slug)) notFound();
  let sectors: SectorEntry[];
  try {
    sectors = orderSectors(await src.listSectors());
  } catch (e) {
    if (e instanceof DataError) return { state: "unavailable", sectors: [] };
    throw e;
  }
  const sector = sectors.find((s) => s.slug === slug);
  if (!sector) notFound();

  const status = await orNull(src.getRunStatus(slug));
  const failed = sector.status === "error";
  if (sector.status !== "ready" && !failed) return { state: "setting_up", sector, sectors, status };

  let signals: Signal[];
  try {
    signals = await src.getSignals(slug);
  } catch (e) {
    if (e instanceof DataError && e.kind === "not_found") return { state: failed ? "error_empty" : "setting_up", sector, sectors, status };
    if (e instanceof DataError) return { state: "unavailable", sectors };
    throw e;
  }
  if (signals.length === 0) return { state: failed ? "error_empty" : "empty", sector, sectors, status };
  const rules = await orNull(src.getSectorRules(slug));
  return { state: "ready", sector, sectors, signals, status, rules, now: new Date(), notice: failed ? "update_failed" : null };
});
