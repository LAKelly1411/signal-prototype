import type { ReactNode } from "react";
import { Icon } from "./Icon";

type Kind = "entity" | "accent" | "plain";

/** icon: "person" | "corporate" or any ICON_PATHS name; ignored for plain tags. */
export function Tag({ kind = "entity", icon, children }: { kind?: Kind; icon?: string; children: ReactNode }) {
  const cls = kind === "plain" ? "pa-tag pa-tag-plain" : kind === "accent" ? "pa-tag pa-tag-accent" : "pa-tag";
  const name = icon === "corporate" ? "corporate_fare" : icon;
  return (
    <span className={cls}>
      {kind !== "plain" && name ? (
        <span className="pa-tag-icon"><Icon name={name} size={20} /></span>
      ) : null}
      {children}
    </span>
  );
}
