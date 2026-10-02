#!/usr/bin/env python3
"""ko-natural lint — LLM 한국어의 번역투/GPT체/형태 시그니처를 탐지한다.

사용:
    python3 lint.py TEXT_FILE --type push                 # 타입 기본값(레지스터·어투·줄 길이) 자동 적용
    python3 lint.py TEXT_FILE --profile retriever-push    # 명명 프로필(타입+축)
    python3 lint.py TEXT_FILE --register casual --tone 해요체 --max-line 45   # 직접 지정(타입 기본값보다 우선)
    echo "텍스트" | python3 lint.py - --type summary
    python3 lint.py --selftest                            # 사전의 모든 패턴을 hit/miss 예문으로 검증

exit code: error 1건 이상이면 1, 아니면 0. (warn만 있으면 0)
패턴 사전: ../references/patterns.json (성장형 — 새 실패 사례는 예문과 함께 여기에 추가)
타입 기본값·프로필: ../references/profiles.json
표준 라이브러리만 사용.
"""
import argparse
import json
import re
import sys
from pathlib import Path

REF = Path(__file__).resolve().parent.parent / "references"
PATTERNS_PATH = REF / "patterns.json"
PROFILES_PATH = REF / "profiles.json"

# ---------- 패턴 사전 기반 검사 ----------

def load_patterns():
    with open(PATTERNS_PATH, encoding="utf-8") as f:
        return json.load(f)["patterns"]


def applicable(p, register, lexicon="normal"):
    if p["register"] == "easy":          # easy 어휘 패턴은 --lexicon easy일 때만
        return lexicon == "easy"
    return register == "all" or p["register"] in ("all", register)


def count_matches(p, text):
    return len(list(re.finditer(p["regex"], text, re.MULTILINE)))


def check_patterns(text, patterns, register, lexicon="normal"):
    findings = []
    n_chars = max(len(text), 1)
    for p in patterns:
        if not applicable(p, register, lexicon):
            continue
        matches = list(re.finditer(p["regex"], text, re.MULTILINE))
        if not matches:
            continue
        if p["type"] == "frequency":
            # 짧은 글에서 1회 출현만으로 밀도가 치솟는 것을 막기 위해 min_count 이상일 때만 본다
            per_1000 = len(matches) * 1000 / n_chars
            if len(matches) < p.get("min_count", 1) or per_1000 <= p["max_per_1000"]:
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


def selftest(patterns):
    """패턴마다 tests.hit는 걸리고 tests.miss는 안 걸리는지 확인한다. 실패 목록을 돌려준다."""
    fails = []
    for p in patterns:
        tests = p.get("tests")
        if not tests or not tests.get("hit"):
            fails.append(f"{p['id']}: tests.hit 예문 없음")
            continue
        need = p.get("min_count", 1) if p["type"] == "frequency" else 1
        for s in tests.get("hit", []):
            if count_matches(p, s) < need:
                fails.append(f"{p['id']} 놓침: {s}")
        for s in tests.get("miss", []):
            if count_matches(p, s) >= need:
                fails.append(f"{p['id']} 오탐: {s}")
    return fails

# ---------- 코드 레벨 검사 ----------

SKIP_LINE = re.compile(r"\s*(?:[|#>]|```)")          # 표·헤더·인용·코드 펜스
BULLET = re.compile(r"^\s*(?:[-*•·]|\d+[.)])\s+")     # 글머리표는 기호만 떼고 문장으로 검사
SENT_END = re.compile(r"[.!?]+(?![\d”\"’'」』])")    # 3.5배·v1.2, 인용 안 물음표(“…있나요?”라고)에서는 자르지 않음
GREETINGS = ("안녕하세요",)                            # 문체 판정에서 제외하는 고정 인사말
REQUEST = re.compile(r"세요$")                        # '~해 주세요'·'~확인하세요' — 합니다체 글에서도 자연스러운 요청형


def split_sentences(text):
    sents = []
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or SKIP_LINE.match(line):
            continue
        line = BULLET.sub("", line)
        for chunk in SENT_END.split(line):
            s = chunk.strip()
            if len(s) >= 4:
                sents.append(s)
    return sents


def core(sentence):
    return sentence.rstrip(".!?…~ \"'”’)」』")


def ending_style(sentence):
    s = core(sentence)
    if s in GREETINGS:
        return None
    if re.search(r"(니다|니까|십시오)$", s):  # 습니다/ㅂ니다/입니다/습니까/하십시오
        return "합니다체"
    if re.search(r"(요|죠)$", s):
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
            if tone == "합니다체" and REQUEST.search(core(s)):
                continue  # 합니다체 공지·메일의 '문의해 주세요'는 자연스럽다('~해 주십시오'가 오히려 딱딱함)
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


