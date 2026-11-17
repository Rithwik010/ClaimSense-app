# ClaimSense web app: design

The visual rules for `frontend-web/` (D-UI-1, D-UI-2, D-UI-5, D-UI-7). The project skill
`.claude/skills/frontend-design/` gives the general approach; where they differ, this file and
`CLAUDE.md` win.

## Subject and job

A claims reviewer at a health plan checks a machine recommendation against the claim, the coverage
policy and the clinical note, then accepts it or overrides a line with a reason. The screen is a
work surface used for hours, not a landing page: legible codes, the evidence next to the decision,
nothing that competes with the claim. The memorable element is the stage strip: a band that shows
where a claim went in the pipeline and fills in once when a claim has just been processed.

## Theme (D-UI-7, amends D-UI-5; D-UI-8)

White pages, a large blue sidebar, indigo serif headings and one blue for actions and links. The
blue family is the Cigna Group's public palette, at the team's request (D-UI-8): brand blue
`#0033FF`, hover `#001F99`, indigo `#110081`, tints `#E6EBFF` and `#CCD6FF`, text `#333333`. No
Cigna or Evernorth logo, name, font, image, leaf pattern or copy.
Cards and tables are white with a soft grey rule; menus, dialogs, sheets, tooltips and toasts are
solid white with a soft shadow, over a 40% indigo scrim for dialogs and sheets. No glass, no glow
and nothing in the background. Every pair below is checked by `scripts/verify/contrast_check.py`.

## Colour

Colour still means something. Every text pair meets WCAG AA on its surface.

| Token | Value | Use | Contrast |
|---|---|---|---|
| `canvas`, `paper`, `raised` | `#FFFFFF` | pages, cards, floating layers | |
| `subtle` | `#F4F4F4` | table headers, quiet panels, empty states | |
| `ink` | `#333333` | body text | 12.6:1 on white |
| `ink-muted` | `#5A5A5A` | secondary text | 6.9:1 on white, 6.3:1 on `subtle` |
| `ink-strong` | `#110081` | headings (serif), numbers that matter, the tab underline | 15.7:1 on white |
| `rules` | `#D9DCE3` | dividers and card borders (decorative) | |
| `control` | `#7A8091` | input, select and checkbox borders | 3.9:1 on white |
| `primary`, `link` | `#0033FF` | buttons, links, claim IDs, focus outline | 7.2:1 on white |
| `primary-hover` | `#001F99` | hovered buttons and links | |
| `brand-tint` | `#E6EBFF` | hover, selected, in-review chips | |
| `highlight` | `#FFF2CC` | evidence quotes, with `ink` text and an amber underline | 11.3:1 |
| sidebar | `#0033FF` | the sidebar (19 rem wide, 4 rem as icons; 17 px links on 48 px rows, 22 px icons, a 28 px wordmark) and the login page's panel; links white (7.2:1), the role label `#CCD6FF` (5.0:1), the page you are on white on `#001F99` (12.7:1) with a 4 px white bar on its left | |

Decisions are always text plus an icon on a tint, as a pill, never colour alone:

| Decision | Text | Icon | Tint | Icon (lucide) | Contrast (text / icon) |
|---|---|---|---|---|---|
| Approve | `#2E6B1F` | `#3F8A2A` | `#E3F0DA` | `CircleCheck` | 5.5:1 / 3.6:1 |
| Pend (needs information) | `#7A5300` | `#9A6A00` | `#FFF2CC` | `CircleHelp` | 6.1:1 / 4.2:1 |
| Deny | `#A1121B` | `#B3141F` | `#FCE4E4` | `CircleX` | 6.6:1 / 5.7:1 |
| Reject | `#474D5B` | `#474D5B` | `#ECEEF2` | `CircleSlash` | 7.3:1 |
| In review, awaiting review | `#110081` | `#110081` | `#E6EBFF` | `Clock` | 13.2:1 |

The primary action is a solid blue button (`#0033FF`, white text 7.2:1; `#001F99` on hover). One
primary button per screen; the others are outline buttons (white, a `control` border, blue text).

## Surfaces and depth

Utilities in `src/index.css` (the names are kept from D-UI-5 so every page restyles from there):

- `surface` and `glass`: white with a `rules` border: lists, tables, forms, line cards, a page's
  summary.
- `glass-strong`: white with a `rules` border and `shadow-lg`: menus, dialogs, tooltips.
- `hover-lift`: the border darkens to `control` on hover, for things that open something.
- `edge-light` and `text-glow` are kept as names only (no light; `text-glow` is the heading indigo).

Radii: badges and tabs 4 px, buttons and fields 8 px, cards 12 px, floating layers 16 px; chips are
pills. Shadows are small and soft, only on what floats.

## Type

Headings (`h1` to `h3`, the wordmark) are Source Serif 4 (variable, bundled with
`@fontsource-variable/source-serif-4` 5.3.0, OFL-1.1, D-UI-7) in `ink-strong`. Atkinson Hyperlegible
Next (variable, bundled with `@fontsource-variable/atkinson-hyperlegible-next`) is everything else,
including codes: it tells O from 0 and I from l, which matters in codes such as
O09.90 and I10. Amounts and other columns of figures use `tabular-nums`. One exception: a JSON
claim shown in the original-file sheet is pretty-printed in the system monospace font (D-UI-6).

