---
name: Daily English Habit
description: A night instrument panel for a daily reading habit; the book is the payload.
colors:
  cyan: "#3ccfe6"
  cyan-ink: "#7fe3f3"
  cyan-deep: "#05242c"
  cyan-wash: "rgba(60,207,230,.11)"
  cyan-line: "rgba(60,207,230,.38)"
  amber: "#f3b54a"
  amber-ink: "#ffcf7a"
  amber-wash: "rgba(243,181,74,.12)"
  ok: "#4fd49a"
  ok-wash: "rgba(79,212,154,.12)"
  bad: "#ff7a72"
  bad-wash: "rgba(255,122,114,.12)"
  blue: "#8fb2ff"
  blue-wash: "rgba(143,178,255,.13)"
  bg: "#0a111e"
  s1: "#0f1829"
  s2: "#142036"
  s3: "#1a2843"
  line: "#1f2d48"
  line-2: "#2b3c5e"
  ink: "#e4ebf5"
  ink-2: "#a3b3ca"
  ink-3: "#7a8ead"
  page: "#0d1626"
  page-ink: "#d5dfec"
  page-line: "#1d2a44"
  page-cur: "rgba(60,207,230,.16)"
  page-word: "#ffe08a"
  page-word-ink: "#1c1606"
  paper: "#f1efe9"
  paper-ink: "#2a2a2c"
  paper-line: "#dedad0"
  lamp-warm: "#ffc45e"
  lamp-violet: "#b48cff"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"SF Pro Text\", \"Segoe UI\", system-ui, Roboto, sans-serif"
    fontSize: "clamp(28px, 3.4vw, 36px)"
    fontWeight: 650
    lineHeight: 1.12
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"SF Pro Text\", \"Segoe UI\", system-ui, Roboto, sans-serif"
    fontSize: "22px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"SF Pro Text\", \"Segoe UI\", system-ui, Roboto, sans-serif"
    fontSize: "17px"
    fontWeight: 650
    letterSpacing: "-0.01em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"SF Pro Text\", \"Segoe UI\", system-ui, Roboto, sans-serif"
    fontSize: "14.5px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"SF Pro Text\", \"Segoe UI\", system-ui, Roboto, sans-serif"
    fontSize: "12.5px"
    fontWeight: 600
    lineHeight: 1.45
  reading:
    fontFamily: "\"Iowan Old Style\", \"Palatino Linotype\", Palatino, \"Book Antiqua\", Georgia, serif"
    fontSize: "20px"
    fontWeight: 400
    lineHeight: 1.9
  measure:
    fontFamily: "ui-monospace, \"SF Mono\", SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "34px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.03em"
    fontFeature: "\"tnum\""
rounded:
  hair: "2px"
  sm: "8px"
  control: "10px"
  md: "12px"
  lg: "16px"
  pill: "20px"
spacing:
  xs: "6px"
  sm: "8px"
  md: "14px"
  lg: "18px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.cyan}"
    textColor: "{colors.cyan-deep}"
    rounded: "{rounded.control}"
    padding: "9px 14px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "#63dcef"
  button-secondary:
    backgroundColor: "{colors.s2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "9px 14px"
    height: "40px"
  button-secondary-hover:
    backgroundColor: "{colors.s3}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.control}"
    padding: "9px 14px"
  button-danger:
    backgroundColor: "{colors.bad}"
    textColor: "#2a0705"
    rounded: "{rounded.control}"
    padding: "9px 16px"
    height: "40px"
  button-sign-in:
    backgroundColor: "{colors.cyan}"
    textColor: "{colors.cyan-deep}"
    rounded: "{rounded.control}"
    padding: "11px"
    height: "46px"
    width: "100%"
  input:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "11px 12px"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.sm}"
    padding: "9px 10px"
    height: "42px"
  nav-item-active:
    backgroundColor: "{colors.s3}"
    textColor: "{colors.ink}"
  tag:
    backgroundColor: "{colors.cyan-wash}"
    textColor: "{colors.cyan-ink}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  card:
    backgroundColor: "{colors.s1}"
    rounded: "{rounded.md}"
    padding: "15px"
  gauge:
    backgroundColor: "{colors.bg}"
    rounded: "{rounded.md}"
    padding: "12px"
  review-card:
    backgroundColor: "{colors.s1}"
    rounded: "{rounded.lg}"
    padding: "34px"
  dialog:
    backgroundColor: "{colors.s1}"
    rounded: "{rounded.lg}"
    padding: "20px"
    width: "440px"
  toast:
    backgroundColor: "{colors.s2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "11px 18px"
