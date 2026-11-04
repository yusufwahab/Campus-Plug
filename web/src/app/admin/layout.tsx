import type { ReactNode } from "react";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { RequireAuth } from "@/lib/auth";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth need="admin">
      <DashboardShell kind="admin">{children}</DashboardShell>
    </RequireAuth>
  );
}
