import type { Metadata } from "next";
import { ProsePage } from "@/components/layout/Prose";
import { Button } from "@/components/ui/Button";
import { faqs } from "@/lib/content";

export const metadata: Metadata = { title: "Help", description: "Answers to common questions about paying, delivery, disputes and selling." };

export default function HelpPage() {
  return (
    <ProsePage title="Help centre" intro="Quick answers. Still stuck? Contact us.">
      <div className="space-y-2">
        {faqs.map((f) => (
          <details key={f.q} className="rounded-card border border-line bg-white p-4">
            <summary className="flex min-h-11 cursor-pointer items-center font-semibold">{f.q}</summary>
            <p className="mt-2 text-sm text-muted">{f.a}</p>
          </details>
        ))}
      </div>
      <Button href="/contact">Contact support</Button>
    </ProsePage>
  );
}
