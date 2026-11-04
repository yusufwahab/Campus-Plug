"use client";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader } from "@/components/admin/PageHeader";
import { PublicShell } from "@/components/layout/PublicShell";
import { FormError } from "@/components/auth/AuthCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { RequestCard } from "@/components/requests/RequestCard";
import { ApiError } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { RequireAuth } from "@/lib/auth";
import { useAction, useApiQuery } from "@/lib/hooks";

type Seller = components["schemas"]["SellerOut"];
type Req = components["schemas"]["RequestOut"];

function Rep() {
  const sellers = useApiQuery<Seller[]>(["rep-sellers"], "/rep/sellers");
  const requests = useApiQuery<Req[]>(["rep-requests"], "/rep/requests");
  const act = useAction([["rep-sellers"]]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ email: "", shop_name: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onboard(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await act("POST", "/rep/sellers", form, "Seller onboarded");
      setOpen(false);
      setForm({ email: "", shop_name: "" });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not onboard that seller.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Hall Rep">
        <Button onClick={() => setOpen(true)}>Onboard a seller</Button>
      </PageHeader>
      <p className="mb-4 text-sm text-muted">Sellers you onboarded and sellers in your hall. You can vouch for sellers you trust. You cannot see student IDs or approve sellers.</p>
      <DataTable
        label="Sellers"
        rows={sellers.data}
        loading={sellers.isPending}
        error={sellers.isError ? sellers.error.message : null}
        onRetry={() => void sellers.refetch()}
        rowKey={(s) => s.public_id}
        empty={{ title: "No sellers yet", body: "Onboard a student who already has an account to open their shop." }}
        columns={[
          { key: "n", header: "Shop", render: (s) => s.name },
          { key: "id", header: "ID", render: (s) => s.public_id },
          { key: "v", header: "Verification", render: (s) => <Badge tone={s.verification_status === "verified" ? "verified" : "pending"}>{s.verification_status}</Badge> },
          { key: "vouch", header: "Vouched", render: (s) => (s.vouched_by_rep ? "Yes" : "No") },
        ]}
        actions={(s) => (s.vouched_by_rep ? null : <Button variant="secondary" onClick={() => void act("POST", `/rep/sellers/${s.public_id}/vouch`, undefined, `You vouched for ${s.name}`)}>Vouch</Button>)}
      />
      <h2 className="mb-2 mt-8 text-lg font-bold">Requests in your hall</h2>
      {requests.isPending && <p role="status" className="text-sm text-muted">Loading requests</p>}
      {requests.isError && <p role="alert" className="text-sm text-danger-fg">{requests.error.message}</p>}
      {requests.data && !requests.data.length && <p className="rounded-card bg-white p-4 text-sm text-muted">No open requests in your hall right now.</p>}
      {requests.data && requests.data.length > 0 && (
        <ul className="grid gap-3 md:grid-cols-2">
          {requests.data.map((r) => <li key={r.id}><RequestCard r={r} /></li>)}
        </ul>
      )}
      <Modal open={open} title="Onboard a seller" onClose={() => setOpen(false)} dirty={!!form.email}>
        <form onSubmit={onboard} className="space-y-3" noValidate>
          <p className="text-sm text-muted">They must already have an account with a confirmed email address. They accept the seller rules the first time they sign in.</p>
          <Input label="Their account email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <Input label="Shop name" value={form.shop_name} onChange={(e) => setForm({ ...form, shop_name: e.target.value })} />
          <FormError message={error} />
          <Button type="submit" className="w-full" loading={busy}>Open their shop</Button>
        </form>
      </Modal>
    </>
  );
}

export default function RepPage() {
  return (
    <RequireAuth need="hall_rep">
      <PublicShell>
        <Rep />
      </PublicShell>
    </RequireAuth>
  );
}