---

# Design System: Daily English Habit

All tokens live once in `static/theme.css` as custom properties on `:root`; pages only use `var(--…)`. `static/index.html` remaps its legacy names (`--gold`, `--card`, `--paper`, `--accent`…) onto these at the top of its `<style>`. New code uses the theme names directly.

## Overview

**Creative North Star: "The Night Instrument Panel"**

The daily habit is a cockpit seen at night: an ink-blue deck under a faint plotting grid, hairline panels, drawn line icons, and one cyan signal that says "this is active" or "do this". The streak is the cockpit's main gauge and the only warm instrument on the panel. The book is the payload: the reading page sits in the middle of the console and is the one place where expression yields entirely to legibility.

Density is calm-operational. Panels are flat and outlined, not lifted; numbers that are measurements read as instrument readouts in monospace; everything else is the system UI sans. Depth is spatial, not decorative: every section rises one layer from behind the cockpit, and a pull-cord lamp changes the light rather than a toggle changing a theme. The direction refuses both the cream-paper bookish default and the neon-glow cockpit.

The sign-in pages are the one room with mood lighting: a standing lamp whose cord cycles the whole room through cyan, warm, violet, and lights out, and the form takes its accent from the lamp.

**Key Characteristics:**
- Ink-blue deck (`bg`) with a 32px plotting grid at 3.5% cyan and one soft cyan radial wash.
- One cyan signal for state and action; amber only for the habit and warm notes.
- System sans for interface, monospace only for measurements, book serif for reading and italic accent words.
- Hairline borders carry structure; one shadow exists and it is reserved for floating layers.
- Motion means depth: sections rise, contents arrive in layers, answers turn over, a deck row zooms in and a window becomes the card.

## Colors

A dark, cool tonal ladder with exactly one cool signal and one warm signal; status colors stay in their lanes.

### Primary
- **Signal Cyan** (`cyan`): the one accent. Active nav/library marker (2px inset bar), primary buttons, goal segments in progress, progress bars, meters, the due "windows" of a deck row, focus outline. On dark surfaces, cyan used as text is always the lighter **Cyan Readout** (`cyan-ink`); text on a cyan fill is always **Cyan Deep** (`cyan-deep`, 8.7:1). **Cyan Wash** and **Cyan Line** are the tinted fill and border for tags, rules, the hovered deck row, and input focus rings.

### Secondary
- **Habit Amber** (`amber`, `amber-ink`, `amber-wash`): the streak and nothing else structural. The lit flame and streak number in the gauge, the mobile streak chip, the ignite pulse when today's goal is met, plus warm notes: "remember this" boxes, lesson spot notes, "work on" chips, "AI off" status, the pending user chip in admin, and the hover bead on the reading-lamp cord.

### Tertiary
- **Status lanes**: **Go Green** (`ok`) for correct answers, goal met (all segments turn green), AI connected, active accounts, beginner level. **Fault Coral** (`bad`) for wrong answers, destructive buttons, error toasts and notices, mistake bars. **Instrument Blue** (`blue`) for "new" badges, B2/mid level, question forms, admin role. Each pairs with its 12-13% wash for backgrounds.
- **Lamp colors (sign-in only)**: the lamp cycles `cyan` → **Warm Glow** (`lamp-warm`) → **Violet** (`lamp-violet`) → lights out (the accent falls back to `ink-2`, glow transparent, the primary button turns `ink` on `bg` so it never looks disabled). Violet also marks the Advanced column of the lesson route map; nowhere else.

