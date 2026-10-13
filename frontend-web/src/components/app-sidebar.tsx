// The app shell's sidebar (started from the shadcn sidebar-07 block): the logged-in role's pages
// only (D-AUTH-1). Collapses to icons; a sheet on small screens. Who is logged in is in the user
// menu at the top right.

import { ShieldCheck } from "lucide-react";
import { NavLink, useLocation } from "react-router";

import { LogoMark, Wordmark } from "@/components/fx";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import { ROLE_LABELS, pagesFor, useUser } from "@/lib/auth";

export function AppSidebar() {
  const { pathname } = useLocation();
  const { role } = useUser();
  const { setOpenMobile } = useSidebar();
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex h-11 items-center gap-2.5 px-1.5 group-data-[collapsible=icon]:px-0">
          <LogoMark size={28} className="shrink-0" />
          <Wordmark className="truncate text-[17px] group-data-[collapsible=icon]:hidden" />
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="text-[12px] font-semibold tracking-wide text-ink-muted">
            {ROLE_LABELS[role]}
          </SidebarGroupLabel>
          <SidebarMenu className="gap-1">
            {pagesFor(role).map((item) => (
              <SidebarMenuItem key={item.to}>
                <SidebarMenuButton
                  asChild
                  tooltip={item.label}
                  className="h-9 text-[15px] text-ink-muted transition-colors hover:text-ink data-active:bg-[linear-gradient(90deg,rgb(67_97_238/0.32),rgb(67_97_238/0.06))] data-active:text-white data-active:shadow-[inset_2px_0_0_var(--color-glow-blue)] [&_svg]:size-[18px]"
                  isActive={
                    pathname.startsWith(item.to) ||
                    (item.to === "/queue" && pathname.startsWith("/review"))
                  }
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
      <SidebarFooter className="group-data-[collapsible=icon]:hidden">
        <p className="flex items-center gap-2 rounded-md border border-rules bg-white/[0.03] px-3 py-2 text-[13px] text-ink-muted">
          <ShieldCheck aria-hidden className="size-4 shrink-0 text-glow-cyan" />
          Prototype · synthetic data only
        </p>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
