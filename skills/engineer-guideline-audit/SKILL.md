---
name: engineer-guideline-audit
description: Audit one project or every project under a path against the Dou engineer-guideline repository, report violations, and apply approved fixes. Use whenever the user wants to check, enforce, or apply the team engineering guidelines — phrases like "가이드라인 점검", "가이드라인 지키고 있는지 확인", "엔지니어 가이드라인 적용", "컨벤션 점검", "환경 설정 파일 규칙 확인", "audit against engineer-guideline". Trigger even when the user says 규칙, 관례, 규정, or convention instead of "가이드라인" — any "does this project follow our team's rules?" request belongs here, including whether a specific file name (e.g. .env.prod) violates the rules, compliance-status reports across multiple projects, or reviewing a newly set-up project against team practices. Do not use for reading or authoring the guideline documents themselves, commit-message convention checks, or debugging env/compose runtime behavior.
metadata:
  author: develinu
  email: dev@dou.so
  version: "1.0.0"
---

# 엔지니어 가이드라인 점검 (Engineer Guideline Audit)

`engineer-guideline` 저장소의 문서를 근거로 프로젝트가 팀 관례를 지키는지 점검하고, 리포트를 만든 뒤, 사용자 승인을 받은 항목만 수정한다. 규칙을 이 스킬에 하드코딩하지 않는다 — 가이드라인 문서가 곧 규칙의 원천이며, 문서가 바뀌면 점검 기준도 자동으로 따라간다. 모든 판정에는 문서의 어느 규칙을 근거로 했는지와 프로젝트의 어느 파일이 증거인지를 남긴다. 근거 없는 판정은 리포트의 신뢰를 무너뜨린다.

## 1단계 — 가이드라인 저장소와 점검 대상 확정

**가이드라인 저장소 찾기.** 사용자가 경로를 지정했으면 그 경로를 쓴다. 지정하지 않았으면 점검 대상 경로에서 시작해 상위 디렉토리로 올라가며 형제 디렉토리 중 `engineer-guideline`을 찾고, 없으면 `~/dou/engineer-guideline`을 확인한다. 그래도 없으면 사용자에게 위치를 묻는다. 찾은 경로를 리포트에 기록해 어떤 버전의 가이드를 기준으로 점검했는지 남긴다.

**점검 대상 확정.** 사용자가 준 경로가:

- **프로젝트 하나**(`.git`이 있거나 `package.json`, `pyproject.toml`, `composer.json`, `go.mod` 같은 매니페스트가 있는 디렉토리)면 그 프로젝트만 점검한다.
- **여러 프로젝트를 담은 상위 경로**면 1-depth 하위 디렉토리 중 프로젝트로 판별되는 것을 모두 점검한다. 가이드라인 저장소 자신과 숨김 디렉토리는 제외한다.

점검을 시작하기 전에 대상 프로젝트 목록을 사용자에게 짧게 보여준다. 잘못된 대상을 오래 점검하는 것이 가장 큰 낭비다.

## 2단계 — 가이드라인 문서에서 점검 항목 도출

가이드라인 저장소의 README에서 문서 목록을 읽고, 각 문서의 프론트매터를 확인해 `status`가 `deprecated`가 아닌 문서만 점검 기준으로 삼는다. `templates/` 아래 파일과 README 자체(저장소 운영 원칙)는 프로젝트 점검 기준이 아니므로 제외한다.

각 문서를 읽으며 점검 항목을 두 종류로 나눈다:

- **기계적으로 검증 가능한 규칙**: 파일명 패턴, 금지된 축약형, `.gitignore` 등록 여부, 커밋 여부처럼 파일 시스템과 git으로 확인할 수 있는 것. 문서에 "검증 방법" 섹션이 있으면 그 방법을 우선 사용한다.
- **판단이 필요한 규칙**: "공통 설정은 기본 파일에, 차이는 오버라이드에" 같은 구조적 원칙. 위반으로 단정하기 전에 실제 파일 내용을 읽고 판단하며, 확신이 없으면 위반이 아니라 주의로 분류한다.

문서에 예외 조항이 있으면(예: 외부 플랫폼이 축약형을 강제하는 경우) 그 예외에 해당하는지 먼저 확인한다. 예외를 무시한 위반 판정은 거짓 양성이다.

## 3단계 — 프로젝트별 점검 실행

프로젝트마다 규칙과 관련된 사실을 먼저 수집한 뒤 판정한다. 사실 수집에 유용한 명령:

