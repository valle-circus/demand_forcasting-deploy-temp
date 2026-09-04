---
name: circus-ui
description: Design and build internal web apps and interfaces for Circus SE colleagues — React + Tailwind, clean and modern, low text density, subtle motion. Use whenever building or reviewing a UI, screen, form, dashboard, table, tool or internal app for non-technical users, or when asked to "make this look better", restyle an interface, or choose a component library. Not for marketing pages or external-facing sites.
---

# Circus internal-app UI

> **Source of truth.** This file is version-controlled here. The account-level
> `circus-ui` skill on claude.ai is a copy — it lives in an app-managed cache
> that a sync can overwrite. Edit this file, then re-package and re-upload:
> `python -m scripts.package_skill .claude/skills/circus-ui <out-dir>`

Internal tools at Circus are used by people who did not choose to use them, are
mid-task, and often on a shared or shop-floor screen. The measure of a good
interface here is **how fast someone who has never seen it can finish their job**
— not how much it can display.

Two rules override everything else in this document:

1. **One screen, one job.** If a screen does two things, it is two screens.
2. **Cut the text, then cut it again.** Most internal tools fail from density, not
   from lacking features.

---

## 1. Stack

Verified current as of August 2026. Do not substitute without a reason.

| Layer | Use | Notes |
|---|---|---|
| Framework | Next.js (App Router) or Vite + React | Next.js if it needs auth/server data; Vite for a pure client tool |
| Styling | Tailwind CSS v4 | CSS-first config via `@theme`, no `tailwind.config.js` |
| Components | shadcn/ui | Copy-in, not a dependency — we own and edit the code |
| Primitives | Base UI | shadcn's default since July 2026. Radix is still supported; use it only in an existing Radix codebase, don't mix the two in one app |
| Motion | `motion` (motion.dev, formerly Framer Motion) | Import from `motion/react` |
| Icons | `lucide-react` | One icon set only. Never mix sets |
| Tables | TanStack Table + shadcn `data-table` | Anything beyond ~20 rows or needing sort/filter |
| Forms | `react-hook-form` + `zod` | Validate on blur, never on every keystroke |
| Charts | Recharts via shadcn `chart` | Follow the `dataviz` skill for colour and chart-type choice |

Install pattern: `npx shadcn@latest add <component>` — then **edit the generated
file** to match the tokens below rather than overriding with utility soup at call
sites.

---

## 2. Tokens

Define once in `globals.css` under `@theme`. Never hardcode a hex, px size or
duration in a component.

### Colour

**These are the real Circus Group brand values, not placeholders.** They were
read from the custom properties in the live `circus-group.com` stylesheet
(2026-09-04) and re-derived for UI contrast. Ship them as they are.

The brand accent is **blue `#2D62FF`** (`--base-color-brand--blue`). It is not
green. An earlier revision of this file carried an emerald placeholder with a
note to swap it for brand values; the note was missed and the placeholder
shipped as a product's identity for a month. Do not reintroduce a "sample"
palette — if a value here is ever wrong, verify it against the brand and fix it
here rather than at the call site.

```css
@theme {
  /* Neutrals — the app is basically these. Ink is brand #1A1A1A, not black. */
  --color-bg:        #FAFAFA;   /* app canvas — brand --circus-white */
  --color-surface:   #FFFFFF;   /* cards, panels, table bodies */
  --color-sunken:    #F2F3F5;   /* table headers, inset strips */
  --color-border:    #E4E6EA;   /* hairlines inside a surface */
  --color-border-strong: #CDD1D8; /* card and table edges */
  --color-border-control:#8A8F9A; /* input/checkbox outlines — 3.2:1 */
  --color-text:      #1A1A1A;   /* primary — 16.7:1 on canvas */
  --color-secondary: #5A5F6B;   /* sub-lines under a value — 6.4:1 */
  /* Labels and column heads. Dark enough to clear 4.5:1 on the sunken surface
     (4.8:1) as well as on white (5.3:1) — table headers sit on sunken. */
  --color-muted:     #666B78;
  --color-faint:     #9AA0AC;   /* placeholders and disabled ONLY — 2.6:1 */

  /* Accent — actions and selection only. */
  --color-accent:        #2D62FF; /* fills and focus ring — 4.9:1 with white text */
  --color-accent-strong: #1E4BD8; /* hover fill and link text — 6.9:1 */
  --color-accent-soft:   #EDF2FF; /* active nav, selected row */

  /* Status — a soft fill with dark text, from the brand's own system pairs.
     Status only: never decoration, never a chart series. */
  --color-success: #114E0B;  --color-success-soft: #CEF5CA;  /* 8.3:1 */
  --color-warning: #7A4A08;  --color-warning-soft: #FDF0D9;  /* 6.6:1 */
  --color-danger:  #8C1F18;  --color-danger-soft:  #F8E4E4;  /* 7.4:1 */
  --color-neutral: #4A4F5A;  --color-neutral-soft: #EEEFF1;  /* 7.1:1 */
}
```

