# Agent Skills

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Skills](https://img.shields.io/badge/npx-skills-blue)](https://www.npmjs.com/package/skills)
[![Figma](https://img.shields.io/badge/Figma-Skills-F24E1E?logo=figma&logoColor=white)](./skills/)

> AI 에이전트를 위한 스킬 모음 — Agent skills for Claude Code, Copilot CLI, Codex, and Gemini CLI.
> Includes Figma MCP integration skills for icons (Iconify) and logos (SVGL).

## 설치 / Installation

### Claude Code

`npx skills` CLI를 사용해 원하는 스킬을 설치합니다.

```bash
npx skills add douinc/agent-skills@<skill-name>
```

예:

```bash
npx skills add douinc/agent-skills@ux-writing-korean
```

### Codex

Codex는 Open Agent Skills 형식의 `SKILL.md`를 읽을 수 있습니다. 원하는 스킬을 Codex 사용자 스킬 경로에 복사하면 모든 Codex 작업에서 사용할 수 있습니다.

```bash
git clone https://github.com/douinc/agent-skills.git
cd agent-skills
mkdir -p ~/.agents/skills
cp -R skills/<skill-name> ~/.agents/skills/
```

예:

```bash
cp -R skills/ux-writing-korean ~/.agents/skills/
```

설치 후 Codex에서 `$<skill-name>`으로 명시적으로 호출하거나, 스킬의 `description`과 맞는 작업을 요청하면 자동으로 사용할 수 있습니다. 새 스킬이 보이지 않으면 Codex를 재시작하세요.

### Global install

이미 이 저장소를 클론한 상태라면, Claude Code와 Codex에 같은 스킬을 전역 설치할 수 있습니다.

```bash
# Claude Code global
mkdir -p ~/.claude/skills
cp -R skills/<skill-name> ~/.claude/skills/

# Codex global
mkdir -p ~/.agents/skills
cp -R skills/<skill-name> ~/.agents/skills/
```

전체 스킬을 한 번에 설치하려면 `<skill-name>` 대신 `*`를 사용합니다.

```bash
cp -R skills/* ~/.claude/skills/
cp -R skills/* ~/.agents/skills/
```

### Claude.ai / Claude API

[Claude Code 플러그인 설치 가이드](https://docs.anthropic.com/en/docs/claude-code/skills) 참고

## 스킬 목록 / Available Skills

### UX Writing

| 스킬 | 설명 | 설치 |
| ---- | ---- | ---- |
| [ux-writing-korean](./skills/ux-writing-korean/) | 한국어 UX 라이팅 가이드 (해요체, 능동형, 긍정형, 캐주얼 경어, 명사 조합 회피) | `npx skills add douinc/agent-skills@ux-writing-korean` |

### Design

| 스킬 | 설명 | 설치 |
| ---- | ---- | ---- |
| [onboarding-design](./skills/onboarding-design/) | 회원가입 플로우, 목표 선택 퀴즈, 권한 요청 화면, 페이월 등 사용자의 첫 번째 의미 있는 행동 이전 화면을 설계·검토할 때 사용 | `npx skills add douinc/agent-skills@onboarding-design` |
| [design-md-to-shadcn](./skills/design-md-to-shadcn/) | 외부 DESIGN.md(Google Labs 디자인 토큰 포맷)를 shadcn/ui 테마의 CSS 변수로 변환·적용 | `npx skills add douinc/agent-skills@design-md-to-shadcn` |
| [dou-product-design](./skills/dou-product-design/) | Next.js + shadcn/ui 기반 Dou 제품 화면 설계·직접 구현 워크플로우. 설치 시 `dou-uxui-issues`도 함께 설치 | `npx skills add douinc/agent-skills@dou-product-design` |
| [dou-uxui-issues](./skills/dou-uxui-issues/) | Dou 제품 UI/UX 이슈의 초안·등록, 하위 이슈 관계와 프로젝트 상태 관리 | `npx skills add douinc/agent-skills@dou-uxui-issues` |

### Figma / Icons

| 스킬 | 설명 | 설치 |
| ---- | ---- | ---- |
| [figma-icons-iconify](./skills/figma-icons-iconify/) | Fetch real SVG icons from Iconify API for Figma designs (supports Tabler, Lucide, Material Design, and 150+ icon sets) | `npx skills add douinc/agent-skills@figma-icons-iconify` |
| [figma-logos-svgl](./skills/figma-logos-svgl/) | Fetch real SVG brand/product logos from SVGL API for Figma designs (React, Vercel, Stripe, GitHub, and 500+ brands) | `npx skills add douinc/agent-skills@figma-logos-svgl` |

### Documentation

| 스킬 | 설명 | 설치 |
| ---- | ---- | ---- |
| [writing-project-readme](./skills/writing-project-readme/) | 명시적으로 호출했을 때만 동작하는 커맨드형 스킬. 비개발자(PM/디자인/운영)도 읽을 수 있는 종합 README를 처음부터 다시 작성 | `npx skills add douinc/agent-skills@writing-project-readme` |
| [manual-authoring](./skills/manual-authoring/) | 첨부한 화면 스크린샷과 설명만으로 A4 사용자 매뉴얼 PDF를 만들거나 수정 (Figma 불필요) | `npx skills add douinc/agent-skills@manual-authoring` |
| [public-sector-rfp-authoring](./skills/public-sector-rfp-authoring/) | 정부·지자체·공공기관 발주기관 관점의 입찰공고서, 제안요청서, 과업내용서, 시스템 구축 RFP 작성 | `npx skills add douinc/agent-skills@public-sector-rfp-authoring` |

### Observability

| 스킬 | 설명 | 설치 |
| ---- | ---- | ---- |
| [langfuse-laravel-ai](./skills/langfuse-laravel-ai/) | `laravel/ai` SDK를 쓰는 Laravel 앱에 Langfuse 트레이싱 연결. `axyr/laravel-langfuse` 자동계측 + trace 컨텍스트(session/user/메타데이터) 보강 | `npx skills add douinc/agent-skills@langfuse-laravel-ai` |

## 새 스킬 만들기 / Contributing

1. `template/SKILL.md`를 참고하여 새 스킬을 만듭니다
2. `skills/<skill-name>/SKILL.md` 경로에 파일을 생성합니다
3. PR을 올려주세요

### SKILL.md 기본 구조

```yaml
---
name: skill-name
description: 스킬 설명과 언제 사용하는지 작성합니다.
metadata:
  author: your-name
  version: "1.0.0"
---

# 스킬 제목

스킬 지침을 여기에 작성합니다.
```

## 라이선스 / License

[MIT](./LICENSE)
