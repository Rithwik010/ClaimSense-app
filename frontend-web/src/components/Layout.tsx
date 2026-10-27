// The app shell: sidebar, a header with the breadcrumb and the user menu (D-AUTH-1), and the page,
// which fades in and rises 4 px on navigation (DESIGN.md). The header is frosted glass so the page
// scrolls under it.

import { motion, useReducedMotion } from "motion/react";
import { Fragment, useId, type ReactNode } from "react";
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
  const [first, second, third] = pathname.split("/").filter(Boolean);
  if (first === "member") {
    // A member's pages (D-MEM-1): My claims, a claim, My benefits, Profile.
    const page = PAGES.find((n) => n.to === `/member/${second ?? ""}`);
    if (second === "claims" && third) {
      return [{ label: "My claims", to: "/member/claims" }, { label: decodeURIComponent(third) }];
    }
    return [{ label: page?.label ?? "ClaimSense" }];
  }
  if (first === "review" && second) {
    return [{ label: "Review queue", to: "/queue" }, { label: decodeURIComponent(second) }];
  }
  const lists: Record<string, string> = { claims: "Claims", "my-claims": "My claims" };
  if (first && first in lists && second) {
    const claim = { label: decodeURIComponent(second), to: `/${first}/${second}` };
    const list = { label: lists[first] ?? first, to: `/${first}` };
    return third === "eob"
      ? [list, claim, { label: "Patient EOB" }]
      : [list, { label: claim.label }];
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
      <SidebarInset className="min-w-0 bg-transparent">
        <header className="sticky top-0 z-20 flex h-14 print:hidden shrink-0 items-center gap-2 border-b border-rules bg-canvas/60 px-4 backdrop-blur-xl backdrop-saturate-150 md:px-6">
          <SidebarTrigger className="-ml-1" aria-label="Show or hide the navigation" />
          <Separator orientation="vertical" className="mr-2 h-4 bg-rules" />
          <Breadcrumb className="min-w-0 flex-1">
            <BreadcrumbList>
              {trail.map((crumb, i) => (
                <Fragment key={crumb.label}>
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
                </Fragment>
              ))}
            </BreadcrumbList>
          </Breadcrumb>
          <UserMenu />
        </header>
        {/* SidebarInset is the page's <main> landmark; this is its animated content. */}
        <motion.div
          key={pathname}
          initial={reduce ? false : { opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reduce ? 0 : 0.18, ease: "easeOut" }}
          className="min-w-0 flex-1 px-4 py-6 md:px-8 md:py-10"
        >
          <div className="mx-auto max-w-[1280px]">
            <ErrorBoundary resetKey={pathname}>
              <Outlet />
            </ErrorBoundary>
          </div>
        </motion.div>
      </SidebarInset>
    </SidebarProvider>
  );
}

export function PageTitle({ title, hint, actions }: { title: string; hint?: string; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-[26px] leading-[34px] font-semibold tracking-[-0.02em] break-words md:text-[30px] md:leading-[38px]">
          {title}
        </h1>
        {hint && <p className="mt-2 max-w-[72ch] text-ink-muted">{hint}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </div>
  );
}

export function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  const id = useId();
  return (
    <section className="mb-8" aria-labelledby={id}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={id} className="text-[18px] leading-[26px] font-semibold">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

/** A panel (14 px radius): a quiet surface by default, frosted glass for a page's summary. */
export function Panel({
  children,
  className = "",
  glass = false,
}: {
  children: ReactNode;
  className?: string;
  glass?: boolean;
}) {
  return <div className={`rounded-lg ${glass ? "glass edge-light" : "surface"} ${className}`}>{children}</div>;
}
