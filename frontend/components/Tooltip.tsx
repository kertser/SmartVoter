"use client";

import { useState, useEffect, type ReactNode } from "react";

/**
 * Lightweight CSS-only tooltip.
 * Wraps any element; shows `content` above/below it on hover/focus.
 *
 * Strategy to prevent hydration mismatches caused by browser extensions
 * (e.g. password managers, ad-blockers, Honey, extwaiokist) that inject DOM
 * nodes into <span> elements after the server HTML lands:
 *
 *   — Before mount (server + initial client render): return the children
 *     directly with no wrapper element.  There is no <span> for an extension
 *     to inject into, so SSR and the initial client render are identical.
 *   — After mount (useEffect): swap to the full <span> + tooltip bubble.
 *     This is a normal React DOM update, not hydration, so mismatches are
 *     irrelevant.
 *
 * Usage:
 *   <Tooltip content="Explains what this badge means" position="bottom">
 *     <span className="badge">72%</span>
 *   </Tooltip>
 */

interface TooltipProps {
  content: string;
  children: ReactNode;
  /** Position relative to trigger. Default: "top" */
  position?: "top" | "bottom";
  className?: string;
}

export function Tooltip({
  content,
  children,
  position = "top",
  className = "",
}: TooltipProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  // Before mount: no wrapper — nothing for browser extensions to inject into.
  if (!mounted) {
    return <>{children}</>;
  }

  const above = position === "top";

  return (
    <span className={`relative group inline-flex ${className}`}>
      {children}

      {/* Bubble */}
      <span
        role="tooltip"
        className={`
          pointer-events-none absolute z-[9999]
          left-1/2 -translate-x-1/2
          ${above ? "bottom-full mb-2" : "top-full mt-2"}
          px-2.5 py-1.5
          bg-slate-800 text-white text-xs leading-snug rounded-lg
          whitespace-nowrap max-w-[240px] text-center
          opacity-0 group-hover:opacity-100 group-focus-within:opacity-100
          transition-opacity duration-150
          shadow-lg
        `}
      >
        {content}
        {/* Arrow */}
        <span
          className={`
            absolute left-1/2 -translate-x-1/2
            ${above ? "top-full border-t-slate-800" : "bottom-full border-b-slate-800"}
            border-4 border-transparent
          `}
        />
      </span>
    </span>
  );
}