Rules:

- **Canvas and surface are different colours.** The page is `--color-bg`, cards
  sit on top in `--color-surface`. White cards on a white page separated by a
  hairline is the single most common reason an internal tool reads as "crowded"
  — there is no figure/ground, so everything competes. Fix this before reaching
  for more padding.
- **The accent is a budget.** Roughly one accent element per screen — the
  primary action or the current selection. Four full-width accent buttons on one
  page means the page has no primary action.
- **Never let the accent hue also carry a status.** This is what went wrong with
  the green: one hue meant "click this" *and* "this is fine" on the same screen.
  Blue accent, green success, and they never collide. If a page needs an "info"
  or "running" state, make it neutral rather than a second blue.
- Everything else is neutral. Secondary buttons are bordered/neutral, not tinted.
- Status is a **tinted pill with dark text and a matching dot**, never a grey
  outline with coloured text — at 12px an outline makes the colour a 1px stroke
  and every status ends up weighing the same.
- Contrast floor: 4.5:1 for body text, 3:1 for large text and for the outline of
  any control a user must find (inputs, checkboxes, radios) — that is what
  `--color-border-control` is for. `--color-border` is decorative only.
  `--color-faint` is for placeholders only. If a line changes what someone
  *does* — "short 08 Sept without the proposal" — it is content, and it belongs
  on `--color-secondary`.
- **Check contrast against the surface a token actually sits on, in the running
  app** — read the *resolved* computed value, not the hex in this file. A token
  that clears 4.5:1 on white can fail on the sunken surface: `--color-muted` on
  `--color-sunken` was 4.22:1 before it was darkened, and an 11px uppercase
  header does not qualify as large text. When one fails, fix the token here so
  every call site is fixed at once, never the one call site you noticed.
- Dark mode: only if asked. Half-done dark mode is worse than none.

**Charts get their own ramp.** Status colours are not a categorical scale, and
borrowing `--color-info` for a chart series is the usual mistake. For an ordered
sequence (in stock → on order → proposed) use one hue stepping outward from the
accent; keep anything not yet committed hatched rather than solid.

```css
--chart-in-stock:  #2D62FF;
--chart-on-order:  #8AA6FF;
--chart-proposal:  #C7D6FF;  /* hatched, outlined in --color-accent */
--chart-secondary: #576D68;  /* brand slate green — comparison series */
--chart-target:    #1A1A1A;  /* target/threshold markers */
```

Brand values that exist but must **not** appear in an internal tool:
`--color--circus-live: #FF3636` (live/broadcast) and any marketing gradient.

### Type

Circus uses **PolySans** for display and **Inter** for body. Inter is the safe
default for a tool and is what body text should use. PolySans is a licensed
retail font — confirm the licence covers internal software before using it, and
if it does, restrict it to the page title and brand mark. `Geist` or a system
stack are acceptable fallbacks. **One family. One weight axis.**

```
12px  micro   — table meta, timestamps, badge text
13px  small   — helper text, secondary labels
14px  base    — body, inputs, table cells, buttons   ← default
16px  large   — card titles, section leads
20px  h3
24px  h2
30px  h1      — page title, once per screen
```

- Base is **14px**, not 16px — internal tools are dense and read at desk distance.
- Weights: 400 body, 500 labels and buttons, 600 headings. Never 700+, never 300.
- Line height 1.5 body, 1.25 headings. Measure caps at ~70 characters.
- **Sentence case everywhere.** No Title Case, no ALL CAPS except ≤11px labels
  with letter-spacing.
