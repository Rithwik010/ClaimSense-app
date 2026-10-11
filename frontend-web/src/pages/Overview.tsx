// Overview (an admin's home, D-AUTH-1): a placeholder until the UI pass builds it. An admin reads
// claims, the queue, audit trails, plans and metrics, and changes nothing.

import { Link } from "react-router";

import { PageTitle, Panel } from "@/components/Layout";

const LINKS = [
  { to: "/claims", label: "Claims", hint: "Every claim on file with its decision and audit trail." },
  { to: "/queue", label: "Review queue", hint: "The claims waiting for a reviewer." },
  { to: "/rule-outcomes", label: "Rule outcomes", hint: "Claims the rules decided on their own." },
  { to: "/metrics", label: "Metrics", hint: "How the model and the OCR did on the test sets." },
];

export function Overview() {
  return (
    <>
      <PageTitle
        title="Overview"
        hint="You can read everything here; reviewing and filing claims are for reviewers and providers."
      />
      <Panel>
        <ul className="divide-y divide-rules">
          {LINKS.map((link) => (
            <li key={link.to} className="px-5 py-4">
              <Link className="font-semibold text-ink underline underline-offset-4" to={link.to}>
                {link.label}
              </Link>
              <p className="text-ink-muted">{link.hint}</p>
            </li>
          ))}
        </ul>
      </Panel>
    </>
  );
}
