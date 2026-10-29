# Design direction: a light theme in the spirit of the Cigna Group's sites

A proposal for the team (branch `p9.5-light-theme`). Main's dark glass theme (D-UI-5) is not changed
by it; if the team approves, it becomes decision D-UI-7 and the work below is done on this branch.

## Summary

1. Cigna Healthcare and Evernorth run on one shared design system ("Leaf", `--leaf-*` tokens): white
   surfaces, one strong brand colour for actions and links, a darker shade for headings, soft grey
   rules, pill or 8 px controls, small soft shadows, and status colours as a tint plus a strong colour.
2. Their intent is reassurance and plain words: big welcoming headings, one clear action per block,
   notices in a tinted strip with an icon, and dense resources in tidy lists and accordions.
3. For ClaimSense: a light theme on a cool grey canvas, white cards, deep indigo headings and one blue
   for actions and links. It is an original palette in that family, not the brands' own values.
4. The decision colours keep our rule (text + icon on a tint) and every pair passes WCAG AA
   (`scripts/verify/contrast_check.py`: 20 of 20).
5. The work is mostly token values plus about 60 hard-coded dark utilities in 25 files; no new
   dependency (Atkinson Hyperlegible Next stays the font).

## How this was gathered

On 29 Oct 2026, a headless Chrome (Playwright, already used for our tests) opened public pages only,
logged out, at 1440, 768 and 390 px with device pixel ratio 1: cigna.com home, the "how to buy
health insurance" explainer, the health care providers page, contact us, the provider directory's
landing page, and evernorth.com's home and EviCore solutions page. On the Cigna home, the providers
page and the Evernorth home it read the computed styles, the CSS custom properties (893 on Cigna,
1,139 on Evernorth), the loaded fonts, the media queries and the focus and hover rules. The
screenshots and style dumps are in `data/generated/design-research/cigna-2026-10-29/` (not
committed). Nothing behind a login was opened; no form was submitted.

Confidence: **Verified** = read from the site's CSS; **Observed** = seen in the screenshots;
**Inferred** = our reading of intent.

## A. Intent and tone (Observed, Inferred)

| Item | Finding |
|---|---|
| Audience | Members and shoppers first; providers, brokers and employers through a utility bar ("For Providers", "For Brokers", "For Employers"). |
| Tone | Warm and reassuring: "Good afternoon" greeting, people photography, "We know your time is valuable". |
| Headlines | Title case, short, benefit-led ("Your plan, on demand", "Support for Health Care Professionals"). |
| Actions | One primary action per block, a verb first ("Explore plans", "Get credentialed", "Get care"). |
| Notices | A full-width tinted strip with an icon and a link, under the navigation. |
| Money and coverage | Explained on their own pages in plain sentences; claims and EOBs sit behind the member login. |

## B. Colour (Verified)

| Role | Cigna | Evernorth |
|---|---|---|
| Action and link | #0033FF, hover #001F99, pressed #001466 | #035C67, hover #00363D |
| Strong brand (headings, info) | #110081 | #035C67 |
| Body text / subtle / disabled | #333333 / #5C5C5C / #858585 | #2D2D2D / #6C6C6C / #949494 |
| Page / subtle surface | #FFFFFF / #F4F4F4 | #FFFFFF / #F6F5F3 |
| Brand tint (hover, selected) | #E6EBFF, #CCD6FF | #EAF4F6, #CCE7EA |
| Borders default / strong | #D6D6D6 / #707070 | #D5D5D5 / #6C6C6C |
| Success tint / strong / text | #DAE6D1 / #488319 / #3A6914 | #D6FFF2 / #006041 / #0E7C5A |
| Error tint / strong / text | #F1CCCC / #BA0000 / #BA0000 | #FFEBEB / #AA1313 / #D02525 |
| Warning tint / strong | #FFF5D6 / #FFCD34 (icon #333) | #FCF5E5 / #F4C465 |
| Info tint / strong | #CCD6FF / #110081 | #EBF2FF / #0048C2 |

## C. Typography (Verified)

| Item | Cigna | Evernorth |
|---|---|---|
| Families | "Value Serif Pro" for display headings, "Value Sans Pro" for everything else (both proprietary) | Inter |
| Body | 16/24 px, 400; 18/27 px on content pages | 16/24 px, 400 |
| Headings (1440 px) | h1 64/80 serif 700; h2 28/36.4 sans 700; h3 32/38.4 serif 700; all #110081 | h1 40/56, h2 32/40, h3 24/32, 600 |
| Headings (390 px) | h1 28/36.4; h2 24/26.9 | — |
| Links and buttons | 16 px 500; buttons 14 px 500 | buttons 16 px 500 |
| Scale | 12, 14, 16, 18, 20, 24, 28, 32, 40, 48, 56, 64, 72, 80 px | same scale |

