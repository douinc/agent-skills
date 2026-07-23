#!/usr/bin/env python3
"""매뉴얼 이미지에 빨간 표시(네모 박스 · 번호 배지)를 그린다.

좌표는 이미지 크기에 대한 비율(0~1)로 준다 — 캡처를 다시 뽑아 해상도가 바뀌어도
같은 값을 그대로 쓸 수 있다.

사용:
  python3 annotate.py <출력.png> <원본.png> x,y,w,h [x,y,w,h ...]
  python3 annotate.py <출력.png> <원본.png> --num x,y,w,h x,y,w,h   # 박스마다 1,2,3 배지

예: 위쪽 줄 서식 선택 상자에 박스
  python3 annotate.py out.png img-live/live-07-template-select.png 0.28,0.09,0.42,0.06
"""
import sys
from PIL import Image, ImageDraw, ImageFont

RED = (232, 43, 47)
RADIUS_RATIO = 0.014  # 이미지 폭 대비 모서리 반경
MARGIN_RATIO = 0.014  # 대상과 선 사이 여백 — 박스가 UI에 달라붙지 않게 바깥으로 넓힌다
STROKE_RATIO = 0.008  # 이미지 폭 대비 선 두께


def font(size: int):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def annotate(src: str, dst: str, boxes: list[tuple[float, float, float, float]], numbered: bool) -> None:
    im = Image.open(src).convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im)
    stroke = max(3, round(W * STROKE_RATIO))
    radius = max(6, round(W * RADIUS_RATIO))

    m = round(W * MARGIN_RATIO)
    for i, (x, y, w, h) in enumerate(boxes, 1):
        px = (round(x * W) - m, round(y * H) - m, round((x + w) * W) + m, round((y + h) * H) + m)
        d.rounded_rectangle(px, radius=radius, outline=RED, width=stroke)
        if numbered:
            r = max(14, round(W * 0.035))
            cx, cy = px[0], px[1]  # 박스 좌상단에 배지
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=RED)
            f = font(int(r * 1.3))
            t = str(i)
            tb = d.textbbox((0, 0), t, font=f)
            d.text((cx - (tb[2] - tb[0]) / 2, cy - (tb[3] - tb[1]) / 2 - tb[1]), t, font=f, fill="white")

    im.save(dst)
    print(f"{dst}  박스 {len(boxes)}개")


if __name__ == "__main__":
    args = sys.argv[1:]
    numbered = "--num" in args
    args = [a for a in args if a != "--num"]
    dst, src, *coords = args
    boxes = [tuple(float(v) for v in c.split(",")) for c in coords]
    annotate(src, dst, boxes, numbered)
