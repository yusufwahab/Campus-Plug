"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { AuthCard, FormError } from "@/components/auth/AuthCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import { RequireAuth, useMe } from "@/lib/auth";
import { safeNext } from "@/lib/safe-next";
import { codeSchema, phoneSchema } from "@/lib/schemas";

type Code = z.infer<typeof codeSchema>;

function VerifyPhone() {
  const me = useMe();
  const router = useRouter();
  const client = useQueryClient();
  const toast = useToast();
  const next = safeNext(useSearchParams().get("next"));
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<{ devCode?: string | null } | null>(null);
  const [phone, setPhone] = useState(me.data?.phone ?? "");
  const [phoneError, setPhoneError] = useState<string | undefined>();
  const [sending, setSending] = useState(false);
  const code = useForm<Code>({ resolver: zodResolver(codeSchema) });

  async function send() {
    setError(null);
    const parsed = phoneSchema.safeParse(phone.replace(/[\s-]/g, ""));
    if (!parsed.success) {
      setPhoneError(parsed.error.issues[0].message);
      return;
    }
    setPhoneError(undefined);
    setSending(true);
    try {
      const res = await api<{ dev_code?: string | null }>("/auth/phone/send", { method: "POST", body: { phone: parsed.data } });
      setSent({ devCode: res.dev_code });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not send the code.");
    } finally {
      setSending(false);
    }
  }

  async function verify(values: Code) {
    setError(null);
    try {
      await api("/auth/phone/verify", { method: "POST", body: values });
      await client.invalidateQueries({ queryKey: ["me"] });
      toast("Phone number confirmed");
      router.push(me.data?.onboarded ? next : `/onboarding?next=${encodeURIComponent(next)}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not verify the code.");
    }
  }

  if (me.data?.phone_verified) {
    return (
      <AuthCard title="Phone confirmed" subtitle="Your number is verified.">
        <Button href={next}>Continue</Button>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Confirm your phone" subtitle="We text a 6-digit code. Sellers must confirm their phone before listing.">
      {!sent ? (
        <div className="space-y-4">
          <Input label="Phone number" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} error={phoneError} />
          <FormError message={error} />
          <Button className="w-full" onClick={send} loading={sending}>
            Send code
          </Button>
          <Button variant="tertiary" className="w-full" href={me.data?.onboarded ? next : "/onboarding"}>
            Skip for now
          </Button>
        </div>
      ) : (
        <form onSubmit={code.handleSubmit(verify)} className="space-y-4" noValidate>
          {sent.devCode && (
            <p className="rounded-input bg-info-bg p-3 text-sm text-info-fg">
              Test mode (no SMS provider yet). Your code is <strong data-testid="dev-code">{sent.devCode}</strong>
            </p>
          )}
          <Input label="6-digit code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} error={code.formState.errors.code?.message} {...code.register("code")} />
          <FormError message={error} />
          <Button type="submit" className="w-full" loading={code.formState.isSubmitting}>
            Confirm
          </Button>
          <Button variant="tertiary" className="w-full" onClick={send} loading={sending}>
            Send a new code
          </Button>
        </form>
      )}
    </AuthCard>
  );
}

export default function VerifyPhonePage() {
  return (
    <RequireAuth>
      <Suspense>
        <VerifyPhone />
      </Suspense>
    </RequireAuth>
  );
}
