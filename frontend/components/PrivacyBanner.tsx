"use client";

import { useState, useEffect } from "react";
import { useT, useLang } from "@/lib/i18n";
import { getOrCreateSessionId } from "@/lib/session";

const CONSENT_KEY = "sv_privacy_accepted";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function PrivacyBanner() {
  const t = useT();
  const { lang } = useLang();
  const [accepted, setAccepted] = useState(true); // start hidden; hydrate below
  const [showDetails, setShowDetails] = useState(false);
  const [deleteState, setDeleteState] = useState<"idle" | "pending" | "done" | "error">("idle");

  // Hydrate on client only to avoid SSR mismatch
  useEffect(() => {
    setAccepted(localStorage.getItem(CONSENT_KEY) === "1");
  }, []);

  if (accepted) return null;

  const handleAccept = () => {
    localStorage.setItem(CONSENT_KEY, "1");
    setAccepted(true);
  };

  const handleDeleteSession = async () => {
    const sessionId = getOrCreateSessionId();
    if (!sessionId) {
      setDeleteState("done");
      return;
    }
    if (!window.confirm(t.privacy.deleteSessionConfirm)) return;
    setDeleteState("pending");
    try {
      const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        localStorage.removeItem("sv_session_id");
        localStorage.removeItem(CONSENT_KEY);
        setDeleteState("done");
      } else {
        setDeleteState("error");
      }
    } catch {
      setDeleteState("error");
    }
  };

  return (
    <div
      role="banner"
      aria-label="Privacy notice"
      className="fixed bottom-0 inset-x-0 z-50 bg-slate-900/95 backdrop-blur border-t border-slate-700 text-white shadow-2xl"
      dir={lang === "he" ? "rtl" : "ltr"}
    >
      <div className="max-w-4xl mx-auto px-4 py-4">
        {!showDetails ? (
          // Compact banner
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
            <p className="flex-1 text-sm text-slate-200 leading-relaxed">
              {t.privacy.bannerText}
            </p>
            <div className="flex gap-2 shrink-0">
              <button
                onClick={() => setShowDetails(true)}
                className="text-xs text-slate-400 underline hover:text-slate-200 transition-colors px-1"
              >
                {t.privacy.learnMore}
              </button>
              <button
                onClick={handleAccept}
                className="px-4 py-1.5 text-sm font-medium bg-indigo-600 hover:bg-indigo-500 rounded-lg transition-colors"
              >
                {t.privacy.accept}
              </button>
            </div>
          </div>
        ) : (
          // Expanded details
          <div className="space-y-3">
            <div className="flex justify-between items-start gap-4">
              <div>
                <h2 className="font-semibold text-base mb-1">{t.privacy.policyHeading}</h2>
                <p className="text-sm text-slate-300 leading-relaxed">{t.privacy.policyBody}</p>
              </div>
              <button
                onClick={() => setShowDetails(false)}
                aria-label="Close"
                className="text-slate-400 hover:text-white text-lg leading-none shrink-0"
              >
                ✕
              </button>
            </div>

            {deleteState === "done" ? (
              <p className="text-sm text-green-400">{t.privacy.deleteSessionSuccess}</p>
            ) : deleteState === "error" ? (
              <p className="text-sm text-red-400">{t.privacy.deleteSessionError}</p>
            ) : (
              <button
                onClick={handleDeleteSession}
                disabled={deleteState === "pending"}
                className="text-xs text-red-400 underline hover:text-red-300 transition-colors disabled:opacity-50"
              >
                {deleteState === "pending" ? "…" : t.privacy.deleteSessionBtn}
              </button>
            )}

            <div className="flex justify-end">
              <button
                onClick={handleAccept}
                className="px-4 py-1.5 text-sm font-medium bg-indigo-600 hover:bg-indigo-500 rounded-lg transition-colors"
              >
                {t.privacy.accept}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}






