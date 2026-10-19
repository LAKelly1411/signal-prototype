"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import { COMPANY_DOMAINS, SOURCE_DOMAINS, SOURCE_LOGOS, SOURCE_NAMES } from "@/lib/brand";
import { initials, isPerson, matchKey } from "@/lib/signals/entities";
import { Icon } from "./Icon";
import styles from "./card.module.css";

/**
 * Whether /api/logo can serve anything (the server has LOGO_DEV_TOKEN). Set
 * by the sector layout; without it every logo is initials and no request is
 * made.
 */
const LogosEnabled = createContext(false);

export function LogosProvider({ enabled, children }: { enabled: boolean; children: ReactNode }) {
  return <LogosEnabled.Provider value={enabled}>{children}</LogosEnabled.Provider>;
}

const COMPANY_BY_KEY = new Map(Object.entries(COMPANY_DOMAINS).map(([n, d]) => [matchKey(n), d]));

function Initials({ text, person }: { text: string; person?: boolean }) {
  const small = text.length > 2 ? ` ${styles.logoSm}` : "";
  return (
    <span className={`${styles.logo} ${styles.logoInitials}${small}`}>
      {person ? <Icon name="person" size={18} /> : text}
    </span>
  );
}

/** A logo from our own proxy; falls back to initials if it fails to load. */
function ProxiedLogo({ domain, fallback }: { domain: string; fallback: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <Initials text={fallback} />;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img className={styles.logo} src={`/api/logo/${encodeURIComponent(domain)}`} alt="" loading="lazy" onError={() => setFailed(true)} />
  );
}

export function SourceLogo({ source }: { source: string }) {
  const enabled = useContext(LogosEnabled);
  const local = SOURCE_LOGOS[source];
  // eslint-disable-next-line @next/next/no-img-element
  if (local) return <img className={styles.logo} src={local} alt="" />;
  const abbr = (SOURCE_NAMES[source] ?? [source, source.slice(0, 3).toUpperCase()])[1];
  const domain = enabled ? SOURCE_DOMAINS[source] : undefined;
  return domain ? <ProxiedLogo domain={domain} fallback={abbr} /> : <Initials text={abbr} />;
}

export function CompanyLogo({ name }: { name: string }) {
  const enabled = useContext(LogosEnabled);
  if (isPerson(name)) return <Initials text="" person />;
  const domain = enabled ? COMPANY_BY_KEY.get(matchKey(name)) : undefined;
  return domain ? <ProxiedLogo domain={domain} fallback={initials(name)} /> : <Initials text={initials(name)} />;
}
