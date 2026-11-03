"use client";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { ConfirmModal, Modal } from "@/components/ui/Modal";
import { CardGridSkeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";

const tints = ["bg-peach", "bg-lilac", "bg-sky", "bg-butter", "bg-mint"];

/** Component reference. Every shared component appears here so layouts can be checked at all widths. */
export default function DesignPage() {
  const toast = useToast();
  const [modal, setModal] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [dirty, setDirty] = useState(false);

  return (
    <div className="space-y-10">
      <h1 className="text-3xl font-extrabold">Design system</h1>

      <section aria-labelledby="buttons" className="space-y-3">
        <h2 id="buttons" className="text-xl font-bold">Buttons</h2>
        <div className="flex flex-wrap gap-2">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="tertiary">Tertiary</Button>
          <Button variant="danger">Danger</Button>
          <Button loading>Loading</Button>
          <Button disabled>Disabled</Button>
        </div>
      </section>

      <section aria-labelledby="badges" className="space-y-3">
        <h2 id="badges" className="text-xl font-bold">Status badges</h2>
        <div className="flex flex-wrap gap-2">
          <Badge tone="verified">Verified</Badge>
          <Badge tone="pending">Pending</Badge>
          <Badge tone="info">Information</Badge>
          <Badge tone="danger">Danger</Badge>
        </div>
        <div className="flex flex-wrap gap-2">
          {tints.map((t) => (
            <span key={t} className={`${t} rounded-card px-4 py-6 text-sm font-semibold`}>
              {t.replace("bg-", "")}
            </span>
          ))}
        </div>
      </section>

      <section aria-labelledby="forms" className="space-y-3">
        <h2 id="forms" className="text-xl font-bold">Form fields</h2>
        <Card className="grid gap-4 md:grid-cols-2">
          <Input label="Shop name" placeholder="Tolu's Kitchen" hint="Shown on your public shop page." />
          <Input label="Phone" error="Enter a valid Nigerian phone number." defaultValue="080" />
          <Select label="Category">
            <option>Food</option>
            <option>Fashion</option>
          </Select>
          <Textarea label="Description" />
        </Card>
      </section>

      <section aria-labelledby="modals" className="space-y-3">
        <h2 id="modals" className="text-xl font-bold">Modals and toasts</h2>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => setModal(true)}>Open modal</Button>
          <Button variant="tertiary" onClick={() => setConfirm(true)}>
            Confirm delete
          </Button>
          <Button variant="secondary" onClick={() => toast("Saved", "success")}>
            Success toast
          </Button>
          <Button variant="tertiary" onClick={() => toast("Could not save", "error")}>
            Error toast
          </Button>
        </div>
        <Modal open={modal} title="Example modal" onClose={() => { setModal(false); setDirty(false); }} dirty={dirty}>
          <Input label="Note" onChange={() => setDirty(true)} />
          <div className="mt-4 flex justify-end">
            <Button onClick={() => { setModal(false); setDirty(false); }}>Save</Button>
          </div>
        </Modal>
        <ConfirmModal
          open={confirm}
          title="Delete listing?"
          body="This cannot be undone."
          confirmLabel="Delete"
          destructive
          onConfirm={() => { setConfirm(false); toast("Deleted"); }}
          onClose={() => setConfirm(false)}
        />
      </section>

      <section aria-labelledby="states" className="space-y-3">
        <h2 id="states" className="text-xl font-bold">States</h2>
        <CardGridSkeleton count={5} />
        <div className="grid gap-4 md:grid-cols-2">
          <EmptyState title="No saved items yet" body="Tap the heart on any listing to keep it here." action={{ label: "Browse listings", href: "/search" }} />
          <ErrorState message="Network request failed." onRetry={() => toast("Retrying", "info")} />
        </div>
      </section>
    </div>
  );
}
