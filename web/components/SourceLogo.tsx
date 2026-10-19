"use client";

import { useState } from "react";
import { COMPANY_DOMAINS, SOURCE_DOMAINS, SOURCE_LOGOS, SOURCE_NAMES } from "@/lib/brand";
import { initials, isPerson, matchKey } from "@/lib/signals/entities";
import { Icon } from "./Icon";
import styles from "./card.module.css";

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
  const local = SOURCE_LOGOS[source];
  // eslint-disable-next-line @next/next/no-img-element
  if (local) return <img className={styles.logo} src={local} alt="" />;
  const abbr = (SOURCE_NAMES[source] ?? [source, source.slice(0, 3).toUpperCase()])[1];
  const domain = SOURCE_DOMAINS[source];
  return domain ? <ProxiedLogo domain={domain} fallback={abbr} /> : <Initials text={abbr} />;
}

export function CompanyLogo({ name }: { name: string }) {
  if (isPerson(name)) return <Initials text="" person />;
  const domain = COMPANY_BY_KEY.get(matchKey(name));
  return domain ? <ProxiedLogo domain={domain} fallback={initials(name)} /> : <Initials text={initials(name)} />;
}
