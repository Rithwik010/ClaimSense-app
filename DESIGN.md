# ClaimSense web app: design

The visual rules for `frontend-web/` (D-UI-1, D-UI-2, D-UI-5). The project skill
`.claude/skills/frontend-design/` gives the general approach; where they differ, this file and
`CLAUDE.md` win.

## Subject and job

A claims reviewer at a health plan checks a machine recommendation against the claim, the coverage
policy and the clinical note, then accepts it or overrides a line with a reason. The screen is a
work surface used for hours, not a landing page: legible codes, the evidence next to the decision,
nothing that competes with the claim. The memorable element is the stage strip: a band of light
that shows where a claim went in the pipeline and fills in once when a claim has just been processed.

## Theme (D-UI-5)

A deep navy canvas lit by three soft light sources (blue top left, violet top right, cyan below),
with a faint 48 px grid that fades toward the edges. Nothing in the background moves. Frosted glass
is used only for surfaces that float: the sidebar, the sticky header, a page's summary (the stage
strip, a claim's amounts, the clinical note, the login card, admin tiles), menus, dialogs, sheets,
tooltips and toasts. Lists, tables, forms and line cards sit on a quiet surface without blur, so
long text stays crisp.

## Colour

Colour still means something. Every text pair below meets WCAG AA on its surface (checked against
the navy panel colour, not just the canvas).

| Token | Value | Use | Contrast |
|---|---|---|---|
| `canvas` | `#070B18` | app background | |
| `paper` | white at 4.5% | panel fill over the canvas (`surface`) | |
| `raised` | `#0F1729` | solid fill where something must not show through (sticky table header) | |
| `ink` | `#E9EEF8` | text, headings | 14.3:1 on a panel |
| `ink-muted` | `#A9B4CA` | secondary text | 8.0:1 on a panel |
| `rules` | white at 9% | dividers and panel borders (decorative) | |
| `control` | `#63749A` | input, select and checkbox borders | 3.6:1 on a panel |
| `link` | `#9DB1FF` | links, claim IDs, the "Sense" of the wordmark | 8.1:1 |
| `glow-blue` / `glow-violet` / `glow-cyan` | `#6F8CFF` / `#A78BFA` / `#67E8F9` | light only: focus ring (cyan), stage strip, selected nav, timeline dots | |
| `highlight` | `#FFE79A` | evidence quotes, always with `on-highlight` `#1B2433` text | 12.7:1 |

Decisions are always text plus an icon on a tint, never colour alone:

| Decision | Text and icon | Tint | Icon (lucide) | Contrast |
|---|---|---|---|---|
| Approve | `#5FDCA0` | green at 14% | `CircleCheck` | 7.4:1 |
| Pend (needs information) | `#F5C26B` | amber at 14% | `CircleHelp` | 7.7:1 |
| Deny | `#FF9189` | red at 14% | `CircleX` | 6.3:1 |
| Reject | `#B7C0D0` | slate at 12% | `CircleSlash` | 6.8:1 |
| In review, awaiting review | `#9DB1FF` | blue at 10% | `Clock` | 6.6:1 |

The primary action is a blue-to-violet gradient (`#4361EE` → `#5847E0`, white text 5.0:1 or more)
with a soft blue glow. One primary button per screen; the others are outline buttons (white at 4%
fill, white at 15% border).

## Glass and depth

Utilities in `src/index.css`:

- `glass`: navy at 58% with a faint top-to-bottom white gradient, 18 px backdrop blur, a white
  10% border, a 1 px inner highlight and one soft shadow.
- `glass-strong`: navy at 90%, 24 px blur: menus, dialogs, tooltips, so what is behind them never
  competes.
- `surface`: white at 3.5% and a `rules` border, no blur: lists, tables, forms, line cards.
- `edge-light`: a hairline of blue-to-cyan light along a glass card's top edge.
- `hover-lift`: lift 1 px and brighten the border on hover, for things that open something.

Radii: controls 8 px, panels 14 px, floating layers 18 px. Shadows are soft and low (see the
`--shadow-*` tokens); no hard drop shadows.

## Type

Atkinson Hyperlegible Next (variable, bundled with `@fontsource-variable/atkinson-hyperlegible-next`)
for everything, including codes: it tells O from 0 and I from l, which matters in codes such as
O09.90 and I10. Amounts and other columns of figures use `tabular-nums`. One exception: a JSON
claim shown in the original-file sheet is pretty-printed in the system monospace font (D-UI-6).

