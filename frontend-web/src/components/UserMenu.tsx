// The user menu at the top right (D-AUTH-1): who is logged in, their role, and Log out.

import { ChevronDown, LogOut } from "lucide-react";
import { useNavigate } from "react-router";

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

export function UserMenu() {
  const user = useUser();
  const { logout } = useAuth();
  const navigate = useNavigate();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex min-w-0 items-center gap-2 rounded-md px-2 py-1 text-left transition-colors hover:bg-white/[0.06] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-glow-cyan"
        aria-label={`${user.display_name}, ${ROLE_LABELS[user.role]}: open the user menu`}
      >
        <span
          aria-hidden
          className="grid size-8 shrink-0 place-items-center rounded-full bg-[linear-gradient(135deg,rgb(67_97_238/0.55),rgb(139_92_246/0.45))] text-[13px] font-semibold text-white ring-1 ring-white/20"
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
  );
}
