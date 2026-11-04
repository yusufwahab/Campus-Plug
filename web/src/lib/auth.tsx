"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";
import { ApiError, api, tokenStore } from "./api";
import type { User } from "./types";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";

export function useMe() {
  const hasToken = typeof window !== "undefined" && !!tokenStore.get();
  return useQuery<User | null>({
    queryKey: ["me"],
    queryFn: async () => {
      if (!tokenStore.get()) return null;
      try {
        return await api<User>("/me");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          tokenStore.clear();
          return null;
        }
        throw e;
      }
    },
    staleTime: 60_000,
    meta: { hasToken },
  });
}

export function useSignOut() {
  const client = useQueryClient();
  const router = useRouter();
  return () => {
    tokenStore.clear();
    client.clear();
    router.push("/");
  };
}

/** Where a signed-in user should land when onboarding or phone checks are still outstanding. */
export function homeFor(user: User): string {
  if (user.role === "admin" || user.role === "super_admin") return "/admin";
  return "/";
}

type Need = "user" | "seller" | "admin" | "verifier" | "hall_rep";

function allowed(user: User, need: Need): boolean {
  const isAdmin = user.role === "admin" || user.role === "super_admin";
  if (need === "user") return true;
  if (isAdmin) return true;
  if (need === "seller") return user.role === "seller";
  return user.permissions.includes(need);
}

/**
 * Client-side route guard. This is only a convenience: every API call is authorised again by FastAPI.
 * Guests go to /login?next=..., signed-in users without access go to /access-denied.
 */
export function RequireAuth({ need = "user", children }: { need?: Need; children: ReactNode }) {
  const me = useMe();
  const router = useRouter();
  const pathname = usePathname();
  const user = me.data;

  useEffect(() => {
    if (me.isPending || me.isError) return;
    if (!user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    else if (!allowed(user, need)) router.replace("/access-denied");
  }, [me.isPending, me.isError, user, need, router, pathname]);

  if (me.isError) return <ErrorState message="We could not check your sign-in." onRetry={() => void me.refetch()} />;
  if (me.isPending || !user || !allowed(user, need)) {
    return (
      <div role="status" aria-label="Checking your sign-in" className="space-y-3">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  return <>{children}</>;
}