- Tabular numerals (`font-variant-numeric: tabular-nums`) on every number in a
  table or metric — non-aligned digits are the single most common "looks amateur"
  tell.

### Space, radius, elevation

- Spacing is a 4px scale: `4 8 12 16 24 32 48 64`. Nothing in between.
- Radius: `8px` controls (button, input, badge), `12px` cards and panels,
  `9999px` pills and avatars only. **A control must not share a radius with the
  container it sits in** — when they match, the eye reads them as the same kind
  of object and the hierarchy flattens.
- **Prefer a 1px border over a shadow.** Maximum two elevation levels in an app:
  flat (border only) and floating (dropdown/modal — a soft shadow). No third.
- Page gutter 24px, card padding 20px, gap between form fields 16px.
- **Vertical rhythm is not one value.** A single `space-y-*` on a page container
  gives the header, the alert, the metric row and the table the same gap, so
  nothing groups with anything. Spend the scale: **40px** below the page header,
  **32px** between sections, **16px** between blocks that belong together,
  **8–12px** inside a component.

---

## 3. Layout and density

- **Persistent left nav** if there are 3+ sections; a plain header if fewer.
  Never both a sidebar and a top tab bar.
- Content max-width **1280px**, centred. Full-bleed only for data tables.
- **One primary action per screen**, top-right of the page header or bottom-right
  of a form. Everything else is secondary or in an overflow menu.
- Tables: **7 visible columns maximum** by default. Extra columns go behind a
  column picker. Row height 44px (touch-safe, still dense) — that means roughly
  `12–14px` vertical and **`16px` horizontal** cell padding. 8px cells put the
  first column against the card edge and are the usual cause of a table looking
  cramped. The header is a *label*, not data: 11px caps, letter-spaced, muted,
  on `--color-sunken`, and sticky.
- **Not everything is a card.** Border, fill, radius and shadow each say
  "separate object". One repeated `rounded border` stamped on the alert, the
  metric row and the table gives three different roles the same weight. Lift the
  one thing that needs lifting.
- Progressive disclosure: advanced or rarely-used controls live behind
  "More options", a second tab, or a detail panel. Do not show them by default
  because "someone might need it". Watch the *count* of disclosures too — five
  stacked strips of metadata above the content is worse than one dense line.
- Touch targets ≥ 40×40px — kitchen and warehouse screens get used with gloves.
  A 32px default button height fails this; use 36px for desk-only surfaces and
  40px for anything a floor screen touches.

---

## 4. Words

This is where most internal tools go wrong. Text is the enemy.

- **Buttons are verbs**: "Save changes", "Create order", "Send to kitchen".
  Never "Submit", "OK", "Confirm" alone.
- **Labels are nouns, ≤3 words.** No colons.
- **Helper text ≤ 12 words**, and only when the label genuinely isn't enough.
  If you need a paragraph to explain a field, the field is wrong.
- **No jargon and no internal system names.** Not "sync SKU master", but
  "update the product list".
- **Empty states**: one line saying what lives here, plus the primary action.
  No illustration unless the brand supplies one. Example: *"No orders yet.
  Create your first order."*
- **Errors**: what happened + what to do next, in that order, in plain German or
  English. Never expose a code, a stack trace or "an error occurred". Not
  *"Validation failed (422)"* but *"That order number is already in use. Try a
  different one."*
- **Never put essential information only in a tooltip.** Tooltips are for
  nice-to-know.
- Confirmations only for destructive or irreversible actions. Everything else
  gets an undo toast instead.
- If the app is used in German, write German first and translate to English —
  not the reverse. German strings run ~30% longer; design the layout for that.

---

## 5. Motion

Motion should be felt, not watched. Every value below is deliberate — use these,
don't invent new ones.

```css
@theme {
  --ease-out:  cubic-bezier(0.16, 1, 0.3, 1);   /* entering */
  --ease-in:   cubic-bezier(0.7, 0, 0.84, 0);   /* exiting */
  --dur-micro: 120ms;  /* hover, focus, colour change */
  --dur-fast:  180ms;  /* button press, small reveal, tab switch */
  --dur-base:  240ms;  /* dropdown, popover, tooltip, accordion */
  --dur-slow:  320ms;  /* modal, drawer, route change */
}
```

Hard rules:

