import { EmptyState } from "@/components/ui/States";

export default function AdminOverview() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-extrabold md:text-3xl">Admin overview</h1>
      <EmptyState title="Nothing to review" body="Alerts, revenue and pending reviews appear here." action={{ label: "Open settings", href: "/admin/settings" }} />
    </div>
  );
}
