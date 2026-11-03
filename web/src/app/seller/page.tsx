import { EmptyState } from "@/components/ui/States";

export default function SellerOverview() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-extrabold md:text-3xl">Seller overview</h1>
      <EmptyState title="Set up your shop" body="Create your shop to see earnings, orders and tasks here." action={{ label: "Start selling", href: "/seller/start" }} />
    </div>
  );
}
