#!/usr/bin/env python3
"""ko-natural lint — LLM 한국어의 번역투/GPT체/형태 시그니처를 탐지한다.

사용:
    python lint.py TEXT_FILE [--register casual|formal|all] [--json] [--max-sentence N]
    echo "텍스트" | python lint.py - --register casual

exit code: error 1건 이상이면 1, 아니면 0. (warn만 있으면 0)
패턴 사전: ../references/patterns.json (성장형 — 새 실패 사례는 여기에 추가)
표준 라이브러리만 사용.
"""
import argparse
import json
import re
import sys
from pathlib import Path

PATTERNS_PATH = Path(__file__).resolve().parent.parent / "references" / "patterns.json"

# ---------- 패턴 사전 기반 검사 ----------

def load_patterns():
    with open(PATTERNS_PATH, encoding="utf-8") as f:
        return json.load(f)["patterns"]


def applicable(p, register, lexicon="normal"):
    if p["register"] == "easy":          # easy 어휘 패턴은 --lexicon easy일 때만
        return lexicon == "easy"
    return register == "all" or p["register"] in ("all", register)


def check_patterns(text, patterns, register, lexicon="normal"):
    findings = []
    n_chars = max(len(text), 1)
    for p in patterns:
        if not applicable(p, register, lexicon):
            continue
        flags = re.MULTILINE
        matches = list(re.finditer(p["regex"], text, flags))
        if not matches:
            continue
        if p["type"] == "frequency":
            per_1000 = len(matches) * 1000 / n_chars
            if per_1000 <= p["max_per_1000"]:
                continue
            findings.append({
                "id": p["id"], "severity": p["severity"], "category": p["category"],
                "message": f'{p["message"]} — {len(matches)}회 (허용 {p["max_per_1000"]}/1000자)',
                "fix": p["fix"],
                "samples": [m.group(0).strip() for m in matches[:3]],
            })
        else:
            for m in matches:
                line_no = text.count("\n", 0, m.start()) + 1
                findings.append({
                    "id": p["id"], "severity": p["severity"], "category": p["category"],
                    "line": line_no, "match": m.group(0).strip(),
                    "message": p["message"], "fix": p["fix"],
                })
    return findings

# ---------- 코드 레벨 검사 ----------

SENT_SPLIT = re.compile(r"(?<=[.!?다요음됨])\s+|\n+")


def split_sentences(text):
    # 마크다운 표·헤더·코드 라인은 제외
    lines = [l for l in text.splitlines() if not re.match(r"\s*([|#>`\-*]|\d+\.)", l)]
    sents = []
    for chunk in re.split(r"[.!?\n]+", " ".join(lines)):
        s = chunk.strip()
        if len(s) >= 4:
            sents.append(s)
    return sents


def ending_style(sentence):
    s = sentence.rstrip(".!?  ")
    if s.endswith("니다"):  # 습니다/ㅂ니다/입니다 모두 '니다'로 끝남 (음절 융합 대응)
        return "합니다체"
    if re.search(r"(어요|아요|해요|예요|에요|이에요|세요|까요|네요|어요)$", s) or s.endswith("요"):
        return "해요체"
    if s.endswith("다"):
        return "다체"
    if re.search(r"(음|됨|함|기)$", s):
        return "명사형"
    return None


def check_ending_consistency(text):
    styles = {}
    for s in split_sentences(text):
        st = ending_style(s)
        if st:
            styles.setdefault(st, []).append(s[-12:])
    findings = []
    present = [k for k in styles if k != "명사형"]
    if "합니다체" in styles and "해요체" in styles:
        findings.append({
            "id": "M02", "severity": "error", "category": "형태",
            "message": f"종결어미 혼용: 합니다체 {len(styles['합니다체'])}문장 + 해요체 {len(styles['해요체'])}문장",
            "fix": "텍스트 타입에 맞는 하나의 문체로 통일",
            "samples": [styles["합니다체"][0], styles["해요체"][0]],
        })
    elif len(present) >= 2:
        counts = ", ".join(f"{k} {len(v)}" for k, v in styles.items() if k != "명사형")
        findings.append({
            "id": "M02", "severity": "warn", "category": "형태",
            "message": f"종결어미 혼용 가능성: {counts}",
            "fix": "의도된 혼용(인용 등)이 아니면 통일",
        })
    return findings


