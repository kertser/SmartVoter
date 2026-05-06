"use client";

import { useState, useEffect, type ReactNode } from "react";

/**
 * Lightweight CSS-only tooltip.
 * Wraps any element; shows `content` above/below it on hover/focus.
 *
 * The tooltip bubble is rendered ONLY after client-side hydration to prevent
 * hydration mismatches caused by browser extensions (e.g. password managers,
 * ad-blockers, Honey) that inject DOM nodes into the page after server render.
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
  // Only render the tooltip bubble on the client.
  // This prevents browser-extension DOM injections from causing React
  // hydration mismatches (the server renders nothing; the client fills it in).
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  const above = position === "top";

  return (
    <span className={`relative group inline-flex ${className}`}>
      {children}

      {/* Bubble — client only */}
      {mounted && (
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
      )}
    </span>
  );
}

