---
name: figma-icons-iconify
description: Use when working with Figma and UI icons are needed — triggers on icon names, icon libraries (Tabler, Lucide, Material Design, Phosphor, Heroicons), or requests to add/insert icons in Figma designs.
metadata:
  author: initred
  email: initred@gmail.com
  version: "1.0.0"
---

# Iconify Icons for Figma

Fetch real, pixel-perfect SVG icons from the [Iconify API](https://iconify.design/) and insert them into Figma designs. **Never draw icons manually with vector paths** — always use this workflow to get accurate icons from 150+ icon sets including Tabler, Lucide, Material Design, and more.

## Prerequisites

- The `figma-use` skill **MUST** be loaded before any `use_figma` tool call. Always invoke it first.
- `fetch()` is **NOT available** inside `use_figma` code. All HTTP requests must happen **before** calling `use_figma`.
- **Use `Bash(curl -s ...)` instead of `WebFetch`** to call the Iconify API. The Iconify API returns 403 for WebFetch requests but works with curl.

## Core Workflow

### Step 1: Fetch SVG via curl

Use the `Bash` tool with `curl -s` to retrieve the SVG from the Iconify API:

```bash
curl -s "https://api.iconify.design/{prefix}/{name}.svg"
```

**Example:**
```bash
curl -s "https://api.iconify.design/tabler/alert-circle.svg"
```

This returns a raw SVG string ready for Figma insertion.

> **Why curl?** The Iconify API returns HTTP 403 for `WebFetch` requests. Always use `Bash(curl -s ...)` instead.

### Step 2: Insert into Figma via use_figma

Pass the fetched SVG string into a `use_figma` call using `figma.createNodeFromSvg()`:

```js
// Paste the exact SVG string from Step 1
const svgString = `<svg xmlns="http://www.w3.org/2000/svg" ...>...</svg>`;

const node = figma.createNodeFromSvg(svgString);
// Name format: {LibraryName}/{icon-name} for easy identification
node.name = "Tabler/alert-circle";

// Resize while preserving aspect ratio.
// Most Iconify icons are square (24x24), but some are not — always check.
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

**Important:** `figma.createNodeFromSvg()` returns a `FrameNode` containing the vector paths. You can resize, rename, reposition, and reparent it like any other frame.

## URL Parameters

Customize the fetched SVG by appending query parameters:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `color` | Set icon color (URL-encode `#`) | `?color=%23ff0000` |
| `width` | Icon width in pixels | `?width=32` |
| `height` | Icon height in pixels | `?height=32` |
| `flip` | Flip direction | `?flip=horizontal` |
| `rotate` | Rotation angle | `?rotate=90deg` |

**Example with parameters:**
```
https://api.iconify.design/tabler/alert-circle.svg?width=24&height=24&color=%230f172a
```

## Searching for Icons

When the user does not specify an exact icon name, search using the Iconify search endpoint:

```bash
curl -s "https://api.iconify.design/search?query={term}&prefixes={prefix}&limit=10"
```

**Example:**
```bash
curl -s "https://api.iconify.design/search?query=alert&prefixes=tabler&limit=10"
```

This returns JSON with matching icon names:
```json
{
  "icons": ["tabler:alert-circle", "tabler:alert-triangle", "tabler:alert-octagon"],
  "total": 15
}
```

Pick the best match and proceed with Step 1 and Step 2 of the core workflow.

## Batch Icons (Multiple at Once)

When inserting multiple icons, use the JSON endpoint to fetch them all in one request:

```bash
curl -s "https://api.iconify.design/{prefix}.json?icons={name1},{name2},{name3}"
```

**Example:**
```bash
curl -s "https://api.iconify.design/tabler.json?icons=alert-circle,home,settings"
```

This returns structured data:
```json
{
  "prefix": "tabler",
  "icons": {
    "alert-circle": {
      "body": "<path d=\"...\"/>",
      "width": 24,
      "height": 24
    }
  }
}
```

To use each icon, extract the data and wrap the `body` in an SVG element:
```js
// Extract icon data from the JSON response
const icon = response.icons["alert-circle"];
const { body } = icon;
const width = icon.width || 24;
const height = icon.height || 24;

const svgString = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
const node = figma.createNodeFromSvg(svgString);
```

**Note:** Check the icon set's default attributes. Tabler icons use `stroke="currentColor" stroke-width="2"`. Material Design icons use `fill="currentColor"`. Match the icon set's style when wrapping the body.

## Common Icon Set Prefixes

| Prefix | Icon Set | Style | Default Attributes |
|--------|----------|-------|-------------------|
| `tabler` | Tabler Icons | Stroke | `stroke="currentColor" stroke-width="2"` |
| `lucide` | Lucide | Stroke | `stroke="currentColor" stroke-width="2"` |
| `mdi` | Material Design Icons | Fill | `fill="currentColor"` |
| `ph` | Phosphor Icons | Stroke/Fill | varies by weight |
| `ri` | Remix Icon | Fill | `fill="currentColor"` |
| `heroicons` | Heroicons | Stroke | `stroke="currentColor" stroke-width="1.5"` |
| `solar` | Solar Icons | Stroke/Fill | varies by style |
| `iconamoon` | IconaMoon | Stroke | `stroke="currentColor"` |

## Recoloring After Insertion

If you need to change the icon color after inserting into Figma, traverse the node's children and update fills or strokes:

```js
const iconNode = figma.getNodeById("ICON_NODE_ID");

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
recolor(iconNode, { r: 0.09, g: 0.09, b: 0.09 });

return { mutatedNodeIds: [iconNode.id] };
```

## Handling Errors

- **Empty search results:** If the search returns no icons, try broader search terms or check the icon set prefix spelling.
- **404 from SVG endpoint:** The icon name is wrong or doesn't exist in that prefix. Verify with the search endpoint first.
- **Malformed SVG / `figma.createNodeFromSvg()` fails:** Some SVGs may contain unsupported features. Try fetching with explicit `?width=24&height=24` parameters, or use the JSON endpoint and wrap the `body` manually.

## Constraints

1. **NEVER draw icons manually** with vector paths, ellipses, or rectangles when the icon is available on Iconify.
2. **NEVER use `fetch()` inside `use_figma`** — it does not exist in the Figma Plugin API sandbox. Always fetch SVG via `Bash(curl -s ...)` before the `use_figma` call. Do NOT use `WebFetch` — the Iconify API returns 403 for it.
3. **Always load the `figma-use` skill** before making any `use_figma` tool call.
4. **Always return created node IDs** from `use_figma` calls for subsequent operations.
5. **Match icon set attributes** when wrapping JSON body in SVG — stroke-based sets (Tabler, Lucide) need stroke attributes, fill-based sets (MDI, Remix) need fill attributes.
6. **Name icon nodes as `{LibraryName}/{icon-name}`** (e.g., `Tabler/alert-circle`, `Lucide/home`, `MDI/settings`). This makes icons identifiable by their source library in the Figma layers panel.
7. **Preserve aspect ratio when resizing.** Most Iconify icons are square (24x24), but not all. Always calculate proportional dimensions from `node.width` and `node.height` after `createNodeFromSvg()`.
