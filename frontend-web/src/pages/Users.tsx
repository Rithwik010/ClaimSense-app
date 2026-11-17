// Users (admin, D-AUTH-2): every login with its role and state (active, locked after five failed
// logins, or deactivated), and what an admin does with them: add a login (a provider's needs the
// NPI of a provider on file, a member's the member ID of a member on file), set a new password
// (which also unlocks it), unlock, deactivate and reactivate. An admin cannot deactivate their own
// login. Passwords are 10 to 256 characters and not the username; the API checks every rule.

import { KeyRound, LockOpen, UserPlus } from "lucide-react";
import { useId, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { useUserAdmin, useUsers, type NewUser } from "@/api/hooks";
import type { Role, UserInfo } from "@/api/types";
import { Chip } from "@/components/Chip";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PageTitle } from "@/components/Layout";
import { ErrorNotice, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ROLE_LABELS, useUser } from "@/lib/auth";
import { dateTime } from "@/lib/format";
import type { Label } from "@/lib/labels";

const ROLES: Role[] = ["provider", "reviewer", "admin", "member"];
export const PASSWORD_MIN = 10;

function state(user: UserInfo): Label {
  if (!user.active) return { label: "Deactivated", hint: "Cannot log in", tone: "reject" };
  if (user.locked_until) {
    return { label: "Locked", hint: `Five failed logins: locked until ${dateTime(user.locked_until)}`, tone: "pend" };
  }
  return { label: "Active", hint: "Can log in", tone: "neutral" };
}

function Field({ label, children, hint }: { label: string; children: (id: string) => ReactNode; hint?: string }) {
  const id = useId();
  return (
    <div className="grid gap-1.5">
      <label htmlFor={id} className="text-[13px] font-semibold">
        {label}
      </label>
      {children(id)}
      {hint && <p className="text-[13px] text-ink-muted">{hint}</p>}
    </div>
  );
}

function NewUserDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const admin = useUserAdmin();
  const [form, setForm] = useState<NewUser>({ username: "", display_name: "", role: "reviewer", password: "" });
  const set = (next: Partial<NewUser>) => setForm((now) => ({ ...now, ...next }));
  const ready = form.username.trim() !== "" && form.password.length >= PASSWORD_MIN;
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          admin.create.reset();
          onClose();
        }
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-[18px] font-semibold">Add a login</DialogTitle>
          <DialogDescription className="text-[15px] text-ink-muted">
            The person logs in with this username and password. Give them the password another way; it is never shown again.
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            admin.create.mutate(
              {
                ...form,
                provider_id: form.role === "provider" ? form.provider_id?.trim() || null : null,
                member_id: form.role === "member" ? form.member_id?.trim() || null : null,
              },
              {
                onSuccess: (user) => {
                  toast.success(`Login ${user.username} added`);
                  setForm({ username: "", display_name: "", role: "reviewer", password: "" });
                  onClose();
                },
              },
            );
          }}
        >
          <Field label="Role">
            {(id) => (
              <Select value={form.role} onValueChange={(value) => set({ role: value as Role })}>
                <SelectTrigger id={id} className="w-full bg-paper">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((role) => (
                    <SelectItem key={role} value={role}>
                      {ROLE_LABELS[role]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </Field>
          <Field label="Username" hint="Letters, digits, dots, dashes or underscores.">
            {(id) => (
              <Input id={id} value={form.username} autoComplete="off" className="bg-paper" onChange={(e) => set({ username: e.target.value })} />
            )}
          </Field>
          <Field label="Name shown" hint={form.role === "provider" || form.role === "member" ? "Left empty: the name on file." : undefined}>
            {(id) => (
              <Input id={id} value={form.display_name} className="bg-paper" onChange={(e) => set({ display_name: e.target.value })} />
            )}
          </Field>
          {form.role === "provider" && (
            <Field label="Provider NPI" hint="The 10-digit NPI of a provider on file.">
              {(id) => (
                <Input
                  id={id}
                  value={form.provider_id ?? ""}
                  inputMode="numeric"
                  className="bg-paper"
                  onChange={(e) => set({ provider_id: e.target.value })}
                />
              )}
            </Field>
          )}
          {form.role === "member" && (
            <Field label="Member ID" hint="The member ID of a member on file, for example MBR-000123.">
              {(id) => (
                <Input id={id} value={form.member_id ?? ""} className="bg-paper" onChange={(e) => set({ member_id: e.target.value })} />
              )}
            </Field>
          )}
          <Field label="Password" hint={`At least ${PASSWORD_MIN} characters, and not the username.`}>
            {(id) => (
              <Input
                id={id}
                type="password"
                value={form.password}
                autoComplete="new-password"
                className="bg-paper"
                onChange={(e) => set({ password: e.target.value })}
              />
            )}
          </Field>
          {admin.create.error && <ErrorNotice error={admin.create.error} />}
          <DialogFooter className="gap-3">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!ready || admin.create.isPending}>
              {admin.create.isPending ? "Adding" : "Add login"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function PasswordDialog({ username, onClose }: { username: string | null; onClose: () => void }) {
  const admin = useUserAdmin();
  const [password, setPassword] = useState("");
  const id = useId();
  return (
    <Dialog
      open={username !== null}
      onOpenChange={(next) => {
        if (!next) {
          setPassword("");
          admin.password.reset();
          onClose();
        }
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-[18px] font-semibold">New password for {username}</DialogTitle>
          <DialogDescription className="text-[15px] text-ink-muted">
            It replaces the current one and unlocks the login. Give it to them another way.
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (!username) return;
            admin.password.mutate(
              { username, password },
              {
                onSuccess: () => {
                  toast.success(`New password set for ${username}`);
                  setPassword("");
                  onClose();
                },
              },
            );
          }}
        >
          <label htmlFor={id} className="text-[13px] font-semibold">
            New password
          </label>
          <Input
            id={id}
            type="password"
            value={password}
            autoComplete="new-password"
            className="bg-paper"
            onChange={(e) => setPassword(e.target.value)}
          />
          <p className="text-[13px] text-ink-muted">At least {PASSWORD_MIN} characters, and not the username.</p>
          {admin.password.error && <ErrorNotice error={admin.password.error} />}
          <DialogFooter className="gap-3">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={password.length < PASSWORD_MIN || admin.password.isPending}>
              {admin.password.isPending ? "Saving" : "Set password"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function Users() {
  const users = useUsers();
  const admin = useUserAdmin();
  const me = useUser().username;
  const [adding, setAdding] = useState(false);
  const [resetting, setResetting] = useState<string | null>(null);
  const [toggling, setToggling] = useState<UserInfo | null>(null);
  return (
    <>
      <PageTitle
        title="Users"
        hint="Every login, its role and whether it can log in. Five failed logins in a row lock a login for 15 minutes."
        actions={
          <Button size="lg" onClick={() => setAdding(true)}>
            <UserPlus aria-hidden /> Add a login
          </Button>
        }
      />
      {users.isPending ? (
        <Skeleton lines={6} />
      ) : users.error ? (
        <ErrorNotice error={users.error} onRetry={() => void users.refetch()} />
      ) : (
        <div className="surface overflow-x-auto rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Login</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Linked to</TableHead>
                <TableHead>State</TableHead>
                <TableHead>Password changed</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.data.map((user) => (
                <TableRow key={user.username}>
                  <TableCell className="min-w-44">
                    <span className="font-semibold">{user.username}</span>
                    <div className="text-[13px] text-ink-muted">{user.display_name}</div>
                  </TableCell>
                  <TableCell>{ROLE_LABELS[user.role]}</TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    {user.provider_id ? `NPI ${user.provider_id}` : user.member_id ?? "—"}
                  </TableCell>
                  <TableCell>
                    <Chip label={state(user)} />
                  </TableCell>
                  <TableCell className="text-[13px] whitespace-nowrap text-ink-muted">{dateTime(user.password_changed_at)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex flex-wrap justify-end gap-2">
                      {user.locked_until && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={admin.unlock.isPending}
                          onClick={() =>
                            admin.unlock.mutate(user.username, {
                              onSuccess: () => toast.success(`${user.username} unlocked`),
                              onError: (error) => toast.error(error.message),
                            })
                          }
                        >
                          <LockOpen aria-hidden /> Unlock
                        </Button>
                      )}
                      <Button size="sm" variant="outline" onClick={() => setResetting(user.username)}>
                        <KeyRound aria-hidden /> New password
                      </Button>
                      {user.username !== me && (
                        <Button size="sm" variant="ghost" onClick={() => setToggling(user)}>
                          {user.active ? "Deactivate" : "Reactivate"}
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <NewUserDialog open={adding} onClose={() => setAdding(false)} />
      <PasswordDialog username={resetting} onClose={() => setResetting(null)} />
      <ConfirmDialog
        open={toggling !== null}
        title={toggling?.active ? `Deactivate ${toggling.username}?` : `Reactivate ${toggling?.username ?? ""}?`}
        confirmLabel={toggling?.active ? "Deactivate" : "Reactivate"}
        onCancel={() => setToggling(null)}
        onConfirm={() => {
          if (!toggling) return;
          admin.active.mutate(
            { username: toggling.username, active: !toggling.active },
            {
              onSuccess: () => toast.success(`${toggling.username} ${toggling.active ? "deactivated" : "reactivated"}`),
              onError: (error) => toast.error(error.message),
            },
          );
          setToggling(null);
        }}
      >
        {toggling?.active
          ? "They are logged out at once and cannot log in until an admin reactivates the login. Nothing they did is changed."
          : "They can log in again with their password."}
      </ConfirmDialog>
    </>
  );
}
