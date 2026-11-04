"use client";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader } from "@/components/admin/PageHeader";
import { ReasonModal } from "@/components/admin/ReasonModal";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import type { components } from "@/lib/api-schema";
import { useAction, useApiQuery } from "@/lib/hooks";

type Cat = components["schemas"]["CategoryAdmin"];
const empty = { slug: "", name: "", tint: "mint", enabled: true, requires_verification: false, commission_pct: "" };

export default function AdminCategories() {
  const cats = useApiQuery<Cat[]>(["admin-categories"], "/admin/categories");
  const act = useAction([["admin-categories"]]);
  const [editing, setEditing] = useState<Cat | "new" | null>(null);
  const [form, setForm] = useState(empty);
  const set = (patch: Partial<typeof empty>) => setForm((f) => ({ ...f, ...patch }));

  function open(c: Cat | "new") {
    setEditing(c);
    setForm(c === "new" ? empty : { slug: c.slug, name: c.name, tint: c.tint, enabled: c.enabled, requires_verification: c.requires_verification, commission_pct: c.commission_override_bps == null ? "" : String(c.commission_override_bps / 100) });
  }

  return (
    <>
      <PageHeader title="Categories">
        <Button onClick={() => open("new")}>New category</Button>
      </PageHeader>
      <DataTable
        label="Categories"
        rows={cats.data}
        loading={cats.isPending}
        error={cats.isError ? cats.error.message : null}
        onRetry={() => void cats.refetch()}
        rowKey={(c) => c.id}
        columns={[
          { key: "n", header: "Name", render: (c) => c.name },
          { key: "s", header: "Slug", render: (c) => c.slug },
          { key: "e", header: "Status", render: (c) => <Badge tone={c.enabled ? "verified" : "neutral"}>{c.enabled ? "Enabled" : "Hidden"}</Badge> },
          { key: "v", header: "Needs verification", render: (c) => (c.requires_verification ? "Yes" : "No") },
          { key: "c", header: "Commission", render: (c) => (c.commission_override_bps == null ? "Default" : `${c.commission_override_bps / 100}%`) },
        ]}
        actions={(c) => <Button variant="tertiary" onClick={() => open(c)}>Edit</Button>}
      />
      {editing && (
        <ReasonModal
          open
          title={editing === "new" ? "New category" : `Edit ${editing.name}`}
          confirmLabel={editing === "new" ? "Create category" : "Save category"}
          onConfirm={(reason) => {
            const bps = form.commission_pct.trim() === "" ? null : Math.round(Number(form.commission_pct) * 100);
            const body = { slug: form.slug, name: form.name, tint: form.tint, enabled: form.enabled, requires_verification: form.requires_verification, commission_override_bps: bps, reason };
            return (editing === "new" ? act("POST", "/admin/categories", body, "Category created") : act("PUT", `/admin/categories/${editing.id}`, body, "Category saved")).then(() => undefined);
          }}
          onClose={() => setEditing(null)}
        >
          <Input label="Name" value={form.name} onChange={(e) => set({ name: e.target.value })} />
          <Input label="Slug" value={form.slug} onChange={(e) => set({ slug: e.target.value })} hint="Lowercase letters, numbers and dashes. Used in the web address." />
          <Select label="Colour" value={form.tint} onChange={(e) => set({ tint: e.target.value })}>
            {["peach", "lilac", "sky", "butter", "mint"].map((t) => <option key={t} value={t}>{t}</option>)}
          </Select>
          <Input label="Commission override (%)" inputMode="decimal" value={form.commission_pct} onChange={(e) => set({ commission_pct: e.target.value })} hint="Empty uses the platform default. Applies to new orders only." />
          <label className="flex min-h-11 items-center gap-3 text-sm font-semibold"><input type="checkbox" className="size-5 accent-forest" checked={form.enabled} onChange={(e) => set({ enabled: e.target.checked })} /> Visible to sellers and buyers</label>
          <label className="flex min-h-11 items-center gap-3 text-sm font-semibold"><input type="checkbox" className="size-5 accent-forest" checked={form.requires_verification} onChange={(e) => set({ requires_verification: e.target.checked })} /> Sellers must be verified to list here</label>
        </ReasonModal>
      )}
    </>
  );
}
