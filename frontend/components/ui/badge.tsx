import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] border px-2 py-0.5 font-mono text-[0.7rem] font-medium tracking-[0.04em] uppercase transition-colors",
  {
    variants: {
      variant: {
        default: "border-line text-ink-muted bg-surface-muted",
        outline: "border-line text-ink-muted",
        accent: "border-accent/40 bg-accent-wash text-accent",
        success: "border-accent/40 bg-accent-wash text-accent",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
