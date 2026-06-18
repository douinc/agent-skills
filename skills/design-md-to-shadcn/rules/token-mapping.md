# DESIGN.md → shadcn token mapping

Deterministic rules for translating DESIGN.md front-matter tokens into the project's shadcn CSS variables in its theme CSS file. DESIGN.md uses a Material-3-style namespace; shadcn uses a fixed semantic set split across `:root` (light) and `.dark`.

## Color mapping

Map each DESIGN.md color token to shadcn variable(s). The **left** column lists likely DESIGN.md token names (first match wins, in order); the **right** column is the shadcn target. `on-*` tokens are the foreground pairs.

| DESIGN.md token (in priority order)            | shadcn variable(s)                          |
| ---------------------------------------------- | ------------------------------------------- |
| `background` → `neutral` → `surface`           | `--background`                              |
| `on-background` → `on-surface` → `foreground`  | `--foreground`                             |
| `surface` → `surface-container` → `background`  | `--card`, `--popover`                       |
| `on-surface` → `on-background`                 | `--card-foreground`, `--popover-foreground` |
| `primary`                                      | `--primary`                                |
| `on-primary`                                   | `--primary-foreground`                      |
| `secondary`                                    | `--secondary`                              |
| `on-secondary`                                 | `--secondary-foreground`                    |
| `tertiary` → `accent`                          | `--accent`                                 |
| `on-tertiary` → `on-accent`                    | `--accent-foreground`                       |
| `surface-container*` → `muted` → `secondary`   | `--muted`                                  |
| `on-surface-variant` → `muted-foreground`      | `--muted-foreground`                        |
| `error` → `destructive`                        | `--destructive`                            |
| `on-error`                                     | `--destructive-foreground` (if present)\*   |
| `outline` → `outline-variant` → `border`       | `--border`, `--input`                       |
| `ring` → focus color → `primary`               | `--ring`                                    |

\* Note: some shadcn setups don't define `--destructive-foreground`; only add it if it already exists in the theme file.

### Rules
- **First match wins.** Use the highest-priority token that exists in the DESIGN.md; skip the rest for that row.
- **Foreground pairs.** If an `on-*` token is missing, compute a readable foreground from the mapped background: near-white (`oklch(0.985 0 0)`) on dark backgrounds, near-black (`oklch(0.145 0 0)`) on light. Target WCAG AA (≥4.5:1) by eye.
- **`--card`/`--popover`.** If no distinct `surface` exists, fall back to `--background`'s value (shadcn's neutral default keeps card == background).
- **`--accent`.** If the design has no tertiary/accent, reuse `--secondary`'s values (matches the project's neutral baseline where accent == secondary == muted).

## Charts & sidebar (derived)

These have no DESIGN.md equivalent — derive them:

- `--chart-1..5`: seed from `primary`, `secondary`, `tertiary`, then interpolate two more across the palette (vary lightness/hue). If the design is essentially monochrome, keep the existing neutral chart ramp.
- `--sidebar`, `--sidebar-foreground`, `--sidebar-border`, `--sidebar-ring`: derive from `surface`/`background` + `border`/`ring` (sidebar is usually a slightly shifted surface). `--sidebar-primary*` / `--sidebar-accent*`: mirror `--primary*` / `--accent*` unless the design specifies a distinct nav treatment.

## Radius mapping

- `--radius` ← DESIGN.md `rounded.md`, else `rounded.DEFAULT`, else `rounded.lg`. Convert to `rem` (e.g. `8px` → `0.5rem`).
- **Leave the `--radius-sm..4xl` calc scale in `@theme {}` untouched** — it's derived from `--radius`.

## Spacing

DESIGN.md `spacing` has **no direct shadcn token target**. Do not write it into the theme CSS file. Surface it as Layout guidance (base grid unit, gutters, container padding) for the component step instead.

## Light vs dark mode handling

DESIGN.md is single-mode. Determine the source mode from the mapped `--background` lightness:
- **L ≥ ~0.5 → light source** → fill `:root` from the design; derive `.dark` by inverting lightness of each token (keep hue/chroma), and flag `.dark` as auto-derived for review.
- **L < ~0.5 → dark source** → fill `.dark` from the design; derive `:root` likewise and flag it.

When deriving, preserve the foreground/background contrast relationships rather than naively inverting each value independently. Tell the user which block was authored vs derived.

## Color normalization

- Convert every value to match the theme file's existing convention (`oklch()`, HSL channels, or raw). The examples below use `oklch()`. Preserve alpha where present (e.g. `rgba(255,255,255,0.1)` → `oklch(1 0 0 / 10%)`).
- Keep the original value as a trailing comment, e.g.:
  ```css
  --primary: oklch(0.45 0.16 29); /* #B8422E */
  ```
- `oklch()` conversion is approximate — note this and recommend a visual check; never claim exact fidelity.

## Unknown / extra tokens

- Unknown DESIGN.md color tokens with valid values: keep as extra custom vars (commented) or report — don't drop silently.
- Unknown component properties / sections: ignore for token mapping; fold any useful intent into the component guidance (step 5).
