#!/usr/bin/env python3
"""외부 LLM 파이프라인용 시스템 프롬프트 블록을 추출한다.

사용:
    python export.py --profile retriever-push                  # 명명 프로필 (references/profiles.json)
    python export.py --type summary [--tone 다체] [--lexicon expert] [--length 3line]

출력(stdout): 핵심 원칙 + 금칙 목록(사전에서 추출) + 타입 스펙 + 축 스펙 + 해당 타입 few-shot 예시.
제품 파이프라인(gpt-4o-mini급 등)의 시스템 프롬프트에 그대로 삽입한다.
표준 라이브러리만 사용.
"""
import argparse
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TYPE_REGISTER = {"summary": "casual", "card": "casual", "push": "casual",
                 "email": "formal", "doc": "formal"}

TYPE_SPECS = {
    "summary": "종결: '~다'체 또는 명사형(혼용 금지). 줄당 45자 이내. 메타 문장 금지 — 내용을 소개한다고 말하지 말고 내용을 말한다. 숫자·고유명사를 앞에.",
    "card": "명사형 종결('저장됨', '재료 6가지'). 20자 이내, 마침표 없음. '해당·정보·목록' 군더더기 금지.",
    "push": "해요체 1문장, 45자 내외. 구체적 숫자 포함. '~하시기 바랍니다' 금지.",
    "email": "합니다체 통일. 용건 먼저, 이유는 구체적으로('내부 사정' 금지). 상투 서두·결구 금지.",
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
- 문장당 정보 하나, 80자 초과 문장 분리
- 구체적 숫자·고유명사가 형용사를 이긴다"""


def load_rules(register, max_rules, include_easy=False):
    with open(BASE / "references" / "patterns.json", encoding="utf-8") as f:
        patterns = json.load(f)["patterns"]
    rules = [p for p in patterns
             if p["severity"] == "error"
             and (p["register"] in ("all", register) or (include_easy and p["register"] == "easy"))]
    lines = [f"- {p['message']}: {p['fix']}" for p in rules[:max_rules]]
    return "\n".join(lines)


def load_examples(text_type):
    md = (BASE / "references" / "examples.md").read_text(encoding="utf-8")
    m = re.search(rf"## type:{text_type}.*?(?=\n## type:|\Z)", md, re.DOTALL)
    if not m:
        return ""
    section = m.group(0)
    # Before/After 쌍만 추출 ('왜' 해설은 프롬프트 토큰 절약을 위해 제외)
    pairs = re.findall(r"\*\*Before[^*]*\*\*:?\s*\n((?:>.*\n?|`.*\n?)+)\s*\*\*After:?\*\*:?\s*\n((?:>.*\n?|`.*\n?)+)", section)
    out = []
    for i, (before, after) in enumerate(pairs, 1):
        clean = lambda s: re.sub(r"^[> ]+", "", s.strip(), flags=re.MULTILINE)
        out.append(f"[예시 {i} — 나쁜 출력]\n{clean(before)}\n[예시 {i} — 좋은 출력]\n{clean(after)}")
    return "\n\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None, help="references/profiles.json의 프로필 이름")
    ap.add_argument("--type", default=None, choices=list(TYPE_SPECS))
    ap.add_argument("--register", default=None, choices=["casual", "formal"])
    ap.add_argument("--tone", default=None, choices=list(TONE_SPECS))
    ap.add_argument("--lexicon", default=None, choices=["easy", "normal", "expert"])
    ap.add_argument("--length", default=None, choices=list(LENGTH_SPECS))
    ap.add_argument("--max-rules", type=int, default=12)
    args = ap.parse_args()

    cfg = {}
    if args.profile:
        profiles = json.load(open(BASE / "references" / "profiles.json", encoding="utf-8"))["profiles"]
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
    register = args.register or TYPE_REGISTER[cfg["type"]]

    axis_lines = [TYPE_SPECS[cfg["type"]]]
    overrides = False
    for key, table in (("tone", TONE_SPECS), ("lexicon", LEXICON_SPECS), ("length", LENGTH_SPECS)):
        spec = table.get(cfg.get(key))
        if spec:
            axis_lines.append(spec)
            overrides = True
    if overrides:
        axis_lines.append("첫 줄의 타입 기본값과 아래 지정이 충돌하면 아래 지정이 우선한다.")

    block = f"""## 한국어 작성 규칙 (필수 준수)

이 텍스트는 한국인 사용자가 앱/문서에서 직접 읽는다. 번역투와 AI 상투 표현 없이, 사람이 쓴 것처럼 자연스럽게 쓴다.

### 원칙
{PRINCIPLES}

### 이 텍스트의 스펙
{chr(10).join('- ' + l for l in axis_lines)}

### 금지 패턴 (위반 시 재작성 대상)
{load_rules(register, args.max_rules, cfg.get('lexicon') == 'easy')}

### 예시
{load_examples(cfg["type"])}"""
    print(block)


if __name__ == "__main__":
    main()
