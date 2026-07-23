#!/usr/bin/env python3
"""창 캡처를 매뉴얼 지면 규격으로 통일한다 — 배경 합성 + 여백 최소화.

데스크탑 창 캡처(macOS Cmd+Shift+4 → Space, 헤드리스 Chrome 캡처 등)는 창 그림자
여백이 두꺼워 창이 이미지 폭의 ~70%밖에 되지 않는다. 그대로 지면에 넣으면 창이 실제보다
훨씬 작아 보이고, 잘린 그림자 때문에 이미지 경계에 옅은 사각형 자국이 생긴다. 그래서:

1. 창 본체의 바운딩 박스를 찾는다(그림자 제외)
   - RGBA(투명 배경) 캡처: 알파 250 이상
   - RGB 캡처: 순백(255,255,255) 영역 — 창 배경이 흰색인 앱 기준
2. 창 + PAD 만큼만 남기고 자른다 → 창이 이미지의 대부분을 차지한다
3. 잘린 그림자 단차가 안 보이도록 가장자리 FEATHER 픽셀을 배경색으로 페이드한다

**BG는 매뉴얼 figure 배경색과 반드시 같게 둔다.** 다르면 지면에서 이미지 경계가
사각형으로 드러난다(실제로 겪은 실패 모드다).

사용: python3 normalize_shot.py <출력.png> <원본.png>
"""
import sys
from PIL import Image

BG = (251, 251, 253)  # #FBFBFD — 매뉴얼의 스크린샷 figure 배경과 동일하게 맞출 것
PAD = 26      # 창 주위 여백(디바이스 픽셀). 그림자를 살짝만 남긴다.
FEATHER = 22  # 가장자리에서 배경색으로 페이드되는 폭


def edge_ramp(w: int, h: int, feather: int) -> Image.Image:
    """가장자리 feather 픽셀이 0 → 255로 올라오는 사각 램프 마스크."""
    mask = Image.new("L", (w, h), 255)
    px = mask.load()
    for i in range(feather):
        v = int(255 * (i + 1) / (feather + 1))
        for x in range(i, w - i):
            px[x, i] = v
            px[x, h - 1 - i] = v
        for y in range(i, h - i):
            px[i, y] = v
            px[w - 1 - i, y] = v
    return mask


def window_box(im: Image.Image):
    """창 본체의 바운딩 박스 — 그림자는 제외한다."""
    alpha = im.getchannel("A")
    if alpha.getextrema()[0] < 255:  # 투명 영역이 있는 캡처
        solid = alpha.point(lambda a: 255 if a >= 250 else 0)
        if solid.getbbox():
            return solid.getbbox()
    rgb = im.convert("RGB")
    white = rgb.point(lambda v: 255 if v >= 254 else 0).convert("L")
    return white.getbbox() or im.getbbox()


def normalize(src: str, dst: str) -> None:
    im = Image.open(src).convert("RGBA")
    box = window_box(im)
    if box is None:
        raise SystemExit(f"{src}: 창을 찾지 못했습니다")
    l, t, r, b = box
    W, H = im.size
    piece = im.crop((max(0, l - PAD), max(0, t - PAD), min(W, r + PAD), min(H, b + PAD)))

    canvas = Image.new("RGB", piece.size, BG)
    canvas.paste(piece, (0, 0), piece)
    flat = Image.new("RGB", piece.size, BG)
    out = Image.composite(canvas, flat, edge_ramp(*piece.size, FEATHER))
    out.save(dst)
    print(f"{dst}  {out.size[0]}x{out.size[1]}  (원본 {W}x{H})")


if __name__ == "__main__":
    normalize(sys.argv[2], sys.argv[1])
