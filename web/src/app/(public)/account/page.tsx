"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { FormError } from "@/components/auth/AuthCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { ConfirmModal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api, tokenStore } from "@/lib/api";
import { RequireAuth, useMe, useSignOut } from "@/lib/auth";
import { passwordSchema, profileSchema } from "@/lib/schemas";

type Profile = z.infer<typeof profileSchema>;
type Password = z.infer<typeof passwordSchema>;

function Account() {
  const me = useMe();
  const client = useQueryClient();
  const router = useRouter();
  const toast = useToast();
  const signOut = useSignOut();
  const user = me.data;
  const [confirm, setConfirm] = useState<"signout" | "delete" | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const profile = useForm<Profile>({ resolver: zodResolver(profileSchema), values: { full_name: user?.full_name ?? "" } });
  const password = useForm<Password>({ resolver: zodResolver(passwordSchema) });

  if (!user) return null;

  async function saveProfile(values: Profile) {
    try {
      await api("/me", { method: "PATCH", body: values });
      await client.invalidateQueries({ queryKey: ["me"] });
      toast("Profile saved");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not save", "error");
    }
  }

  async function savePassword(values: Password) {
    setPasswordError(null);
    try {
      await api("/me/password", { method: "POST", body: values });
      password.reset();
      toast("Password changed");
    } catch (e) {
      setPasswordError(e instanceof ApiError ? e.message : "Could not change your password.");
    }
  }

  async function toggleOptional(on: boolean) {
    await api("/me", { method: "PATCH", body: { notify_optional: on } });
    await client.invalidateQueries({ queryKey: ["me"] });
    toast(on ? "Optional notifications on" : "Optional notifications off", "info");
  }

  async function deleteAccount() {
    setDeleting(true);
    setDeleteError(null);
    try {
      await api("/me", { method: "DELETE" });
      tokenStore.clear();
      client.clear();
      router.push("/");
    } catch (e) {
      setDeleteError(e instanceof ApiError ? e.message : "Could not delete your account.");
      setConfirm(null);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-3xl font-extrabold">Account</h1>
      <Card className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{user.email}</span>
        <Badge tone={user.phone_verified ? "verified" : "pending"}>{user.phone_verified ? "Phone confirmed" : "Phone not confirmed"}</Badge>
        {!user.phone_verified && (
          <Button href="/verify-phone" variant="tertiary">
            Confirm phone
          </Button>
        )}
      </Card>

      <Card>
        <h2 className="text-lg font-bold">Profile</h2>
        <form onSubmit={profile.handleSubmit(saveProfile)} className="mt-3 space-y-3" noValidate>
          <Input label="Full name" error={profile.formState.errors.full_name?.message} {...profile.register("full_name")} />
          <Button type="submit" variant="secondary" loading={profile.formState.isSubmitting}>
            Save profile
          </Button>
        </form>
        <p className="mt-3 text-sm text-muted">
          Campus and hall are set in{" "}
          <Link className="font-semibold text-ink underline" href="/onboarding">
            onboarding
          </Link>
          .
        </p>
      </Card>

      <Card>
        <h2 className="text-lg font-bold">Security</h2>
        <form onSubmit={password.handleSubmit(savePassword)} className="mt-3 space-y-3" noValidate>
          <Input label="Current password" type="password" autoComplete="current-password" error={password.formState.errors.current_password?.message} {...password.register("current_password")} />
          <Input label="New password" type="password" autoComplete="new-password" error={password.formState.errors.new_password?.message} {...password.register("new_password")} />
          <FormError message={passwordError} />
          <Button type="submit" variant="secondary" loading={password.formState.isSubmitting}>
            Change password
          </Button>
        </form>
      </Card>

      <Card className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-bold">Reports</h2>
          <p className="text-sm text-muted">Track reports you have made.</p>
        </div>
        <Button href="/reports" variant="tertiary">
          My reports
        </Button>
      </Card>

      <Card>
        <h2 className="text-lg font-bold">Notifications</h2>
        <label className="mt-3 flex min-h-11 items-center gap-3 text-sm">
          <input type="checkbox" className="size-5 accent-forest" checked={user.notify_optional} onChange={(e) => void toggleOptional(e.target.checked)} />
          <span>
            Optional updates (promotions, reminders, tips)
            <span className="block text-xs text-muted">Order and security messages always stay on.</span>
          </span>
        </label>
      </Card>

      <Card className="space-y-3">
        <h2 className="text-lg font-bold">Sign out or delete</h2>
        <FormError message={deleteError} />
        <div className="flex flex-wrap gap-2">
          <Button variant="tertiary" onClick={() => setConfirm("signout")}>
            Sign out
          </Button>
          <Button variant="danger" onClick={() => setConfirm("delete")}>
            Delete account
          </Button>
        </div>
      </Card>

      <ConfirmModal open={confirm === "signout"} title="Sign out?" body="You will need to sign in again to chat, order or sell." confirmLabel="Sign out" onConfirm={signOut} onClose={() => setConfirm(null)} />
      <ConfirmModal
        open={confirm === "delete"}
        title="Delete your account?"
        body="Your profile is removed and you are signed out. Accounts with open orders or disputes cannot be deleted until those finish."
        confirmLabel="Delete account"
        destructive
        loading={deleting}
        onConfirm={deleteAccount}
        onClose={() => setConfirm(null)}
      />
    </div>
  );
}

export default function AccountPage() {
  return (
    <RequireAuth>
      <Account />
    </RequireAuth>
  );
}
