/**
 * AuditTable — styled to match the Figma Make "Document Management" table.
 *
 * Figma MCP inspection (App.tsx DocumentsScreen / RegulationsScreen):
 *
 * Container:
 *   bg-white rounded-lg border overflow-hidden
 *   border-color: rgba(0,0,0,0.07)  → border-border + shadow-card
 *
 * Header row (<thead><tr>):
 *   background: #F8F9FA              → bg-table-header
 *   <th> px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider
 *        color: #6B7A8D              → text-muted-foreground
 *
 * Body row (<tr>):
 *   border-t border-color rgba(0,0,0,0.05) → border-t border-table-row-border
 *   hover:bg-gray-50 transition-colors cursor-pointer
 *
 * Body cell (<td>):
 *   px-4 py-3
 */

import * as React from "react";
import { cn } from "@/lib/utils";

/** Card shell wrapping the scrollable table (Figma table container). */
export function AuditTable({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-card shadow-card",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Optional toolbar row above the table (search / filters). */
export function AuditTableToolbar({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 border-b border-border p-4",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function AuditTableScroll({ children }: { children: React.ReactNode }) {
  return <div className="overflow-x-auto">{children}</div>;
}

export const AuditTableElement = React.forwardRef<
  HTMLTableElement,
  React.HTMLAttributes<HTMLTableElement>
>(({ className, ...props }, ref) => (
  <table ref={ref} className={cn("w-full caption-bottom text-sm", className)} {...props} />
));
AuditTableElement.displayName = "AuditTableElement";

export const AuditTableHeader = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <thead ref={ref} className={cn(className)} {...props} />
));
AuditTableHeader.displayName = "AuditTableHeader";

export const AuditTableBody = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tbody ref={ref} className={cn(className)} {...props} />
));
AuditTableBody.displayName = "AuditTableBody";

/** Header row — Figma: bg #F8F9FA */
export const AuditTableHeaderRow = React.forwardRef<
  HTMLTableRowElement,
  React.HTMLAttributes<HTMLTableRowElement>
>(({ className, ...props }, ref) => (
  <tr ref={ref} className={cn("bg-table-header", className)} {...props} />
));
AuditTableHeaderRow.displayName = "AuditTableHeaderRow";

/** Column heading — Figma: px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#6B7A8D] */
export const AuditTableHead = React.forwardRef<
  HTMLTableCellElement,
  React.ThHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <th
    ref={ref}
    className={cn(
      "px-4 py-3 text-left align-middle text-xs font-semibold uppercase tracking-wider text-muted-foreground",
      className,
    )}
    {...props}
  />
));
AuditTableHead.displayName = "AuditTableHead";

/** Data row — Figma: border-t rgba(0,0,0,0.05), hover gray-50 */
export const AuditTableRow = React.forwardRef<
  HTMLTableRowElement,
  React.HTMLAttributes<HTMLTableRowElement>
>(({ className, ...props }, ref) => (
  <tr
    ref={ref}
    className={cn(
      "cursor-pointer border-t border-table-row-border transition-colors hover:bg-gray-50",
      className,
    )}
    {...props}
  />
));
AuditTableRow.displayName = "AuditTableRow";

/** Data cell — Figma: px-4 py-3 */
export const AuditTableCell = React.forwardRef<
  HTMLTableCellElement,
  React.TdHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <td ref={ref} className={cn("px-4 py-3 align-middle", className)} {...props} />
));
AuditTableCell.displayName = "AuditTableCell";

/** Footer pagination bar — Figma: border-t rgba(0,0,0,0.07), px-4 py-3 */
export function AuditTableFooter({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-between border-t border-border px-4 py-3",
        className,
      )}
    >
      {children}
    </div>
  );
}