VERB_FINAL = set("다요죠까오네지자라게래야든데걸군니대나")


def _verb_final(ch):
    """문장 종결로 볼 수 있는 마지막 음절인가. 받침 없는 ㅏ·ㅐ·ㅓ·ㅕ·ㅘ·ㅙ·ㅝ는 반말 해체 어미(봐·해·어려워·돼)로 본다."""
    if ch in VERB_FINAL:
        return True
    idx = ord(ch) - 0xAC00
    if not 0 <= idx < 11172:
        return True  # 한글 음절이 아니면 판단하지 않음
    jung, jong = (idx // 28) % 21, idx % 28
    return jong == 0 and jung in (0, 1, 4, 6, 9, 10, 14)


NOUN_PERIOD = re.compile(r"([가-힣])\.(?=\s|$)")


def check_noun_period(text):
    """앱 카피·요약에서 명사구·명사형에 마침표를 찍은 전보문('이동.', '끝.', '똑똑함.')을 찾는다."""
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if SKIP_LINE.match(line):
            continue
        for m in NOUN_PERIOD.finditer(line):
            if not _verb_final(m.group(1)):
                hits.append((i, line[max(0, m.start() - 10):m.end()]))
    if not hits:
        return []
    return [{
        "id": "M08", "severity": "warn", "category": "형태", "line": hits[0][0],
        "message": f"명사구·명사형 + 마침표 {len(hits)}곳 — 전보문처럼 읽힘: " + ", ".join(f"「…{h}」" for _, h in hits[:3]),
        "fix": "완결된 문장으로 쓰거나('이동해요', '이동한다'), UI 라벨이면 마침표를 뺀다",
    }]


def check_line_length(text, max_len):
    """요약·카드·푸시처럼 '줄' 단위 제약이 있는 타입용. 타입 기본값 또는 --max-line 지정 시 동작."""
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

# 코드 레벨 검사(어투·문장 분리·전보문)의 회귀 예문: (설명, 텍스트, lint 인자, 있어야 할 id, 없어야 할 id)
LONG = "이번 업데이트로 검색 속도가 기존 대비 3.5배 빨라졌고 저장 용량은 2.1GB에서 1.4GB로 줄었으며 동기화 오류도 0.3% 수준으로 낮아져서 대부분의 사용자가 체감할 만큼 개선됐습니다."
CODE_TESTS = [
    ("인사말 '안녕하세요.'는 합니다체 위반이 아니다", "안녕하세요.\n\n개편을 연기합니다.", {"register": "formal", "tone": "합니다체"}, set(), {"M06"}),
    ("합니다체 글의 요청형 '~해 주세요'는 허용", "개편을 연기합니다. 고객센터로 문의해 주세요.", {"register": "formal", "tone": "합니다체"}, set(), {"M06"}),
    ("합니다체 글의 해요체 평서문은 위반", "개편을 연기합니다. 배포되면 메일드릴게요.", {"register": "formal", "tone": "합니다체"}, {"M06"}, set()),
    ("인용 안 물음표에서 문장을 자르지 않는다", "예를 들어 “얼마까지 쓸 수 있나요?”라고 물으면 규정을 찾아 답합니다.", {"register": "formal", "tone": "합니다체"}, set(), {"M06"}),
    ("소수점에서 자르지 않아 긴 문장을 잡는다", LONG, {"register": "formal"}, {"M03"}, set()),
    ("글머리표 줄도 어투를 검사한다", "- 설정을 저장했습니다.\n- 알림을 켰어요.", {"register": "casual", "tone": "해요체"}, {"M06"}, set()),
    ("'~습니까'는 합니다체로 본다", "확인하셨습니까? 지금 열어 보세요.", {"register": "casual", "tone": "해요체"}, {"M06"}, set()),
    ("명사구+마침표 전보문은 경고", "zoxide로 폴더 이동. 설치하면 끝. 첫 며칠은 덜 똑똑함.", {"register": "casual"}, {"M08"}, set()),
    ("완결된 문장·반말·라벨은 전보문 경고 없음", "폴더로 바로 이동해요. 설치하면 끝이다. 좀 어려워.\n저장됨", {"register": "casual"}, set(), {"M08"}),
    ("보고서 개조식 '~함.'은 formal에서 경고하지 않음", "- 배포를 완료함.", {"register": "formal"}, set(), {"M08"}),
]


def code_selftest():
    fails = []
    for desc, text, kw, must, must_not in CODE_TESTS:
        ids = {f["id"] for f in lint(text, **kw)["findings"]}
        if not must <= ids or ids & must_not:
            fails.append(f"코드 검사 실패: {desc} — 검출 {sorted(ids)}")
    return fails

# ---------- 설정 해석 ----------

def resolve_settings(args):
    """우선순위: 명시 플래그 > 프로필 축 > 타입 기본값 > 전역 기본값."""
    cfg = {"register": "all", "tone": None, "lexicon": "normal", "max_line": None, "max_sentence": 80}
    data = json.load(open(PROFILES_PATH, encoding="utf-8"))
    text_type = args.type
    prof = {}
    if args.profile:
        if args.profile not in data["profiles"]:
            sys.exit(f"프로필 없음: {args.profile}. 사용 가능: {', '.join(data['profiles'])}")
        prof = data["profiles"][args.profile]
        text_type = text_type or prof.get("type")
    if text_type:
        cfg.update(data["types"][text_type])
    cfg.update({k: v for k, v in prof.items() if k in ("tone", "lexicon")})
    for k in ("register", "tone", "lexicon", "max_line", "max_sentence"):
        v = getattr(args, k)
        if v is not None:
            cfg[k] = v
    if cfg["lexicon"] == "easy":
        cfg["max_sentence"] = min(cfg["max_sentence"], 60)  # 표시되는 설정이 실제 기준과 같도록
    cfg["type"] = text_type
    return cfg

# ---------- 메인 ----------

def lint(text, register="all", max_sentence=80, tone=None, lexicon="normal", max_line=None):
    if lexicon == "easy":
        max_sentence = min(max_sentence, 60)  # 쉬운 글은 문장도 짧게
    findings = check_patterns(text, load_patterns(), register, lexicon)
    findings += check_tone(text, tone) if tone else check_ending_consistency(text)
    findings += check_sentence_length(text, max_sentence)
    if register == "casual":
        findings += check_noun_period(text)
    if max_line:
        findings += check_line_length(text, max_line)
    errors = [f for f in findings if f["severity"] == "error"]
    warns = [f for f in findings if f["severity"] == "warn"]
    return {"errors": len(errors), "warns": len(warns), "findings": findings}


def main():
    types = list(json.load(open(PROFILES_PATH, encoding="utf-8"))["types"])
    ap = argparse.ArgumentParser(description="ko-natural lint")
    ap.add_argument("file", nargs="?", help="검사할 텍스트 파일 ('-' = stdin)")
    ap.add_argument("--type", default=None, choices=types, help="텍스트 타입 — 레지스터·어투·길이 기본값을 profiles.json에서 적용")
    ap.add_argument("--profile", default=None, help="profiles.json의 명명 프로필")
    ap.add_argument("--register", default=None, choices=["casual", "formal", "all"])
    ap.add_argument("--tone", default=None, choices=["해요체", "합니다체", "다체", "명사형"],
                    help="지정 시 다른 어투를 error로 지적")
    ap.add_argument("--lexicon", default=None, choices=["easy", "normal", "expert"],
                    help="easy: 쉬운 어휘 사전 활성화 + 문장 60자 제한")
    ap.add_argument("--json", action="store_true", help="JSON 출력 (채점·자동화용)")
    ap.add_argument("--max-sentence", type=int, default=None)
    ap.add_argument("--max-line", type=int, default=None,
                    help="줄 단위 글자수 제한 (타입 기본값: summary·push 45, card 20). 초과 시 error")
    ap.add_argument("--selftest", action="store_true", help="패턴 사전·코드 검사 회귀 테스트")
    args = ap.parse_args()

    if args.selftest:
        fails = selftest(load_patterns()) + code_selftest()
        for f in fails:
            print(f"[FAIL] {f}")
        print(f"selftest: 실패 {len(fails)}건")
        sys.exit(1 if fails else 0)
    if not args.file:
        ap.error("검사할 파일이 필요합니다 ('-' = stdin)")

    cfg = resolve_settings(args)
    text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    result = lint(text, cfg["register"], cfg["max_sentence"], cfg["tone"], cfg["lexicon"], cfg["max_line"])
    result["applied"] = cfg

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        applied = ", ".join(f"{k}={v}" for k, v in cfg.items() if v not in (None, "all", "normal"))
        print(f"적용 설정: {applied or '기본값'}")
        for f in result["findings"]:
            loc = f":{f['line']}" if "line" in f else ""
            match = f" 「{f['match']}」" if "match" in f else ""
            print(f"[{f['severity'].upper()}] {f['id']}{loc}{match} {f['message']}")
            print(f"        → {f['fix']}")
        print(f"\n오류 {result['errors']} / 경고 {result['warns']}")
    sys.exit(1 if result["errors"] else 0)


if __name__ == "__main__":
    main()
