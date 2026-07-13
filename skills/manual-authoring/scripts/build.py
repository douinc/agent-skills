#!/usr/bin/env python3
"""Assemble section HTML into one combined document per edition, with continuous
page numbering — the reference build for a multi-part / multi-edition manual.

Why one combined HTML instead of merging separate PDFs: merging PDFs (e.g. with
Quartz CGPDFContext) shifts page content and clips the running header. Rendering a
single HTML that contains every <section class="page"> avoids that. So each
edition (e.g. a general edition and a customer-specific edition) is built by
concatenating the SAME shared section bodies under one <style>, differing only
where they must — a login page with an account table, a cover subtitle, an
edition-only page inserted after the cover, etc.

This file is a REFERENCE you adapt per project, not a fixed CLI. Three pieces
matter and are shown below as functions:

  1. style_and_body()  — pull <style> and <body> out of a per-part source file so
     you can edit a page once and rebuild every edition.
  2. renumber()        — after concatenating, rewrite folios and TOC page numbers
     to the CONTINUOUS physical page position. Read the docstring — this is the
     part people get wrong.
  3. insert_edition_page() — drop an edition-only page (+ its TOC row) in after a
     cover, so one edition can carry pages another doesn't.

Typical driver (mirrors a real build):

    app_style, app_body = style_and_body('part-app.html')
    _,        con_body  = style_and_body('part-console.html')          # general
    wil_style, wil_con  = style_and_body('part-console-customer.html') # w/ acct table
    extra_css = extract_block(wil_style, '/* account table */')

    # general edition: shared bodies as-is
    write_combined('combined-general.html', app_style, app_body, con_body)

    # customer edition: insert a demo/quick-start page after the app cover,
    # and use the console body that carries the account table
    app_body_cust, _ = insert_edition_page(app_body, open('page-demo.html').read(),
                                           toc_label='데모 진행 안내')
    write_combined('combined-customer.html', app_style + extra_css,
                   app_body_cust, wil_con)

Then render each combined HTML with scripts/render.sh and verify with verify.py.
"""
import re
import os
import sys


def style_and_body(path):
    """Return (style, body) extracted from a self-contained section source file."""
    s = open(path).read()
    style = re.search(r"<style>(.*?)</style>", s, re.S).group(1)
    body = re.search(r"<body>(.*?)</body>", s, re.S).group(1)
    return style, body


def insert_edition_page(app_body, page_html, toc_label=None, toc_pg="2"):
    """Insert an edition-only page right after the first cover in app_body.

    Returns (new_body, None). If toc_label is given, also inserts a table-of-
    contents row for it at the top of the cover's TOC. Numbers here are
    placeholders — renumber() fixes them to the real continuous page position, so
    you don't have to hand-count.
    """
    body = app_body
    if toc_label is not None:
        toc_row = (
            '<h4>목차</h4>\n    <div class="toc-group">\n'
            f'      <div class="toc-row"><span class="id">-</span>'
            f'<span>{toc_label}</span><span class="dots"></span>'
            f'<span class="pg">{toc_pg}</span></div>\n    </div>'
        )
        body = body.replace("<h4>목차</h4>", toc_row, 1)
    end_of_cover = body.index("</section>") + len("</section>")
    body = body[:end_of_cover] + "\n" + page_html + body[end_of_cover:]
    return body, None


def renumber(body):
    """Rewrite folios and TOC page numbers to CONTINUOUS physical page position.

    THE PROBLEM this solves: when you concatenate parts that each hardcode their
    own folios (mobile app pages 3-14, web console pages 3-9, each restarting),
    the printed footer number no longer matches where the page actually sits in
    the combined PDF, and any cross-reference like "see 2-6 (page 22)" is wrong.
    Editions also differ (a customer edition with an extra inserted page shifts
    everything after it), so you cannot hardcode a number that's right for both.

    THE FIX: number every <section class="page"> by its physical order.
      - Covers are front matter: counted (they occupy a page) but not stamped
        with a number — they have a .runfoot without a .folio span, so nothing to
        rewrite.
      - Every content page's <span class="folio">N</span> becomes its physical
        index.
      - Each cover's table of contents lists the pages that follow it, contiguously
        — so its <span class="pg">N</span> values become cover_index+1, +2, …

    Run this on the fully assembled body (after insert_edition_page), once per
    edition, so each edition gets numbers correct for its own page count. Any
    cross-reference text you wrote by hand (e.g. "자세히 · 2-6 (22쪽)") should use
    these same physical numbers so it matches the printed footer.
    """
    parts = re.split(r'(<section class="page[^"]*">)', body)
    out = [parts[0]]
    p = 0
    i = 1
    while i < len(parts):
        opentag = parts[i]
        seg = parts[i + 1] if i + 1 < len(parts) else ""
        p += 1
        if "cover" in opentag:
            cnt = [p]

            def repl(m):
                cnt[0] += 1
                return m.group(1) + str(cnt[0]) + m.group(2)

            seg = re.sub(r'(<span class="pg">)\d+(</span>)', repl, seg)
        else:
            seg = re.sub(
                r'(<span class="folio">)\d+(</span>)',
                lambda m: m.group(1) + str(p) + m.group(2),
                seg,
                count=1,
            )
        out += [opentag, seg]
        i += 2
    return "".join(out)


def write_combined(out_path, style, *bodies):
    body = renumber("\n".join(bodies))
    html = (
        '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8" />\n'
        f"<title>{os.path.basename(out_path)}</title>\n<style>{style}</style>\n"
        "</head>\n<body>\n" + body + "\n</body>\n</html>\n"
    )
    open(out_path, "w").write(html)
    print(f"wrote {out_path} ({len(html)} bytes)")


if __name__ == "__main__":
    # Minimal CLI: combine parts sharing the first file's <style>, with folios
    # renumbered continuously.  build.py out.html part1.html [part2.html ...]
    if len(sys.argv) < 3:
        sys.exit("usage: build.py <out.html> <part1.html> [part2.html ...]")
    out = sys.argv[1]
    parts = sys.argv[2:]
    style, _ = style_and_body(parts[0])
    bodies = [style_and_body(p)[1] for p in parts]
    write_combined(out, style, *bodies)
