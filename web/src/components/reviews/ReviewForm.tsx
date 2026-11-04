"use client";
import { useState } from "react";
import { FormError } from "@/components/auth/AuthCard";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";

/** One rating and an optional comment, posted to the given review endpoint. */
export function ReviewForm({ path, onDone, intro }: { path: string; onDone: () => void; intro?: string }) {
  const toast = useToast();
  const [rating, setRating] = useState(0);
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!rating) {
      setError("Choose a star rating from 1 to 5.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api(path, { method: "POST", body: { rating, body } });
      toast("Thanks for your review");
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send the review.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      {intro && <p className="text-sm text-muted">{intro}</p>}
      <fieldset className="space-y-2">
        <legend className="text-sm font-semibold">Your rating</legend>
        <div className="flex gap-2">
          {[1, 2, 3, 4, 5].map((n) => (
            <label
              key={n}
              className={`flex min-h-11 min-w-11 cursor-pointer items-center justify-center rounded-input border text-base font-semibold has-[:focus-visible]:outline has-[:focus-visible]:outline-2 ${rating === n ? "border-ink bg-ink text-white" : "border-line bg-white"}`}
            >
              <input type="radio" name="rating" value={n} checked={rating === n} onChange={() => setRating(n)} className="sr-only" />
              <span aria-label={`${n} star${n === 1 ? "" : "s"}`}>{n}★</span>
            </label>
          ))}
        </div>
      </fieldset>
      <Textarea label="Comment (optional)" value={body} onChange={(e) => setBody(e.target.value)} maxLength={1500} />
      {error && <FormError message={error} />}
      <Button type="submit" loading={busy}>
        Send review
      </Button>
    </form>
  );
}
