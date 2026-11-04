import type { Metadata } from "next";
import { ProsePage } from "@/components/layout/Prose";
import { Button } from "@/components/ui/Button";

export const metadata: Metadata = { title: "Sell on Campus Plug", description: "Open a free shop, list in under a minute and get paid safely on campus." };

const perks = [
  ["List in under a minute", "Mobile-friendly form, photos shrunk on your phone, and a payout preview before you publish."],
  ["Get paid safely", "Buyers pay in the app. Once they confirm delivery your share is paid out to your bank."],
  ["Build trust", "Verify with your student ID to earn the Verified badge, unlock in-app payments and list without limits."],
  ["Reach your hall first", "Buyers see sellers in their own hall and nearby areas first."],
];

export default function SellPage() {
  return (
    <ProsePage title="Sell on Campus Plug" intro="Turn what you make, find or know into income on your campus.">
      <ul className="grid gap-3 md:grid-cols-2">
        {perks.map(([title, body]) => (
          <li key={title} className="rounded-card border border-line bg-white p-5">
            <h2 className="text-lg font-bold">{title}</h2>
            <p className="mt-1 text-sm text-muted">{body}</p>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <Button href="/seller/start">Open your shop</Button>
        <Button href="/seller-rules" variant="tertiary">
          Read the seller rules
        </Button>
      </div>
    </ProsePage>
  );
}
