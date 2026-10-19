import { ICON_PATHS } from "@/lib/brand";

export function Icon({ name, size = 16 }: { name: string; size?: number }) {
  const icon = ICON_PATHS[name] ?? ICON_PATHS.label;
  return (
    <svg width={size} height={size} viewBox={icon.viewBox} fill="currentColor" aria-hidden="true" focusable="false">
      <path d={icon.d} />
    </svg>
  );
}
