// Login, the only public page (D-AUTH-1): username and password; after logging in, the page asked
// for (when the role may open it) or the role's home. The page (D-UI-11): the form on white beside
// a blue panel written for a member first (anyone may land here): what you can do after logging in
// and how your information is handled; nothing about how claims are processed inside. On a phone
// the form comes first and the panel follows it.
//
// The panel's wording is data (`PanelContent`), so the wordings being compared can be shown on the
// real page (dev-only preview, src/design/LoginPanels.tsx); the login page itself shows `PANEL`.

import {
  ListChecks,
  Lock,
  MessageSquareText,
  ReceiptText,
  ShieldCheck,
  UserCheck,
  type LucideIcon,
} from "lucide-react";
import { Navigate } from "react-router";

import { LogoMark, Wordmark } from "@/components/fx";
import { cn } from "@/lib/utils";

import { LoginForm } from "./login/LoginForm";
import { destination, useLoginForm } from "./login/useLoginForm";

export interface PanelPoint {
  icon: LucideIcon;
  text: string;
  /** Who the point is for, shown in bold before the text ("Members: ..."). */
  label?: string;
}

/** What the blue panel says: a headline, one supporting line, up to three points, a trust strip. */
export interface PanelContent {
  headline: string;
  line?: string;
  points: PanelPoint[];
  strip: PanelPoint[];
}

// The strip is true for every claim: a rule decides some claims on its own, but every
// recommendation goes to a person before it is final (D-AUTH-1).
const PANEL: PanelContent = {
  headline: "Your claims, clearly explained.",
  line: "See where each claim stands and why, in plain language.",
  points: [
    { icon: ListChecks, text: "Follow each claim from submission to decision" },
    { icon: MessageSquareText, text: "Understand every decision in plain words" },
    { icon: ReceiptText, text: "See your benefits, costs and statements (EOB) in one place" },
  ],
  strip: [
    { icon: Lock, text: "Your information stays private" },
    { icon: ShieldCheck, text: "Secure sign-in" },
    { icon: UserCheck, text: "A person reviews every recommendation" },
  ],
};

function Brand({ onBlue = false, className }: { onBlue?: boolean; className?: string }) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <LogoMark size={36} />
      <Wordmark className={cn("text-[28px] leading-none", onBlue ? "text-white" : "text-ink-strong")} />
    </div>
  );
}

export function Login({ panel = PANEL, intro = "Welcome back." }: { panel?: PanelContent; intro?: string }) {
  const form = useLoginForm();

  if (form.user) return <Navigate to={destination(form.from, form.user.role)} replace />;

  return (
    <div className="flex min-h-svh flex-col bg-white lg:flex-row-reverse">
      <main className="flex flex-1 flex-col px-4 py-6 sm:px-10 lg:px-16 lg:py-10">
        <Brand className="mx-auto w-full max-w-[400px] lg:hidden" />
        <div className="flex flex-1 items-center justify-center py-10 lg:py-0">
          <LoginForm form={form} intro={intro} className="w-full max-w-[400px]" />
        </div>
      </main>

      <aside
        aria-label="About ClaimSense"
        className="flex flex-col gap-10 bg-sidebar px-4 py-10 sm:px-10 lg:w-[46%] lg:justify-between lg:px-16 lg:py-14"
      >
        <Brand onBlue className="hidden lg:flex" />
        <div className="flex flex-col gap-9">
          <div>
            <h2 className="font-heading text-[34px] leading-10 font-bold tracking-[-0.01em] text-white md:text-[52px] md:leading-[56px]">
              {panel.headline}
            </h2>
            {panel.line && (
              <p className="mt-3 text-[16px] leading-6 text-pretty text-brand-tint md:text-[18px] md:leading-7">
                {panel.line}
              </p>
            )}
          </div>
          {panel.points.length > 0 && (
            <ul className="flex flex-col gap-4">
              {panel.points.map(({ icon: Icon, text, label }) => (
                <li key={text} className="flex items-center gap-3.5 text-[15px] leading-6 text-white">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary-hover">
                    <Icon aria-hidden className="size-[18px]" strokeWidth={1.8} />
                  </span>
                  <span className="text-pretty">
                    {label && <strong className="font-bold">{label}: </strong>}
                    {text}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <ul
          aria-label="How your information is handled"
          className="flex flex-wrap gap-x-5 gap-y-2.5 border-t border-white/25 pt-6"
        >
          {panel.strip.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-center gap-2 text-[14px] leading-5 text-white">
              <Icon aria-hidden className="size-4 shrink-0" strokeWidth={2} />
              {text}
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
