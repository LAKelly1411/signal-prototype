"use client";

import { useRef } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { Group } from "@/lib/signals/groups";
import { GroupCard } from "./GroupCard";
import { PreviewPane } from "./PreviewPane";
import styles from "./groups.module.css";

/** The cards, plus the preview of the one selected in the URL (?pattern= / ?theme=). */
export function GroupList({ groups, param, scale, now }: { groups: Group[]; param: "pattern" | "theme"; scale: number; now: Date }) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const selectedId = search.get(param);
  const current = groups.find((g) => g.id === selectedId) ?? null;

  const listRef = useRef<HTMLDivElement>(null);

  const close = () => {
    const id = current?.id;
    go(null);
    // Hand focus back to the card the pane was showing.
    for (const b of listRef.current?.querySelectorAll<HTMLElement>("[data-group-id]") ?? []) if (b.dataset.groupId === id) b.focus({ preventScroll: true });
  };

  const go = (id: string | null) => {
    const next = new URLSearchParams(search.toString());
    if (id === null) next.delete(param);
    else next.set(param, id);
    const qs = next.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  return (
    <div ref={listRef} className={`${styles.list}${current ? ` ${styles.withPane}` : ""}`}>
      {groups.map((g) => (
        <GroupCard key={g.id} group={g} selected={current?.id === g.id} scale={scale} now={now} onSelect={() => go(g.id)} />
      ))}
      {current ? <PreviewPane key="pane" group={current} scale={scale} now={now} onClose={close} /> : null}
    </div>
  );
}
