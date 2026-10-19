"use client";

import { ErrorState } from "@/components/ErrorState";

/** A tab that throws; the sector layout (masthead, menu, tabs) stays in place around it. */
export default function SectorError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ErrorState reset={reset} />;
}
