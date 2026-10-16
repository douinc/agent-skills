#!/usr/bin/env python3
"""HyperFrames 자막을 한국어 구절 단위로 다시 묶는다.

HyperFrames `captions.mjs`는 0.18초 쉼과 2–4단어 상한으로 자막을 나눈다. 한국어에서는
"주식회사 / 도우입니다."나 "그리고 그 / 서비스를"처럼 구절 중간이 끊긴다. 이 스크립트는
`captions.mjs build` 뒤에 실행해 `caption_groups.json`과 `compositions/captions.html`의
`var GROUPS = [...]`를 다시 쓴다. 단어 시각은 건드리지 않는다.

구절 경계:
  1. SCRIPT.md 원고에 ` / `가 있으면 그 자리에서 나눈다(가장 확실하다).
  2. 없으면 문장부호(. , ? ! …) 뒤에서 나누고, 한 묶음이 --max-words 어절을 넘지 않게 한다.
     한 글자 어절("그", "더")은 다음 어절과 붙여 줄 끝에 홀로 남지 않게 한다.

예:
  python3 ko_captions.py --project .
  python3 ko_captions.py --project . --max-words 3 --dry-run
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from openrouter_media import forms, norm, parse_script  # noqa: E402

TAIL = 0.12  # 마지막 단어 뒤에 남겨 두는 초
END_PUNCT = re.compile(r"[.,?!…·:;]$")


def phrases_for(raw, max_words):
    if " / " in f" {raw} ":
        return [forms(part)[0] for part in re.split(r"\s+/\s+", raw) if forms(part)[0]]
    # 문장부호로 먼저 자르고, 긴 조각은 고르게 나눈다(앞에서부터 채우면 끝 어절이 홀로 남는다)
    segments, cur = [], []
    for tok in forms(raw)[0]:
        cur.append(tok)
        if END_PUNCT.search(tok):
            segments.append(cur)
            cur = []
    if cur:
        segments.append(cur)
    out = []
    for seg in segments:
        parts = -(-len(seg) // max_words)
        size = -(-len(seg) // parts)
        chunks = [seg[k:k + size] for k in range(0, len(seg), size)]
        for c in range(len(chunks) - 1):  # 한 글자 어절("그")이 줄 끝에 남으면 다음 묶음으로 넘긴다
            while len(chunks[c]) > 1 and len(norm(chunks[c][-1])) <= 1:
                chunks[c + 1].insert(0, chunks[c].pop())
        out.extend(chunks)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=".")
    ap.add_argument("--script", help="기본: <project>/SCRIPT.md")
    ap.add_argument("--max-words", type=int, default=4, help="` / `가 없을 때 한 묶음의 최대 어절 수(기본 4)")
    ap.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 결과만 보여 준다")
    a = ap.parse_args()

    root = Path(a.project)
    cg_path, html_path = root / "caption_groups.json", root / "compositions" / "captions.html"
    cg = json.loads(cg_path.read_text())
    words = [dict(w, frame=g["frame"]) for g in cg["groups"] for w in g["words"]]
    _, lines = parse_script((Path(a.script) if a.script else root / "SCRIPT.md").read_text())

    groups, i = [], 0
    for ln in lines:
        for ph in phrases_for(ln["text"], a.max_words):
            chunk = words[i:i + len(ph)]
            got = [w["text"] for w in chunk]
            if [norm(t) for t in got] != [norm(t) for t in ph] or any(w["frame"] != ln["frame"] for w in chunk):
                sys.exit(f"frame {ln['frame']}: 원고 구절 {ph}와 자막 단어 {got}가 맞지 않는다. "
                         "SCRIPT.md와 audio_meta.json이 같은 원고에서 나왔는지 확인한다(tts를 다시 돌린 뒤 captions build).")
            groups.append((ln["frame"], chunk))
            i += len(ph)
    if i != len(words):
        sys.exit(f"자막 단어 {len(words) - i}개가 원고에 없다: {[w['text'] for w in words[i:i + 8]]}")

    out = []
    for gi, (frame, chunk) in enumerate(groups):
        end = round(chunk[-1]["end"] + TAIL, 3)
        if gi + 1 < len(groups):
            end = min(end, groups[gi + 1][1][0]["start"])
        out.append({
            "id": f"caption-group-{gi}", "frame": frame, "start": chunk[0]["start"], "end": end,
            "text": " ".join(w["text"] for w in chunk),
            "words": [{"id": f"caption-word-{gi}-{wi}", "text": w["text"], "start": w["start"], "end": w["end"]}
                      for wi, w in enumerate(chunk)],
        })
    for g in out:
        print(f"{g['start']:6.2f}–{g['end']:6.2f}  {g['text']}")
    if a.dry_run:
        return

    html = html_path.read_text()
    literal = "var GROUPS = " + json.dumps(out, ensure_ascii=False).replace("<", "\\u003c") + ";"
    html, n = re.subn(r"var GROUPS = \[.*?\];\n", lambda m: literal + "\n", html, count=1, flags=re.S)
    if n != 1:
        sys.exit(f"{html_path}에서 `var GROUPS = [...];` 줄을 찾지 못했다. HyperFrames 자막 형식이 바뀌었을 수 있다.")
    cg["groups"] = out
    cg_path.write_text(json.dumps(cg, ensure_ascii=False, indent=2))
    html_path.write_text(html)
    print(f"✓ {len(out)}개 묶음으로 다시 썼다: {cg_path.name}, {html_path.relative_to(root)}")


if __name__ == "__main__":
    main()
