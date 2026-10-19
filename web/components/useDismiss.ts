"use client";
import { useEffect, type RefObject } from "react";

/** Closes an open <details> menu on a click outside it or on Escape (focus returns to its summary). */
export function useDismiss(ref: RefObject<HTMLDetailsElement | null>) {
  useEffect(() => {
    const onPointer = (e: PointerEvent) => {
      const el = ref.current;
      if (el?.open && !el.contains(e.target as Node)) el.removeAttribute("open");
    };
    const onKey = (e: KeyboardEvent) => {
      const el = ref.current;
      if (e.key !== "Escape" || !el?.open) return;
      el.removeAttribute("open");
      el.querySelector("summary")?.focus();
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [ref]);
}