- **Animate `opacity` and `transform` only.** Never height, width, top/left, or
  colour on a large surface — they cause jank.
- **Travel distance is small**: 4–8px for menus and tooltips, 12–16px for modals
  and drawers. Anything sliding further reads as a toy.
- **Entering is `ease-out`, exiting is `ease-in`, and exits are ~30% faster than
  entrances.** Leaving should feel like it gets out of the way.
- **Stagger sparingly**: 30ms per item, capped at 6 items, list entry only. Never
  stagger on re-render or filter.
- Springs (`type: "spring", stiffness: 400, damping: 30`) for drag and reorder
  only. Everything else is a tween.
- **Nothing loops.** No pulsing, no bouncing, no attention-seeking idle motion —
  except a single skeleton shimmer while loading.
- **Loading**: skeletons that match the real layout, not spinners. Show them only
  after 300ms of waiting, otherwise a fast response flashes.
- Optimistic UI for anything that usually succeeds — update immediately, reconcile
  after, toast on failure.

Always respect reduced motion — this is not optional:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

---

## 6. Recurring patterns

Build these the same way every time so the apps feel like one family.

- **Page header**: title (30px) + one-line description (14px muted, optional) on
  the left, primary action on the right. Breadcrumb above only if nesting is 3+
  deep.
- **Form**: single column, always. Labels above fields. Validate on blur. Errors
  under the field in `--color-danger` at 13px. Actions bottom-right, primary on
  the right, "Cancel" as a text button.
- **Table**: sticky header, zebra-free (borders only), row hover = surface tint,
  selected row = `--color-accent-soft`. Row actions appear on hover on desktop
  and are always visible on touch. Empty and loading states are required, not
  nice-to-have.
- **Detail view**: prefer a right-hand side panel over a modal when the user needs
  the list context. Modals are for focused, blocking decisions.
- **Toast**: bottom-right, 4s, one line, with undo where applicable. Never stack
  more than three.
- **Status**: a small pill with a dot — colour plus text, never colour alone
  (colour-blind users, and a photocopied screenshot).

---

## 7. Anti-patterns — do not ship these

- A dashboard of KPI cards nobody asked for, in place of the one thing the user
  actually came to do.
- Gradients, glassmorphism, glow, or animated backgrounds. This is a tool.
- More than one accent colour, or status colours used decoratively.
- Icon-only buttons without a visible label or an `aria-label`.
- Emoji as UI iconography.
- Placeholder text used as the label.
- Explaining the interface in the interface — onboarding text, "welcome" banners,
  paragraphs above forms.
- Centre-aligned body text, or text over an image.
- A modal opened from inside a modal.
- Custom scrollbars, custom selects, custom date pickers. Use the primitives.
- **Internal system names anywhere a user can see them** — a project or phase
  code as the brand mark ("P2"), a raw record id where a name belongs
  (`LOC_DEMO_BERLIN_001` instead of "Demo Kitchen Berlin"), or a template
  filename in upload copy. Check the picker especially: several component
  libraries render a select's *value* rather than its label unless you tell
  them otherwise, so the id leaks even when the code looks right.
- Unbuilt features advertised inside a working tool ("coming soon" cards).
- Anything that loops forever — a pulsing dot, a breathing badge. The loading
  skeleton's shimmer is the one exception.

---

## 8. Before shipping — check every one

1. Can a new colleague finish the main task without being told anything?
2. Is there exactly **one** obvious primary action on the screen?
3. Did you delete every sentence that isn't load-bearing?
4. Are there loading, empty and error states for every async surface?
5. Are all durations and colours coming from tokens, not literals — and are the
   token *values* the real brand ones from §2, not something sampled or guessed?
6. Squint at the page. Do the canvas, the cards and the table read as three
   depths, or as one flat white field behind hairlines?
7. Does any user-visible string contain an internal id, code or filename?
8. Tab through it: is focus visible, ordered, and trapped correctly in modals?
9. Does it hold up at 1280px, 1440px, and on a tablet in landscape?
10. Does it still work with `prefers-reduced-motion: reduce`?
11. Are numbers tabular-aligned and dates formatted consistently (`DD.MM.YYYY`
    for German users)?
12. Is any essential information available *only* on hover — or set in
    `--color-faint`, which amounts to the same thing?

If the answer to 1 is no, fix that before anything else on this list.
