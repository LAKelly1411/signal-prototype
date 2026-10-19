"use client";

import { EmptyState } from "./EmptyState";
import styles from "./shell.module.css";

/** What an error boundary shows: the calm unavailable message and a way to try again. */
export function ErrorState({ reset }: { reset: () => void }) {
  return (
    <EmptyState kind="unavailable">
      <button type="button" className={styles.retry} onClick={() => reset()}>
        Try again
      </button>
    </EmptyState>
  );
}