### Neutral
- **Deck** (`bg`): the page behind everything, also inset wells (gauge, inputs, icon tiles).
- **Panel / Raised / Pressed** (`s1`, `s2`, `s3`): panels and cards; hover; selected and track backgrounds.
- **Hairline** (`line`) for dividers and panel borders; **Control Line** (`line-2`) for control and floating-layer borders.
- **Ink ladder**: `ink` primary text (15.7:1 on `bg`), `ink-2` secondary (8.9:1), `ink-3` tertiary and labels (5.3:1 on `s1`).
- **Reading page, night** (`page`, `page-ink` at 13.4:1, `page-line`, `page-cur` for the sentence being read, `page-word` + `page-word-ink` for the word being spoken).
- **Reading page, paper** (`paper`, `paper-ink` at 12.5:1, `paper-line`): applied by `body.paper-mode`, which redefines only the `--page*` tokens.

### Named Rules
**The One Signal Rule.** Cyan is the only colour that means "active" or "act". Never introduce a second accent for buttons, links, or selection.

**The Habit Owns Amber Rule.** Amber marks the streak and warm notes. It is never a button, a link, a selection, or a decorative highlight.

**The Paper Is Only the Page Rule.** Paper mode changes the book page and nothing else; the cockpit around it stays dark.

## Typography

**Interface Font:** system UI sans (`-apple-system`, SF Pro Text, Segoe UI, system-ui, Roboto)
**Reading Font:** book serif (Iowan Old Style, Palatino Linotype, Palatino, Book Antiqua, Georgia)
**Measurement Font:** system monospace (ui-monospace, SF Mono, Menlo, Consolas)

**Character:** a quiet instrument sans for every control, a warm book serif wherever the learner reads or a word is the subject, and monospace numerals that read like gauges. No web fonts are loaded (CSP `default-src 'self'`); the stacks are the system.

### Hierarchy
- **Display** (650, clamp(28px, 3.4vw, 36px), 1.12, -0.025em): sign-in headings; the empty-state line uses the same voice at 28px.
- **Headline** (650, 22-26px, -0.02em): section roofs ("Your *decks*"), admin title, large lesson title (24px).
- **Title** (650, 17px, -0.01em): reader top bar, section panel names, dialog headings, route-map columns.
- **Body** (400, 14-15.5px, 1.55-1.65): interface text, lesson explanations (max 70ch).
- **Label** (600-650, 12-13px): card headings (13px), field labels, list headers; `ink-2` or `ink-3`. Sidebar list header is 11.5px with 0.02em tracking.
- **Reading** (400, 20px, 1.9, justified with hyphens, max 68ch; 19px/1.85 left-aligned on phones): the book. Chapter name 27px/600 in the same serif. Writing editor 19px/1.7; study term 19px; review-card term 40px (34px on phones); quiz prompts 23-24px.
- **Measure** (600, monospace, tabular): streak number 34px, stat tiles 30px, level readout 26-30px, test result 46px; small readouts (counts, page numbers, percentages, bar values) 11-13px.

### Named Rules
**The Measurement-Only Mono Rule.** Monospace is for numbers that are measurements (streak, counts, levels, percentages, page numbers) and code. Never for headings, labels, or prose.

**The Italic Accent Word Rule.** A heading may set one or two words in the book serif italic (500) as its accent: cyan-ink in the app ("Your *decks*", "A little English, *every day*"), the lamp colour on sign-in. One accent phrase per heading.

**The Reading Wins Rule.** In long text, legibility beats expression: serif at 19-20px, 1.85-1.9 leading, 68ch measure, AA contrast in both night and paper.

## Layout

- **App shell (desktop):** three-column grid, full viewport height: left console 272px (`--side-w`), centre reader, right rail 336px. The body never scrolls; columns scroll internally.
- **≤1100px:** the right rail hides; two columns.
- **≤900px:** one column. Sidebar and rail become drawers (`min(86vw, 310px)`, slide in 0.26s) over a dark veil; a streak chip appears in the top bar so the habit stays visible; sections cover the whole screen; safe-area insets are honoured everywhere.
- **Sections** open as overlays to the right of the sidebar: a centred panel (max 940px, 88vh) or a full panel with a sticky blurred header; content columns cap at 660px (tabs) or 1120px (statistics).
- **Reader:** paper card max 860px with 52px/72px padding (28px/20px on phones); a floating toolbar sits 22px above the bottom edge, centred; on phones it spans the width.
- **Sign-in room:** grid `1fr | 440px | .35fr` with the lamp stage on the left and the form sheet centred; below 900px the lamp shrinks to a 250px band above the form.
- **Rhythm:** gaps of 6, 8, 10, 14px inside components; panel padding 14-18px; page padding 24px (12-14px on phones). Two-column grids collapse at 820-860px.

