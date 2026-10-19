import { SignalCard } from "@/components/SignalCard";
import { FeedFilters } from "@/components/FeedFilters";
import { EmptyBlock } from "@/components/EmptyState";
import type { SortOrder } from "@/components/SortMenu";
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

  const basePath = `/${view.sector.slug}/feed`;

  let body: React.ReactNode;
  if (scored.length === 0) {
    body = <EmptyBlock title="No scored signals yet." role="status"><p className={styles.emptyBody}>Check back after the next pipeline run.</p></EmptyBlock>;
  } else if (filtered.length === 0) {
    body = (
      <EmptyBlock title="No signals match your filters." role="status">
        <p className={styles.emptyBody}>
          Try widening them, or <a href={sort === "score" ? `${basePath}?sort=score` : basePath}>Clear all</a> to start again.
        </p>
      </EmptyBlock>
    );
  } else if (sort === "score") {
    body = filtered.map(card);
  } else {
    const todayAny = scored.some((s) => calendarDate(s.published_at).getTime() >= today.getTime());
    body = BUCKETS.filter((b) => buckets[b].length || b === "Today").map((b) => (
      <section key={b}>
        <h2 className={styles.bucket}>{b}</h2>
        {buckets[b].length === 0 && (todayAny ? (
          <EmptyBlock title="Nothing from today matches your filters." className={styles.inBucket}>
            <p className={styles.emptyBody}>Try widening them, or catch up on earlier signals below.</p>
          </EmptyBlock>
        ) : (
          <EmptyBlock title="Nothing new yet today." className={styles.inBucket}>
            <p className={styles.emptyBody}>We check our sources throughout the day, so new signals will appear here as they come in.</p>
          </EmptyBlock>
        ))}
        {buckets[b].map(card)}
      </section>
    ));
  }

  return (
    <>
      <FeedFilters options={options} />
      <p className={styles.count}>Showing {filtered.length} of {scored.length} scored signals.</p>
      {body}
    </>
  );
}
