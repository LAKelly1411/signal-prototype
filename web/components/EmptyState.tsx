import styles from "./shell.module.css";

const COPY = {
  unavailable: ["Not available yet", "We couldn't load the latest signals. Try again in a few minutes."],
  setting_up: ["Setting up", "We're gathering the first signals for this sector. This usually takes under an hour."],
  empty: ["No signals yet", "This sector is set up, but nothing has come through yet. New signals will appear here as they're found."],
} as const;

export function EmptyState({ kind, name }: { kind: keyof typeof COPY; name?: string }) {
  const [title, body] = COPY[kind];
  const text = name && kind !== "unavailable" ? body.replace("this sector", name).replace("This sector", name) : body;
  return (
    <div className={styles.empty} role="status">
      <div>
        <div className={styles.emptyTitle}>{title}</div>
        <div className={styles.emptyBody}>{text}</div>
      </div>
    </div>
  );
}
