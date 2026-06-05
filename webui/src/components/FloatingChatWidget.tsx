"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { MessageSquare, Minus, X } from "lucide-react";

const ComplianceChat = dynamic(
  () => import("@/components/ComplianceChat").then((m) => m.ComplianceChat),
  { ssr: false, loading: () => <div className="flex-1 animate-pulse rounded-lg bg-muted/40" /> },
);

type PanelState = "closed" | "open" | "minimised";

export function FloatingChatWidget() {
  const [panel, setPanel] = useState<PanelState>("closed");
  const [unread, setUnread] = useState(0);
  const prevPanel = useRef<PanelState>("closed");

  // Count unread messages when minimised
  useEffect(() => {
    if (panel === "open") setUnread(0);
  }, [panel]);

  function toggle() {
    setPanel((s) => (s === "open" ? "closed" : "open"));
  }

  function minimise() {
    prevPanel.current = "open";
    setPanel("minimised");
  }

  function close() {
    setPanel("closed");
    setUnread(0);
  }

  return (
    <>
      {/* ── Floating button (always visible when closed/minimised) ── */}
      {panel !== "open" && (
        <button
          type="button"
          onClick={toggle}
          className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-primary shadow-xl ring-2 ring-primary/20 transition-transform hover:scale-105 active:scale-95"
          aria-label="Open Compliance AI Assistant"
        >
          <MessageSquare className="h-6 w-6 text-white" />
          {unread > 0 && (
            <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
              {unread}
            </span>
          )}
        </button>
      )}

      {/* ── Minimised pill ── */}
      {panel === "minimised" && (
        <button
          type="button"
          onClick={() => setPanel("open")}
          className="fixed bottom-24 right-6 z-50 flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-xs font-semibold text-white shadow-lg hover:bg-primary/90"
        >
          <MessageSquare className="h-3.5 w-3.5" />
          Compliance AI
          {unread > 0 && (
            <span className="rounded-full bg-red-500 px-1.5 py-0.5 text-[10px]">{unread}</span>
          )}
        </button>
      )}

      {/* ── Chat panel ──
          Mounted for both "open" and "minimised" so the conversation state is
          preserved while minimised. Only unmounted (and reset) when closed. */}
      {panel !== "closed" && (
        <div
          className={
            "fixed bottom-6 right-6 z-50 flex flex-col overflow-hidden rounded-2xl border border-border bg-background shadow-2xl" +
            (panel === "minimised" ? " hidden" : "")
          }
          style={{ width: "min(480px, calc(100vw - 24px))", height: "min(680px, calc(100vh - 80px))" }}
        >
          {/* Header bar */}
          <div className="flex shrink-0 items-center justify-between bg-primary px-4 py-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-white/20">
                <MessageSquare className="h-4 w-4 text-white" />
              </div>
              <div>
                <p className="text-sm font-semibold text-white leading-tight">Compliance AI Assistant</p>
                <p className="text-[10px] text-white/60 leading-tight">Ask about contracts &amp; regulations</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={minimise}
                className="rounded p-1.5 text-white/70 hover:bg-white/10 hover:text-white"
                aria-label="Minimise"
              >
                <Minus className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={close}
                className="rounded p-1.5 text-white/70 hover:bg-white/10 hover:text-white"
                aria-label="Close"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Chat body */}
          <div className="min-h-0 flex-1 overflow-hidden">
            <ComplianceChat compact />
          </div>
        </div>
      )}
    </>
  );
}
