---
name: design-md-to-shadcn
description: "Applies an external DESIGN.md (Google Labs design-token format) to a project's shadcn/ui theme. Activate when the user provides or references a DESIGN.md / design.md file, a designmd.app or Stitch design system, a downloaded brand design system, or asks to 'apply a design system / theme' to a shadcn project. Translates DESIGN.md tokens into shadcn CSS variables in the project's theme CSS file and turns the prose into component guidance. Inbound-only: does not extract a DESIGN.md from the project."
metadata:
  author: initred
  email: initred@dou.so
  version: "1.0.0"
---

# DESIGN.md → shadcn/ui

Take an external **DESIGN.md** (the Google Labs design-token format, version `alpha`, Apache-2.0) and apply it to the project's shadcn/ui theme.

## What this skill is for

The DESIGN.md format pairs machine-readable YAML front matter (design tokens) with markdown prose (rationale + guidance). It uses a **Material-3-style token namespace** (`primary`, `secondary`, `tertiary`, `neutral`, `surface`, `on-surface`, `surface-container-*`, `on-primary`, …) that does **not** map 1:1 to shadcn's fixed semantic tokens.

The official `design.md export --format css-tailwind` emits `--color-primary` etc. — single-mode, no foreground pairs — which is **not** usable by shadcn. This skill provides the missing mapping layer: DESIGN.md tokens → shadcn `:root` / `.dark` CSS variables, plus prose → component guidance.

- **Direction:** inbound only (external DESIGN.md → the project). Do not generate a DESIGN.md from the project.
- **Dependencies:** none. No `@google/design.md` CLI, no package installs. Pure parsing + the mapping table in [rules/token-mapping.md](rules/token-mapping.md).

## Project target (locate, then verify before editing)

First find the project's shadcn theme CSS file and config — don't assume a path:

- **Theme CSS file:** the file holding shadcn tokens as CSS variables in `:root` (light) and `.dark`. Common locations: `app/globals.css`, `src/index.css`, `src/app.css`, `resources/css/app.css`, `styles/globals.css`. Confirm by grepping for `--background`, `--primary`, or `--radius`.
- **`components.json`** (repo root): read `style`, `baseColor`, `cssVariables`, `tailwind.css` (points to the theme file), and the `aliases`. Note whether tokens are HSL/`oklch()`/raw and match that convention.
- Composition rules (Card/Dialog/Tabs/etc.) and component install belong to the **`shadcn` skill** — defer to it for step 5.

> Re-read the theme CSS file before editing; its token blocks are the source of truth and may differ from any assumptions.

## Workflow

### 1. Collect the input

Get the DESIGN.md as a file path, pasted text, or URL. If a URL, fetch the raw markdown (e.g. WebFetch). Confirm it has `---` front matter; if it's prose-only, extract what tokens you can and note the gaps.

### 2. Parse

- **Front matter** (between the `---` fences): `name`, `colors`, `typography`, `rounded`, `spacing`, `components`.
- **Body** (`##` sections, canonical order): Overview / Colors / Typography / Layout / Elevation & Depth / Shapes / Components / Do's and Don'ts. Section aliases exist (Overview≡"Brand & Style", Layout≡"Layout & Spacing", Elevation≡"Elevation & Depth").
- Resolve token references `{path.to.token}` (e.g. `{colors.primary}`, `{rounded.md}`) to their values before mapping.

### 3. Map tokens → shadcn (the core step)

Follow [rules/token-mapping.md](rules/token-mapping.md) exactly:

- Color tokens → shadcn semantic variables (with foreground pairs).
- `rounded.md`/`DEFAULT` → `--radius`.
- Detect light vs dark from the background's lightness; fill the matching block, derive the opposite block (flag it for review).
- Normalize every color to the theme file's existing convention (`oklch()`, HSL channels, or raw) — match what's already there; keep the original value in a trailing comment.

### 4. Apply to the theme CSS file

Edit **only** the variable lines inside `:root` and `.dark`. **Preserve** everything else: `@import`s, fonts, `@theme {}` (including any `--color-* → var(--*)` aliases and the `--radius-*` calc scale), and `@layer base {}`.

- Use targeted `Edit` calls per variable block — never overwrite the whole file.
- Present a concise summary of the changes (old → new per token) before/with the edit.
- Unmapped DESIGN.md tokens: keep them as extra custom vars with a comment, or report them — do not silently drop.

### 5. Component & layout guidance

Summarize the prose (Overview, Layout, Elevation & Depth, Shapes, Components, Do's and Don'ts) into concrete rules for any UI built next — e.g. "one primary action per screen", radius/elevation conventions, component variants. Then hand off actual component selection / install / composition to the **`shadcn` skill**.

## Guardrails

- Never overwrite the theme CSS file wholesale — edit token lines only; keep imports/fonts/`@theme`/`@layer base` intact.
- Show the token diff before applying so the user can sanity-check.
- Color conversions (to `oklch()`/HSL) are approximations — recommend a visual check; do not claim exact color fidelity.
- This skill maps tokens and surfaces guidance; it does not install components (that's the `shadcn` skill) and does not add dependencies.
- After editing, the user must rebuild/restart the dev server to see changes — use the project's own build command (e.g. `npm run build`/`dev`, `pnpm`, `bun`, or `vendor/bin/sail …` for Laravel Sail setups). Check `package.json` scripts if unsure.
