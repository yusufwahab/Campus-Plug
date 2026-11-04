import type { Metadata } from "next";
import { ProsePage } from "@/components/layout/Prose";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/States";
import { serverApi } from "@/lib/server-api";
import type { components } from "@/lib/api-schema";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Banned items", description: "Items that may not be listed on Campus Plug." };

export default async function BannedItemsPage() {
  const items = await serverApi<components["schemas"]["BannedItemPublic"][]>("/banned-items");
  return (
    <ProsePage title="Banned items" intro="You may not list these on Campus Plug. Listings that break this list are removed.">
      {items.length ? (
        <ul className="space-y-2">
          {items.map((i) => (
            <li key={i.id} className="rounded-card border border-line bg-white p-4">
              <p className="flex flex-wrap items-center gap-2 font-bold">
                {i.name} {i.extra_review && <Badge tone="pending">Extra review</Badge>}
              </p>
              {i.reason && <p className="text-sm text-muted">{i.reason}</p>}
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title="The list is being prepared" body="Illegal items, weapons, drugs and counterfeit goods are never allowed." />
      )}
    </ProsePage>
  );
}