| Role | Size / line height | Weight |
|---|---|---|
| Login headline | 40–46 / 48–54 px, light gradient text | 600 |
| Page title | 26 / 34 px (30 / 38 from 768 px), tracking −2% | 600 |
| Section title | 18 / 26 px | 600 |
| Body | 15 / 24 px | 400 |
| Strong body, line titles | 15 / 24 px | 600 |
| Small (hints, table meta) | 13 / 20 px | 400 |

Sentence case everywhere. Buttons say what happens. Prose lines stay under about 75 characters.

## Spacing and layout

- Spacing on a 4 px grid: 4, 8, 12, 16, 24, 32, 48.
- App shell: glass sidebar (collapses to icons; a sheet below 768 px) with the logo mark, the
  role's pages and a "Prototype · synthetic data only" note; a sticky glass header with the
  breadcrumb and the user menu. The page content is the `<main>` landmark (the sidebar inset).
- Not everything is a card. Lists and tables sit directly on a surface with dividers.

## Components

shadcn/ui (Radix), restyled through the theme variables: sidebar, table, badge, tabs, collapsible,
sheet, dialog, select, textarea, tooltip, sonner, skeleton, breadcrumb, chart, alert, button.
Effects in `src/components/fx.tsx`, written on Motion and Tailwind rather than installed (no new
dependencies): `BlurFade`, `Spotlight`, `NumberTicker`, `LogoMark`, `Wordmark`, `PipelineBeam`.
Their ideas come from Magic UI (Blur Fade, Magic Card, Number Ticker, Animated Beam); no code was
copied.

## Motion

Motion (`motion/react`) and CSS transitions, restrained:

1. Page change: fade and a 4 px rise, 180 ms.
2. Hover: 120–160 ms colour and border changes; cards that open something lift 1 px; buttons
   press to 98%.
3. Expanding and collapsing a service line.
4. The evidence pulse: the highlight behind a quote pulses once when its criterion is clicked
   (the right column switches to its Clinical note tab first).
5. After "Process claim", the stage strip fills in step by step (one stagger, about 1 s); the
   step waiting for a reviewer glows softly.
6. Entrances: login content and admin tiles blur-fade in once (400 ms, small stagger).
7. Admin counts count up once (`NumberTicker`); outcome bars grow in once. Counts only: money and
   decisions never animate.
8. Login: one band of light travels slowly along the pipeline (7 s, then a pause).
9. Spotlight: admin tiles catch a soft light under the pointer.

With `prefers-reduced-motion: reduce` every moment is instant (`MotionConfig reducedMotion="user"`
plus the CSS media query): no beam, counts show their final value, the pulse is a static
highlight.

## Breakpoints

Checked at 390, 768 and 1440 px; no horizontal page scroll at any of them.

| Width | Shell | Review claim and claim detail | Tables |
|---|---|---|---|
| 390 px | sidebar becomes a sheet behind a menu button; login shows the card only | one column: strip (scrolls sideways inside itself), lines, then the Summary, Clinical note and Audit trail tabs | scroll sideways inside their panel |
| 768 px | sidebar collapsed to icons | one column; the tabs follow the lines | as at 390 px where needed |
| 1440 px | sidebar open; login splits into story and card | two columns: lines left (about 60%), the Summary, Clinical note and Audit trail tabs right, sticky (Summary first) | full width |

## Print

The patient EOB (D-EOB-1) is meant to be printed: in print the sidebar, header, toasts and buttons
are hidden, and the page is black text on white with grey rules, no glass, light or shadow
(`@media print` in `src/index.css`, the `print:` variants). The services table replaces the phone
cards. Decisions keep their text and icon, so nothing relies on colour on paper either.

## Accessibility

Visible focus on every interactive element: a 2 px cyan outline with a 2 px offset (buttons add a
soft cyan ring); every input labelled; keyboard-reachable sidebar, tabs, sheet and dialog (Radix);
AA contrast for all text (table above); decisions never shown by colour alone; text never sits on
blur without a solid enough backing (glass is at least 58% navy, 90% for overlays); one `<main>`
landmark per page; motion respects the user's setting.
