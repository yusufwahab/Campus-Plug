import type { Metadata } from "next";
import { ProsePage } from "@/components/layout/Prose";
import { loadPolicy } from "@/lib/policy";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Privacy policy", description: "How Campus Plug handles your information." };

export default async function PrivacyPage() {
  return <ProsePage {...await loadPolicy("privacy")} />;
}
