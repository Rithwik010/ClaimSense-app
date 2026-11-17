// The wordings for the login page's blue panel, for choosing one (D-UI-11): each is shown on the
// real login page at /design/login-panel?v=1 to 7. Dev server only: App.tsx adds the route under
// import.meta.env.DEV, so the production build has neither the route nor this code. Every line is
// true for ClaimSense and says nothing about how claims are processed inside. Removed once one is
// chosen.

import {
  Calculator,
  CircleQuestionMark,
  ClipboardCheck,
  KeyRound,
  ListChecks,
  Lock,
  MessageSquareText,
  ReceiptText,
  Search,
  ShieldCheck,
  ShieldPlus,
  Stethoscope,
  User,
  UserCheck,
  Wallet,
} from "lucide-react";
import { Link, useSearchParams } from "react-router";

import { Login, type PanelContent, type PanelPoint } from "@/pages/Login";

const PRIVATE: PanelPoint = { icon: Lock, text: "Your information stays private" };
const SECURE: PanelPoint = { icon: ShieldCheck, text: "Secure sign-in" };
const PERSON: PanelPoint = { icon: UserCheck, text: "A person reviews every recommendation" };
const NBSP = " "; // keeps a phrase of a headline on one line

/** `intro` replaces the form's "Welcome back." where the panel already says it. */
export const PANELS: { name: string; panel: PanelContent; intro?: string }[] = [
  {
    name: "Status first",
    panel: {
      headline: "Know where your claim stands.",
      line: "Check its status, read the outcome, and see what you owe.",
      points: [
        { icon: ListChecks, text: "Track every claim sent to your plan" },
        { icon: MessageSquareText, text: "Read each decision in plain words" },
        { icon: ReceiptText, text: "View your statement (EOB) once a claim is final" },
      ],
      strip: [PRIVATE, SECURE],
    },
  },
  {
    name: "Questions people ask",
    panel: {
      headline: `Questions about a${NBSP}claim? Start here.`,
      points: [
        { icon: Search, text: "Where is my claim?" },
        { icon: CircleQuestionMark, text: "Why was it decided this way?" },
        { icon: Wallet, text: "What do I owe?" },
      ],
      strip: [{ icon: MessageSquareText, text: "Answers in plain words" }, PERSON],
    },
  },
  {
    name: "One place for everyone",
    panel: {
      headline: "One place for every claim.",
      line: "Your account opens the pages you need.",
      points: [
        { icon: User, label: "Members", text: "claims, benefits and statements" },
        { icon: Stethoscope, label: "Providers", text: "send claims and follow each outcome" },
        { icon: ClipboardCheck, label: "Reviewers", text: "work through claims waiting for a decision" },
      ],
      strip: [SECURE, { icon: KeyRound, text: "You see only what your account allows" }],
    },
  },
  {
    name: "Calm and reassuring",
    panel: {
      headline: "Clear answers, no jargon.",
      line: "Every decision comes with a reason you can read.",
      points: [
        PERSON,
        { icon: MessageSquareText, text: "Each outcome explains why" },
        { icon: Lock, text: "Members see only their own claims" },
      ],
      strip: [SECURE],
    },
  },
  {
    name: "Your plan, explained",
    panel: {
      headline: "Your health plan, made clearer.",
      line: "Claims, benefits and costs together, explained simply.",
      points: [
        { icon: ShieldPlus, text: "See what your plan covers" },
        { icon: ListChecks, text: "Follow your claims as they're decided" },
        { icon: Wallet, text: "See what you owe on each claim" },
      ],
      strip: [PRIVATE, SECURE],
    },
  },
  {
    name: "From visit to decision",
    panel: {
      headline: `From visit to${NBSP}decision, in${NBSP}plain${NBSP}words.`,
      line: "See each claim's status, outcome and costs as soon as it's decided.",
      points: [
        { icon: ListChecks, text: "A status for every claim" },
        { icon: MessageSquareText, text: "The reason for each outcome" },
        { icon: Calculator, text: "Costs and benefits, worked out to the cent" },
      ],
      strip: [SECURE, PERSON],
    },
  },
  {
    name: "Minimal",
    intro: "",
    panel: {
      headline: "Welcome back.",
      line: "Log in to see your claims and what happens next.",
      points: [],
      strip: [PRIVATE, SECURE],
    },
  },
];

export default function LoginPanels() {
  const [params] = useSearchParams();
  const option = PANELS[Number(params.get("v")) - 1];

  if (option) return <Login key={option.name} panel={option.panel} intro={option.intro} />;
  return (
    <main className="mx-auto max-w-[720px] px-4 py-10">
      <h1 className="font-heading text-[30px] leading-9 font-bold">Login panel wordings</h1>
      <p className="mt-2 text-ink-muted">Development preview. Each is the real login page with another wording.</p>
      <ol className="mt-6 flex flex-col gap-3">
        {PANELS.map((o, i) => (
          <li key={o.name}>
            <Link to={`?v=${i + 1}`} className="font-semibold text-link">
              {i + 1}. {o.name}
            </Link>
            <span className="text-ink-muted">: {o.panel.headline}</span>
          </li>
        ))}
      </ol>
    </main>
  );
}
