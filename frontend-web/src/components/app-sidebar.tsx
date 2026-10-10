// The app shell's sidebar (started from the shadcn sidebar-07 block): navigation, then the
// person's role and reviewer ID in the footer. Collapses to icons; a sheet on small screens.

import { BarChart3, ClipboardCheck, FileUp, Files, Scale } from "lucide-react";
import { NavLink, useLocation } from "react-router";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Role } from "@/api/types";
import { useSession } from "@/lib/session";

export const NAV = [
  { to: "/submit", label: "Submit claim", icon: FileUp },
  { to: "/queue", label: "Review queue", icon: ClipboardCheck },
  { to: "/claims", label: "Claims", icon: Files },
  { to: "/rule-outcomes", label: "Rule outcomes", icon: Scale },
  { to: "/metrics", label: "Metrics", icon: BarChart3 },
];

const ROLES: { value: Role; label: string }[] = [
  { value: "provider", label: "Provider" },
  { value: "reviewer", label: "Reviewer" },
  { value: "admin", label: "Admin" },
];

export function AppSidebar() {
  const { pathname } = useLocation();
  const { role, setRole, reviewerId, setReviewerId } = useSession();
  const { setOpenMobile } = useSidebar();
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex h-10 items-center gap-2 px-2">
          <span
            aria-hidden
            className="grid size-6 shrink-0 place-items-center rounded-md bg-ink text-[13px] font-semibold text-white"
          >
            C
          </span>
          <span className="truncate text-[15px] font-semibold group-data-[collapsible=icon]:hidden">
            ClaimSense
          </span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu>
            {NAV.map((item) => (
              <SidebarMenuItem key={item.to}>
                <SidebarMenuButton
                  asChild
                  tooltip={item.label}
                  isActive={pathname.startsWith(item.to) || (item.to === "/queue" && pathname.startsWith("/review"))}
                >
                  <NavLink to={item.to} onClick={() => setOpenMobile(false)}>
                    <item.icon aria-hidden />
                    <span>{item.label}</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="gap-3 border-t border-rules p-3 group-data-[collapsible=icon]:hidden">
        <label className="grid gap-1 text-[13px] text-ink-muted" htmlFor="role">
          Role
          <Select value={role} onValueChange={(value) => setRole(value as Role)}>
            <SelectTrigger id="role" aria-label="Role" className="w-full bg-paper text-ink">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ROLES.map((r) => (
                <SelectItem key={r.value} value={r.value}>
                  {r.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
        <label className="grid gap-1 text-[13px] text-ink-muted" htmlFor="reviewer-id">
          Reviewer ID
          <Input
            id="reviewer-id"
            value={reviewerId}
            placeholder="For example reviewer-1"
            className="bg-paper text-ink"
            onChange={(event) => setReviewerId(event.target.value)}
          />
        </label>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
