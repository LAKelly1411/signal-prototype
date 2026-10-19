import type { ReactNode } from "react";
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

export function EmptyState({ kind, name = "this sector", children }: { kind: Kind; name?: string; children?: ReactNode }) {
  const [title, body] = copy(kind, name);
  return (
    <div className={styles.empty} role="status">
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
