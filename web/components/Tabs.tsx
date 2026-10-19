"use client";
import Link from "next/link";
import { usePathname, useSearchParams, useSelectedLayoutSegment } from "next/navigation";
import { TABS } from "@/lib/tabs";
import { SortMenu } from "./SortMenu";
import styles from "./shell.module.css";

/** The section tabs; on the Feed, the sort menu sits at the right end of the row. */
export function Tabs({ slug, current }: { slug: string; current?: string }) {
  const segment = useSelectedLayoutSegment();
  const active = current ?? segment;
  return (
    <div className={styles.tabRow}>
      <nav className={styles.tabs} aria-label="Sections">
        {TABS.map(([key, label]) => (
          <Link key={key} href={`/${slug}/${key}`} className={styles.tab} aria-current={active === key ? "page" : undefined}>
            {label}
          </Link>
        ))}
      </nav>
      {active === "feed" && <FeedSort />}
    </div>
  );
}

function FeedSort() {
  const pathname = usePathname();
  const sp = useSearchParams();
  return <SortMenu basePath={pathname} query={sp.toString()} />;
}
