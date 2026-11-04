"use client";
import Link from "next/link";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader, SearchBar } from "@/components/admin/PageHeader";
import { ReasonModal } from "@/components/admin/ReasonModal";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import type { components } from "@/lib/api-schema";
import { useAction, useApiQuery, useDebounced } from "@/lib/hooks";

type Seller = components["schemas"]["SellerRow"];

export default function AdminSellers() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const search = useDebounced(q);
  const sellers = useApiQuery<Seller[]>(["admin-sellers"], "/admin/sellers", { q: search, page });
  const act = useAction([["admin-sellers"]]);
  const [badge, setBadge] = useState<Seller | null>(null);
  const [commission, setCommission] = useState<Seller | null>(null);
  const [percent, setPercent] = useState("");

  return (
    <>
      <PageHeader title="Sellers" />
      <SearchBar value={q} onChange={(v) => { setQ(v); setPage(1); }} label="Search shop, email or CP-SL ID" />
      <DataTable
        label="Sellers"
        rows={sellers.data}
        loading={sellers.isPending}
        error={sellers.isError ? sellers.error.message : null}
        onRetry={() => void sellers.refetch()}
        rowKey={(s) => s.public_id}
        page={page}
        onPage={setPage}
        empty={{ title: "No sellers match", body: "Try a shop name, an email or an ID like CP-SL-2001." }}
        columns={[
          { key: "shop", header: "Shop", render: (s) => <Link href={`/shop/${s.slug}`} className="font-semibold underline">{s.name}</Link> },
          { key: "id", header: "ID", render: (s) => s.public_id },
          { key: "owner", header: "Owner", render: (s) => s.owner_email },
          { key: "v", header: "Verification", render: (s) => <Badge tone={s.verification_status === "verified" ? "verified" : "pending"}>{s.verification_status}</Badge> },
          { key: "t", header: "Trust", render: (s) => s.trust_level.replace(/_/g, " ") },
          { key: "c", header: "Commission", render: (s) => (s.commission_override_bps === null || s.commission_override_bps === undefined ? "Default" : `${s.commission_override_bps / 100}%`) },
          { key: "l", header: "Listings", render: (s) => s.listings },
        ]}
        actions={(s) => (
          <>
            {s.verification_status === "verified" && <Button variant="danger" onClick={() => setBadge(s)}>Remove badge</Button>}
            <Button variant="tertiary" onClick={() => { setCommission(s); setPercent(s.commission_override_bps === null || s.commission_override_bps === undefined ? "" : String(s.commission_override_bps / 100)); }}>Commission</Button>
          </>
        )}
      />
      {badge && (
        <ReasonModal open title={`Remove ${badge.name}'s verified badge?`} description="They lose in-app payments and the unlimited listing limit until they are verified again." confirmLabel="Remove badge" destructive onConfirm={(reason) => act("POST", `/admin/sellers/${badge.public_id}/remove-badge`, { reason }, "Badge removed").then(() => undefined)} onClose={() => setBadge(null)} />
      )}
      {commission && (
        <ReasonModal
          open
          title={`Commission for ${commission.name}`}
          description="Applies to new orders only. Orders already placed keep the rate they were created with. Leave empty to use the default."
          confirmLabel="Change commission"
          onConfirm={(reason) => {
            const bps = percent.trim() === "" ? null : Math.round(Number(percent) * 100);
            if (bps !== null && (Number.isNaN(bps) || bps < 0 || bps > 10000)) return Promise.reject(new Error("Enter a percentage between 0 and 100"));
            return act("POST", `/admin/sellers/${commission.public_id}/commission`, { commission_override_bps: bps, reason }, "Commission updated").then(() => undefined);
          }}
          onClose={() => setCommission(null)}
        >
          <Input label="Commission (%)" inputMode="decimal" value={percent} onChange={(e) => setPercent(e.target.value)} hint="For example 15 for 15%." />
        </ReasonModal>
      )}
    </>
  );
}
