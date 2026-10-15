#!/usr/bin/env python3
"""렌더된 영상을 브리프 값과 대조한다. 종료 코드 0이 '납품 가능'이다.

ffprobe로 컨테이너·코덱·크기·fps·길이·픽셀 포맷을 읽고, 오디오가 있으면 ffmpeg ebur128로
통합 라우드니스(LUFS)를 잰다. 표준 라이브러리만 쓴다.

예:
  python3 verify_mp4.py renders/video.mp4 --width 1920 --height 1080 --fps 30 --duration 30
  python3 verify_mp4.py renders/video.mp4 --width 1080 --height 1920 --duration 20 --silent
  python3 verify_mp4.py renders/video.mp4 --json
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path):
    r = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ])
    if r.returncode != 0:
        raise SystemExit(f"ffprobe 실패: {r.stderr.strip()}")
    return json.loads(r.stdout)


def faststart(path):
    """moov 상자가 mdat보다 앞에 있으면 True(웹에서 다 받기 전에 재생이 시작된다). MP4가 아니면 None."""
    order = []
    with open(path, "rb") as f:
        while True:
            head = f.read(8)
            if len(head) < 8:
                break
            size, kind = int.from_bytes(head[:4], "big"), head[4:8]
            if 1 < size < 8:  # 깨진 상자
                break
            if size == 1:
                size = int.from_bytes(f.read(8), "big")
                f.seek(size - 16, 1)
            elif size == 0:
                order.append(kind)
                break
            else:
                f.seek(size - 8, 1)
            order.append(kind)
            if kind in (b"moov", b"mdat") and b"moov" in order and b"mdat" in order:
                break
    if b"moov" not in order or b"mdat" not in order:
        return None
    return order.index(b"moov") < order.index(b"mdat")


def loudness(path):
    """통합 라우드니스(LUFS)와 트루 피크(dBTP). 측정 실패 시 None."""
    r = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-",
    ])
    summary = r.stderr.rsplit("Summary:", 1)[-1]
    i = re.search(r"I:\s+(-?[\d.]+|-inf)\s+LUFS", summary)
    p = re.search(r"Peak:\s+(-?[\d.]+|-inf)\s+dBFS", summary)
    to_f = lambda m: None if not m or m.group(1) == "-inf" else float(m.group(1))
    return to_f(i), to_f(p)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--width", type=int)
    ap.add_argument("--height", type=int)
    ap.add_argument("--fps", type=float)
    ap.add_argument("--duration", type=float, help="브리프 길이(초)")
    ap.add_argument("--duration-tolerance", type=float, default=0.25, help="허용 오차(초), 기본 0.25")
    ap.add_argument("--codec", default="h264")
    ap.add_argument("--silent", action="store_true", help="무음 영상: 오디오 트랙이 없어야 통과")
    ap.add_argument("--lufs", type=float, default=-14.0, help="목표 통합 라우드니스, 기본 -14")
    ap.add_argument("--lufs-tolerance", type=float, default=2.0)
    ap.add_argument("--json", action="store_true", help="결과를 JSON으로 출력")
    a = ap.parse_args()

    for tool in ("ffprobe", "ffmpeg"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool}가 PATH에 없다")
    path = Path(a.video)
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"파일이 없거나 비어 있다: {path}")

    info = probe(path)
    v = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
    au = next((s for s in info["streams"] if s.get("codec_type") == "audio"), None)
    if v is None:
        raise SystemExit("비디오 스트림이 없다")

    fps = float(Fraction(v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1"))
    dur = float(info["format"].get("duration") or v.get("duration") or 0)
    facts = {
        "file": str(path),
        "size_mb": round(path.stat().st_size / 1e6, 2),
        "codec": v.get("codec_name"),
        "pix_fmt": v.get("pix_fmt"),
        "width": v.get("width"),
        "height": v.get("height"),
        "fps": round(fps, 3),
        "duration_s": round(dur, 3),
        "audio": au.get("codec_name") if au else None,
    }

    checks = []  # (level, name, ok, detail) — level: error는 납품 차단, warn은 보고

    def check(level, name, ok, detail):
        checks.append({"level": level, "name": name, "ok": bool(ok), "detail": detail})

    check("error", "codec", facts["codec"] == a.codec, f"{facts['codec']} (기대 {a.codec})")
    check("warn", "pix_fmt", facts["pix_fmt"] == "yuv420p",
          f"{facts['pix_fmt']} (yuv420p가 아니면 일부 플레이어·SNS에서 재생이 깨질 수 있다)")
    fs = faststart(path)
    if fs is not None:
        check("warn", "faststart", fs, "moov가 앞에 있음" if fs else
              "moov가 뒤에 있다. 웹 임베드면 ffmpeg -i in.mp4 -c copy -movflags +faststart out.mp4")
    if a.width:
        check("error", "width", facts["width"] == a.width, f"{facts['width']} (기대 {a.width})")
    if a.height:
        check("error", "height", facts["height"] == a.height, f"{facts['height']} (기대 {a.height})")
    if a.fps:
        check("error", "fps", abs(fps - a.fps) < 0.01, f"{facts['fps']} (기대 {a.fps})")
    if a.duration:
        diff = dur - a.duration
        check("error", "duration", abs(diff) <= a.duration_tolerance,
              f"{facts['duration_s']}s (기대 {a.duration}s, 차이 {diff:+.2f}s)")

    if a.silent:
        check("error", "silent", au is None, "오디오 트랙 없음" if au is None else f"오디오 트랙 있음({au.get('codec_name')})")
    elif au is None:
        check("error", "audio", False, "오디오 트랙이 없다 (무음 영상이면 --silent)")
    else:
        lufs, peak = loudness(path)
        facts["lufs_i"], facts["true_peak_db"] = lufs, peak
        if lufs is None:
            check("error", "loudness", False, "통합 라우드니스를 잴 수 없다 (사실상 무음)")
        else:
            check("warn", "loudness", abs(lufs - a.lufs) <= a.lufs_tolerance,
                  f"{lufs} LUFS (목표 {a.lufs}±{a.lufs_tolerance})")
        if peak is not None:
            check("warn", "true_peak", peak <= -1.0, f"{peak} dBFS (−1 이하 권장, 넘으면 클리핑 위험)")

    errors = [c for c in checks if c["level"] == "error" and not c["ok"]]
    result = {"ok": not errors, "facts": facts, "checks": checks}
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("  ".join(f"{k}={val}" for k, val in facts.items()))
        for c in checks:
            mark = "OK  " if c["ok"] else ("FAIL" if c["level"] == "error" else "WARN")
            print(f"[{mark}] {c['name']}: {c['detail']}")
        print("결과: 납품 가능" if result["ok"] else f"결과: 실패 {len(errors)}건")
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
