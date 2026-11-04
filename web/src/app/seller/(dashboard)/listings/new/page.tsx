import { ListingForm } from "@/components/seller/ListingForm";

export default function NewListingPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-2xl font-extrabold md:text-3xl">New listing</h1>
      <ListingForm />
    </div>
  );
}
