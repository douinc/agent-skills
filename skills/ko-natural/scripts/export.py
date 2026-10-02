#!/usr/bin/env python3
"""외부 LLM 파이프라인용 시스템 프롬프트 블록을 추출한다.

사용:
    python3 export.py --profile retriever-push                  # 명명 프로필 (references/profiles.json)
    python3 export.py --type summary [--tone 다체] [--lexicon expert] [--length 3line]
    python3 export.py --type summary --examples my_examples.md  # 도메인에 맞는 few-shot으로 교체

출력(stdout): 핵심 원칙 + 금칙 목록(사전에서 추출) + 타입 스펙 + 축 스펙 + 해당 타입 few-shot 예시.
제품 파이프라인(gpt-4o-mini급 등)의 시스템 프롬프트에 그대로 삽입한다.
예시는 소형 모델이 규칙보다 강하게 따라 하므로, 콘텐츠 도메인이 다르면 --examples로 같은 도메인 예시를 넣는다.
표준 라이브러리만 사용.
"""
import argparse
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

TYPE_SPECS = {
    "summary": "종결: '~다'체 문장으로 통일. 명사형('~함')·마침표 찍은 명사구는 쓰지 않는다. 줄마다 완결된 문장, 줄당 45자 이내. 메타 문장 금지 — 내용을 소개한다고 말하지 말고 내용을 말한다. 첫 줄은 이름 + 무엇 + 왜 좋은지.",
    "card": "명사형 종결('저장됨', '재료 6가지'). 20자 이내, 마침표 없음. '해당·정보·목록' 군더더기 금지.",
    "push": "해요체 1문장, 45자 이내. 데이터에 있는 숫자를 넣는다. '~하시기 바랍니다' 금지.",
    "email": "합니다체 통일. 용건 먼저. 이유는 입력에 있는 만큼만 구체적으로 — 지어내지도, 입력에 있던 사유를 지우지도 않는다. 상투 서두·결구 금지.",
    "doc": "'~다'체 통일. 문장 80자 이내. 개조식/서술식 혼용 금지. 판단과 수치를 명시.",
}

TONE_SPECS = {
    "해요체": "종결어미는 해요체('~해요', '~예요')로 전 문장 통일한다.",
    "합니다체": "종결어미는 합니다체('~합니다', '~입니다')로 전 문장 통일한다.",
    "다체": "종결어미는 '~다'체로 전 문장 통일한다. 해요체·합니다체 금지.",
    "명사형": "명사형 종결('저장됨', '재료 6가지'). 서술형 문장 금지, 마침표 없음.",
}
LEXICON_SPECS = {
    "easy": "독자는 비전문가다. 전문용어·공문투 한자어를 일상어로 풀어쓴다(도출→찾기, 소요→걸림, 숙지→알아두기). 한 문장 60자 이내.",
    "expert": "독자는 해당 분야 실무자다. 전문용어는 원어 그대로 유지하고 풀어쓰지 않는다. 정확성이 친절함보다 우선.",
    "normal": None,
}
LENGTH_SPECS = {
    "1line": "출력은 한 줄, 45자 이내.",
    "3line": "출력은 3줄, 각 줄 45자 이내.",
    "paragraph": "출력은 한 문단(3~5문장).",
}

PRINCIPLES = """- 동사로 말한다: '검토를 진행하다'가 아니라 '검토하다'
- 대명사·소유격은 생략이 기본: '당신의', '그것' 반복 금지
- 능동이 기본, 이중피동 금지: '보여진다'가 아니라 '보인다'
- 종결어미는 하나로 통일
- 헤징·상투구 금지: '~할 수 있습니다' 연발, '중요한 역할', '다양한', '물론입니다'
- 문장당 정보 하나, 긴 문장은 나눈다(길이 기준은 아래 스펙)
- 구체적 숫자·고유명사가 형용사를 이긴다. 단, 입력에 있는 사실만 쓴다 — 숫자·이유·이름을 지어내지 않는다"""


