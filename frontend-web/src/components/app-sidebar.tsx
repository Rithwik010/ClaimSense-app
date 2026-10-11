// The app shell's sidebar (started from the shadcn sidebar-07 block): the logged-in role's pages
// only (D-AUTH-1). Collapses to icons; a sheet on small screens. Who is logged in is in the user
// menu at the top right.

import { NavLink, useLocation } from "react-router";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import { pagesFor, useUser } from "@/lib/auth";

export function AppSidebar() {
  const { pathname } = useLocation();
  const { role } = useUser();
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
            {pagesFor(role).map((item) => (
              <SidebarMenuItem key={item.to}>
                <SidebarMenuButton
                  asChild
                  tooltip={item.label}
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
      <SidebarRail />
    </Sidebar>
  );
}
