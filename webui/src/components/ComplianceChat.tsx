"use client";

import { useEffect, useRef, useState } from "react";
import { BookOpen, ChevronDown, ChevronUp, Loader2, Send, ShieldCheck, X } from "lucide-react";
import { api, type ChatResponse, type ChatSource } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

type Role = "user" | "assistant" | "error";

interface Message {
  id: string;
  role: Role;
  text: string;
  sources?: ChatSource[];
  timestamp: Date;
}

// ── Suggested starter questions ──────────────────────────────────────────────

const SUGGESTIONS = [
  "What are the GDPR obligations for data breach notification?",
  "What rights do data subjects have under GDPR?",
  "What does ISO 27001 require for access control?",
  "What are the penalties for non-compliance?",
];

// ── Sub-components ────────────────────────────────────────────────────────────

function SourceCard({ source }: { source: ChatSource }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="overflow-hidden rounded border border-border bg-card text-xs">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left hover:bg-muted/60"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="flex items-center gap-2 min-w-0">
          <BookOpen size={11} className="shrink-0 text-muted-foreground" />
          <span className="font-semibold text-primary truncate">
            {source.source} — {source.article}
          </span>
          {source.title && (
            <span className="hidden text-muted-foreground sm:inline truncate">
              · {source.title}
            </span>
          )}
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

function AssistantBubble({ msg }: { msg: Message }) {
  // Convert **bold** markdown to <strong> and split on \n\n for paragraphs
  const renderAnswer = (text: string) => {
    return text.split("\n\n").map((block, i) => {
      if (block.startsWith("•")) {
        const lines = block.split("\n").filter(Boolean);
        return (
          <ul key={i} className="mt-2 space-y-2 pl-0">
            {lines.map((line, j) => {
              const content = line.replace(/^•\s*/, "");
              return (
                <li key={j} className="flex gap-2 text-[13px]">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                  <span dangerouslySetInnerHTML={{ __html: boldify(content) }} />
                </li>
              );
            })}
          </ul>
        );
      }
      if (block.startsWith("---")) {
        return (
          <p
            key={i}
            className="mt-3 text-[11px] leading-relaxed text-muted-foreground border-t border-border pt-2"
            dangerouslySetInnerHTML={{ __html: boldify(block.replace(/^---\n?/, "")) }}
          />
        );
      }
      return (
        <p
          key={i}
          className="text-[13px] leading-relaxed"
          dangerouslySetInnerHTML={{ __html: boldify(block) }}
        />
      );
    });
  };

  return (
    <div className="flex gap-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary">
        <ShieldCheck size={13} className="text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="rounded-2xl rounded-tl-none bg-card border border-border px-4 py-3 shadow-sm">
          {msg.role === "error" ? (
            <p className="text-[13px] text-destructive">{msg.text}</p>
          ) : (
            <div className="space-y-1">{renderAnswer(msg.text)}</div>
          )}
        </div>
        {msg.sources && msg.sources.length > 0 && (
          <div className="mt-2 space-y-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground pl-1">
              {msg.sources.length} source{msg.sources.length > 1 ? "s" : ""} cited
            </p>
            {msg.sources.map((s) => (
              <SourceCard key={s.id} source={s} />
            ))}
          </div>
        )}
        <p className="mt-1.5 pl-1 text-[10px] text-muted-foreground">
          {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </p>
      </div>
    </div>
  );
}

function UserBubble({ msg }: { msg: Message }) {
  return (
    <div className="flex justify-end gap-3">
      <div className="max-w-[80%]">
        <div className="rounded-2xl rounded-tr-none bg-primary px-4 py-2.5">
          <p className="text-[13px] text-white">{msg.text}</p>
        </div>
        <p className="mt-1 text-right text-[10px] text-muted-foreground">
          {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </p>
      </div>
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-[10px] font-bold text-white">
        SC
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary">
        <ShieldCheck size={13} className="text-white" />
      </div>
      <div className="rounded-2xl rounded-tl-none border border-border bg-card px-4 py-3 shadow-sm">
        <div className="flex items-center gap-1">
          {[0, 1, 2].map((i) => (
            <span key={i} className="chat-dot h-2 w-2 rounded-full bg-muted-foreground/50" />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function boldify(text: string): string {
  return text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\*(.+?)\*/g, "<em>$1</em>");
}

let msgCounter = 0;
function nextId() {
  return `msg-${++msgCounter}`;
}

// ── Main component ────────────────────────────────────────────────────────────

export function ComplianceChat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: nextId(),
      role: "assistant",
      text: "Hello! I'm your **Compliance 360 AI assistant**.\n\nAsk me anything about your regulatory obligations — GDPR, ISO 27001, data privacy, financial compliance, and more.\n\nI'll ground every answer in the regulatory corpus and cite the exact clauses I'm drawing from.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

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
      const payload: { question: string; top_k: number; sources?: string[] } = {
        question: q,
        top_k: 5,
      };
      if (sourceFilter) payload.sources = [sourceFilter];

      const res: ChatResponse = await api.chat(payload);
      const assistantMsg: Message = {
        id: nextId(),
        role: "assistant",
        text: res.answer,
        sources: res.sources,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const detail =
        err instanceof Error ? err.message : "Could not reach the compliance API.";
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "error",
          text: `⚠ ${detail}`,
          timestamp: new Date(),
        },
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
        text: "Chat cleared. Ask me a new compliance question.",
        timestamp: new Date(),
      },
    ]);
  };

  return (
    <div className="flex h-[640px] flex-col rounded-lg border border-border bg-background shadow-card overflow-hidden">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border bg-primary px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10">
            <ShieldCheck size={16} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-white">Compliance AI Assistant</p>
            <p className="text-[10px] text-white/60">RAG-grounded · cites regulatory corpus</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Source filter */}
          <select
            className="h-7 rounded border border-white/20 bg-white/10 px-2 text-[11px] text-white"
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            title="Filter regulatory source"
          >
            <option value="">All sources</option>
            <option value="GDPR">GDPR</option>
            <option value="ISO27001">ISO 27001</option>
            <option value="LocalLaw">Local Law</option>
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

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.map((msg) =>
          msg.role === "user" ? (
            <UserBubble key={msg.id} msg={msg} />
          ) : (
            <AssistantBubble key={msg.id} msg={msg} />
          ),
        )}
        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions (only when no user messages yet) */}
      {messages.filter((m) => m.role === "user").length === 0 && !loading && (
        <div className="shrink-0 border-t border-border px-4 py-2">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Try asking
          </p>
          <div className="flex flex-wrap gap-1.5">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => send(s)}
                className="rounded-full border border-border bg-card px-3 py-1 text-[11px] text-brand-ink hover:border-accent hover:bg-accent/5 hover:text-accent transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="shrink-0 border-t border-border bg-card px-4 py-3">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask a compliance question… (Enter to send)"
            disabled={loading}
            className="flex-1 resize-none rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-brand-ink placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-accent/40 disabled:opacity-50"
            style={{ maxHeight: "120px" }}
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
            }}
          />
          <button
            type="button"
            onClick={() => send(input)}
            disabled={!input.trim() || loading}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent text-white transition-opacity disabled:opacity-40 hover:bg-accent/90"
          >
            {loading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Send size={15} />
            )}
          </button>
        </div>
        <p className="mt-1.5 text-[10px] text-muted-foreground">
          Answers grounded in regulatory corpus · not legal advice · Shift+Enter for new line
        </p>
      </div>

    </div>
  );
}
