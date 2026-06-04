"use client";

import { useEffect, useRef, useState } from "react";
import { BookOpen, ChevronDown, ChevronUp, Loader2, Send, ShieldCheck, X } from "lucide-react";
import { api, type ChatResponse, type ChatSource, type PortfolioHit } from "@/lib/api";

type Role = "user" | "assistant" | "error";

interface Message {
  id: string;
  role: Role;
  text: string;
  sources?: ChatSource[];
  portfolio_hits?: PortfolioHit[];
  refused?: boolean;
  timestamp: Date;
}

const LAST_AUDIT_KEY = "compliance360_last_audit_id";

const SUGGESTIONS = [
  "Why was termination flagged in my last audit?",
  "Who are the parties in my uploaded contract?",
  "Summarize findings for my last audit",
  "What are the GDPR obligations for data breach notification?",
  "How many active contracts are in the bank portfolio?",
];

function SourceCard({ source }: { source: ChatSource }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="overflow-hidden rounded border border-border bg-card text-xs">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left hover:bg-muted/60"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="flex min-w-0 items-center gap-2">
          <BookOpen size={11} className="shrink-0 text-muted-foreground" />
          <span className="truncate font-semibold text-primary">
            {source.source} — {source.article}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className="rounded px-1.5 py-0.5 font-medium"
            style={{
              backgroundColor: source.score > 0.7 ? "#F0F9E8" : "#FFF7ED",
              color: source.score > 0.7 ? "#2D6A0A" : "#92400E",
            }}
          >
            {(source.score * 100).toFixed(0)}%
          </span>
          {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </div>
      </button>
      {open && (
        <div className="border-t border-border bg-muted/30 px-3 py-2.5 text-[11px] leading-relaxed text-muted-foreground">
          {source.text}
        </div>
      )}
    </div>
  );
}

function PortfolioHitCard({ hit }: { hit: PortfolioHit }) {
  return (
    <div className="rounded border border-border bg-muted/30 px-3 py-2 text-[11px]">
      <div className="font-semibold text-primary">{hit.id}</div>
      <div className="text-muted-foreground">
        {hit.title || "Untitled"} · {hit.category}
        {hit.risk_level ? ` · ${hit.risk_level}` : ""}
      </div>
      <p className="mt-1 line-clamp-2 text-brand-ink">{hit.preview}</p>
    </div>
  );
}

function boldify(text: string): string {
  return text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\*(.+?)\*/g, "<em>$1</em>");
}

