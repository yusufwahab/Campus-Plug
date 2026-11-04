"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { AuthCard, FormError } from "@/components/auth/AuthCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { ApiError, api } from "@/lib/api";
import { forgotSchema } from "@/lib/schemas";

type Values = z.infer<typeof forgotSchema>;

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState<{ devToken?: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(forgotSchema) });

  async function onSubmit(values: Values) {
    setError(null);
    try {
      const res = await api<{ dev_token?: string | null }>("/auth/forgot", { method: "POST", body: values, token: null });
      setSent({ devToken: res.dev_token });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not send the reset link.");
    }
  }

  if (sent) {
    return (
      <AuthCard title="Check your email" subtitle="If that email has an account, a reset link is on its way. It expires in 30 minutes.">
        {sent.devToken && (
          <p className="mb-4 rounded-input bg-info-bg p-3 text-sm text-info-fg">
            Test mode (no email provider yet):{" "}
            <Link className="font-semibold underline" href={`/reset-password?token=${encodeURIComponent(sent.devToken)}`}>
              open the reset link
            </Link>
          </p>
        )}
        <Button href="/login" variant="tertiary">
          Back to sign in
        </Button>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Forgot your password?" subtitle="Enter your email and we will send a reset link.">
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Input label="Email" type="email" autoComplete="email" error={form.formState.errors.email?.message} {...form.register("email")} />
        <FormError message={error} />
        <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
          Send reset link
        </Button>
      </form>
    </AuthCard>
  );
}
