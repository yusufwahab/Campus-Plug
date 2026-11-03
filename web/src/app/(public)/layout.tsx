import type { ReactNode } from "react";
import { PublicShell } from "@/components/layout/PublicShell";
import { Footer } from "@/components/layout/Footer";

export default function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <PublicShell>
        {children}
        <Footer />
      </PublicShell>
    </>
  );
}
