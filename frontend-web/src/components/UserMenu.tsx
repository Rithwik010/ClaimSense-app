// The user menu at the top right (D-AUTH-1): who is logged in, their role, Change password
// (D-AUTH-2: the current password, then a new one of 10 to 256 characters that is not the username)
// and Log out.

import { ChevronDown, KeyRound, LogOut } from "lucide-react";
import { useId, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";

import { useChangePassword } from "@/api/hooks";
import { ErrorNotice } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ROLE_LABELS, useAuth, useUser } from "@/lib/auth";

function initials(name: string): string {
  const words = name.replace(/,.*$/, "").split(/\s+/).filter(Boolean);
  return (words.length > 1 ? words[0]![0]! + words[words.length - 1]![0]! : (words[0] ?? "?").slice(0, 2)).toUpperCase();
}

const PASSWORD_MIN = 10;

function PasswordForm({ onDone }: { onDone: () => void }) {
  const change = useChangePassword();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const ids = { current: useId(), next: useId(), again: useId() };
  const mismatch = again !== "" && again !== next;
  return (
    <form
      className="grid gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (mismatch || next.length < PASSWORD_MIN) return;
        change.mutate(
          { current_password: current, new_password: next },
          {
            onSuccess: () => {
              toast.success("Password changed");
              onDone();
            },
          },
        );
      }}
    >
      <label htmlFor={ids.current} className="text-[13px] font-semibold">
        Current password
      </label>
      <Input id={ids.current} type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
      <label htmlFor={ids.next} className="text-[13px] font-semibold">
        New password
      </label>
      <Input id={ids.next} type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
      <p className="text-[13px] text-ink-muted">At least {PASSWORD_MIN} characters, and not your username.</p>
      <label htmlFor={ids.again} className="text-[13px] font-semibold">
        New password again
      </label>
      <Input
        id={ids.again}
        type="password"
        autoComplete="new-password"
        value={again}
        aria-invalid={mismatch}
        onChange={(e) => setAgain(e.target.value)}
      />
      {mismatch && <p className="text-[13px] font-semibold text-deny">The two new passwords are not the same.</p>}
      {change.error && <ErrorNotice error={change.error} />}
      <DialogFooter className="mt-1 gap-3">
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={!current || next.length < PASSWORD_MIN || next !== again || change.isPending}
        >
          {change.isPending ? "Changing" : "Change password"}
        </Button>
      </DialogFooter>
    </form>
  );
}

export function UserMenu() {
  const user = useUser();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [changing, setChanging] = useState(false);
  return (
    <>
    <Dialog open={changing} onOpenChange={setChanging}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-[18px] font-semibold">Change your password</DialogTitle>
          <DialogDescription className="text-[15px] text-ink-muted">
            You stay logged in here. Use the new password next time you log in.
          </DialogDescription>
        </DialogHeader>
        <PasswordForm onDone={() => setChanging(false)} />
      </DialogContent>
    </Dialog>
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex min-w-0 items-center gap-2 rounded-full border border-rules px-2 py-1 text-left transition-colors hover:bg-brand-tint focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-glow-cyan"
        aria-label={`${user.display_name}, ${ROLE_LABELS[user.role]}: open the user menu`}
      >
        <span
          aria-hidden
          className="grid size-8 shrink-0 place-items-center rounded-full bg-primary text-[13px] font-semibold text-white"
        >
          {initials(user.display_name)}
        </span>
        <span className="hidden min-w-0 sm:block">
          <span className="block truncate text-[15px] leading-5 font-semibold">{user.display_name}</span>
          <span className="block text-[13px] leading-4 text-ink-muted">{ROLE_LABELS[user.role]}</span>
        </span>
        <ChevronDown aria-hidden className="size-4 shrink-0 text-ink-muted" />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="glass-strong w-64 rounded-lg p-1 ring-0"
      >
        <DropdownMenuLabel className="px-2 py-1.5">
          <span className="block text-[15px] font-semibold text-ink">{user.display_name}</span>
          <span className="block text-[13px] font-normal text-ink-muted">{ROLE_LABELS[user.role]}</span>
          <span className="block text-[13px] font-normal text-ink-muted">Username {user.username}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator className="bg-rules" />
        <DropdownMenuItem className="px-2 py-1.5 text-[15px]" onSelect={() => setChanging(true)}>
          <KeyRound aria-hidden />
          Change password
        </DropdownMenuItem>
        <DropdownMenuItem
          className="px-2 py-1.5 text-[15px]"
          onSelect={() => {
            void logout().finally(() => navigate("/login", { replace: true }));
          }}
        >
          <LogOut aria-hidden />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
    </>
  );
}