def rule_line(p):
    """메시지에 피할 표현이 따옴표로 없으면(예: '관공서투 날짜 표현') 나쁜 예문을 붙인다.
    없으면 '관공서투 날짜 표현: 오늘, 내일'처럼 대체어가 금지어로 읽힌다. 모든 규칙에 붙이면 도메인 밖 예문이 소음이 된다."""
    hit = (p.get("tests") or {}).get("hit") or []
    example = f" — 예: 「{hit[0]}」" if hit and "'" not in p["message"] else ""
    return f"- {p['message']}{example} → {p['fix']}"


def load_rules(register, max_rules, include_easy=False, skip_lexical=False):
    """error 패턴을 관련도 순(easy 어휘 → 레지스터 전용 → 공통)으로 고른 뒤 max_rules개로 자른다.
    파일 순서대로 자르면 뒤에 있는 easy·레지스터 전용 규칙이 먼저 잘려 나간다."""
    with open(BASE / "references" / "patterns.json", encoding="utf-8") as f:
        patterns = json.load(f)["patterns"]
    errors = [p for p in patterns if p["severity"] == "error"
              and not (skip_lexical and p["category"] == "어휘")]  # 실무자 대상이면 '수령·금일' 같은 생활 어휘 규칙은 소음
    easy = [p for p in errors if include_easy and p["register"] == "easy"]
    specific = [p for p in errors if p["register"] == register]
    common = [p for p in errors if p["register"] == "all"]
    rules = (easy + specific + common)[:max_rules]
    return "\n".join(rule_line(p) for p in rules)


def load_warn_rules(register, max_rules):
    """warn 패턴(번역투·GPT체) 중 레지스터에 맞는 것을 '피할 표현'으로 낸다. 소형 모델은 넓은 목록이 있어야 덜 직역한다."""
    with open(BASE / "references" / "patterns.json", encoding="utf-8") as f:
        patterns = json.load(f)["patterns"]
    warns = [p for p in patterns if p["severity"] == "warn" and p["category"] in ("번역투", "GPT체")
             and p["register"] in ("all", register)]
    # 번역투 먼저, 그 안에서는 1회만 나와도 걸리는 match 패턴 먼저 — 파일 순서로 자르면 뒤에 추가한 패턴이 빠진다
    warns.sort(key=lambda p: (p["category"] != "번역투", p["type"] == "frequency"))
    return "\n".join(rule_line(p) for p in warns[:max_rules])


def load_examples(text_type, path, prefer=None):
    md = Path(path).read_text(encoding="utf-8")
    m = re.search(rf"## type:{text_type}\b.*?(?=\n## type:|\Z)", md, re.DOTALL)
    if not m:
        return ""
    section = m.group(0)
    # Before/After 쌍만 추출 ('왜' 해설은 프롬프트 토큰 절약을 위해 제외)
    labeled = re.findall(r"\*\*Before([^*]*)\*\*:?\s*\n((?:>.*\n?|`.*\n?)+)\s*\*\*After:?\*\*:?\s*\n((?:>.*\n?|`.*\n?)+)", section)
    # prefer(예: '기술')가 Before 표제에 붙은 예시가 있으면 그것만 쓴다 — 소형 모델은 예시의 도메인을 따라 한다
    if prefer and any(prefer in label for label, _, _ in labeled):
        labeled = [x for x in labeled if prefer in x[0]]
    pairs = [(before, after) for _, before, after in labeled]
    # 한 줄 인라인 형식: **Before:** `a` / `b`  →  **After:** `x` / `y`
    for before, after in re.findall(r"\*\*Before[^*]*\*\*:?[ \t]+(`[^\n]+)\n\*\*After:?\*\*:?[ \t]+(`[^\n]+)", section):
        pairs.append(tuple("\n".join(x.strip(" `") for x in s.split(" / ")) for s in (before, after)))
    out = []
    for i, (before, after) in enumerate(pairs, 1):
        clean = lambda s: re.sub(r"^[> ]+", "", s.strip(), flags=re.MULTILINE).strip("`")
        out.append(f"[예시 {i} — 나쁜 출력]\n{clean(before)}\n[예시 {i} — 좋은 출력]\n{clean(after)}")
    return "\n\n".join(out)


