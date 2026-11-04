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
import { codeSchema } from "@/lib/schemas";

type Code = z.infer<typeof codeSchema>;

function VerifyEmail() {
  const me = useMe();
  const router = useRouter();
  const client = useQueryClient();
  const toast = useToast();
  const next = safeNext(useSearchParams().get("next"));
  const [error, setError] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const code = useForm<Code>({ resolver: zodResolver(codeSchema) });

  async function resend() {
    setError(null);
    setSending(true);
    try {
      const res = await api<{ dev_code?: string | null }>("/auth/email/send", { method: "POST" });
      setDevCode(res.dev_code ?? null);
      toast("A new code is on its way");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not send the code.");
    } finally {
      setSending(false);
    }
  }

  async function verify(values: Code) {
    setError(null);
    try {
      await api("/auth/email/verify", { method: "POST", body: values });
      await client.invalidateQueries({ queryKey: ["me"] });
      toast("Email address confirmed");
      router.push(me.data?.onboarded ? next : `/onboarding?next=${encodeURIComponent(next)}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not verify the code.");
    }
  }

  if (me.data?.email_verified) {
    return (
      <AuthCard title="Email confirmed" subtitle="Your email address is verified.">
        <Button href={next}>Continue</Button>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Confirm your email" subtitle={`We emailed a 6-digit code to ${me.data?.email ?? "you"}. It expires in 10 minutes. Sellers must confirm their email before listing.`}>
      <form onSubmit={code.handleSubmit(verify)} className="space-y-4" noValidate>
        {devCode && (
          <p className="rounded-input bg-info-bg p-3 text-sm text-info-fg">
            Test mode (no email provider yet). Your code is <strong data-testid="dev-code">{devCode}</strong>
          </p>
        )}
        <Input label="6-digit code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} error={code.formState.errors.code?.message} {...code.register("code")} />
        <FormError message={error} />
        <Button type="submit" className="w-full" loading={code.formState.isSubmitting}>
          Confirm
        </Button>
        <Button variant="tertiary" className="w-full" onClick={resend} loading={sending}>
          Send a new code
        </Button>
        <Button variant="tertiary" className="w-full" href={me.data?.onboarded ? next : "/onboarding"}>
          Skip for now
        </Button>
      </form>
    </AuthCard>
  );
}

export default function VerifyEmailPage() {
  return (
    <RequireAuth>
      <Suspense>
        <VerifyEmail />
      </Suspense>
    </RequireAuth>
  );
}
