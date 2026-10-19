import type { CSSProperties } from "react";
import { SCROLL, loginArt } from "@/lib/loginArt";
import styles from "./LoginArt.module.css";

type Vars = CSSProperties & Record<`--${string}`, string | number>;

/** The sign-in hero's illustration: a heat map and a jagged timeline that scroll together. */
export default function LoginArt() {
  const { values, cells, picks, shift, cols, rows } = loginArt();
  const n = values.length;
  const step = 100 / cols;
  const track = [...values, ...values, values[0]];
  const pts = track.map((v, i) => `${((i + 0.5) * step).toFixed(3)},${((1 - v) * 100).toFixed(2)}`).join(" ");

  // Each highlight is shown while it crosses the middle of the panel; the
  // keyframes are per pick, so they live in a plain <style> (global names).
  const marks = [0, 1].flatMap((copy) => picks.map((p, k) => ({ ...p, idx: p.idx + copy * n, copy, k })));
  const keyframes = marks
    .map((p) => {
      const { copy, k } = p;
      const f = ((p.idx + 0.5) * step) / 100;
      const lo = Math.max((f - 0.41) / shift, 0);
      const hi = Math.min((f - 0.14) / shift, 1);
      const frames =
        hi - lo > 0.04
          ? `0%, ${(lo * 100).toFixed(2)}% { opacity: 0; } ${(lo * 100 + 2).toFixed(2)}%, ${(hi * 100 - 2).toFixed(2)}% { opacity: 1; } ${(hi * 100).toFixed(2)}%, 100% { opacity: 0; }`
          : "0%, 100% { opacity: 0; }";
      return `@keyframes la-show-${copy}-${k} { ${frames} }`;
    })
    .join(" ");

  return (
    <>
      <style>{keyframes}</style>
      <div
        className={styles.line}
        role="img"
        aria-label="A scrolling timeline of signals per week, with its busiest weeks highlighted"
      >
        <div className={styles.track} style={{ "--shift": `-${(shift * 100).toFixed(4)}%` } as Vars}>
          <div className={styles.heat} style={{ "--cols": cols, "--rows": rows } as Vars}>
            {cells.map((c) => (
              <span
                key={`${c.col}-${c.row}`}
                className={styles.cell}
                style={
                  {
                    left: `${(((c.col + 0.5) * 100) / cols).toFixed(3)}%`,
                    "--r": c.row,
                    "--a": c.alpha.toFixed(2),
                    animationDuration: `${c.dur.toFixed(1)}s`,
                    animationDelay: `${c.delay.toFixed(2)}s`,
                  } as Vars
                }
              >
                {c.spark && (
                  <span
                    className={styles.spark}
                    style={{ animationDuration: `${c.sparkDur.toFixed(1)}s`, animationDelay: `${c.sparkDelay.toFixed(2)}s` }}
                  />
                )}
              </span>
            ))}
          </div>
          <svg className={styles.trackLine} viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            <polyline className={styles.lineStroke} points={pts} />
          </svg>
          {marks.map((p) => {
            const { copy, k } = p;
            return (
              <div
                key={p.idx}
                className={styles.at}
                style={{
                  left: `${((p.idx + 0.5) * step).toFixed(3)}%`,
                  bottom: `calc(46vh * ${p.value.toFixed(3)})`,
                  animation: `la-show-${copy}-${k} ${SCROLL}s linear infinite`,
                }}
              >
                <span className={styles.pulse} />
                <span className={styles.point} />
                <span className={styles.tip}>
                  <span>{p.label}</span>
                  <b>{p.count} signals</b>
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
