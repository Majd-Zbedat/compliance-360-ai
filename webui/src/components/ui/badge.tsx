import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        outline: "text-foreground",
        risk_high: "border-transparent bg-risk-high/10 text-risk-high",
        risk_medium: "border-transparent bg-risk-medium/15 text-risk-medium",
        risk_low: "border-transparent bg-risk-low/15 text-risk-low",
        status: "border-transparent bg-muted text-muted-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export function RiskBadge({ risk }: { risk: string }) {
  const variant =
    risk === "High" ? "risk_high" : risk === "Medium" ? "risk_medium" : "risk_low";
  return (
    <Badge variant={variant} className="uppercase tracking-wide">
      {risk}
    </Badge>
  );
}