function AssistantBubble({ msg }: { msg: Message }) {
  const renderAnswer = (text: string) =>
    text.split("\n\n").map((block, i) => (
      <p
        key={i}
        className="text-[13px] leading-relaxed whitespace-pre-wrap"
        dangerouslySetInnerHTML={{ __html: boldify(block) }}
      />
    ));

  return (
    <div className="flex gap-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary">
        <ShieldCheck size={13} className="text-white" />
      </div>
      <div className="min-w-0 flex-1">
        <div
          className={`rounded-2xl rounded-tl-none border px-4 py-3 shadow-sm ${
            msg.refused ? "border-amber-200 bg-amber-50" : "border-border bg-card"
          }`}
        >
          {msg.role === "error" ? (
            <p className="text-[13px] text-destructive">{msg.text}</p>
          ) : (
            renderAnswer(msg.text)
          )}
        </div>
        {msg.portfolio_hits && msg.portfolio_hits.length > 0 && (
          <div className="mt-2 space-y-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Portfolio matches
            </p>
            {msg.portfolio_hits.map((h) => (
              <PortfolioHitCard key={h.id} hit={h} />
            ))}
          </div>
        )}
        {msg.sources && msg.sources.length > 0 && (
          <div className="mt-2 space-y-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Regulatory sources
            </p>
            {msg.sources.map((s) => (
              <SourceCard key={s.id} source={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

let msgCounter = 0;
function nextId() {
  return `msg-${++msgCounter}`;
}

export function ComplianceChat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: nextId(),
      role: "assistant",
      text: "Hello! I'm your **Compliance 360 AI assistant**.\n\nAsk about **your last audited contract** (select it below), **regulations**, or **portfolio datasets**. Off-topic questions are declined.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const [portfolioFilter, setPortfolioFilter] = useState<string>("");
  const [auditId, setAuditId] = useState<string>("");
  const [recentAudits, setRecentAudits] = useState<{ id: string; filename: string }[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const stored = sessionStorage.getItem(LAST_AUDIT_KEY);
    if (stored) setAuditId(stored);
    api
      .listAudits()
      .then((rows) =>
        setRecentAudits(
          rows.slice(0, 8).map((a) => ({ id: a.id, filename: a.filename })),
        ),
      )
      .catch(() => {});
    const onAudit = (e: Event) => {
      const id = (e as CustomEvent<{ auditId: string }>).detail?.auditId;
      if (id) setAuditId(id);
    };
    window.addEventListener("compliance360-audit-complete", onAudit);
    return () => window.removeEventListener("compliance360-audit-complete", onAudit);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async (question: string) => {
    const q = question.trim();
    if (!q || loading) return;

    const userMsg: Message = { id: nextId(), role: "user", text: q, timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const payload: {
        question: string;
        top_k: number;
        sources?: string[];
        contract_category?: string;
        audit_id?: string;
      } = { question: q, top_k: 5 };
      if (sourceFilter) payload.sources = [sourceFilter];
      if (portfolioFilter) payload.contract_category = portfolioFilter;
      if (auditId) payload.audit_id = auditId;

      const res: ChatResponse = await api.chat(payload);
      const assistantMsg: Message = {
        id: nextId(),
        role: "assistant",
        text: res.answer,
        sources: res.sources,
        portfolio_hits: res.portfolio_hits,
        refused: res.refused,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const detail =
        err instanceof Error ? err.message : "Could not reach the compliance API.";
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "error", text: `⚠ ${detail}`, timestamp: new Date() },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  const clearChat = () => {
    setMessages([
      {
        id: nextId(),
        role: "assistant",
        text: "Chat cleared. Ask a compliance or portfolio question.",
        timestamp: new Date(),
      },
    ]);
  };

  return (
    <div className="flex h-[640px] flex-col overflow-hidden rounded-lg border border-border bg-background shadow-card">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border bg-primary px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10">
            <ShieldCheck size={16} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-white">Compliance AI Assistant</p>
            <p className="text-[10px] text-white/60">
              Audited contracts · regulations · portfolios
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <select
            className="max-w-[200px] h-7 rounded border border-white/20 bg-white/10 px-2 text-[11px] text-white [&>option]:bg-white [&>option]:text-gray-900"
            value={auditId}
            onChange={(e) => setAuditId(e.target.value)}
            title="Contract audit context"
          >
            <option value="" className="bg-white text-gray-900">No audit context</option>
            {recentAudits.map((a) => (
              <option key={a.id} value={a.id} className="bg-white text-gray-900">
                {a.filename.length > 28 ? `${a.filename.slice(0, 25)}…` : a.filename}
              </option>
            ))}
          </select>
          <select
            className="h-7 rounded border border-white/20 bg-white/10 px-2 text-[11px] text-white [&>option]:bg-white [&>option]:text-gray-900"
            value={portfolioFilter}
            onChange={(e) => setPortfolioFilter(e.target.value)}
            title="Portfolio category"
          >
            <option value="" className="bg-white text-gray-900">All portfolios</option>
            <option value="bank" className="bg-white text-gray-900">Bank</option>
            <option value="cybersecurity" className="bg-white text-gray-900">Cybersecurity</option>
            <option value="ai" className="bg-white text-gray-900">AI</option>
          </select>
          <select
            className="h-7 rounded border border-white/20 bg-white/10 px-2 text-[11px] text-white [&>option]:bg-white [&>option]:text-gray-900"
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            title="Filter regulatory source"
          >
            <option value="" className="bg-white text-gray-900">All regulations</option>
            <option value="GDPR" className="bg-white text-gray-900">GDPR</option>
            <option value="ISO27001" className="bg-white text-gray-900">ISO 27001</option>
            <option value="LocalLaw" className="bg-white text-gray-900">Local Law</option>
          </select>
          <button
            type="button"
            onClick={clearChat}
            className="flex h-7 w-7 items-center justify-center rounded text-white/60 hover:bg-white/10 hover:text-white"
            title="Clear chat"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {messages.map((msg) =>
          msg.role === "user" ? (
            <div key={msg.id} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-tr-none bg-primary px-4 py-2.5 text-[13px] text-white">
                {msg.text}
              </div>
            </div>
          ) : (
            <AssistantBubble key={msg.id} msg={msg} />
          ),
        )}
        {loading && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 size={14} className="animate-spin" />
            Searching audit, regulations, and portfolio data…
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="shrink-0 border-t border-border bg-muted/30 px-4 py-3">
        <div className="mb-2 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => send(s)}
              className="rounded-full border border-border bg-card px-2.5 py-1 text-[10px] text-muted-foreground hover:border-accent hover:text-primary"
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            rows={2}
            placeholder="Ask about your audit, regulations, or portfolios…"
            className="flex-1 resize-none rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:border-accent"
          />
          <button
            type="button"
            onClick={() => send(input)}
            disabled={loading || !input.trim()}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent text-white disabled:opacity-40"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