```bash
# 규칙 관련 파일 현황 (예: 환경 설정 관례라면)
ls -a <project> | grep -E '^\.env|^docker-compose'
# git이 실제로 추적 중인 파일 — .gitignore 등록 여부는 이것으로 최종 확인한다
git -C <project> ls-files
# 이름을 바꿔야 할 파일이 코드·CI·문서 어디에서 참조되는지
grep -rn --exclude-dir={.git,node_modules,vendor,dist} '\.env\.prod\b' <project>
```

각 항목을 네 등급으로 판정한다:

- **위반**: 문서의 규칙과 명확히 어긋남. 근거 규칙과 증거 파일(경로:라인)을 함께 기록한다.
- **주의**: 규칙 위반 가능성이 있으나 판단 여지가 있거나, 자동 수정이 위험한 것(예: 커밋된 비밀 값은 git 히스토리 정리가 필요하므로 파일명만 고쳐서는 해결되지 않음).
- **양호**: 규칙 대상이 존재하고 규칙을 지키고 있음.
- **해당 없음**: 규칙이 다루는 대상이 프로젝트에 아예 없음. 예를 들어 Docker를 쓰지 않는 프로젝트에 Compose 규칙 위반을 만들지 않는다. 해당 없음을 위반으로 부풀리면 리포트 전체가 의심받는다.

**비밀 값은 특별 취급한다.** 커밋된 파일에서 실제 비밀 값으로 보이는 문자열(토큰, 패스워드, 개인 키 패턴)을 발견하면 값 자체를 리포트에 옮겨 적지 않는다. 파일 경로와 키 이름만 기록하고, git 히스토리에 남아 있으므로 파일 수정만으로는 해결되지 않는다는 점을 명시한다.

## 4단계 — 리포트 작성

대화에는 프로젝트별 요약을, 파일에는 상세 리포트를 남긴다. 리포트 파일은 현재 작업 디렉토리에 `guideline-audit-YYYY-MM-DD.md`로 저장한다(사용자가 다른 경로를 원하면 그에 따른다).

```markdown
# 엔지니어 가이드라인 점검 리포트
- 점검일: YYYY-MM-DD / 기준: <가이드라인 저장소 경로> (<기준 문서 목록>)

## 요약
| 프로젝트 | 위반 | 주의 | 양호 | 해당 없음 |
| --- | --- | --- | --- | --- |

## <프로젝트명>
### 위반
- **<규칙 요약>** — 근거: <문서명 § 섹션> / 증거: `<파일:라인>`
  - 수정안: <무엇을 어떻게 바꾸고, 함께 갱신해야 할 참조는 무엇인지>
### 주의 / 양호 / 해당 없음
...
```

수정안에는 파일 하나만 고치면 되는지, 참조(CI 설정, 스크립트, 문서)까지 함께 갱신해야 하는지를 반드시 적는다. 이름 변경 규모를 미리 보여줘야 사용자가 승인 여부를 판단할 수 있다.

## 5단계 — 사용자 승인 후 적용

리포트를 보여준 뒤 어떤 항목을 적용할지 사용자에게 확인받는다. 항목이 여럿이면 프로젝트·항목 단위로 선택할 수 있게 묻는다. 승인 없이 파일을 수정하지 않는다 — 단, 사용자가 처음부터 "바로 적용해"라고 했으면 그 지시가 승인이다.

적용할 때 지키는 것:

- **이름 변경과 참조 갱신은 한 세트다.** `.env.prod` → `.env.production`으로 바꾸면 그 이름을 참조하는 모든 곳(CI 워크플로우, 스크립트, `package.json`, Dockerfile, Compose 파일, 문서)을 같은 커밋 단위 안에서 함께 고친다. 참조를 남기면 위반을 고친 것이 아니라 프로젝트를 깨뜨린 것이다.
- git이 추적 중인 파일은 `git mv`로 옮겨 이력을 보존한다.
- 적용 후 잔여 참조를 다시 grep으로 확인하고, Compose 설정을 바꿨다면 `docker compose config`류의 검증 명령이 가능한 환경에서는 실행해 합성 결과를 확인한다.
- **자동 수정하지 않는 것**: git 히스토리에 커밋된 비밀 값(히스토리 정리는 파괴적 작업이므로 방법만 안내), 저장소 밖의 배포 플랫폼 설정, 판단이 갈리는 구조 변경. 이런 항목은 리포트에 후속 조치로 남긴다.
- 커밋은 사용자가 요청할 때만 한다. 적용을 마치면 무엇을 바꿨는지 프로젝트별로 정리해 보여준다.
