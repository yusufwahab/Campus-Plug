"use client";
import clsx from "clsx";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader } from "@/components/admin/PageHeader";
import { ReasonModal } from "@/components/admin/ReasonModal";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import type { components } from "@/lib/api-schema";
import { policies } from "@/lib/content";
import { naira } from "@/lib/format";
import { useAction, useApiQuery } from "@/lib/hooks";

type Settings = { values: Record<string, unknown> };
type Banned = components["schemas"]["BannedItemPublic"];
type Kind = "bps" | "kobo" | "bool" | "int" | "list";
type Def = { key: string; label: string; help: string; kind: Kind; unit?: string; group: string };

const defs: Def[] = [
  { group: "Money", key: "commission_bps", label: "Default commission", help: "Charged on the item price after seller discounts, never on delivery. Applies to new orders only.", kind: "bps" },
  { group: "Money", key: "provider_fee_absorbed", label: "Platform absorbs payment provider fee", help: "When on, the provider fee comes out of Campus Plug's commission, not the seller's payout.", kind: "bool" },
  { group: "Money", key: "instant_split", label: "Instant split fallback", help: "Pay the seller straight away instead of holding funds. Only for when holding cannot be done safely.", kind: "bool" },
  { group: "Money", key: "high_value_threshold_kobo", label: "High-value price needing verification", help: "Listings at or above this price need a verified seller.", kind: "kobo" },
  { group: "Listings", key: "unverified_listing_limit", label: "Unverified seller listing limit", help: "Live listings an unverified seller may have.", kind: "int", unit: "listings" },
  { group: "Listings", key: "max_images_per_listing", label: "Maximum photos per listing", help: "", kind: "int", unit: "photos" },
  { group: "Listings", key: "free_listing_days", label: "Free listing period", help: "Listings expire after this long unless renewed.", kind: "int", unit: "days" },
  { group: "Listings", key: "renewal_days", label: "Renewal period", help: "Added when a seller taps Still available.", kind: "int", unit: "days" },
  { group: "Listings", key: "verification_required_categories", label: "Categories needing verification", help: "Category slugs, separated by commas.", kind: "list" },
  { group: "Order windows", key: "seller_accept_hours", label: "Seller acceptance window", help: "Orders not accepted in time are cancelled and refunded.", kind: "int", unit: "hours" },
  { group: "Order windows", key: "buyer_confirm_hours", label: "Buyer confirmation window", help: "After delivery, the order confirms automatically unless disputed.", kind: "int", unit: "hours" },
  { group: "Order windows", key: "dispute_response_hours", label: "Seller dispute response window", help: "", kind: "int", unit: "hours" },
  { group: "Trust", key: "trusted_min_confirmed_deals", label: "Trusted Seller: confirmed deals", help: "Deals needed, together with the rating below.", kind: "int", unit: "deals" },
  { group: "Trust", key: "trusted_min_rating_x10", label: "Trusted Seller: minimum rating", help: "Enter rating times ten: 45 means 4.5 stars.", kind: "int" },
  { group: "Features", key: "allow_vendors", label: "Allow non-student vendors", help: "Vendors are reviewed separately. Off by default.", kind: "bool" },
  { group: "Features", key: "sms_enabled", label: "SMS notifications", help: "Needs an SMS provider (see owner actions).", kind: "bool" },
  { group: "Features", key: "whatsapp_enabled", label: "WhatsApp notifications", help: "Needs a WhatsApp provider (see owner actions).", kind: "bool" },
];

function show(def: Def, value: unknown): string {
  if (def.kind === "bps") return `${Number(value) / 100}%`;
  if (def.kind === "kobo") return naira(Number(value));
  if (def.kind === "bool") return value ? "On" : "Off";
  if (def.kind === "list") return (value as string[]).length ? (value as string[]).join(", ") : "None";
  return `${value}${def.unit ? ` ${def.unit}` : ""}`;
}

function toInput(def: Def, value: unknown): string {
  if (def.kind === "bps") return String(Number(value) / 100);
  if (def.kind === "kobo") return String(Number(value) / 100);
  if (def.kind === "list") return (value as string[]).join(", ");
  return String(value);
}

function parse(def: Def, text: string): unknown {
  if (def.kind === "bps") return Math.round(Number(text) * 100);
  if (def.kind === "kobo") return Math.round(Number(text) * 100);
  if (def.kind === "int") return Number(text);
  if (def.kind === "list") return text.split(",").map((s) => s.trim()).filter(Boolean);
  return text === "true";
}

const tabs = ["Rules and fees", "Banned items", "Policy text"] as const;

