"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { FormError } from "@/components/auth/AuthCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { naira, nairaToKobo } from "@/lib/format";
import { compressImage } from "@/lib/image";

type Category = components["schemas"]["CategoryOut"];
type Location = components["schemas"]["LocationOut"];
type Preview = components["schemas"]["PayoutPreview"];
type Detail = components["schemas"]["ListingDetail"];

const money = z.string().regex(/^\d+(\.\d{1,2})?$/, "Enter an amount in naira");
const optionalMoney = z.string().refine((v) => v === "" || /^\d+(\.\d{1,2})?$/.test(v), "Enter an amount in naira");

const schema = z.object({
  type: z.enum(["product", "service"]),
  title: z.string().min(3, "Give it a clear title").max(140),
  category_id: z.string().min(1, "Choose a category"),
  description: z.string().max(4000),
  price: money,
  price_max: optionalMoney,
  negotiable: z.boolean(),
  location_id: z.string(),
  condition: z.string(),
  quantity: z.string().regex(/^\d+$/, "Enter a whole number"),
  fulfilment: z.enum(["pickup", "delivery", "both"]),
  delivery_fee: optionalMoney,
  preorder: z.boolean(),
  availability: z.string().max(200),
  duration_min: z.string().refine((v) => v === "" || /^\d+$/.test(v), "Enter minutes"),
  deposit: optionalMoney,
  variants: z.array(z.object({ name: z.string().min(1, "Name"), options: z.string().min(1, "Add options, separated by commas") })),
  packages: z.array(z.object({ name: z.string().min(1, "Name"), price: money, description: z.string() })),
});
type Values = z.infer<typeof schema>;

const defaults: Values = {
  type: "product", title: "", category_id: "", description: "", price: "", price_max: "", negotiable: false, location_id: "",
  condition: "new", quantity: "1", fulfilment: "pickup", delivery_fee: "", preorder: false, availability: "", duration_min: "", deposit: "", variants: [], packages: [],
};

function toValues(d: Detail): Values {
  const kobo = (n: number | null | undefined) => (n ? String(n / 100) : "");
  return {
    ...defaults,
    type: d.type as Values["type"],
    title: d.title,
    category_id: "",
    description: d.description,
    price: kobo(d.price_kobo),
    price_max: kobo(d.price_max_kobo),
    negotiable: d.negotiable,
    condition: d.condition ?? "new",
    quantity: String(d.quantity),
    fulfilment: d.fulfilment as Values["fulfilment"],
    delivery_fee: kobo(d.delivery_fee_kobo),
    preorder: d.preorder,
    availability: d.availability ?? "",
    duration_min: d.duration_min ? String(d.duration_min) : "",
    deposit: kobo(d.deposit_kobo),
  };
}

