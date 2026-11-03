import type { ReactNode } from "react";
import { DashboardShell } from "@/components/layout/DashboardShell";

export default function SellerLayout({ children }: { children: ReactNode }) {
  return <DashboardShell kind="seller">{children}</DashboardShell>;
}