SENTENCE_STYLES = ("합니다체", "해요체", "다체")


def check_tone(text, tone):
    """지정 어투와 다른 종결어미를 error로 지적한다. 명사형은 문장 어투 지정 시 중립으로 허용."""
    violations = []
    for s in split_sentences(text):
        st = ending_style(s)
        if st is None:
            continue
        if tone == "명사형":
            if st in SENTENCE_STYLES:
                violations.append((st, s[-15:]))
        elif st in SENTENCE_STYLES and st != tone:
            violations.append((st, s[-15:]))
    if not violations:
        return []
    return [{
        "id": "M06", "severity": "error", "category": "형태",
        "message": f"지정 어투({tone}) 위반 {len(violations)}문장: " + ", ".join(f"{st}「…{tail}」" for st, tail in violations[:3]),
        "fix": f"모든 문장을 {tone}로 통일",
    }]


def check_sentence_length(text, max_len):
    findings = []
    for s in split_sentences(text):
        if len(s) > max_len:
            findings.append({
                "id": "M03", "severity": "warn", "category": "형태",
                "message": f"긴 문장 ({len(s)}자 > {max_len}자)",
                "fix": "문장 분리 — 문장당 정보 하나",
                "match": s[:40] + "…",
            })
    return findings


def check_line_length(text, max_len):
    """요약·카드처럼 '줄' 단위 제약이 있는 타입용. --max-line 지정 시만 동작."""
    findings = []
    for i, l in enumerate(text.splitlines(), 1):
        if len(l.strip()) > max_len:
            findings.append({
                "id": "M07", "severity": "error", "category": "형태", "line": i,
                "message": f"줄 길이 초과 ({len(l.strip())}자 > {max_len}자)",
                "fix": "정보 우선순위를 정해 줄이기 — 수동 글자수 세기 대신 이 검사를 재실행",
                "match": l.strip()[:40] + "…",
            })
    return findings

# ---------- 메인 ----------

def lint(text, register="all", max_sentence=80, tone=None, lexicon="normal", max_line=None):
    if lexicon == "easy":
        max_sentence = min(max_sentence, 60)  # 쉬운 글은 문장도 짧게
    findings = check_patterns(text, load_patterns(), register, lexicon)
    findings += check_tone(text, tone) if tone else check_ending_consistency(text)
    findings += check_sentence_length(text, max_sentence)
    if max_line:
        findings += check_line_length(text, max_line)
    errors = [f for f in findings if f["severity"] == "error"]
    warns = [f for f in findings if f["severity"] == "warn"]
    return {"errors": len(errors), "warns": len(warns), "findings": findings}


def main():
    ap = argparse.ArgumentParser(description="ko-natural lint")
    ap.add_argument("file", help="검사할 텍스트 파일 ('-' = stdin)")
    ap.add_argument("--register", default="all", choices=["casual", "formal", "all"])
    ap.add_argument("--tone", default=None, choices=["해요체", "합니다체", "다체", "명사형"],
                    help="지정 시 다른 어투를 error로 지적")
    ap.add_argument("--lexicon", default="normal", choices=["easy", "normal", "expert"],
                    help="easy: 쉬운 어휘 사전 활성화 + 문장 60자 제한")
    ap.add_argument("--json", action="store_true", help="JSON 출력 (채점·자동화용)")
    ap.add_argument("--max-sentence", type=int, default=80)
    ap.add_argument("--max-line", type=int, default=None,
                    help="줄 단위 글자수 제한 (요약 45, 카드 20 등). 초과 시 error")
    args = ap.parse_args()

    text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    result = lint(text, args.register, args.max_sentence, args.tone, args.lexicon, args.max_line)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for f in result["findings"]:
            loc = f":{f['line']}" if "line" in f else ""
            match = f" 「{f['match']}」" if "match" in f else ""
            print(f"[{f['severity'].upper()}] {f['id']}{loc}{match} {f['message']}")
            print(f"        → {f['fix']}")
        print(f"\n오류 {result['errors']} / 경고 {result['warns']}")
    sys.exit(1 if result["errors"] else 0)


if __name__ == "__main__":
    main()
