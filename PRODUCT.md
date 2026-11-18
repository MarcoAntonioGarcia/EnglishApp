# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Spanish speakers learning English. Open to anyone through public sign-up, but the
primary user is the owner, and the content targets **intermediate to advanced**
learners (B1–C1) who already read some English and want to build vocabulary and
writing through real books.

## Product Purpose

Daily English Habit turns English practice into a small daily routine: read a real
book aloud sentence by sentence, look up any word with AI help (translation,
grammar, examples), save it to spaced-repetition flashcards, and practice writing
with AI correction and level estimates. Success means the learner comes back every
day; the streak and the daily goal are the measure.

## Positioning

A reader-first habit tool: the learner's own books (or public-domain ones by level)
are the material, and every other module (flashcards, writing, lessons) feeds back
into the daily streak. The lessons use a contrastive method written for Spanish
speakers ("why this happens to you in Spanish").

## Operating Context

- Short daily sessions on a phone (flashcards, a few pages) and longer reading or
  writing sessions on a laptop. Both must work; mobile already uses drawers.
- Each user brings their own free Gemini API key; without it the AI runs in a
  simulated mode.
- Voice comes from the browser (Apple voices on iPhone and Mac); the server does not
  generate audio in production.
- Hosted on Render's free plan with Neon Postgres; sign-up confirms the email through
  Brevo.

## Capabilities and Constraints

- Modules: Reading (library, reader, study rail, contents, vocabulary), Flashcards
  (review/words), Decks, Writing (new, my writings, errors journal, lessons from
  mistakes), Statistics, Lessons (route map and levels), Level Test, Settings,
  admin panel.
- The whole interface is in **English**. Lesson explanations aimed at Spanish
  speakers may stay in Spanish where the content was written that way.
- Plain static HTML/CSS/JS served by FastAPI; no build step, no external CDNs (CSP:
  `default-src 'self'`, inline script and style allowed).
- Per-user preferences live in `localStorage` under `lira_*` keys; renaming them
  would reset every user's settings.
- Free software under AGPL-3.0. A general-purpose reader: it ships no books; the
  catalog only downloads public-domain works (Project Gutenberg).

## Brand Commitments

- Name: **Daily English Habit**. Never "Lira" or "English App" in the interface.
- Voice: daily consistency and discipline — "a little every day" — without hype.
- Visual direction chosen by the owner: **A, a night mission-control panel** (deep
  ink-blue background, electric cyan accent, monospace numerals, a subtle grid, the
  streak as the cockpit's main gauge), with a **paper reading mode** toggle for long
  reading.

## Evidence on Hand

- Real lesson content: `lessons_data.py`; seeded decks: `seed_decks.py`; book
  catalog: `catalog.py`.
- No testimonials, user counts, or metrics exist; none may be invented.

## Product Principles

1. The daily habit leads: the streak and today's goal are always visible.
2. Reading stays comfortable: expression never costs legibility in long text.
3. One tap from any word to understanding and to a saved card.
4. Honest feedback: levels and corrections are estimates, labelled as such.
5. Works the same on a phone and on a laptop.

## Accessibility & Inclusion

WCAG AA contrast for text, visible keyboard focus, reduced-motion support, touch
targets of at least 44 px, and no actions hidden behind hover on touch screens.
Native `prompt`/`alert`/`confirm` dialogs are replaced with in-page dialogs.
