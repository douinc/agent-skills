---
name: token-audit
description: Audit a Claude Code or Codex CLI project for token waste and fix it with the user's approval. Use whenever the user wants to check, reduce, or optimize token usage, context bloat, or API/subscription costs of an agent project — phrases like "토큰 점검", "토큰 낭비 찾아줘", "토큰 최적화", "컨텍스트 최적화", "Claude Code 비용 줄여줘", "API 비용이 너무 나와", "audit token efficiency", "check my CLAUDE.md/AGENTS.md/MCP setup". Also trigger when the user complains that sessions hit context limits too fast, that costs jumped unexpectedly, or asks whether their project setup is token-efficient — even if they don't say the word "token".
metadata:
  author: develinu
  email: dev@dou.so
  version: "1.0.0"
---

# 토큰 효율 점검 (Token Audit)

Claude Code·Codex 프로젝트의 설정을 근거 기반 체크리스트로 점검하고, 영향도순 리포트를 만든 뒤, 사용자 확인을 받아 수정한다. 모든 체크의 기준치·근거 수치·수정안은 `references/checks.md`에 있다 — **점검을 시작하기 전에 반드시 읽는다.** 근거 없는 판정은 이 스킬의 신뢰를 무너뜨린다.

## 1단계 — 환경 탐지

프로젝트 루트에서 존재하는 파일을 확인한다 (Glob 사용):

- **Claude Code**: `CLAUDE.md`(루트·중첩), `.claude/settings.json`, `.claude/settings.local.json`, `.claude/agents/*.md`, `.claude/skills/`, `.claude/rules/`, `.mcp.json`
- **Codex**: `AGENTS.md`(루트·중첩), `.codex/config.toml`

존재하는 파일만 점검한다. 파일이 없는 것은 "해당 없음"이지 문제가 아니다. 두 환경 파일이 모두 없으면 점검할 프로젝트 폴더가 맞는지 사용자에게 확인한다. 글로벌 설정(`~/.claude/`, `~/.codex/`)은 접근 가능하고 사용자가 원할 때만 포함한다.

## 2단계 — 점검 실행

`references/checks.md`를 읽고, 탐지된 환경에 해당하는 체크를 전부 실행한다. 각 항목을 세 등급으로 판정한다:

- **심각**: 세션당 수만 토큰 규모의 낭비, 또는 품질을 함께 훼손하는 요인
- **개선**: 측정 가능한 낭비이지만 규모가 작거나 상황 의존적
- **양호**: 기준 통과

판정 원칙 — 이것이 스킬의 품질을 좌우한다:

- **깨끗한 프로젝트에는 깨끗하다고 말한다.** 문제를 억지로 만들어내면 사용자는 진짜 경고도 무시하게 된다. 잘 된 설정은 양호 섹션에서 구체적으로 인정한다.
- 토큰 추정은 "문자 수 ÷ 4 ≈ 토큰"으로 근사하고, 추정임을 명시한다.
- 모든 판정에 checks.md의 근거 수치를 인용한다. 과장하지 않는다.
- 확실하지 않은 것(예: MCP 서버가 실제로 쓰이는지)은 단정하지 말고 사용자에게 질문 목록으로 남긴다.

## 3단계 — 리포트

리포트는 사용자의 언어로 작성하고, 마크다운 파일로 저장한 뒤(프로젝트 루트 또는 사용자 지정 위치, 파일명 `token-audit-report.md`) 대화에는 핵심 요약만 제시한다. 구조는 고정:

```markdown
# 토큰 효율 점검 리포트 — <프로젝트명> (<날짜>)

## 요약
- 판정: 심각 N건 / 개선 N건 / 양호 N건
- 최우선 조치 3가지와 예상 효과 (한 줄씩)

## 심각
### [체크ID] <제목> — <추정 영향>
현황 → 왜 문제인가(근거 수치 인용) → 수정안 → 예상 절감

## 개선 권장
(같은 형식)

## 양호
(통과한 항목과 이유를 짧게 — 잘한 것을 인정)

## 확인 필요
(단정할 수 없어 사용자 답이 필요한 질문들)

## 습관 체크리스트
(파일로 점검 불가한 항목 — checks.md의 H 섹션을 리포트 말미에 항상 포함)
```

## 4단계 — 수정 적용

- **대화형 세션**: 심각 항목부터 하나씩 제안 → 사용자 확인 → 적용. CLAUDE.md/AGENTS.md의 내용 삭제·이동은 반드시 변경 전/후 diff를 보여주고 승인받는다. 설정 파일(JSON/TOML) 키 추가·변경도 적용 전에 정확한 변경 내용을 보여준다.
- **비대화형(헤드리스·자동 실행·서브에이전트)**: 리포트만 작성하고 프로젝트 파일을 수정하지 않는다. 사용자가 없는 곳에서 지시 파일을 고치는 것은 위험하다.
- 수정을 적용했으면 해당 체크만 재실행해 등급 변화를 요약한다.

## 흔한 함정

- CLAUDE.md를 `@import`로 쪼개는 것은 정리는 되지만 **토큰 절감이 아니다** — import된 파일도 시작 시 전부 로드된다. 절감은 삭제, skills 이전, 경로 조건부 rules 이전에서 나온다.
- 절감 제안이 캐시를 깨는 방향이면 역효과다(예: 세션 중 모델 전환 유도). 캐시 관련 항목은 checks.md의 H 섹션 수치를 근거로 설명한다.
- 이 스킬의 수치는 2026-08 기준 조사값이다. 가격·기본값이 의심되면 공식 문서(code.claude.com/docs, developers.openai.com/codex)를 재확인한다.
