# Agent Skills

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Skills](https://img.shields.io/badge/npx-skills-blue)](https://www.npmjs.com/package/skills)

> AI 에이전트를 위한 스킬 모음 — Agent skills for Claude Code, Copilot CLI, Codex, and Gemini CLI.

## 설치 / Installation

### Claude Code

```bash
npx skills add douinc/agent-skills@<skill-name>
```

### Claude.ai / Claude API

[Claude Code 플러그인 설치 가이드](https://docs.anthropic.com/en/docs/claude-code/skills) 참고

## 스킬 목록 / Available Skills

### UX Writing

| 스킬 | 설명 | 설치 |
| ---- | ---- | ---- |
| [ux-writing-korean](./skills/ux-writing-korean/) | 한국어 UX 라이팅 가이드 (해요체, 능동형, 긍정형, 캐주얼 경어, 명사 조합 회피) | `npx skills add douinc/agent-skills@ux-writing-korean` |

### Figma / Icons

| 스킬 | 설명 | 설치 |
| ---- | ---- | ---- |
| [figma-icons-iconify](./skills/figma-icons-iconify/) | Fetch real SVG icons from Iconify API for Figma designs (supports Tabler, Lucide, Material Design, and 150+ icon sets) | `npx skills add douinc/agent-skills@figma-icons-iconify` |
| [figma-logos-svgl](./skills/figma-logos-svgl/) | Fetch real SVG brand/product logos from SVGL API for Figma designs (React, Vercel, Stripe, GitHub, and 500+ brands) | `npx skills add douinc/agent-skills@figma-logos-svgl` |

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
