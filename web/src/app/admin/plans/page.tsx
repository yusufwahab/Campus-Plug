"use client";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader } from "@/components/admin/PageHeader";
import { ReasonModal } from "@/components/admin/ReasonModal";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Field";
import type { components } from "@/lib/api-schema";
import { naira, nairaToKobo } from "@/lib/format";
import { useAction, useApiQuery } from "@/lib/hooks";

type Plan = components["schemas"]["PlanAdmin"];
const blank = { name: "", price: "", days: "30", bps: "", benefits: "" };

export default function AdminPlans() {
  const rows = useApiQuery<Plan[]>(["admin-plans"], "/admin/plans");
  const act = useAction([["admin-plans"]]);
  const [editing, setEditing] = useState<Plan | "new" | null>(null);
  const [form, setForm] = useState(blank);

  function edit(plan: Plan | "new") {
    setForm(plan === "new" ? blank : { name: plan.name, price: String(plan.price_kobo / 100), days: String(plan.period_days), bps: plan.commission_bps === null || plan.commission_bps === undefined ? "" : String(plan.commission_bps / 100), benefits: plan.benefits.join("\n") });
    setEditing(plan);
  }
  const payload = (reason: string, active = true) => ({
    name: form.name,
    price_kobo: nairaToKobo(Number(form.price)),
    period_days: Number(form.days),
    commission_bps: form.bps.trim() === "" ? null : Math.round(Number(form.bps) * 100),
    benefits: form.benefits.split("\n").map((b) => b.trim()).filter(Boolean),
    active,
    reason,
  });

  return (
    <>
      <PageHeader title="Plans">
        <Button onClick={() => edit("new")}>New plan</Button>
      </PageHeader>
      <p className="mb-3 max-w-prose text-sm text-muted">
        Price and commission changes apply to new purchases and new orders. Current subscribers keep what they paid for, and orders keep the rate they were created with.
      </p>
      <DataTable
        label="Plans"
        rows={rows.data}
        loading={rows.isPending}
        error={rows.isError ? rows.error.message : null}
        onRetry={() => void rows.refetch()}
        rowKey={(r) => r.id}
        empty={{ title: "No plans yet", body: "Create a premium plan sellers can buy." }}
        columns={[
          { key: "n", header: "Plan", render: (r) => <strong>{r.name}</strong> },
          { key: "p", header: "Price", render: (r) => `${naira(r.price_kobo)} / ${r.period_days} days` },
          { key: "c", header: "Commission", render: (r) => (r.commission_bps === null || r.commission_bps === undefined ? "Default" : `${r.commission_bps / 100}%`) },
          { key: "s", header: "Status", render: (r) => <Badge tone={r.active ? "verified" : "neutral"}>{r.active ? "On sale" : "Off sale"}</Badge> },
        ]}
        actions={(r) => <Button variant="tertiary" onClick={() => edit(r)}>Edit</Button>}
      />
      {editing && (
        <ReasonModal
          open
          title={editing === "new" ? "New plan" : `Edit ${editing.name}`}
          confirmLabel={editing === "new" ? "Create plan" : "Save plan"}
          onConfirm={(reason) =>
            (editing === "new" ? act("POST", "/admin/plans", payload(reason), "Plan created") : act("PUT", `/admin/plans/${editing.id}`, payload(reason, editing.active), "Plan saved")).then(() => undefined)
          }
          onClose={() => setEditing(null)}
        >
          <Input label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <Input label="Price (₦)" inputMode="numeric" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
          <Input label="Days" inputMode="numeric" value={form.days} onChange={(e) => setForm({ ...form, days: e.target.value })} />
          <Input label="Commission (%)" inputMode="decimal" value={form.bps} onChange={(e) => setForm({ ...form, bps: e.target.value })} hint="Leave empty to keep the default rate" />
          <Textarea label="Benefits (one per line)" value={form.benefits} onChange={(e) => setForm({ ...form, benefits: e.target.value })} />
        </ReasonModal>
      )}
    </>
  );
}
