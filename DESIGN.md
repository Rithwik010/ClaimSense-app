# ClaimSense web app: design

The visual rules for `frontend-web/` (D-UI-1, D-UI-2). The project skill
`.claude/skills/frontend-design/` gives the general approach; where they differ, this file and
`CLAUDE.md` win.

## Subject and job

A claims reviewer at a health plan checks a machine recommendation against the claim, the coverage
policy and the clinical note, then accepts it or overrides a line with a reason. The screen is a
work surface used for hours, not a landing page: legible codes, the evidence next to the decision,
nothing that competes with the claim. The one memorable element is the stage strip, which shows
where a claim went in the pipeline and fills in once when a claim has just been processed.

## Colour

Colour only where it means something. The chrome is ink on paper.

| Token | Hex | Use |
|---|---|---|
| `paper` | `#FFFFFF` | panels, tables, inputs |
| `canvas` | `#F4F5F7` | app background behind panels |
| `ink` | `#1B2433` | text, primary buttons (white text), focus ring, icons |
| `ink-muted` | `#525C6C` | secondary text (6.8:1 on paper, 6.2:1 on canvas) |
| `rules` | `#DADDE3` | dividers and panel borders (decorative) |
| `control` | `#858E9E` | input, select and checkbox borders (3.3:1 on paper) |
| `highlight` | `#FFE79A` | evidence quotes in the clinical note (ink on it: 12.7:1) |

Decisions are always text plus an icon on a light tint, never colour alone:

| Decision | Text and icon | Tint | Icon (lucide) |
|---|---|---|---|
| Approve | `#1E7A4C` | `#E7F2EC` | `CircleCheck` |
| Pend (needs information) | `#9A5B00` | `#FBF0DF` | `CircleHelp` |
| Deny | `#B3261E` | `#FBE9E7` | `CircleX` |
| Reject | `#5B6472` | `#EEF0F3` | `CircleSlash` |

Every pair passes WCAG AA for normal text (4.6:1 or more). There is no accent colour, no gradient
and no dark theme.

## Type

Atkinson Hyperlegible Next (variable, bundled with `@fontsource-variable/atkinson-hyperlegible-next`)
for everything. It tells O from 0 and I from l, which matters in codes such as O09.90 and I10. No
monospace face, not even for codes. Amounts and other columns of figures use `tabular-nums`.

| Role | Size / line height | Weight |
|---|---|---|
| Page title | 24 / 32 px | 600 |
| Section title | 18 / 26 px | 600 |
| Body | 15 / 24 px | 400 |
| Strong body, line titles | 15 / 24 px | 600 |
| Small (hints, table meta) | 13 / 20 px | 400 |

Sentence case everywhere. No all-caps labels, no letter-spaced eyebrows, no "A · B · C" meta
strings, no "→" in buttons or links. Prose lines stay under about 75 characters.

## Spacing, shape and elevation

- Spacing on a 4 px grid: 4, 8, 12, 16, 24, 32, 48.
- Borders, not shadows: 1 px `rules` around panels; overlays (dialog, sheet) get a border and a
  dimmed backdrop, no drop shadow.
- Radii differ by role: controls (buttons, inputs, badges) 6 px; panels 10 px; the stage strip's
  steps are square-ended segments of one bar.
- Not everything is a card. Lists and tables sit directly on a panel with dividers; only distinct
  objects (a service line, the clinical note) get their own bordered panel.

## Components

shadcn/ui (Radix), added with `npx shadcn@latest add <name>` and restyled through the theme
variables: sidebar (app shell from the `sidebar-07` block), table, badge, tabs, collapsible, sheet,
dialog, select, textarea, tooltip, sonner (toasts), skeleton, breadcrumb, chart, alert, button.

- Buttons say what happens: "Read claim", "Process claim", "Accept recommendation", "Override
  line", "Finalize claim". A toast repeats the verb: "Claim finalized", "Line overridden".
- One primary (ink) button per screen; the others are bordered secondary buttons.
- Empty states say what to do next; errors say what happened and how to fix it, without apology.
- Status and decision badges use the decision table above; tiers are plain bordered badges.

## Screens

- **App shell:** sidebar with the logged-in role's pages only (D-AUTH-1); breadcrumb and the user
  menu (name, role, Log out) in the header. The login page is the only page without the shell.
- **Review claim** (the demo's main screen): the stage strip across the top (Intake, Rules, Policy,
  Model, Amounts, Explanation, Review), each step with its result, steps a claim never reached shown
  as "Not reached". Left: the service lines, each expanding to its criteria (Met / Not met / Not
  documented / Does not apply) with the quote. Right: the clinical note, sticky, every evidence
  quote highlighted. Clicking a criterion scrolls the note to its quote and pulses the highlight
  once. "Override line" opens a side sheet with the new decision, a required reason and, only when
  needed, the benefit category.
- **Claim detail:** the same layout, read-only, with tabs for the explanation and the audit trail
  (a simple timeline).
- **Review queue:** a table sorted by tier (full, standard, quick) then age; a tier filter;
  decision badges.
- **Submit claim, Rule outcomes, Metrics:** tables on panels; Metrics adds one grouped bar chart
  (v1 and v2) and the "Where v2 goes wrong" table.

## Motion

Motion (`motion/react`) for exactly four moments, nothing else:

1. A 150-200 ms fade between pages.
2. Expanding and collapsing a service line.
3. The evidence pulse: the highlight behind a quote pulses once when its criterion is clicked.
4. After "Process claim", the stage strip fills in step by step as the claim moved through the
   pipeline, read from the audit events the API already returns (one stagger, about 1 s in all).

No entrance animations on sections, no hover lifts, no count-ups, no looping animation. With
`prefers-reduced-motion: reduce` every moment becomes an instant change (`MotionConfig
reducedMotion="user"` plus the CSS media query); the pulse becomes a static highlight.

## Breakpoints

Checked in the browser at 390, 768 and 1440 px wide; no horizontal page scroll at any of them.

| Width | Shell | Review claim and claim detail | Tables |
|---|---|---|---|
| 390 px | sidebar becomes a sheet behind a menu button | one column: strip (scrolls sideways inside itself), lines, then the note | scroll sideways inside their panel |
| 768 px | sidebar collapsed to icons | one column; the note follows the lines | as at 390 px where needed |
| 1440 px | sidebar open | two columns: lines left (about 60%), note right, sticky | full width |

## Accessibility

Visible focus ring (2 px ink, 2 px offset) on every interactive element; every input labelled;
keyboard reachable sidebar, tabs, sheet and dialog (Radix); AA contrast for all text; decisions
never shown by colour alone; motion respects the user's setting.
