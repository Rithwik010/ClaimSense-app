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
        <div className="flex h-16 items-center gap-3 px-2 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
          <LogoMark size={36} className="shrink-0" />
          <Wordmark className="truncate text-[28px] text-white group-data-[collapsible=icon]:hidden" />
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="mb-1 text-[13px] font-semibold tracking-[0.08em] text-[#ccd6ff] uppercase">
            {ROLE_LABELS[role]}
          </SidebarGroupLabel>
          <SidebarMenu className="gap-1.5">
            {pagesFor(role).map((item) => (
              <SidebarMenuItem key={item.to}>
                <SidebarMenuButton
                  asChild
                  tooltip={item.label}
                  className="h-12 gap-3 px-3 text-[17px] font-medium text-white transition-colors hover:bg-sidebar-accent hover:text-white data-active:bg-sidebar-accent data-active:font-bold data-active:text-white data-active:shadow-[inset_4px_0_0_#ffffff] group-data-[collapsible=icon]:size-12! group-data-[collapsible=icon]:p-3! [&_svg]:size-[22px]"
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
        <p className="flex items-center gap-2 rounded-md border border-[#ccd6ff]/40 bg-sidebar-accent px-3 py-2.5 text-[14px] text-white">
          <ShieldCheck aria-hidden className="size-[18px] shrink-0 text-white" />
          Prototype · synthetic data only
        </p>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
