# README Template

이 파일은 [`SKILL.md`](./SKILL.md)에서 분리한 풀 템플릿입니다. 섹션 순서는 룰의 일부이므로 임의 변경 금지 — 상단 1/3은 비개발자, 하단 2/3은 개발자.

프로젝트 유형(서비스 앱, 라이브러리, CLI, 플러그인 마켓플레이스, 모노레포)에 따라 SKILL.md의 `Adapting to Project Type` 표에 맞춰 일부 섹션을 생략/대체하세요.

---

```markdown
# {Product Name}

> **{One-line tagline}**
> {One sentence on the value to the end user.}

{Core stack badges — 4–6 max}

**Download / Try** · {App Store} · {Play Store} · {Web URL}

---

## 목차 / Table of Contents
…

## What is {Product}?
Plain-language paragraph. No jargon.

## Who is it for?
| User | Scenario |

## Core features
| Feature | Plain-language description (technology in parentheses) |

## User journey
\`\`\`mermaid
flowchart LR
  Sign up --> Onboarding --> Core action --> Outcome
\`\`\`

## Platforms
Web / iOS / Android / CLI / API — whichever apply.

---

## Tech stack
| Layer | Technologies |

## System architecture
\`\`\`mermaid
flowchart LR
  Client --> Server --> Datastore
  Server --> External APIs
  Server -.-> Observability
\`\`\`

## Project structure
Annotated tree. One line per folder.

## Core domain model
ERD (Mermaid `erDiagram`) + table mapping model → role.

## External integrations
| Service | Purpose |

## Security & privacy
Encryption, auth, sensitive-data handling.

## Standards & compliance
Only if applicable (FHIR, HIPAA, GDPR, …).

---

## Development setup
> See **[DEVELOPMENT.md](./DEVELOPMENT.md)** for the full guide.

Quick start (3–5 lines max):
\`\`\`bash
…
\`\`\`

## Common commands
| Command | Purpose |

## Tests & code style
Tooling + one-liners.

---

## License / Contact
```
