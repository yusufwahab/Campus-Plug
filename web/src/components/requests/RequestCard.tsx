import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { components } from "@/lib/api-schema";
import { naira, timeAgo } from "@/lib/format";

type Req = components["schemas"]["RequestOut"];

export function RequestCard({ r }: { r: Req }) {
  return (
    <Card className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {r.category_name && <Badge tone="neutral">{r.category_name}</Badge>}
        {r.budget_kobo && <Badge tone="info">Budget {naira(r.budget_kobo)}</Badge>}
        {r.mine && <Badge tone="verified">Your request</Badge>}
        <span className="text-xs text-muted">{timeAgo(r.created_at)}</span>
      </div>
      <h2 className="font-heading text-lg font-bold">
        <Link href={`/requests/${r.id}`} className="hover:underline">{r.title}</Link>
      </h2>
      {r.description && <p className="line-clamp-2 text-sm text-muted">{r.description}</p>}
      <p className="text-xs text-muted">
        {r.buyer_first_name}
        {r.location_name ? ` · ${r.location_name}` : ""} · {r.responses} {r.responses === 1 ? "reply" : "replies"}
      </p>
    </Card>
  );
}