### Named Rules
**The Habit Always Visible Rule.** The streak gauge (desktop) or streak chip (phone) is on screen in the reader at every width.

## Elevation & Depth

Flat by default, outlined by hairlines. Panels, cards, tiles and rows sit on tonal steps (`bg` → `s1` → `s2` → `s3`) with 1px borders and no shadow. A single shadow exists and it is reserved for things that float above the cockpit: dialogs, modals, section panels, the reading-options popover, the floating toolbar, the toast, mobile drawers, and the sign-in sheet. Floating glass (toolbar, sticky section header, sign-in sheet) adds an 8-10px backdrop blur over a 86-94% opaque panel. Dialog backdrops are `rgba(3,7,14,.62)` with 3px blur.

### Shadow Vocabulary
- **Pop** (`box-shadow: 0 6px 16px rgba(0,0,0,.36), 0 26px 60px rgba(0,0,0,.42)`): every floating layer listed above. Nothing at rest gets it.

### Named Rules
**The Float Earns the Shadow Rule.** A surface gets the shadow only if it floats over other content. Resting panels use a border and a tonal step.

**The Plotting Grid Rule.** The deck background is a 32px grid of 1px lines at 3.5% `cyan-ink` plus one faint cyan radial wash (`.deck-grid`). It stays subliminal; never raise its opacity or animate it.

### Motion

One ease for everything: `cubic-bezier(.16,1,.3,1)` (`--ease`), a fast-out, soft-landing curve. Motion always means a change of depth or a physical action.

- **depthIn** (0.55s): a section rises from behind the cockpit: from 94% scale, 18px down, 6px blur.
- **layerIn** (0.5s): its contents arrive in layers, 14px up, staggered 0.05s per child, capped at 0.2s.
- **turnIn** (0.45s): a revealed answer turns over from -55° on the X axis, hinged at the top.
- **Zoom into a row** (decks): the chosen storey scales to at most 2.5x (min 1.4x, fitted to the panel), the others fade and blur out; after 430ms its first lit window grows into the review card as a cyan **pane** that settles into `s1` (0.45s) and hands over to the real card. Back zooms out (from 2.2x) onto the same row and refocuses it.
- **Lamp cord springs:** reading lamp 0.7s `cubic-bezier(.3,1.6,.5,1)`, 14px travel; sign-in lamp 0.8s `cubic-bezier(.3,1.7,.45,1)`, 22px travel. Light changes cross-fade over 0.5-0.8s. The reading lamp sways twice on load (3.5s each) and then rests.
- **Micro-states:** hover and colour changes 0.15s; drawers 0.26s; progress and meters 0.4-0.5s.
- **Reduced motion:** a global rule collapses every animation and transition to 0.01ms; the deck zoom and window-to-card pane are skipped in script, leaving a plain cut.

**The One Protagonist Rule.** Each screen has at most one featured motion (a section rising, a row zooming, a card turning, the cord). Nothing loops except the sign-in fireflies.

## Shapes

Gently rounded rectangles, consistently stepped: 2px for gauge segments and deck windows, 8px for small controls and list rows, 10px for buttons, inputs and icon tiles, 12px for cards and panels, 16px for dialogs, section panels, the reading page, the review card and the deck tower; 20px pills for tags, chips and mode buttons. Avatars and status dots are circles. Borders are always 1px (`line` for structure, `line-2` for controls); the only heavier strokes are the 2px inset active bar on nav and library rows and the 2px top inset on route-map column heads. Icons are drawn line icons from an inline SVG sprite: 24px grid, 1.7 stroke, round caps and joins, rendered at 18px (15px small), coloured by `currentColor`.

## Components

