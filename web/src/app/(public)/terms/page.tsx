import type { Metadata } from "next";
import { ProsePage } from "@/components/layout/Prose";
import { loadPolicy } from "@/lib/policy";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Terms of use", description: "How Campus Plug works for buyers and sellers." };

export default async function TermsPage() {
  return <ProsePage {...await loadPolicy("terms")} />;
}
