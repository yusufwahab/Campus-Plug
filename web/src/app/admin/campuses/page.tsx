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

type Campus = components["schemas"]["CampusAdmin"];
type Location = components["schemas"]["LocationAdmin"];

export default function AdminCampuses() {
  const campuses = useApiQuery<Campus[]>(["admin-campuses"], "/admin/campuses");
  const locations = useApiQuery<Location[]>(["admin-locations"], "/admin/locations");
  const act = useAction([["admin-campuses"], ["admin-locations"]]);
  const [campus, setCampus] = useState<Campus | "new" | null>(null);
  const [loc, setLoc] = useState<Location | "new" | null>(null);
  const [cf, setCf] = useState({ slug: "", name: "", enabled: false });
  const [lf, setLf] = useState({ campus_id: "", name: "", kind: "hall", enabled: true });

  return (
    <>
      <PageHeader title="Campuses and locations">
        <Button onClick={() => { setCf({ slug: "", name: "", enabled: false }); setCampus("new"); }}>New campus</Button>
        <Button variant="tertiary" onClick={() => { setLf({ campus_id: String(campuses.data?.[0]?.id ?? ""), name: "", kind: "hall", enabled: true }); setLoc("new"); }}>New location</Button>
      </PageHeader>

      <h2 className="mb-2 text-lg font-bold">Campuses</h2>
      <DataTable
        label="Campuses"
        rows={campuses.data}
        loading={campuses.isPending}
        error={campuses.isError ? campuses.error.message : null}
        onRetry={() => void campuses.refetch()}
        rowKey={(c) => c.id}
        columns={[
          { key: "n", header: "Name", render: (c) => c.name },
          { key: "s", header: "Slug", render: (c) => c.slug },
          { key: "e", header: "Status", render: (c) => <Badge tone={c.enabled ? "verified" : "neutral"}>{c.enabled ? "Live" : "Not live"}</Badge> },
        ]}
        actions={(c) => <Button variant="tertiary" onClick={() => { setCf({ slug: c.slug, name: c.name, enabled: c.enabled }); setCampus(c); }}>Edit</Button>}
      />

      <h2 className="mb-2 mt-8 text-lg font-bold">Locations</h2>
      <DataTable
        label="Locations"
        rows={locations.data}
        loading={locations.isPending}
        error={locations.isError ? locations.error.message : null}
        onRetry={() => void locations.refetch()}
        rowKey={(l) => l.id}
        columns={[
          { key: "n", header: "Name", render: (l) => l.name },
          { key: "c", header: "Campus", render: (l) => campuses.data?.find((c) => c.id === l.campus_id)?.name ?? l.campus_id },
          { key: "k", header: "Type", render: (l) => l.kind },
          { key: "e", header: "Status", render: (l) => <Badge tone={l.enabled ? "verified" : "neutral"}>{l.enabled ? "Shown" : "Hidden"}</Badge> },
        ]}
        actions={(l) => <Button variant="tertiary" onClick={() => { setLf({ campus_id: String(l.campus_id), name: l.name, kind: l.kind, enabled: l.enabled }); setLoc(l); }}>Edit</Button>}
      />

      {campus && (
        <ReasonModal
          open
          title={campus === "new" ? "New campus" : `Edit ${campus.name}`}
          description="Only campuses marked live appear to buyers and sellers."
          confirmLabel="Save campus"
          onConfirm={(reason) => (campus === "new" ? act("POST", "/admin/campuses", { ...cf, reason }, "Campus created") : act("PUT", `/admin/campuses/${campus.id}`, { ...cf, reason }, "Campus saved")).then(() => undefined)}
          onClose={() => setCampus(null)}
        >
          <Input label="Name" value={cf.name} onChange={(e) => setCf({ ...cf, name: e.target.value })} />
          <Input label="Slug" value={cf.slug} disabled={campus !== "new"} onChange={(e) => setCf({ ...cf, slug: e.target.value })} hint="Lowercase letters, numbers and dashes." />
          <label className="flex min-h-11 items-center gap-3 text-sm font-semibold"><input type="checkbox" className="size-5 accent-forest" checked={cf.enabled} onChange={(e) => setCf({ ...cf, enabled: e.target.checked })} /> Live for buyers and sellers</label>
        </ReasonModal>
      )}
      {loc && (
        <ReasonModal
          open
          title={loc === "new" ? "New location" : `Edit ${loc.name}`}
          description="Locations are halls or general areas. Never add room numbers or map pins."
          confirmLabel="Save location"
          onConfirm={(reason) => (loc === "new" ? act("POST", "/admin/locations", { ...lf, campus_id: Number(lf.campus_id), reason }, "Location created") : act("PUT", `/admin/locations/${loc.id}`, { ...lf, campus_id: Number(lf.campus_id), reason }, "Location saved")).then(() => undefined)}
          onClose={() => setLoc(null)}
        >
          <Select label="Campus" value={lf.campus_id} disabled={loc !== "new"} onChange={(e) => setLf({ ...lf, campus_id: e.target.value })}>
            {campuses.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
          <Input label="Name" value={lf.name} onChange={(e) => setLf({ ...lf, name: e.target.value })} />
          <Select label="Type" value={lf.kind} onChange={(e) => setLf({ ...lf, kind: e.target.value })}>
            <option value="hall">Hall</option>
            <option value="area">General area</option>
          </Select>
          <label className="flex min-h-11 items-center gap-3 text-sm font-semibold"><input type="checkbox" className="size-5 accent-forest" checked={lf.enabled} onChange={(e) => setLf({ ...lf, enabled: e.target.checked })} /> Shown to users</label>
        </ReasonModal>
      )}
    </>
  );
}
