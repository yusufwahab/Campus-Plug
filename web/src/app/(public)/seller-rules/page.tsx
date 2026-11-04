import type { Metadata } from "next";
import Link from "next/link";
import { ProsePage } from "@/components/layout/Prose";
import { loadPolicy } from "@/lib/policy";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Seller rules", description: "Rules every seller accepts before opening a shop." };

export default async function SellerRulesPage() {
  return (
    <ProsePage {...await loadPolicy("seller-rules")}>
      <p>
        See the <Link href="/banned-items" className="font-semibold underline">banned items list</Link>.
      </p>
    </ProsePage>
  );
}
