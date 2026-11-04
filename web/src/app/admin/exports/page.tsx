"use client";
import { Download } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/admin/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useToast } from "@/components/ui/Toast";
import { API_ORIGIN, tokenStore } from "@/lib/api";

const exportsList = [
  { kind: "users", title: "Users", body: "Accounts with role, status and phone confirmation." },
  { kind: "sellers", title: "Sellers", body: "Shops with verification, trust level and deal counts." },
  { kind: "listings", title: "Listings", body: "All listings with status, price and views." },
  { kind: "searches", title: "Searches", body: "Every search including ones with no results." },
  { kind: "activity-log", title: "Activity log", body: "Every Admin action with who, when and why." },
];

export default function AdminExports() {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);

  async function download(kind: string) {
    setBusy(kind);
    try {
      const res = await fetch(`${API_ORIGIN}/api/v1/admin/exports/${kind}.csv`, { headers: { Authorization: `Bearer ${tokenStore.get()}` } });
      if (!res.ok) throw new Error("Export failed");
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = `${kind}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast(`${kind}.csv downloaded`);
    } catch {
      toast("Could not export. Try again.", "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <PageHeader title="CSV exports" />
      <p className="mb-4 text-sm text-muted">Each export is recorded in the activity log. Handle downloaded files carefully: they contain personal data.</p>
      <ul className="grid gap-3 md:grid-cols-2">
        {exportsList.map((e) => (
          <li key={e.kind}>
            <Card className="flex h-full flex-col justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold">{e.title}</h2>
                <p className="text-sm text-muted">{e.body}</p>
              </div>
              <Button variant="tertiary" className="self-start" loading={busy === e.kind} onClick={() => void download(e.kind)}>
                <Download className="size-4" aria-hidden="true" />
                Download CSV
              </Button>
            </Card>
          </li>
        ))}
      </ul>
    </>
  );
}
