import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function confidenceLabel(score: number): string {
  if (score >= 0.75) return "High";
  if (score >= 0.5) return "Medium";
  return "Low";
}

export function confidenceColor(score: number): string {
  if (score >= 0.75) return "text-green-700 bg-green-50";
  if (score >= 0.5) return "text-yellow-700 bg-yellow-50";
  return "text-orange-700 bg-orange-50";
}

