"use client";
import { useEffect, useId, useState } from "react";
import { useRouter } from "next/navigation";
import { Glyph } from "./Glyph";
import styles from "./groups.module.css";

const HELP = "Includes quiet patterns and routine runs of filings.";

/** "Show quieter patterns": a switch with a (?) help tip, driving ?quiet=1 (Python st.toggle on the Patterns tab). */
export function QuietToggle({ checked, href }: { checked: boolean; href: string }) {
  const router = useRouter();
  const [on, setOn] = useState(checked);
  useEffect(() => setOn(checked), [checked]);
  const tipId = useId();
  return (
    <div className={styles.quiet}>
      <button
        type="button" role="switch" aria-checked={on} className={styles.switch}
        onClick={() => { setOn(!on); router.replace(href, { scroll: false }); }}
      >
        <span className={styles.track} aria-hidden="true"><span className={styles.knob} /></span>
        Show quieter patterns
      </button>
      <span className={styles.help}>
        <button type="button" className={styles.helpButton} aria-label="About quieter patterns" aria-describedby={tipId}>
          <Glyph name="help" size={16} />
        </button>
        <span role="tooltip" id={tipId} className={`pa-tooltip ${styles.tip}`}>{HELP}</span>
      </span>
    </div>
  );
}
