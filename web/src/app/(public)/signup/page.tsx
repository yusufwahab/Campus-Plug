"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { AuthCard, FormError } from "@/components/auth/AuthCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { ApiError, api, tokenStore } from "@/lib/api";
import { safeNext } from "@/lib/safe-next";
import { signupSchema } from "@/lib/schemas";
import type { TokenOut } from "@/lib/types";

type Values = z.infer<typeof signupSchema>;

function SignupForm() {
  const router = useRouter();
  const client = useQueryClient();
  const next = safeNext(useSearchParams().get("next"));
  const [error, setError] = useState<string | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(signupSchema) });
  const errors = form.formState.errors;

  async function onSubmit(values: Values) {
    setError(null);
    try {
      const res = await api<TokenOut>("/auth/signup", { method: "POST", body: values, token: null });
      if (res.token) tokenStore.set(res.token);
      await client.invalidateQueries({ queryKey: ["me"] });
      router.push(`/verify-email?next=${encodeURIComponent(next)}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create your account.");
    }
  }

  return (
    <AuthCard title="Create your account" subtitle="Join your campus marketplace in a minute.">
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Input label="Full name" autoComplete="name" error={errors.full_name?.message} {...form.register("full_name")} />
        <Input label="Email" type="email" autoComplete="email" error={errors.email?.message} {...form.register("email")} />
        <Input label="Phone number" type="tel" autoComplete="tel" hint="Your number stays hidden from other users until you both agree to share it." error={errors.phone?.message} {...form.register("phone")} />
        <Input label="Password" type="password" autoComplete="new-password" hint="At least 8 characters." error={errors.password?.message} {...form.register("password")} />
        <FormError message={error} />
        <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
          Create account
        </Button>
      </form>
      <p className="mt-4 text-sm text-muted">
        Already have an account?{" "}
        <Link href="/login" className="font-semibold text-ink underline">
          Sign in
        </Link>
      </p>
    </AuthCard>
  );
}

export default function SignupPage() {
  return (
    <Suspense>
      <SignupForm />
    </Suspense>
  );
}
