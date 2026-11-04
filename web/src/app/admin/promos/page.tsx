"use client";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader } from "@/components/admin/PageHeader";
import { ReasonModal } from "@/components/admin/ReasonModal";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import type { components } from "@/lib/api-schema";
import { naira, nairaToKobo } from "@/lib/format";
import { useAction, useApiQuery } from "@/lib/hooks";

type Promo = components["schemas"]["PromoOut"];
const blank = { code: "", kind: "admin_buyer", percent: "", fixed: "", bps: "", min: "", limit: "" };

export default function AdminPromos() {
  const rows = useApiQuery<Promo[]>(["admin-promos"], "/admin/promos");
  const act = useAction([["admin-promos"]]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);
  const [toggle, setToggle] = useState<Promo | null>(null);

  function body(reason: string) {
    return {
      code: form.code,
      kind: form.kind,
      percent: form.kind === "admin_buyer" && form.percent ? Number(form.percent) : null,
      fixed_kobo: form.kind === "admin_buyer" && form.fixed ? nairaToKobo(Number(form.fixed)) : null,
      commission_bps: form.kind === "admin_seller" ? Math.round(Number(form.bps) * 100) : null,
      min_spend_kobo: form.min ? nairaToKobo(Number(form.min)) : 0,
      usage_limit: form.limit ? Number(form.limit) : null,
      reason,
    };
  }

  return (
    <>
      <PageHeader title="Promo codes">
        <Button onClick={() => { setForm(blank); setOpen(true); }}>New code</Button>
      </PageHeader>
      <p className="mb-3 max-w-prose text-sm text-muted">
        Campaign codes give buyers a discount that Campus Plug pays for, so seller payouts do not change. Seller commission codes lower a shop&apos;s commission on new orders.
      </p>
      <DataTable
        label="Promo codes"
        rows={rows.data}
        loading={rows.isPending}
        error={rows.isError ? rows.error.message : null}
        onRetry={() => void rows.refetch()}
        rowKey={(r) => r.id}
        empty={{ title: "No codes yet", body: "Create a campaign code or a seller commission code." }}
        columns={[
          { key: "c", header: "Code", render: (r) => <strong>{r.code}</strong> },
          { key: "k", header: "Type", render: (r) => (r.kind === "admin_seller" ? "Seller commission" : "Buyer campaign") },
          { key: "v", header: "Value", render: (r) => (r.kind === "admin_seller" ? `${(r.commission_bps ?? 0) / 100}% commission` : r.percent ? `${r.percent}% off` : `${naira(r.fixed_kobo ?? 0)} off`) },
          { key: "u", header: "Used", render: (r) => `${r.used}${r.usage_limit ? ` of ${r.usage_limit}` : ""}` },
          { key: "s", header: "Status", render: (r) => <Badge tone={r.active ? "verified" : "neutral"}>{r.active ? "Active" : "Off"}</Badge> },
        ]}
        actions={(r) => <Button variant="tertiary" onClick={() => setToggle(r)}>{r.active ? "Turn off" : "Turn on"}</Button>}
      />
      <ReasonModal
        open={open}
        title="New promo code"
        confirmLabel="Create code"
        onConfirm={(reason) => act("POST", "/admin/promos", body(reason), "Code created").then(() => undefined)}
        onClose={() => setOpen(false)}
      >
        <Input label="Code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} hint="3 to 20 letters or numbers" />
        <Select label="Type" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
          <option value="admin_buyer">Buyer campaign (Campus Plug pays)</option>
          <option value="admin_seller">Seller commission rate</option>
        </Select>
        {form.kind === "admin_buyer" ? (
          <>
            <Input label="Percent off" inputMode="numeric" value={form.percent} onChange={(e) => setForm({ ...form, percent: e.target.value, fixed: "" })} hint="Or use a fixed amount below" />
            <Input label="Fixed amount off (₦)" inputMode="numeric" value={form.fixed} onChange={(e) => setForm({ ...form, fixed: e.target.value, percent: "" })} />
          </>
        ) : (
          <Input label="Commission (%)" inputMode="decimal" value={form.bps} onChange={(e) => setForm({ ...form, bps: e.target.value })} />
        )}
        <Input label="Minimum spend (₦)" inputMode="numeric" value={form.min} onChange={(e) => setForm({ ...form, min: e.target.value })} hint="Optional" />
        <Input label="Uses allowed" inputMode="numeric" value={form.limit} onChange={(e) => setForm({ ...form, limit: e.target.value })} hint="Optional" />
      </ReasonModal>
      {toggle && (
        <ReasonModal
          open
          title={`${toggle.active ? "Turn off" : "Turn on"} ${toggle.code}?`}
          confirmLabel={toggle.active ? "Turn off" : "Turn on"}
          onConfirm={(reason) => act("POST", `/admin/promos/${toggle.id}/active`, { active: !toggle.active, reason }, "Code updated").then(() => undefined)}
          onClose={() => setToggle(null)}
        />
      )}
    </>
  );
}
