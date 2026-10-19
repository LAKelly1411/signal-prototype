import styles from "./shell.module.css";

/** The PA lockup: the mark beside the product name set as two ink blocks. */
export function Masthead() {
  return (
    <div className={styles.masthead}>
      <div className={`pa-lockup ${styles.lockup}`}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/pa-logo.svg" alt="Press Association" className={styles.logo} />
        <span className="pa-wordmark" aria-hidden="true"><span>Sector</span><span>Signal</span></span>
      </div>
    </div>
  );
}