def main():
    profiles_doc = json.load(open(BASE / "references" / "profiles.json", encoding="utf-8"))
    types = profiles_doc["types"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None, help="references/profiles.json의 프로필 이름")
    ap.add_argument("--type", default=None, choices=list(TYPE_SPECS))
    ap.add_argument("--register", default=None, choices=["casual", "formal"])
    ap.add_argument("--tone", default=None, choices=list(TONE_SPECS))
    ap.add_argument("--lexicon", default=None, choices=["easy", "normal", "expert"])
    ap.add_argument("--length", default=None, choices=list(LENGTH_SPECS))
    ap.add_argument("--max-rules", type=int, default=16)
    ap.add_argument("--max-warn", type=int, default=18, help="'피할 표현'(warn 패턴) 최대 개수, 0이면 생략")
    ap.add_argument("--examples", default=str(BASE / "references" / "examples.md"),
                    help="few-shot 예시 파일(examples.md와 같은 '## type:이름' 형식)")
    args = ap.parse_args()

    cfg = {}
    if args.profile:
        profiles = profiles_doc["profiles"]
        if args.profile not in profiles:
            sys.exit(f"프로필 없음: {args.profile}. 사용 가능: {', '.join(profiles)}")
        cfg = dict(profiles[args.profile])
    # CLI 플래그가 프로필을 오버라이드
    for k in ("type", "tone", "lexicon", "length"):
        v = getattr(args, k)
        if v:
            cfg[k] = v
    if "type" not in cfg:
        sys.exit("--type 또는 --profile 필요")
    type_default = types[cfg["type"]]
    register = args.register or type_default["register"]

    axis_lines = [TYPE_SPECS[cfg["type"]]]
    tone_override = cfg.get("tone") and cfg.get("tone") != type_default.get("tone")
    for key, table in (("tone", TONE_SPECS), ("lexicon", LEXICON_SPECS), ("length", LENGTH_SPECS)):
        if key == "tone" and not tone_override:
            continue  # 타입 기본 어투와 같으면 같은 규칙을 두 번 쓰지 않는다
        spec = table.get(cfg.get(key))
        if spec:
            axis_lines.append(spec)
    if tone_override:
        axis_lines.append("종결어미는 위 타입 설명보다 바로 위 어투 지정을 따른다.")

    examples = load_examples(cfg["type"], args.examples, "기술" if cfg.get("lexicon") == "expert" else None)
    block = f"""## 한국어 작성 규칙 (필수 준수)

이 텍스트는 한국인 사용자가 앱/문서에서 직접 읽는다. 번역투와 AI 상투 표현 없이, 사람이 쓴 것처럼 자연스럽게 쓴다.

### 원칙
{PRINCIPLES}

### 이 텍스트의 스펙
{chr(10).join('- ' + l for l in axis_lines)}

### 금지 패턴 (위반 시 재작성 대상)
{load_rules(register, args.max_rules, cfg.get('lexicon') == 'easy', cfg.get('lexicon') == 'expert')}"""
    warn_rules = load_warn_rules(register, args.max_warn) if args.max_warn else ""
    if warn_rules:
        block += f"\n\n### 피할 표현 (맥락상 꼭 필요하지 않으면 바꾼다)\n{warn_rules}"
    if examples:
        block += ("\n\n### 예시 (문체 참고용 — 예시의 사실을 출력에 섞지 않는다. "
                  f"숫자·이름은 입력 원문에 있을 때만 쓴다)\n{examples}")
    print(block)


if __name__ == "__main__":
    main()