### Buttons
Tactile and quiet: filled only when they are the action.
- **Shape:** 10px radius, 40px min height (32px small), 14px/550 text, icon + label with an 8px gap.
- **Primary:** cyan fill, cyan-deep text, 650 weight; hover lightens to `#63dcef`. One per view.
- **Secondary:** `s2` fill with `line-2` border; hover `s3`.
- **Outline-on-deck:** `bg` fill, cyan-line border, cyan-ink text; hover cyan-wash.
- **Ghost:** transparent, `ink-2`; hover `s2` and `ink`.
- **Danger (dialogs):** coral fill, near-black coral text; used only for confirmed destructive actions.
- **Active state:** 1px press (`translateY(1px)`). **Disabled:** 45% opacity, no press.
- **Icon button:** 38px square, 10px radius, `s1` with `line-2` border, `ink-2` icon.
- **Sign-in primary:** full width, 46px, takes the lamp colour; with lights out it turns `ink` on `bg`.

### Chips and Tags
- **Style:** 20px pills, 11-12px/600. Tags and count pills are cyan-wash with cyan-ink (counts in monospace). Status chips use their lane's wash and colour (`ok`, amber, `bad`, `blue`).
- **Mode buttons** (segmented choices): `s1` pill with `line-2` border, 36px; active is a cyan fill.

### Cards / Containers
- **Corner Style:** 12px (cards, tiles, rows); 16px for large panels.
- **Background:** `s1` on the deck; inset wells use `bg`.
- **Shadow Strategy:** none (see Elevation).
- **Border:** 1px `line`; `line-2` or `cyan-line` when emphasised.
- **Internal Padding:** 15px cards, 16px tiles, 34px review card.
- **Stat tiles:** instrument readouts; on the statistics page they join into one bordered strip divided by hairlines.

### Inputs / Fields
- **Style:** `bg` fill, 1px `line-2`, 10px radius, 16px text (prevents zoom on iOS), `ink-3` placeholder.
- **Focus:** border turns cyan (lamp colour on sign-in) plus a 3px cyan-wash ring.
- **Validation:** border turns `ok` or `bad`; the verdict line below uses the same colour.

### Navigation
- **Sidebar nav:** full-width rows, 42px min height, 14.5px/550, 18px line icon + label. Default `ink-2`; hover `s2`; active `s3` with a 2px cyan inset bar on the left and a cyan icon. A 7px cyan dot marks a section with something waiting.
- **Library rows:** 44px rows with a small book-spine tile; same active treatment; rename/delete reveal on hover and are always visible on touch (`hover:none`).
- **Tabs:** 36px, 9px radius, transparent; active `s3` with a `line-2` border. On phones they scroll horizontally.

### Streak Gauge (signature)
The cockpit's main instrument, top of the left console. A `bg` well with a hairline border holds a flame tile, the streak number in 34px monospace amber-ink (55% opacity until today counts, then full), a "day streak" label, and a 10-segment goal bar (6px segments, 3px gaps): `s3` empty, cyan as reviews accrue, all green once today's goal is met. The goal line below is a button that opens the daily-goal dialog. When the goal is met the flame and number "ignite" once (0.9s scale pulse with an amber-wash ring).

### Reading Page and Lamp (signature)
The book page is a 16px-radius card in `page` colours. Tapping a sentence highlights it with `page-cur`; while reading aloud, the current word gets `page-word` with dark ink. A pendant lamp hangs at the top right of the reader: pull its cord (a 0.7s spring) to switch Night ↔ Paper. In paper mode the bulb lights warm and a soft warm radial glow falls on the page; the button's `aria-pressed` tracks the state.

### Deck Rows with Windows (signature)
Decks are listed as storeys in one bordered column ("Your *decks*" with a monospace total). Each row: a 40px monogram tile, name (15.5px/650), a sub-line with the review count in cyan-ink, and a strip of 24 "windows" (7×11px, 2px radius) in proportion: cyan = due today, 30% cyan = seen, `s3` = never seen. Hover or keyboard focus lights the floor with a horizontal cyan-wash band between cyan-line hairlines and nudges the chevron 3px. Rows are `role="button"`, focusable, and open on Enter or Space.

