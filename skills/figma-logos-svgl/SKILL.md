---
name: figma-logos-svgl
description: Use when working with Figma and brand or product logos are needed — triggers on brand names (React, Next.js, Vercel, Stripe, GitHub), company logos, or requests to add/insert logos in Figma designs.
metadata:
  author: initred
  email: initred@gmail.com
  version: "1.0.0"
---

# SVGL Logos for Figma

Fetch real brand and product SVG logos from the [SVGL API](https://svgl.app/) and insert them into Figma designs. **Never draw logos manually** — always use this workflow to get accurate logos from a curated collection of 500+ brand SVGs.

**SVGL vs Iconify:** Use this skill for **brand/product logos** (React, Vercel, Stripe, GitHub). Use `figma-icons-iconify` for **UI icons** (arrows, alerts, settings).

## Prerequisites

- The `figma-use` skill **MUST** be loaded before any `use_figma` tool call. Always invoke it first.
- `fetch()` is **NOT available** inside `use_figma` code. All HTTP requests must happen **before** calling `use_figma`.
- **Use `Bash(curl -s ...)` instead of `WebFetch`** to call the SVGL API. The SVGL API may return 403 for WebFetch requests but works with curl.

## Core Workflow

### Step 1: Search for the Logo

Use the SVGL search endpoint to find the logo:

```bash
curl -s "https://api.svgl.app?search={name}"
```

**Example:**
```bash
curl -s "https://api.svgl.app?search=react"
```

This returns a JSON array. Each item has a `route` field which is either:
- **A string** — single SVG URL (e.g., `"https://svgl.app/library/preact.svg"`)
- **A theme object** — with `light` and `dark` variants:
  ```json
  { "light": "https://svgl.app/library/react_light.svg", "dark": "https://svgl.app/library/react_dark.svg" }
  ```

Pick the matching result by `title`, then choose the appropriate variant (light/dark) based on the design context.

> **Note:** The `category` field can be a string (`"Software"`) or an array (`["Software", "Privacy"]`). Handle both types when filtering by category.

### Step 2: Fetch the SVG Content

Fetch the raw SVG using the URL from Step 1:

```bash
curl -s "https://svgl.app/library/{filename}.svg"
```

**Example:**
```bash
curl -s "https://svgl.app/library/react_dark.svg"
```

### Step 3: Insert into Figma via use_figma

Pass the fetched SVG string into a `use_figma` call using `figma.createNodeFromSvg()`:

```js
// Paste the exact SVG string from Step 2
const svgString = `<svg xmlns="http://www.w3.org/2000/svg" ...>...</svg>`;

const node = figma.createNodeFromSvg(svgString);
// Name format: SVGL/{logo-name} for easy identification
node.name = "SVGL/React";

// IMPORTANT: Preserve aspect ratio when resizing.
// Extract original dimensions from the created node, then scale proportionally.
const originalWidth = node.width;
const originalHeight = node.height;
const targetHeight = 24; // desired height
const targetWidth = targetHeight * (originalWidth / originalHeight);
node.resize(targetWidth, targetHeight);

// Append to target frame (replace TARGET_ID with actual node ID)
const target = figma.getNodeById("TARGET_ID");
target.appendChild(node);

return { createdNodeIds: [node.id] };
```

> **Aspect ratio is critical.** Brand logos are rarely square (e.g., Nuxt is 256x168). Always calculate proportional dimensions from the original SVG width/height. Never force a square resize like `node.resize(16, 16)` unless the original SVG is square.

## API Endpoints

| Endpoint | Description | Example |
|----------|-------------|---------|
| `https://api.svgl.app?search={query}` | Search logos by name | `?search=vercel` |
| `https://api.svgl.app?limit={n}` | Get all logos with limit | `?limit=10` |
| `https://api.svgl.app/category/{name}` | Get logos by category | `/category/software` |
| `https://api.svgl.app/categories` | List all categories | — |

## Handling Light/Dark Variants

Many logos have separate light and dark versions. Check the `route` field type:

```bash
# Search result with theme variants:
# { "title": "React", "route": { "light": "...react_light.svg", "dark": "...react_dark.svg" } }

# For dark backgrounds → use the dark variant
curl -s "https://svgl.app/library/react_dark.svg"

# For light backgrounds → use the light variant
curl -s "https://svgl.app/library/react_light.svg"
```

**When unsure which variant to use:** default to the `light` variant, or check the target frame's background color.

## Wordmarks

Some logos also have wordmark versions (logo with text). These are in the `wordmark` field:

```json
{
  "title": "React",
  "route": { "light": "...react_light.svg", "dark": "...react_dark.svg" },
  "wordmark": { "light": "...react-wordmark-light.svg", "dark": "...react-wordmark-dark.svg" }
}
```

Use the `wordmark` URL when the user requests a logo with text or a full brand mark.

## Recoloring After Insertion

If you need to change the logo color after inserting into Figma, traverse the node's children and update fills:

```js
const logoNode = figma.getNodeById("LOGO_NODE_ID");

function recolor(node, color) {
  if ("fills" in node && node.fills.length > 0) {
    node.fills = [{ type: 'SOLID', color }];
  }
  if ("strokes" in node && node.strokes.length > 0) {
    node.strokes = [{ type: 'SOLID', color }];
  }
  if ("children" in node) {
    for (const child of node.children) {
      recolor(child, color);
    }
  }
}

// Color values are 0-1 range (not 0-255)
recolor(logoNode, { r: 1, g: 1, b: 1 });

return { mutatedNodeIds: [logoNode.id] };
```

## Handling Errors

- **Empty search results:** If `curl -s "https://api.svgl.app?search={name}"` returns `[]`, the logo is not in SVGL. Try alternative names or check spelling.
- **404 from SVG URL:** The `route` URL is broken or outdated. Re-search to get the latest URL.
- **`figma.createNodeFromSvg()` fails:** Strip the `<?xml ...?>` declaration from the SVG string and retry. Some SVGL SVGs include XML preambles that can cause issues.

## Constraints

1. **NEVER draw logos manually** with vector paths, shapes, or text when the logo is available on SVGL.
2. **NEVER use `fetch()` inside `use_figma`** — it does not exist in the Figma Plugin API sandbox. Always fetch SVG via `Bash(curl -s ...)` before the `use_figma` call.
3. **Always load the `figma-use` skill** before making any `use_figma` tool call.
4. **Always return created node IDs** from `use_figma` calls for subsequent operations.
5. **Name logo nodes as `SVGL/{LogoName}`** (e.g., `SVGL/React`, `SVGL/Vercel`, `SVGL/GitHub`). This makes logos identifiable by their source in the Figma layers panel.
6. **Respect light/dark variants** — choose the appropriate variant based on the design's background color.
7. **SVG may contain `<?xml ...?>` declaration** — `figma.createNodeFromSvg()` handles this, but if it fails, strip the XML declaration before passing to Figma.
8. **NEVER force-resize to a square.** Always preserve the original SVG aspect ratio. Calculate proportional width/height from `node.width` and `node.height` after `createNodeFromSvg()`, then resize with `node.resize(targetHeight * (node.width / node.height), targetHeight)`.
