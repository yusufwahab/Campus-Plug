"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { AuthCard, FormError } from "@/components/auth/AuthCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import { resetSchema } from "@/lib/schemas";

type Values = z.infer<typeof resetSchema>;

function ResetForm() {
  const token = useSearchParams().get("token");
  const router = useRouter();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(resetSchema) });

  async function onSubmit(values: Values) {
    setError(null);
    try {
      await api("/auth/reset", { method: "POST", body: { token, new_password: values.new_password }, token: null });
      toast("Password updated. Sign in with your new password.");
      router.push("/login");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not reset your password.");
    }
  }

  if (!token) {
    return (
      <AuthCard title="Reset link missing" subtitle="Open the link from your email, or request a new one.">
        <Button href="/forgot-password">Request a new link</Button>
      </AuthCard>
    );
  }
  return (
    <AuthCard title="Choose a new password">
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Input label="New password" type="password" autoComplete="new-password" error={form.formState.errors.new_password?.message} {...form.register("new_password")} />
        <FormError message={error} />
        <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
          Update password
        </Button>
      </form>
    </AuthCard>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetForm />
    </Suspense>
  );
}
