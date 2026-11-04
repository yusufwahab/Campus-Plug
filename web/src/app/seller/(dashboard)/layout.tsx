import type { ReactNode } from "react";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { RequireAuth } from "@/lib/auth";

export default function SellerLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth need="seller">
      <DashboardShell kind="seller">{children}</DashboardShell>
    </RequireAuth>
  );
}