### Review Card
Centred, `s1`, 16px radius, 34px padding, min 270px tall. Term in the book serif (40px), translation in cyan-ink (23px/600), example in italic `ink-2`. Grade buttons stack a label over a monospace interval. Revealing the answer turns it over (`turnIn`). Keyboard: Space/Enter reveals, 1-4 grades.

### Dialogs
In-page replacements for `prompt`/`alert`/`confirm` (`static/ui.js`, styled in `theme.css`). 440px max, `s1`, `line-2` border, 16px radius, pop shadow, 20px padding; title 17px/650, text `ink-2`, actions right-aligned (Cancel as outline, OK as cyan primary or coral danger). Fades and rises in (0.18s / 0.26s).

### Toast
Bottom-centred `s2` capsule with `line-2` border and the pop shadow, 14px text, max `min(92vw, 520px)`; slides up 16px and fades in 0.25s. Info stays 1.6s; errors switch to a dark coral surface and stay 5s.

### Sign-in Sheet and Lamp Room
Sign-in, account, and welcome pages share one scene: a standing lamp (SVG, pull cord), a light cone and floor pool in `--lamp-glow`, five slow fireflies, and a translucent `s1` sheet (16px radius, 8px blur, pop shadow plus a 1px lamp-tinted ring). The brand mark, heading accent word, links and button all take `--lamp`. The lamp choice persists per device (`lira_lamp`) and the pages work without it.

## Do's and Don'ts

### Accessibility commitments

- **Contrast (WCAG AA, measured):** `ink` 15.7:1, `ink-2` 8.9:1, `ink-3` 5.3-5.7:1, `cyan-ink` 12:1, `amber-ink` 12.2:1 on panels; `cyan-deep` on cyan 8.7:1; night page text 13.4:1, paper page text 12.5:1.
- **Focus:** `:focus-visible` always shows a 2px cyan outline offset 2px; inputs show the cyan border and ring; custom controls (lamp, deck rows) draw their own visible focus.
- **Touch targets:** the commitment is 44px on touch. List rows (44px) and the sign-in button (46px) meet it; new controls must meet it.
- **Dialogs:** the rest of the page is made `inert` while open; focus is trapped and restored; Esc and backdrop cancel; destructive dialogs use `role="alertdialog"` and start focused on **Cancel**, so a stray Enter never deletes.
- **No hover-only actions on touch:** hover-revealed controls are always visible under `hover:none`; keyboard hints show only for fine pointers.

### Do:
- **Do** take colours from `static/theme.css` tokens (`var(--cyan)`, `var(--s1)`…) and add any new colour there as a token. A few literal hover and state shades remain in pages (`#63dcef` primary hover, `#3a4f78` hover border); don't add more.
- **Do** keep cyan as the single signal for active and primary; one filled primary button per view.
- **Do** use amber only for the streak/habit and warm notes.
- **Do** set measurements in monospace with tabular numerals and everything else in the system sans; use the book serif for reading surfaces and italic accent words.
- **Do** separate resting surfaces with 1px hairlines and tonal steps; give the pop shadow only to floating layers.
- **Do** draw icons from the inline SVG sprite (24px grid, 1.7 stroke, `currentColor`).
- **Do** make every new section enter with `depthIn` and its children with `layerIn`, and check it under `prefers-reduced-motion`.
- **Do** use `uiDialog` / `uiConfirm` / `uiPrompt` for any question to the user, with `danger: true` for destructive ones.

### Don't:
- **Don't** use emoji or text glyphs as icons; use the sprite.
- **Don't** use gradient text.
- **Don't** add neon glows to UI chrome (text, buttons, borders, panels). Glow belongs only to the lamps' light: bulbs, cones, floor pools, fireflies, and the paper-mode page glow.
- **Don't** run more than one protagonist motion per screen, and don't loop motion in the app.
- **Don't** draw a literal building (facade, skyline, roofline) anywhere. Decks borrow only storey rows and window strips; the full building metaphor is reserved for the future language picker.
- **Don't** let paper mode restyle the cockpit; it changes only the `--page*` tokens.
- **Don't** use native `prompt`/`alert`/`confirm`.
- **Don't** set prose, labels, or headings in monospace.
