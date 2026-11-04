"use client";
import { Button } from "@/components/ui/Button";
import type { components } from "@/lib/api-schema";
import type { useAction } from "@/lib/hooks";

type User = components["schemas"]["UserOut"];

export type UserAction = { user: User; kind: "suspended" | "banned" | "active" | "verifier" | "hall_rep" | "remove-verifier" | "remove-hall_rep" };

export function userActionCopy(a: UserAction) {
  const name = a.user.full_name;
  switch (a.kind) {
    case "suspended": return { title: `Suspend ${name}?`, description: "They are signed out and cannot sign in until you reactivate them.", confirm: "Suspend", destructive: true };
    case "banned": return { title: `Ban ${name}?`, description: "They are signed out and cannot sign in. Use this for serious or repeated violations.", confirm: "Ban", destructive: true };
    case "active": return { title: `Reactivate ${name}?`, description: "They can sign in again.", confirm: "Reactivate", destructive: false };
    case "verifier": return { title: `Make ${name} a Verifier?`, description: "They can review verification submissions assigned to them and nothing else in Admin.", confirm: "Grant permission", destructive: false };
    case "hall_rep": return { title: `Make ${name} a Hall Rep?`, description: "They can onboard and vouch for sellers and see their hall's requests. They cannot see student IDs or approve sellers.", confirm: "Grant permission", destructive: false };
    case "remove-verifier": return { title: `Remove ${name}'s Verifier permission?`, description: "They lose access to the verification queue.", confirm: "Remove permission", destructive: true };
    case "remove-hall_rep": return { title: `Remove ${name}'s Hall Rep permission?`, description: "They lose access to Hall Rep tools.", confirm: "Remove permission", destructive: true };
  }
}

export async function runUserAction(act: ReturnType<typeof useAction>, a: UserAction, reason: string) {
  const id = a.user.id;
  if (a.kind === "suspended" || a.kind === "banned" || a.kind === "active") {
    await act("POST", `/admin/users/${id}/status`, { status: a.kind, reason }, "Account updated");
  } else {
    const permission = a.kind.replace("remove-", "") as "verifier" | "hall_rep";
    await act("POST", `/admin/users/${id}/permissions`, { permission, granted: !a.kind.startsWith("remove-"), reason }, "Permission updated");
  }
}

export function UserButtons({ user, onAction }: { user: User; onAction: (a: UserAction) => void }) {
  const isAdmin = user.role === "admin" || user.role === "super_admin";
  return (
    <>
      {user.status === "active" ? (
        <>
          <Button variant="tertiary" onClick={() => onAction({ user, kind: "suspended" })}>Suspend</Button>
          <Button variant="danger" onClick={() => onAction({ user, kind: "banned" })}>Ban</Button>
        </>
      ) : (
        <Button variant="secondary" onClick={() => onAction({ user, kind: "active" })}>Reactivate</Button>
      )}
      {!isAdmin && (
        <>
          <Button variant="tertiary" onClick={() => onAction({ user, kind: user.permissions.includes("verifier") ? "remove-verifier" : "verifier" })}>
            {user.permissions.includes("verifier") ? "Remove Verifier" : "Make Verifier"}
          </Button>
          <Button variant="tertiary" onClick={() => onAction({ user, kind: user.permissions.includes("hall_rep") ? "remove-hall_rep" : "hall_rep" })}>
            {user.permissions.includes("hall_rep") ? "Remove Hall Rep" : "Make Hall Rep"}
          </Button>
        </>
      )}
    </>
  );
}
