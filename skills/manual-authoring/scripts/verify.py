#!/usr/bin/env python3
"""Render specific PDF pages to PNG so the author can eyeball them.

The whole point of this skill is the render→look→fix loop: you cannot trust
that a manual page is correct until you have *seen* it. After every change,
render the affected pages and actually read the PNGs (open them / attach them),
looking specifically for: text or images cropped at the page bottom, phone
mockups clipped left/right, and the running header cut off at the top.

Usage:
    verify.py <pdf> <page[,page...]>   e.g.  verify.py manual.pdf 8,9,14
    verify.py <pdf> all                 renders every page
Outputs /tmp/verify_p<N>.png for each requested page and prints the paths.

macOS only — uses Quartz (pyobjc). Install once with:
    python3 -m pip install pyobjc-framework-Quartz
"""
import sys

try:
    import Quartz
    import CoreFoundation
except ImportError:
    sys.exit("Quartz not installed. Run: python3 -m pip install pyobjc-framework-Quartz")


def _url(path):
    b = path.encode()
    return CoreFoundation.CFURLCreateFromFileSystemRepresentation(None, b, len(b), False)


def render(pdf_path, pages, scale=1.3):
    doc = Quartz.CGPDFDocumentCreateWithURL(_url(pdf_path))
    if doc is None:
        sys.exit(f"could not open {pdf_path}")
    n = Quartz.CGPDFDocumentGetNumberOfPages(doc)
    if pages == "all":
        idxs = range(1, n + 1)
    else:
        idxs = [int(x) for x in pages.split(",")]
    out = []
    for i in idxs:
        if i < 1 or i > n:
            print(f"skip page {i} (doc has {n})")
            continue
        pg = Quartz.CGPDFDocumentGetPage(doc, i)
        r = Quartz.CGPDFPageGetBoxRect(pg, Quartz.kCGPDFMediaBox)
        w, h = int(r.size.width * scale), int(r.size.height * scale)
        ctx = Quartz.CGBitmapContextCreate(
            None, w, h, 8, 0,
            Quartz.CGColorSpaceCreateDeviceRGB(),
            Quartz.kCGImageAlphaNoneSkipFirst,
        )
        Quartz.CGContextSetRGBFillColor(ctx, 1, 1, 1, 1)
        Quartz.CGContextFillRect(ctx, Quartz.CGRectMake(0, 0, w, h))
        Quartz.CGContextScaleCTM(ctx, scale, scale)
        Quartz.CGContextDrawPDFPage(ctx, pg)
        img = Quartz.CGBitmapContextCreateImage(ctx)
        op = f"/tmp/verify_p{i}.png"
        dst = Quartz.CGImageDestinationCreateWithURL(_url(op), "public.png", 1, None)
        Quartz.CGImageDestinationAddImage(dst, img, None)
        Quartz.CGImageDestinationFinalize(dst)
        out.append(op)
        print(op)
    print(f"({n} pages total)")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    render(sys.argv[1], sys.argv[2])
