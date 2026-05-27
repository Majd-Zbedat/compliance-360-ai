"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Bell,
  BookOpen,
  ChevronDown,
  FileText,
  LayoutDashboard,
  MessageSquare,
  Search,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/audits", label: "Documents", icon: FileText },
  { href: "/regulations", label: "Regulations", icon: BookOpen },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
];

const crumbs: Record<string, string> = {
  "/": "Dashboard",
  "/audits": "Document Management",
  "/audits/new": "New Audit",
  "/regulations": "Regulation Library",
  "/analytics": "Analytics & Risk Intelligence",
};

function breadcrumbLabel(pathname: string | null) {
  if (!pathname) return "Dashboard";
  if (crumbs[pathname]) return crumbs[pathname];
  if (pathname.startsWith("/audits/")) return "Document Management";
  return "Dashboard";
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const pageLabel = breadcrumbLabel(pathname);

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="hidden w-[220px] shrink-0 flex-col bg-sidebar text-sidebar-foreground lg:flex">
        <div className="border-b border-white/10 px-5 py-5">
          <div className="mb-4 flex items-center gap-2.5">
            <div className="grid h-7 w-7 place-items-center rounded bg-accent">
              <ShieldCheck className="h-3.5 w-3.5 text-white" />
            </div>
            <div>
              <div className="text-sm font-bold leading-tight tracking-tight text-white">Compliance</div>
              <div className="text-xs font-bold leading-tight tracking-wider text-accent">360°</div>
            </div>
          </div>
          <button
            type="button"
            className="flex w-full items-center justify-between rounded-md border border-white/10 bg-white/5 px-3 py-2 text-left text-xs text-white/80"
          >
            <span className="truncate font-medium">GlobalCorp International</span>
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-white/50" />
          </button>
        </div>

        <nav className="flex-1 space-y-0.5 px-3 pt-4">
          <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-widest text-white/30">
            Main Menu
          </p>
          {navItems.map((item) => {
            const Icon = item.icon;
            const active =
              item.href === "/"
                ? pathname === "/"
                : item.href === "/audits"
                  ? pathname?.startsWith("/audits")
                  : pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md border-l-2 px-3 py-2.5 text-sm font-medium transition-colors duration-150",
                  active
                    ? "border-accent bg-sidebar-accent text-accent"
                    : "border-transparent text-white/60 hover:text-white/80",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="space-y-1 border-t border-white/10 px-3 pb-4 pt-3">
          <Link
            href="#"
            className="flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium text-white/60 hover:text-white/80"
          >
            <Settings className="h-4 w-4" />
            Settings
          </Link>
          <div className="mt-2 flex items-center gap-3 rounded-lg bg-white/5 p-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-white">
              SC
            </div>
            <div className="min-w-0">
              <p className="truncate text-xs font-semibold text-white">Sarah Chen</p>
              <p className="truncate text-[10px] text-white/50">Chief Compliance Officer</p>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border bg-card px-7">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Compliance 360</span>
            <span className="text-muted-foreground/50">&gt;</span>
            <span className="font-medium text-brand-ink">{pageLabel}</span>
          </div>
          <div className="flex items-center gap-3">
            <button type="button" className="rounded-md p-2 text-muted-foreground hover:bg-muted">
              <Search className="h-4 w-4" />
            </button>
            <AssistantSheet />
            <button type="button" className="relative rounded-md p-2 text-muted-foreground hover:bg-muted">
              <Bell className="h-4 w-4" />
              <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500" />
            </button>
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white">
              SC
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}

function AssistantSheet() {
  return (
    <Sheet>
      <SheetTrigger>
        <button
          type="button"
          className="inline-flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted"
          aria-label="Open compliance assistant"
        >
          <MessageSquare className="h-4 w-4" />
        </button>
      </SheetTrigger>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Compliance assistant</SheetTitle>
          <SheetDescription>
            Local Ollama chat sidebar (wire your model in a follow-up turn).
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-3 text-sm">
          <div className="rounded-lg border border-border bg-muted/40 p-3">
            <div className="font-medium">System</div>
            <p className="mt-1 text-muted-foreground">
              I can answer questions about the regulatory corpus and surface relevant clauses, but I
              do <em>not</em> provide unqualified legal advice.
            </p>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
