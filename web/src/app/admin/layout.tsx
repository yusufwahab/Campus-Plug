import type { ReactNode } from "react";
import { DashboardShell } from "@/components/layout/DashboardShell";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return <DashboardShell kind="admin">{children}</DashboardShell>;
}
