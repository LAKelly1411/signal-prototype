"use client";
import Link from "next/link";
import { useSelectedLayoutSegment } from "next/navigation";
import { TABS } from "@/lib/tabs";
import styles from "./shell.module.css";

export function Tabs({ slug, current }: { slug: string; current?: string }) {
  const segment = useSelectedLayoutSegment();
  const active = current ?? segment;
  return (
    <nav className={`pa-tabs ${styles.tabs}`} aria-label="Sections">
      {TABS.map(([key, label]) => (
        <Link key={key} href={`/${slug}/${key}`} className="pa-tab" aria-current={active === key ? "page" : undefined}>
          {label}
        </Link>
      ))}
    </nav>
  );
}
