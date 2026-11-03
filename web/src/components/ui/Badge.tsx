import clsx from "clsx";
import type { ReactNode } from "react";

export type BadgeTone = "verified" | "pending" | "info" | "danger" | "neutral";

const tones: Record<BadgeTone, string> = {
  verified: "bg-verified-bg text-verified-fg",
  pending: "bg-pending-bg text-pending-fg",
  info: "bg-info-bg text-info-fg",
  danger: "bg-danger-bg text-danger-fg",
  neutral: "bg-line text-ink",
};

export function Badge({ tone = "neutral", children, className }: { tone?: BadgeTone; children: ReactNode; className?: string }) {
  return (
    <span className={clsx("inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold", tones[tone], className)}>
      {children}
    </span>
  );
}
