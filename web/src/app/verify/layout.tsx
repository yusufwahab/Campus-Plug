import type { ReactNode } from "react";
import { PublicShell } from "@/components/layout/PublicShell";
import { RequireAuth } from "@/lib/auth";

export default function VerifyLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth need="verifier">
      <PublicShell>{children}</PublicShell>
    </RequireAuth>
  );
}
