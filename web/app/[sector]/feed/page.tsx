import { SignalCard } from "@/components/SignalCard";
import { FeedFilters } from "@/components/FeedFilters";
import { FeedToolbar, type SortOrder } from "@/components/FeedToolbar";
import { loadSector } from "@/lib/load";
import { computeHeat } from "@/lib/signals/heat";
import { criteriaFromSearchParams, filterOptions, filterSignals, scoredSignals, sortSignals } from "@/lib/signals/filters";
import { calendarDay, DAY_MS, dateBucket, utcDay } from "@/lib/signals/time";
import type { Signal } from "@/lib/data/types";
import styles from "./feed.module.css";

const BUCKETS = ["Today", "Yesterday", "This week", "Earlier"] as const;
/** Midnight-aligned UTC date of the calendar day as written in the ISO string. */
const calendarDate = (iso: string) => new Date(calendarDay(iso) * DAY_MS);

export default async function FeedPage({
  params, searchParams,
}: { params: Promise<{ sector: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { sector: slug } = await params;
  const raw = await searchParams;
  const view = await loadSector(slug);
  if (view.state !== "ready") return null;

  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(raw)) for (const x of Array.isArray(v) ? v : v == null ? [] : [v]) sp.append(k, x);

  const { now } = view;
  const scored = scoredSignals(view.signals);
  const options = filterOptions(scored);
  const sort: SortOrder = sp.get("sort") === "score" ? "score" : "recent";
  const filtered = sortSignals(filterSignals(scored, criteriaFromSearchParams(sp, options), now), sort);

  // Python's _build_cluster_info: heat over every scored member of each cluster.
  const byCluster = new Map<string, Signal[]>();
  for (const s of scored) if (s.cluster_id) (byCluster.get(s.cluster_id) ?? byCluster.set(s.cluster_id, []).get(s.cluster_id)!).push(s);
  const clusterInfo = new Map([...byCluster].map(([id, members]) => [id, { heat: computeHeat(members, now), size: members.length }]));
  const card = (s: Signal) => <SignalCard key={s.id} signal={s} now={now} clusterInfo={s.cluster_id ? clusterInfo.get(s.cluster_id) : undefined} />;

  const today = new Date(utcDay(now) * DAY_MS);
  const buckets: Record<string, Signal[]> = { Today: [], Yesterday: [], "This week": [], Earlier: [] };
  if (sort === "recent") for (const s of filtered) buckets[dateBucket(calendarDate(s.published_at), today)].push(s);

  const query = sp.toString();
  const basePath = `/${view.sector.slug}/feed`;

  let body: React.ReactNode;
  if (scored.length === 0) {
    body = <p className={styles.empty}>No scored signals yet. Check back after the next pipeline run.</p>;
  } else if (filtered.length === 0) {
    body = (
      <p className={styles.empty}>
        No signals match these filters. <a href={sort === "score" ? `${basePath}?sort=score` : basePath}>Clear all</a>
      </p>
    );
  } else if (sort === "score") {
    body = filtered.map(card);
  } else {
    const todayAny = scored.some((s) => calendarDate(s.published_at).getTime() >= today.getTime());
    body = BUCKETS.filter((b) => buckets[b].length || b === "Today").map((b) => (
      <section key={b}>
        <h2 className={styles.bucket}>{b}</h2>
        {buckets[b].length === 0 && (
          <p className={styles.empty}>{todayAny ? "Nothing from today matches your filters." : "Nothing new yet today."}</p>
        )}
        {buckets[b].map(card)}
      </section>
    ));
  }

  return (
    <div className={styles.layout}>
      <FeedFilters options={options} />
      <div className={styles.main}>
        <FeedToolbar shown={filtered.length} total={scored.length} sort={sort} basePath={basePath} query={query} />
        {body}
      </div>
    </div>
  );
}
