"use client";

import { ErrorState } from "@/components/ErrorState";
import { Masthead } from "@/components/Masthead";
import styles from "@/components/shell.module.css";

/** Anything that throws outside a sector's tabs (including the sector layout itself). */
export default function RootError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className={styles.page}>
      <Masthead />
      <ErrorState reset={reset} />
    </div>
  );
}
