# ko-natural 유지보수·외부 파이프라인

SKILL.md에서 분리한 문서다. 사전을 고치거나 외부 파이프라인용 프롬프트를 만들 때만 읽는다.

## 사전 성장 루프 (유지보수)

사용자가 어색하다고 지적한 표현은 패턴 후보로 제안하고, 동의를 받으면 `references/patterns.json`에 추가한다(id는 카테고리 접두사 + 다음 번호, 정규식·severity·fix·tests 포함). 사전은 합성 시드로 시작했으므로, 실제 실패 사례가 쌓일수록 이 스킬의 가치가 커진다.

- **활용형까지 잡는지 확인한다.** '하'와 '한·합·했', '지'와 '진·져'는 서로 다른 음절이다. `수령[하해]`는 "수령합니다"를 놓친다 — `(?:하|해|한|할|합|했)`처럼 활용 음절을 나열한다.
- **예문으로 고정한다.** `tests.hit`에 걸려야 할 문장, `tests.miss`에 걸리면 안 될 문장을 넣고 `python3 <스킬 디렉터리>/scripts/lint.py --selftest`가 통과하는지 확인한다.
- **오탐은 miss 예문부터 추가한다.** 그다음 regex를 좁히거나 severity를 낮춘다.
- 스킬을 `npx skills add`로 설치했다면 재설치할 때 덮어쓰인다. 팀이 함께 쓸 패턴은 스킬 저장소에 PR로 올린다.

## 외부 파이프라인 적용

이 스킬은 Claude 작업에 직접 적용되고, 외부 API 파이프라인(예: 제품의 요약 생성)에는 export로 간접 적용된다:

```bash
python3 <스킬 디렉터리>/scripts/export.py --profile retriever-push > prompt_block.txt
python3 <스킬 디렉터리>/scripts/export.py --type summary --lexicon expert --length 3line   # 축 직접 지정
python3 <스킬 디렉터리>/scripts/export.py --profile retriever-dev-summary --examples tech_examples.md   # 도메인 맞춤 few-shot
```

소형 모델은 규칙보다 예시를 더 강하게 따라 한다. 예시를 직접 만들 때는 좋은 출력에 나쁜 출력(또는 함께 보여 준 원문)에 없는 수치·사실을 보태지 않는다 — 보태면 '지어내지 말라'는 규칙보다 '사실을 보태도 된다'는 예시가 먼저 학습된다. 콘텐츠 도메인이 내장 예시(레시피·여행·기술 레포)와 다르면 같은 형식(`## type:이름` + Before/After)의 예시 파일을 `--examples`로 넘긴다.

출력물(핵심 원칙 + 금칙 목록 + 타입 스펙 + 축 스펙 + few-shot 예시)을 파이프라인의 시스템 프롬프트에 삽입하고, 서버에서는 patterns.json 기반 린트를 후처리 검증으로 이식하면 자산 하나로 두 소비처를 커버한다.
