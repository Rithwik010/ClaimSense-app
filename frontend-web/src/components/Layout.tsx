// The app shell: sidebar, a header with the breadcrumb and the user menu (D-AUTH-1), and the page,
// which fades in on navigation (motion moment 1, DESIGN.md).

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { Link, Outlet, useLocation } from "react-router";

import { AppSidebar } from "@/components/app-sidebar";
import { UserMenu } from "@/components/UserMenu";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { PAGES } from "@/lib/auth";
import { ErrorBoundary } from "./ErrorBoundary";

function crumbs(pathname: string): { label: string; to?: string }[] {
  const [first, second] = pathname.split("/").filter(Boolean);
  if (first === "review" && second) {
    return [{ label: "Review queue", to: "/queue" }, { label: decodeURIComponent(second) }];
  }
  if (first === "claims" && second) {
    return [{ label: "Claims", to: "/claims" }, { label: decodeURIComponent(second) }];
  }
  const item = PAGES.find((n) => n.to === `/${first ?? ""}`);
  return [{ label: item?.label ?? "ClaimSense" }];
}

export function Layout() {
  const { pathname } = useLocation();
  const reduce = useReducedMotion();
  const trail = crumbs(pathname);
  const wide = typeof window === "undefined" || window.innerWidth >= 1200;
  return (
    <SidebarProvider defaultOpen={wide}>
      <AppSidebar />
      <SidebarInset className="min-w-0 bg-canvas">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-rules bg-paper px-4">
          <SidebarTrigger className="-ml-1" aria-label="Show or hide the navigation" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <Breadcrumb className="min-w-0 flex-1">
            <BreadcrumbList>
              {trail.map((crumb, i) => (
                <span key={crumb.label} className="contents">
                  {i > 0 && <BreadcrumbSeparator />}
                  <BreadcrumbItem>
                    {crumb.to ? (
                      <BreadcrumbLink asChild>
                        <Link to={crumb.to}>{crumb.label}</Link>
                      </BreadcrumbLink>
                    ) : (
                      <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
                    )}
                  </BreadcrumbItem>
                </span>
              ))}
            </BreadcrumbList>
          </Breadcrumb>
          <UserMenu />
        </header>
        <motion.main
          key={pathname}
          initial={{ opacity: reduce ? 1 : 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: reduce ? 0 : 0.18, ease: "easeOut" }}
          className="min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8"
        >
          <div className="mx-auto max-w-[1280px]">
            <ErrorBoundary resetKey={pathname}>
              <Outlet />
            </ErrorBoundary>
          </div>
        </motion.main>
      </SidebarInset>
    </SidebarProvider>
  );
}

export function PageTitle({ title, hint, actions }: { title: string; hint?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-[24px] leading-8 font-semibold break-words">{title}</h1>
        {hint && <p className="mt-1 max-w-[72ch] text-ink-muted">{hint}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </div>
  );
}

export function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="mb-8">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[18px] leading-[26px] font-semibold">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

/** A bordered paper panel (10 px radius); lists and tables sit directly on it. */
export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-lg border border-rules bg-paper ${className}`}>{children}</div>;
}
