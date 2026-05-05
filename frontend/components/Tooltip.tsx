"use client";

import type { ReactNode } from "react";

/**
 * Lightweight CSS-only tooltip.
 * Wraps any element; shows `content` above it on hover/focus.
 *
 * Usage:
 *   <Tooltip content="Explains what this badge means">
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
  const above = position === "top";

  return (
    <span className={`relative group inline-flex ${className}`}>
      {children}

      {/* Bubble */}
      <span
        role="tooltip"
        className={`
          pointer-events-none absolute z-50
          left-1/2 -translate-x-1/2
          ${above ? "bottom-full mb-2" : "top-full mt-2"}
          px-2.5 py-1.5
          bg-slate-800 text-white text-xs leading-snug rounded-lg
          whitespace-nowrap max-w-[220px] text-center
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