| Role | Size / line height | Weight |
|---|---|---|
| Login panel headline (serif, white on the blue panel) | 34 / 40 px (52 / 56 from 768 px) | 700 |
| Page title (serif) | 28 / 36 px (34 / 42 from 768 px) | 700 |
| Section title (serif) | 21 / 28 px | 700 |
| Body | 15 / 24 px | 400 |
| Strong body, line titles | 15 / 24 px | 600 |
| Small (hints, table meta) | 13 / 20 px | 400 |

Sentence case everywhere. Buttons say what happens. Prose lines stay under about 75 characters.

## Spacing and layout

- Spacing on a 4 px grid: 4, 8, 12, 16, 24, 32, 48.
- App shell: the blue sidebar (collapses to icons; a sheet below 768 px) with the logo mark, the
  serif wordmark and the role's pages; a sticky white header with a soft rule, the breadcrumb and
  the user menu. The page content is the `<main>` landmark (the sidebar inset).
- Not everything is a card. Lists and tables sit directly on a surface with dividers.

## Components

shadcn/ui (Radix), restyled through the theme variables: sidebar, table, badge, tabs, collapsible,
sheet, dialog, select, textarea, tooltip, sonner, skeleton, breadcrumb, chart, alert, button.
Effects in `src/components/fx.tsx`, written on Motion and Tailwind rather than installed (no new
dependencies): `BlurFade`, `Spotlight`, `NumberTicker`, `LogoMark`, `Wordmark`, `PipelineBeam`.
Their ideas come from Magic UI (Blur Fade, Magic Card, Number Ticker, Animated Beam); no code was
copied.

Shared pieces added for the dashboard improvements (D-UI-12, no new dependencies):
`ListTools` (a sortable column header kept in the URL, and a CSV download of the rows shown),
`HeaderTools` (go to a claim by its ID; the notifications bell), `ClaimHeader` (the claim at a
glance for staff), `FollowUps` (the provider's follow-up buttons, the appeal history and a text
dialog with its length rules), `Feedback` (the reviewer's criterion corrections). Charts follow the
one-colour rule: a single series in `primary` (#0033FF, checked on white for lightness, chroma and
3:1 contrast), two measures as small multiples on one scale rather than two hues, always with a
table view. A limit's progress is a thin `ink-strong` bar on `subtle`, `role="meter"`, its length
the API's basis points.

## Motion

Motion (`motion/react`) and CSS transitions, restrained:

1. Page change: fade and a 4 px rise, 180 ms.
2. Hover: 120–160 ms colour and border changes; buttons press to 98%.
3. Expanding and collapsing a service line.
4. The evidence pulse: the highlight behind a quote pulses once when its criterion is clicked
   (the right column switches to its Clinical note tab first).
5. After "Process claim", the stage strip fills in step by step (one stagger, about 1 s); the
   step waiting for a reviewer pulses softly.
6. Entrances: the admin tiles blur-fade in once (400 ms, small stagger).
7. Admin counts count up once (`NumberTicker`); outcome bars grow in once. Counts only: money and
   decisions never animate.
8. Spotlight: admin tiles catch a faint blue tint under the pointer.

With `prefers-reduced-motion: reduce` every moment is instant (`MotionConfig reducedMotion="user"`
plus the CSS media query): counts show their final value, the pulse is a static
highlight.

## Breakpoints

Checked at 390, 768 and 1440 px; no horizontal page scroll at any of them.

| Width | Shell | Review claim and claim detail | Tables |
|---|---|---|---|
| 390 px | sidebar becomes a sheet behind a menu button; login shows the form first, then the blue panel; the claim search moves out of the header (the bell and user menu stay) | one column: strip (scrolls sideways inside itself), lines, then the Summary, Clinical note and Audit trail tabs | the claim lists and the review queue are cards (D-UI-12); other tables scroll sideways inside their panel |
| 768 px | sidebar collapsed to icons; login as at 390 px | one column; the tabs follow the lines | as at 390 px where needed |
| 1440 px | sidebar open; login shows the blue panel on the left (46%: headline, what you can do, trust strip) beside the form (D-UI-11) | two columns: lines left (about 60%), the Summary, Clinical note and Audit trail tabs right, sticky (Summary first) | full width |

## Print

The patient EOB (D-EOB-1) is meant to be printed: in print the sidebar, header, toasts and buttons
are hidden, and the page is black text on white with grey rules and no shadow
(`@media print` in `src/index.css`, the `print:` variants). The services table replaces the phone
cards. Decisions keep their text and icon, so nothing relies on colour on paper either.

## Accessibility

Visible focus on every interactive element: a 2 px blue outline with a 2 px offset (white in the
blue sidebar; buttons add a soft ring); every input labelled; keyboard-reachable sidebar, tabs, sheet and dialog (Radix);
AA contrast for all text (table above; `scripts/verify/contrast_check.py`); decisions never shown
by colour alone; no text on blur or transparency; one `<main>`
landmark per page; motion respects the user's setting.