## D. Layout and spacing (Verified, Observed)

Content max width about 1200–1280 px; generous section rhythm (64–96 px between sections at 1440).
Breakpoints at 375, 560, 768, 960 and 1200 px (Cigna in rem: 23.44, 35, 48, 60, 75). Cards overlap
the hero edge; resource lists use two or three columns that stack on phones.

## E. Components (Verified, Observed)

| Component | Finding |
|---|---|
| Header | Two tiers: a white bar (logo left, utility links and search right) over a brand-colour band with the section navigation and a pill "Log in" button (Cigna); one dark teal bar (Evernorth). |
| Buttons | Cigna: pill (radius 900 px), 14 px 500, white on #0033FF. Evernorth: 8 px radius, 12×24 px padding. Secondary buttons are outlined. |
| Fields | Radius 8 px (pill for brand search); 16×24 px padding; label above. |
| Cards | White, radius 30 px (Cigna) or 16 px (Evernorth); a soft shadow `0 8px 6px 0 rgb(0 0 0 / 10%)`. |
| Badges, tabs | Radius 4 px. |
| Notices | Tint background, icon left, link inline (info: #E6EBFF and #110081). |
| Footer | Light, link columns, legal row. |
| Elevation | Three shadows: small `0 1px 2px 1px rgb(0 0 0 / 20%)`, default, large `0 10px 12px 0 rgb(0 0 0 / 20%)`. |

## F–H. Interaction, accessibility, responsive (Verified, Observed)

- Focus: a 2 px (0.125 rem) outline with an offset, knockout white on brand surfaces.
- Hover: links darken to the strong brand; menu items take the brand tint.
- Skip links to navigation, content and footer on both sites.
- Phones: the navigation collapses to "Menu" with a hamburger; the login stays a visible pill;
  cards stack full width; headings drop to 28 px.
- The provider directory runs an older, separate design (square buttons): an outlier.

## ClaimSense translation

### 1. What fits a claims tool

Fits: the two-tier sense of place (white bar, brand accent), white cards on a light canvas, one blue
for actions, indigo headings, tinted notice strips, pill primary buttons, 8 px fields, 4 px badges,
small soft shadows, plain-words microcopy. Does not fit: full-bleed hero photos, 64 px serif
headlines, lifestyle imagery and marketing greetings. A reviewer's screen stays dense and calm.

### 2. Proposed tokens (original values in the same family)

```css
@theme {
  --color-canvas: #f5f6f8;        /* page */
  --color-paper: #ffffff;         /* cards, tables */
  --color-raised: #ffffff;        /* sheets, dialogs, menus (with shadow-lg) */
  --color-ink: #2b2f38;           /* body text */
  --color-ink-muted: #5b6170;     /* secondary text */
  --color-ink-strong: #1b1464;    /* headings, focus ring, info */
  --color-rules: #d9dce3;         /* dividers, card borders */
  --color-control: #7a8091;       /* field and control borders */
  --color-primary: #2442d6;       /* actions and links */
  --color-primary-hover: #1a2fa3;
  --color-primary-pressed: #13237a;
  --color-brand-tint: #e8ecff;    /* hover, selected, info notice */
  --color-highlight: #fff2cc;     /* the quoted evidence in a note */

  --color-approve: #2e6b1f;  --color-approve-icon: #3f8a2a;  --color-approve-tint: #e3f0da;
  --color-pend: #7a5300;     --color-pend-icon: #9a6a00;     --color-pend-tint: #fff2cc;
  --color-deny: #a1121b;     --color-deny-icon: #b3141f;     --color-deny-tint: #fce4e4;
  --color-reject: #474d5b;   --color-reject-tint: #eceef2;

  --radius-sm: 4px;   /* badges, tabs */
  --radius-md: 8px;   /* fields, small cards */
  --radius-lg: 12px;  /* cards */
  --radius-xl: 16px;  /* sheets, dialogs */
  --radius-pill: 999px; /* buttons */

  --shadow-sm: 0 1px 2px rgb(16 24 40 / 0.12);
  --shadow: 0 6px 12px -4px rgb(16 24 40 / 0.14);
  --shadow-lg: 0 12px 24px -8px rgb(16 24 40 / 0.18);

  --font-sans: "Atkinson Hyperlegible Next Variable", system-ui, sans-serif; /* kept */
}
```

Type scale (from the same family): 12, 14, 16 (body), 18 (member pages' body), 20, 24, 28, 32 px;
headings 700 in `ink-strong`; no serif (theirs is proprietary; a free serif would be a new package).

### 3. Decision colours (text + icon on a tint; never colour alone)

| Decision | Text | Icon | Tint | Text contrast | Icon contrast |
|---|---|---|---|---|---|
| Approved | #2E6B1F | #3F8A2A | #E3F0DA | 5.48:1 | 3.64:1 |
| Pended | #7A5300 | #9A6A00 | #FFF2CC | 6.14:1 | 4.24:1 |
| Denied | #A1121B | #B3141F | #FCE4E4 | 6.63:1 | 5.72:1 |
| Rejected | #474D5B | — | #ECEEF2 | 7.29:1 | — |
| In review | #1B1464 | — | #E8ECFF | 13.43:1 | — |

Also: body text 12.40:1 on the canvas, muted text 5.73:1, links 7.43:1 on white, white on the
primary 7.43:1, control borders 3.94:1. All from `scripts/verify/contrast_check.py`.

### 4. Page by page (highest impact first)

- **App shell.** White top bar with "ClaimSense" in indigo and the user menu; a 4 px primary band
  under it as the brand accent; a white sidebar whose active item is indigo on the brand tint with a
  left bar. System notices (model or retrieval down) as a tinted strip with an icon, like Cigna's.
- **Review claim.** White line cards with the decision chip at the top right; the override sheet
  solid white with `shadow-lg` over a 40% indigo scrim; "Finalize claim" a primary pill.
- **Claims lists (My claims, Review queue, Claims, Returned and auto-denied).** White table cards,
  a canvas-grey header row, row hover in the brand tint, tabs with count badges (4 px), filters as
  pill segmented controls.
- **Claim page.** The summary card first; tabs with an indigo underline; the note's evidence in the
  pale yellow highlight with an underline, so it is not colour alone.
- **Submit claim.** The drop zone white with a dashed control-grey border, brand tint on drag-over;
  "Read claim" a primary pill; low-confidence fields marked with the pend chip.
- **Admin (Overview, Model metrics, Audit lookup, System status).** White stat cards with indigo
  numbers; tables as above; status rows as notice strips (success, warning, error).
- **Member pages and the EOB.** The friendliest pages: 18 px body text, plain headings, amounts in a
  clear table; the print styles stay as they are.
- **Login.** A white card on the canvas, indigo heading, pill "Log in".

### 5. Components (shadcn/ui)

Restyle through tokens only: Button (default = primary pill; outline = white pill with a primary
border and text; ghost = text action), Badge (decision chips), Card, Table, Tabs, Sheet, Dialog,
Select, Input, Sidebar, Breadcrumb. One addition: shadcn's Alert for the notice strips
(`npx shadcn@latest add alert`, which copies a component and adds no npm package). No new dependency.

### 6. DESIGN.md amendment (draft for D-UI-7)

> **Theme (D-UI-7, amends D-UI-5).** Light: white cards on a cool grey canvas (#F5F6F8), deep
> indigo headings (#1B1464), one blue for actions and links (#2442D6), soft grey rules. Inspired by
> the Cigna Group's sites, with our own values; no Cigna or Evernorth logos, names, fonts, images or
> copy. **Glass:** none; sheets, dialogs and menus are solid white with `shadow-lg`, over a 40%
> indigo scrim. **Colour** still marks decisions only, as text + icon on a tint (table in §3).
> Buttons are pills; fields 8 px; badges and tabs 4 px; cards 12 px. Shadows are small and soft.
> Type, spacing, motion, breakpoints, print and accessibility rules are unchanged.

### 7. Implementation plan (on `p9.5-light-theme`)

1. `src/index.css`: the tokens above in `@theme`, shadcn's variables (`--background`, `--card`,
   `--primary`, `--ring` and the rest) mapped onto them; the glass utilities become solid surfaces.
2. Replace the ~60 hard-coded dark utilities (`text-white`, `bg-white/[0.04]`, `border-white/15`,
   `#111a30` and so on) in 25 files with the tokens.
3. Component variants: Button (pill), Badge (decision chips with an icon), Tabs, Table, Sheet scrim,
   Sidebar active state, the app bar and its accent band; shadcn Alert for notices.
4. `DESIGN.md` as in §6; decision D-UI-7 in `DECISIONS.md`.
5. Verify: `npm run lint`, `typecheck`, `test`, `build`; Playwright with axe (contrast is checked
   there); every page looked at at 390, 768 and 1440 px; `make offline-check` (no font or asset
   from outside the laptop).
6. Risks: tests that assert class names; charts on Model metrics that use the old glow colours;
   print styles; the evidence highlight's contrast. About 2–3 hours of work and checks.

## Guardrails kept

Inspiration, not imitation: no Cigna or Evernorth logos, wordmarks, fonts, icons, photos or copy;
the product stays "ClaimSense" with its own values; nothing from behind a login was used.

## Open questions

1. Accent: Cigna's blue family (this proposal) or Evernorth's teal family (the team is Evernorth's)?
   A teal variant is a token swap.
2. Keep the dark theme as a switch (both themes), or replace it on this branch?
3. A free serif for page titles, echoing Cigna's headings, would need a font package (approval).
