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
import { codeSchema, loginSchema } from "@/lib/schemas";
import type { TokenOut, User } from "@/lib/types";
import { homeFor } from "@/lib/auth";
import { safeNext } from "@/lib/safe-next";

type Login = z.infer<typeof loginSchema>;
type Code = z.infer<typeof codeSchema>;

function LoginForm() {
  const router = useRouter();
  const client = useQueryClient();
  const requestedNext = useSearchParams().get("next");
  const next = safeNext(requestedNext);
  const [error, setError] = useState<string | null>(null);
  const [mfa, setMfa] = useState<{ token: string; enrolled: boolean; secret?: string } | null>(null);

  const creds = useForm<Login>({ resolver: zodResolver(loginSchema) });
  const code = useForm<Code>({ resolver: zodResolver(codeSchema) });

  async function finish(token: string) {
    tokenStore.set(token);
    client.removeQueries({ queryKey: ["me"] });
    const user = await client.fetchQuery({ queryKey: ["me"], queryFn: () => api<User>("/me") });
    router.push(requestedNext ? next : homeFor(user));
  }

  async function onCreds(values: Login) {
    setError(null);
    try {
      const res = await api<TokenOut>("/auth/login", { method: "POST", body: values, token: null });
      if (res.mfa_required && res.mfa_token) {
        let secret: string | undefined;
        if (!res.mfa_enrolled) {
          secret = (await api<{ secret: string }>("/auth/mfa/enroll", { method: "POST", body: { mfa_token: res.mfa_token }, token: null })).secret;
        }
        setMfa({ token: res.mfa_token, enrolled: !!res.mfa_enrolled, secret });
      } else if (res.token) {
        await finish(res.token);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not sign in.");
    }
  }

  async function onCode(values: Code) {
    setError(null);
    try {
      const res = await api<TokenOut>("/auth/mfa/verify", { method: "POST", body: { mfa_token: mfa?.token, code: values.code }, token: null });
      if (res.token) await finish(res.token);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not verify the code.");
    }
  }

  if (mfa) {
    return (
      <AuthCard title="Two-step sign-in" subtitle="Admin accounts need a code from your authenticator app.">
        <form onSubmit={code.handleSubmit(onCode)} className="space-y-4" noValidate>
          {mfa.secret && (
            <div className="rounded-input bg-info-bg p-3 text-sm text-info-fg">
              <p className="font-semibold">First time? Add this key to your authenticator app:</p>
              <code className="mt-1 block break-all font-mono" data-testid="mfa-secret">
                {mfa.secret}
              </code>
            </div>
          )}
          <Input label="6-digit code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} error={code.formState.errors.code?.message} {...code.register("code")} />
          <FormError message={error} />
          <Button type="submit" className="w-full" loading={code.formState.isSubmitting}>
            Verify and sign in
          </Button>
        </form>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Welcome back" subtitle="Sign in to chat, order and sell.">
      <form onSubmit={creds.handleSubmit(onCreds)} className="space-y-4" noValidate>
        <Input label="Email" type="email" autoComplete="email" error={creds.formState.errors.email?.message} {...creds.register("email")} />
        <Input label="Password" type="password" autoComplete="current-password" error={creds.formState.errors.password?.message} {...creds.register("password")} />
        <FormError message={error} />
        <Button type="submit" className="w-full" loading={creds.formState.isSubmitting}>
          Sign in
        </Button>
      </form>
      <p className="mt-4 text-sm">
        <Link href="/forgot-password" className="font-semibold underline">
          Forgot your password?
        </Link>
      </p>
      <p className="mt-2 text-sm text-muted">
        New here?{" "}
        <Link href={`/signup?next=${encodeURIComponent(next)}`} className="font-semibold text-ink underline">
          Create an account
        </Link>
      </p>
    </AuthCard>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
