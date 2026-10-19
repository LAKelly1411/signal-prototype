import type { ReactNode } from "react";
import { Glyph } from "./Glyph";
import styles from "./shell.module.css";

type Kind = "unavailable" | "setting_up" | "empty" | "error_empty";

const copy = (kind: Kind, name: string): [string, string] => {
  switch (kind) {
    case "setting_up":
      return ["Setting up", `We're gathering the first signals for ${name}. This usually takes under an hour.`];
    case "empty":
      return ["No signals yet", `${name} is set up, but nothing has come through yet. New signals will appear here as they're found.`];
    case "error_empty":
      return ["Not available yet", `We couldn't load ${name} yet. We'll try again on the next scheduled update.`];
    default:
      return ["Not available yet", "We couldn't load the latest signals. Try again in a few minutes."];
  }
};

/** A friendly grey block for an empty section or feed: inbox icon, bold title, muted body (Python _empty_block). */
export function EmptyBlock({ title, children, role, className }: { title: string; children?: ReactNode; role?: string; className?: string }) {
  return (
    <div className={className ? `${styles.empty} ${className}` : styles.empty} role={role}>
      <Glyph name="inbox" size={24} className={styles.emptyIcon} />
      <div>
        <div className={styles.emptyTitle}>{title}</div>
        {children}
      </div>
    </div>
  );
}

export function EmptyState({ kind, name = "this sector", children }: { kind: Kind; name?: string; children?: ReactNode }) {
  const [title, body] = copy(kind, name);
  return (
    <div className={styles.empty} role="status">
      <Glyph name="inbox" size={24} className={styles.emptyIcon} />
      <div>
        <div className={styles.emptyTitle}>{title}</div>
        <div className={styles.emptyBody}>{body}</div>
        {children}
      </div>
    </div>
  );
}

/** Shown above the tabs when the last run failed but earlier data is still being served. */
export function UpdateNotice() {
  return <p className={styles.notice}>The last update didn&apos;t finish. Showing the latest data we have.</p>;
}
