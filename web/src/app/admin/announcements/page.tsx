"use client";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader } from "@/components/admin/PageHeader";
import { ReasonModal } from "@/components/admin/ReasonModal";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input, Select, Textarea } from "@/components/ui/Field";
import type { components } from "@/lib/api-schema";
import { useAction, useApiQuery } from "@/lib/hooks";

type Row = components["schemas"]["AnnouncementOut"];

export default function AdminAnnouncements() {
  const rows = useApiQuery<Row[]>(["admin-announcements"], "/admin/announcements");
  const act = useAction([["admin-announcements"], ["announcements"]]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", body: "", audience: "all" });

  return (
    <>
      <PageHeader title="Announcements">
        <Button onClick={() => { setForm({ title: "", body: "", audience: "all" }); setOpen(true); }}>New announcement</Button>
      </PageHeader>
      <DataTable
        label="Announcements"
        rows={rows.data}
        loading={rows.isPending}
        error={rows.isError ? rows.error.message : null}
        onRetry={() => void rows.refetch()}
        rowKey={(r) => r.id}
        empty={{ title: "No announcements", body: "Announcements show as a banner to the audience you choose." }}
        columns={[
          { key: "t", header: "Title", render: (r) => r.title },
          { key: "a", header: "Audience", render: (r) => r.audience },
          { key: "s", header: "Status", render: (r) => <Badge tone={r.active ? "verified" : "neutral"}>{r.active ? "Showing" : "Hidden"}</Badge> },
        ]}
        actions={(r) => <Button variant="tertiary" onClick={() => void act("POST", `/admin/announcements/${r.id}/active`, undefined, r.active ? "Announcement hidden" : "Announcement shown", { active: !r.active })}>{r.active ? "Hide" : "Show"}</Button>}
      />
      <ReasonModal
        open={open}
        title="New announcement"
        description="Shown as a banner on the marketplace. Not an email or push message."
        confirmLabel="Publish announcement"
        onConfirm={() => act("POST", "/admin/announcements", form, "Announcement published").then(() => undefined)}
        onClose={() => setOpen(false)}
      >
        <Input label="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <Textarea label="Message" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} />
        <Select label="Audience" value={form.audience} onChange={(e) => setForm({ ...form, audience: e.target.value })}>
          <option value="all">Everyone</option>
          <option value="sellers">Sellers</option>
          <option value="buyers">Buyers</option>
        </Select>
      </ReasonModal>
    </>
  );
}