export function ListingForm({ existing }: { existing?: Detail }) {
  const router = useRouter();
  const client = useQueryClient();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [preview, setPreview] = useState(false);
  const [submitting, setSubmitting] = useState<"publish" | "draft" | null>(null);

  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/categories") });
  const locations = useQuery({ queryKey: ["locations"], queryFn: () => api<Location[]>("/locations") });
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: existing ? toValues(existing) : defaults });
  const variants = useFieldArray({ control: form.control, name: "variants" });
  const packages = useFieldArray({ control: form.control, name: "packages" });
  const errors = form.formState.errors;
  const [type, price, categoryId] = useWatch({ control: form.control, name: ["type", "price", "category_id"] });

  useEffect(() => {
    if (existing && categories.data) form.setValue("category_id", String(categories.data.find((c) => c.slug === existing.category_slug)?.id ?? ""));
  }, [existing, categories.data, form]);

  const priceKobo = /^\d+(\.\d{1,2})?$/.test(price) ? nairaToKobo(Number(price)) : 0;
  const payout = useQuery({
    queryKey: ["payout-preview", priceKobo, categoryId],
    queryFn: () => api<Preview>("/listings/payout-preview", { query: { price_kobo: priceKobo, category_id: categoryId } }),
    enabled: priceKobo > 0 && !!categoryId,
  });

  async function addFiles(list: FileList | null) {
    if (!list) return;
    try {
      const compressed = await Promise.all([...list].map(compressImage));
      setFiles((cur) => [...cur, ...compressed]);
      setPreviews((cur) => [...cur, ...compressed.map((f) => URL.createObjectURL(f))]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add that image.");
    }
  }

  function payload(v: Values, publish: boolean, edit: boolean) {
    const k = (s: string) => (s ? nairaToKobo(Number(s)) : null);
    const body: Record<string, unknown> = {
      category_id: Number(v.category_id), title: v.title, description: v.description,
      price_kobo: nairaToKobo(Number(v.price)), price_max_kobo: k(v.price_max), negotiable: v.negotiable,
      location_id: v.location_id ? Number(v.location_id) : null,
    };
    // Type, publish flag, variants and packages are only set when creating.
    if (!edit) Object.assign(body, { type: v.type, publish });
    if (v.type === "product") {
      Object.assign(body, {
        condition: v.condition, quantity: Number(v.quantity), fulfilment: v.fulfilment, delivery_fee_kobo: k(v.delivery_fee) ?? 0, preorder: v.preorder,
      });
      if (!edit) body.variants = v.variants.map((x) => ({ name: x.name, options: x.options.split(",").map((o) => o.trim()).filter(Boolean) }));
    } else {
      Object.assign(body, {
        availability: v.availability || null, deposit_kobo: k(v.deposit),
      });
      if (!edit) {
        body.duration_min = v.duration_min ? Number(v.duration_min) : null;
        body.packages = v.packages.map((x) => ({ name: x.name, price_kobo: nairaToKobo(Number(x.price)), description: x.description }));
      }
    }
    return body;
  }

  async function submit(v: Values, publish: boolean) {
    setError(null);
    setSubmitting(publish ? "publish" : "draft");
    try {
      let publicId = existing?.public_id;
      if (existing) {
        await api(`/listings/${existing.public_id}`, { method: "PATCH", body: payload(v, publish, true) });
      } else {
        publicId = (await api<Detail>("/listings", { method: "POST", body: payload(v, publish, false) })).public_id;
      }
      for (const file of files) {
        const data = new FormData();
        data.append("file", file);
        await api(`/listings/${publicId}/images`, { method: "POST", body: data });
      }
      await client.invalidateQueries({ queryKey: ["seller-listings"] });
      toast(publish ? "Listing published" : "Draft saved");
      router.push("/seller/listings");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save the listing.");
    } finally {
      setSubmitting(null);
    }
  }

  const places = locations.data ?? [];
  return (
    <form onSubmit={form.handleSubmit((v) => submit(v, true))} className="space-y-4 pb-28 md:pb-0" noValidate>
      <Card className="space-y-4">
        <fieldset disabled={!!existing}>
          <legend className="text-sm font-semibold">What are you listing?</legend>
          <div className="mt-2 flex gap-2">
            {(["product", "service"] as const).map((t) => (
              <label key={t} className={`flex min-h-11 flex-1 cursor-pointer items-center justify-center rounded-full border-2 text-sm font-semibold ${type === t ? "border-ink bg-lime" : "border-line bg-white"}`}>
                <input type="radio" value={t} className="sr-only" {...form.register("type")} />
                {t === "product" ? "Product" : "Service"}
              </label>
            ))}
          </div>
        </fieldset>
        <Input label="Title" error={errors.title?.message} {...form.register("title")} />
        <Select label="Category" error={errors.category_id?.message} {...form.register("category_id")}>
          <option value="">Choose a category</option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        <Textarea label="Description" hint="Describe it clearly. Never include exact room numbers: use the hall or area." error={errors.description?.message} {...form.register("description")} />
        <Select label="Hall or area" hint="Buyers see this, never your room." {...form.register("location_id")}>
          <option value="">Use my shop location</option>
          {places.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name}
            </option>
          ))}
        </Select>
      </Card>

      <Card className="space-y-4">
        <h2 className="text-lg font-bold">Price</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <Input label={type === "service" ? "Starting price (₦)" : "Price (₦)"} inputMode="decimal" error={errors.price?.message} {...form.register("price")} />
          <Input label="Highest price (₦, optional)" inputMode="decimal" error={errors.price_max?.message} {...form.register("price_max")} />
        </div>
        <label className="flex min-h-11 items-center gap-3 text-sm font-semibold">
          <input type="checkbox" className="size-5 accent-forest" {...form.register("negotiable")} /> Price is negotiable
        </label>
        <div className="rounded-input bg-ground p-4 text-sm" aria-live="polite">
          <p className="font-semibold">Payout preview</p>
          {payout.data ? (
            <dl className="mt-2 space-y-1">
              <div className="flex justify-between"><dt>Buyer pays</dt><dd className="font-semibold">{naira(payout.data.buyer_price_kobo)}</dd></div>
              <div className="flex justify-between"><dt>Campus Plug commission ({payout.data.commission_bps / 100}%)</dt><dd>-{naira(payout.data.commission_kobo)}</dd></div>
              <div className="flex justify-between border-t border-line pt-1"><dt className="font-semibold">You receive</dt><dd className="font-heading text-lg font-bold">{naira(payout.data.seller_payout_kobo)}</dd></div>
            </dl>
          ) : (
            <p className="text-muted">Enter a price and category to see what you will earn on in-app payments.</p>
          )}
        </div>
      </Card>

      {type === "product" ? (
        <Card className="space-y-4">
          <h2 className="text-lg font-bold">Product details</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <Select label="Condition" {...form.register("condition")}>
              <option value="new">New</option>
              <option value="like_new">Like new</option>
              <option value="used">Used</option>
            </Select>
            <Input label="Quantity" inputMode="numeric" error={errors.quantity?.message} {...form.register("quantity")} />
            <Select label="Pickup or delivery" {...form.register("fulfilment")}>
              <option value="pickup">Pickup only</option>
              <option value="delivery">Delivery only</option>
              <option value="both">Pickup or delivery</option>
            </Select>
            <Input label="Delivery fee (₦)" inputMode="decimal" error={errors.delivery_fee?.message} {...form.register("delivery_fee")} />
          </div>
          <label className="flex min-h-11 items-center gap-3 text-sm font-semibold">
            <input type="checkbox" className="size-5 accent-forest" {...form.register("preorder")} /> This is a pre-order
          </label>
          {!existing && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Variants (size, colour…)</h3>
              {variants.fields.map((f, i) => (
                <div key={f.id} className="grid gap-2 md:grid-cols-[1fr_2fr_auto]">
                  <Input label="Name" error={errors.variants?.[i]?.name?.message} {...form.register(`variants.${i}.name`)} />
                  <Input label="Options (comma separated)" error={errors.variants?.[i]?.options?.message} {...form.register(`variants.${i}.options`)} />
                  <Button variant="tertiary" className="self-end" onClick={() => variants.remove(i)} aria-label={`Remove variant ${i + 1}`}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </Button>
                </div>
              ))}
              {variants.fields.length < 4 && (
                <Button variant="tertiary" onClick={() => variants.append({ name: "", options: "" })}>
                  <Plus className="size-4" aria-hidden="true" /> Add variant
                </Button>
              )}
            </div>
          )}
        </Card>
      ) : (
        <Card className="space-y-4">
          <h2 className="text-lg font-bold">Service details</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <Input label="Availability" hint="For example: Weekdays after 4pm" {...form.register("availability")} />
            <Input label="Duration (minutes)" inputMode="numeric" error={errors.duration_min?.message} {...form.register("duration_min")} />
            <Input label="Booking deposit (₦, optional)" inputMode="decimal" error={errors.deposit?.message} {...form.register("deposit")} />
          </div>
          {!existing && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Packages</h3>
              {packages.fields.map((f, i) => (
                <div key={f.id} className="grid gap-2 md:grid-cols-[1fr_1fr_2fr_auto]">
                  <Input label="Name" error={errors.packages?.[i]?.name?.message} {...form.register(`packages.${i}.name`)} />
                  <Input label="Price (₦)" inputMode="decimal" error={errors.packages?.[i]?.price?.message} {...form.register(`packages.${i}.price`)} />
                  <Input label="What is included" {...form.register(`packages.${i}.description`)} />
                  <Button variant="tertiary" className="self-end" onClick={() => packages.remove(i)} aria-label={`Remove package ${i + 1}`}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </Button>
                </div>
              ))}
              {packages.fields.length < 6 && (
                <Button variant="tertiary" onClick={() => packages.append({ name: "", price: "", description: "" })}>
                  <Plus className="size-4" aria-hidden="true" /> Add package
                </Button>
              )}
            </div>
          )}
        </Card>
      )}

      <Card className="space-y-3">
        <h2 className="text-lg font-bold">Photos</h2>
        <p className="text-sm text-muted">Photos are shrunk on your phone before upload. {type === "service" ? "Add portfolio photos of your work." : "Show the item clearly."}</p>
        <label className="inline-flex min-h-11 cursor-pointer items-center rounded-full border-2 border-ink px-5 text-sm font-semibold focus-within:outline focus-within:outline-2">
          Add photos
          <input type="file" accept="image/*" multiple className="sr-only" onChange={(e) => void addFiles(e.target.files)} />
        </label>
        {previews.length > 0 && (
          <ul className="flex flex-wrap gap-2">
            {previews.map((src, i) => (
              <li key={src} className="relative size-20 overflow-hidden rounded-input">
                <Image src={src} alt={`New photo ${i + 1}`} fill unoptimized sizes="80px" className="object-cover" />
                <button
                  type="button"
                  aria-label={`Remove photo ${i + 1}`}
                  className="absolute right-0 top-0 grid size-11 place-items-center bg-ink/70 text-white"
                  onClick={() => {
                    setFiles((cur) => cur.filter((_, j) => j !== i));
                    setPreviews((cur) => cur.filter((_, j) => j !== i));
                  }}
                >
                  <Trash2 className="size-4" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <FormError message={error} />
      <div className="fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-30 flex gap-2 border-t border-line bg-white p-3 md:static md:border-0 md:bg-transparent md:p-0">
        <Button variant="tertiary" className="flex-1 md:flex-none" onClick={() => setPreview(true)}>
          Preview
        </Button>
        {!existing && (
          <Button variant="tertiary" className="flex-1 md:flex-none" loading={submitting === "draft"} onClick={form.handleSubmit((v) => submit(v, false))}>
            Save draft
          </Button>
        )}
        <Button type="submit" className="flex-[2] md:flex-none" loading={submitting === "publish"}>
          {existing ? "Save changes" : "Publish"}
        </Button>
      </div>

      <Modal open={preview} title="Listing preview" onClose={() => setPreview(false)}>
        <div className="space-y-2">
          <Badge tone="neutral">{type}</Badge>
          <p className="font-heading text-2xl font-extrabold">{priceKobo ? naira(priceKobo) : "₦0"}</p>
          <p className="font-semibold">{form.getValues("title") || "Your title"}</p>
          <p className="whitespace-pre-line text-sm text-muted">{form.getValues("description") || "Your description"}</p>
          {payout.data && <p className="text-sm">You receive {naira(payout.data.seller_payout_kobo)} after commission.</p>}
        </div>
      </Modal>
    </form>
  );
}
