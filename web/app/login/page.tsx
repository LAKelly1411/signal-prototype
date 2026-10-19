import { devLoginEnabled, entraConfigured } from "@/auth";
import LoginArt from "@/components/LoginArt";
import { signInWithDev, signInWithEntra } from "./actions";
import styles from "./login.module.css";

export type LoginPanelProps = { entra: boolean; dev: boolean; error?: string; next?: string };

/** The sign-in side: lockup, title and whichever way in is configured. */
export function LoginPanel({ entra, dev, error, next }: LoginPanelProps) {
  return (
    <div className={styles.panel}>
      <div className={styles.lockup}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/pa-logo.svg" alt="Press Association" />
        <span className={styles.wordmark}>
          <span>Sector</span>
          <span>Signal</span>
        </span>
      </div>
      <div className={styles.title}>Sign in</div>
      <p className={styles.copy}>
        {entra ? "Use your Press Association Microsoft account to continue." : "Enter the team password to continue."}
      </p>
      {error === "CredentialsSignin" && (
        <p className={styles.error} role="alert">
          That password isn&apos;t right. Try again.
        </p>
      )}
      {entra && (
        <form action={signInWithEntra} className={styles.form}>
          <input type="hidden" name="next" value={next ?? "/"} />
          <button type="submit" className={styles.button}>
            Sign in with Microsoft
          </button>
        </form>
      )}
      {dev && (
        <form action={signInWithDev} className={styles.form}>
          <input type="hidden" name="next" value={next ?? "/"} />
          <label className={styles.label} htmlFor="password">
            Password
          </label>
          <input id="password" name="password" type="password" required className={styles.input} />
          <button type="submit" className={styles.button}>
            Sign in
          </button>
        </form>
      )}
      {!entra && !dev && <p className={styles.copy}>Sign-in isn&apos;t set up yet.</p>}
      <p className={styles.foot}>A Press Association prototype</p>
    </div>
  );
}

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ error?: string; next?: string }> }) {
  const { error, next } = await searchParams;
  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroText}>
          <span className="pa-kicker ink">Sector Signal</span>
          <h1 className={styles.headline}>Spot the story before it breaks.</h1>
          <p className={styles.lede}>
            Regulators, filings, Parliament and the markets, watched around the clock and scored for newsworthiness.
          </p>
        </div>
        <LoginArt />
      </section>
      <section className={styles.side}>
        <LoginPanel entra={entraConfigured(process.env)} dev={devLoginEnabled(process.env)} error={error} next={next} />
      </section>
    </main>
  );
}
