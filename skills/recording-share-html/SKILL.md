---
name: recording-share-html
description: "회의·미팅 녹음의 STT 전사(영업·고객 미팅, 협력사·투자자 회의, 내부 회의, 세미나, 업무 메모)를 그 자리에 없던 팀원이 바로 읽을 HTML 회의록 한 장으로 정리한다. 핵심·결정·할 일·숫자·상대 반응·주제별 내용과 원문 전사 탭(찾기·화자 거르기)이 들어간다. '회의록 정리해 줘', '녹음 정리해서 팀에 공유', '미팅 녹음 HTML로', '전사 요약 문서', 'meeting minutes from transcript' 같은 요청에 쓴다. 환자 진료처럼 개인 민감 정보가 중심인 녹음에는 쓰지 않는다."
metadata:
  author: iw@dou.so
  version: "1.0.0"
---

# 녹음 전사 → 팀 공유 HTML 회의록

전사를 정해진 JSON으로 정리하고(`prompt.md`), 그 JSON을 `render.py`가 파일 하나짜리 HTML로 만든다. 정리 규칙과 화면 틀이 파일로 고정돼 있어, 사람이 손으로 만들 때와 봇이 자동으로 만들 때 같은 결과가 나온다.

## 필요한 것

- Python 3.10+ (`render.py`는 표준 라이브러리만 쓴다)
- 화자별 한 줄로 된 전사 텍스트. STT 도구는 가리지 않는다.

## 순서

1. **전사 준비** — `transcript.txt`. 한 줄에 발언 하나, `화자 1: 내용` 또는 `[HH:MM:SS] 이름: 내용` 꼴. 뒤쪽 꼴이면 경과 시각을 읽는다.
2. **정리 JSON 만들기** — `prompt.md`를 읽고 그 규칙과 `schema.json` 모양대로 전사를 정리해 `summary.json`에 쓴다. 전사에 없는 내용은 넣지 않는다.
3. **메타** — `meta.json`. 모든 값은 선택이다.

   ```json
   {
     "recorder": "홍길동",
     "author_email": "hong@example.com",
     "recorded_at": "2026-11-03T13:47:00+09:00",
     "duration_min": 26,
     "source": "휴대폰",
     "kind_label": "외부 업무 대화",
     "scope": "external",
     "meeting_mode": "offline"
   }
   ```

   | 키 | 뜻 |
   | --- | --- |
   | `recorder`, `requester` | 녹음한 사람, 정리를 요청한 사람 |
   | `recorded_at` | 녹음 **시작** 시각(ISO 8601) |
   | `source` / `source_label` | 녹음 수단 칩. `source_label`을 주면 그 글이 그대로 칩이 된다(예: "구글밋") |
   | `scope` | `external`·`internal` → '외부 녹음'·'내부 녹음' 태그 |
   | `meeting_mode` | `online`·`offline` → '회의록'과 '온라인 회의'·'오프라인 회의' 태그. 시작 시각이 있으면 제목이 `[회의록] YYYY-MM-DD 제목`이 된다 |
   | `title_prefix` | 제목 머리말을 직접 정할 때 |
   | `source_tag`, `tags` | 출처 태그(기본 "녹음")와 덧붙일 태그 |
   | `generator` | 만든 도구 이름(`<meta name="generator">`) |
   | `meta_prefix` | 문서 보관소가 읽을 분류 meta의 이름 머리. 예: `"docs"` → `docs:type`·`docs:tags`·`docs:title` |

4. **그림(필요할 때만)** — 시스템 구성·절차·주고받는 순서·일정·조직 구조처럼 글보다 그림이 빨리 읽히는 내용이면 `summary.json`의 `diagrams`(종류·제목·목적·그릴 내용)를 다이어그램 도구에 넘겨 독립 HTML로 만든다. 2개까지. 대부분의 녹음은 그림이 없어도 된다.
5. **HTML** —

   ```bash
   python render.py summary.json --meta meta.json --transcript transcript.txt \
     [--diagram "그림 제목=그림.html"] > 회의록.html
   ```

6. **확인** — 브라우저로 열어 제목·상대·숫자·할 일이 전사와 맞는지 본다.

## 화면

- 머리: 종류·시각·길이 칩, 제목, 상대·녹음한 사람, 한 줄 요약
- [정리 | 원문 전사] 탭. 그림은 정리 탭 '핵심' 다음에 들어가고 '크게 보기'로 화면 가득 볼 수 있다.
  - 탭은 CSS만으로 바뀐다(스크립트가 막힌 곳에서도 읽힌다). 주소 끝에 `#transcript`를 붙이면 전사 탭으로 열린다.
  - 전사 탭: 화자별 색, 경과 시각, 찾기(일치 강조), 화자 칩(말한 비율, 눌러서 거르기)
  - 인쇄하면 두 탭이 다 나온다.
- 머리의 `keywords` meta에 출처, 외부/내부 녹음, 미팅 종류, 상대 기관, 핵심어가 들어간다. 세미나·강연은 문서 종류가 '교육·발표 자료', 나머지는 '회의·결정 기록'이다.

## 자동화에 쓸 때

`prompt.md`를 모델의 시스템 지시로, `schema.json`을 구조화 출력 스키마로 주고, 받은 JSON을 `render.py`의 `render(data, meta, transcript, diagrams)`에 넘기면 된다. 긴 녹음은 구조화 출력 없이 받으면 JSON이 깨지기 쉽다.

## 지켜야 할 것

- 개인을 알아볼 수 있는 민감 정보(환자 이름·연락처 등)는 넣지 않는다. 사례는 "70대 환자"처럼 일반화한다.
- 이름·숫자가 불확실하면 고쳐 넣지 말고 `caveats`에 적는다. STT의 화자 구분은 자주 틀린다.
- 공유하기 전에 녹음·공유에 대한 상대방 동의와 회사 규정을 확인한다.