export default function AdminSettings() {
  const [tab, setTab] = useState<(typeof tabs)[number]>("Rules and fees");
  const settings = useApiQuery<Settings>(["admin-settings"], "/admin/settings");
  const banned = useApiQuery<Banned[]>(["banned-items"], "/banned-items");
  const act = useAction([["admin-settings"], ["banned-items"]]);
  const [editing, setEditing] = useState<Def | null>(null);
  const [text, setText] = useState("");
  const [bannedForm, setBannedForm] = useState({ name: "", reason: "", extra_review: false });
  const [bannedOpen, setBannedOpen] = useState(false);
  const [removing, setRemoving] = useState<Banned | null>(null);
  const [policy, setPolicy] = useState<keyof typeof policies>("terms");
  const [policyText, setPolicyText] = useState("");
  const [policyOpen, setPolicyOpen] = useState(false);

  const groups = [...new Set(defs.map((d) => d.group))];

  return (
    <>
      <PageHeader title="Settings" />
      <div role="tablist" aria-label="Settings sections" className="mb-4 flex flex-wrap gap-2">
        {tabs.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={clsx("min-h-11 rounded-full px-5 text-sm font-semibold", tab === t ? "bg-ink text-white" : "border border-line bg-white")}>
            {t}
          </button>
        ))}
      </div>

      {tab === "Rules and fees" && (
        <>
          {settings.isPending && <Skeleton className="h-64" />}
          {settings.isError && <ErrorState message={settings.error.message} onRetry={() => void settings.refetch()} />}
          {settings.data && (
            <div className="space-y-6">
              {groups.map((g) => (
                <section key={g} aria-labelledby={`g-${g}`}>
                  <h2 id={`g-${g}`} className="mb-2 text-lg font-bold">{g}</h2>
                  <Card className="divide-y divide-line p-0 md:p-0">
                    {defs.filter((d) => d.group === g).map((d) => (
                      <div key={d.key} className="flex flex-wrap items-center justify-between gap-3 p-4">
                        <div className="max-w-xl">
                          <p className="font-semibold">{d.label}</p>
                          {d.help && <p className="text-sm text-muted">{d.help}</p>}
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="font-heading text-lg font-bold" data-testid={`value-${d.key}`}>{show(d, settings.data.values[d.key])}</span>
                          <Button variant="tertiary" aria-label={`Change ${d.label}`} onClick={() => { setEditing(d); setText(toInput(d, settings.data.values[d.key])); }}>Change</Button>
                        </div>
                      </div>
                    ))}
                  </Card>
                </section>
              ))}
            </div>
          )}
        </>
      )}

      {tab === "Banned items" && (
        <>
          <div className="mb-3"><Button onClick={() => { setBannedForm({ name: "", reason: "", extra_review: false }); setBannedOpen(true); }}>Add banned item</Button></div>
          <DataTable
            label="Banned items"
            rows={banned.data}
            loading={banned.isPending}
            error={banned.isError ? banned.error.message : null}
            onRetry={() => void banned.refetch()}
            rowKey={(b) => b.name}
            empty={{ title: "No banned items yet", body: "The published banned items list is shown to sellers and buyers." }}
            columns={[
              { key: "n", header: "Item", render: (b) => b.name },
              { key: "r", header: "Why", render: (b) => b.reason || "None" },
              { key: "x", header: "Extra review", render: (b) => (b.extra_review ? "Yes" : "No") },
            ]}
            actions={(b) => <Button variant="danger" onClick={() => setRemoving(b)}>Remove</Button>}
          />
        </>
      )}

      {tab === "Policy text" && (
        <Card className="max-w-2xl space-y-3">
          <Select label="Policy" value={policy} onChange={(e) => setPolicy(e.target.value as keyof typeof policies)}>
            <option value="terms">Terms of use</option>
            <option value="privacy">Privacy policy</option>
            <option value="seller-rules">Seller rules</option>
          </Select>
          <Textarea label="Replacement text" rows={10} value={policyText} onChange={(e) => setPolicyText(e.target.value)} hint="Replaces the starter text on the public page. Have it reviewed by a legal adviser first." />
          <Button disabled={policyText.trim().length < 20} onClick={() => setPolicyOpen(true)}>Publish {policies[policy].title.toLowerCase()}</Button>
        </Card>
      )}

      {editing && settings.data && (
        <ReasonModal
          open
          title={`Change ${editing.label.toLowerCase()}`}
          description={editing.help || undefined}
          confirmLabel="Save change"
          onConfirm={(reason) => {
            const value = parse(editing, text);
            if (typeof value === "number" && Number.isNaN(value)) return Promise.reject(new Error("Enter a number"));
            return act("PUT", `/admin/settings/${editing.key}`, { value, reason }, "Setting saved").then(() => undefined);
          }}
          onClose={() => setEditing(null)}
        >
          {editing.kind === "bool" ? (
            <Select label={editing.label} value={text} onChange={(e) => setText(e.target.value)}>
              <option value="true">On</option>
              <option value="false">Off</option>
            </Select>
          ) : (
            <Input label={editing.label} value={text} onChange={(e) => setText(e.target.value)} inputMode={editing.kind === "list" ? "text" : "decimal"} hint={editing.kind === "bps" ? "Enter a percentage, for example 20" : editing.kind === "kobo" ? "Enter an amount in naira" : undefined} />
          )}
        </ReasonModal>
      )}
      <ReasonModal open={bannedOpen} title="Add banned item" confirmLabel="Add to list" onConfirm={() => act("POST", "/admin/banned-items", bannedForm, "Banned item added").then(() => undefined)} onClose={() => setBannedOpen(false)}>
        <Input label="Item" value={bannedForm.name} onChange={(e) => setBannedForm({ ...bannedForm, name: e.target.value })} />
        <Input label="Why it is banned" value={bannedForm.reason} onChange={(e) => setBannedForm({ ...bannedForm, reason: e.target.value })} />
        <label className="flex min-h-11 items-center gap-3 text-sm font-semibold"><input type="checkbox" className="size-5 accent-forest" checked={bannedForm.extra_review} onChange={(e) => setBannedForm({ ...bannedForm, extra_review: e.target.checked })} /> Allowed only after extra review (pre-orders, paid courses)</label>
      </ReasonModal>
      {removing && <ReasonModal open title={`Remove ${removing.name} from the list?`} confirmLabel="Remove" destructive onConfirm={(reason) => act("DELETE", `/admin/banned-items/${removing.id}`, undefined, "Removed", { reason }).then(() => undefined)} onClose={() => setRemoving(null)} />}
      <ReasonModal open={policyOpen} title="Publish policy text?" description="The public page changes immediately." confirmLabel="Publish" onConfirm={(reason) => act("PUT", `/admin/policies/${policy}`, { body: policyText, reason }, "Policy published").then(() => { setPolicyText(""); })} onClose={() => setPolicyOpen(false)} />
    </>
  );
}
