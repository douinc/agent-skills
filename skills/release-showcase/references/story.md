# story.json · clips.json

`showcase init <태그>`가 `<storiesDir>/<태그>/story.json` 초안을 만든다. `TODO`가 남아 있으면 `check`가 오류를 낸다.

## story.json

```jsonc
{
  "app": "web",                       // config apps의 키
  "tag": "web-v2.4.0",                // 이번 정식 태그
  "base": "web-v2.3.2",               // 사용자가 직전에 쓰던 정식 태그
  "versionLabel": "2.4.0",            // 화면에 보일 버전 (기본: 태그에서 접두사를 뺀 값)
  "baseLabel": "2.3.2",
  "title": "가계부 2.4.0 — 무엇이 달라졌나",
  "date": "2026-03-02", "channel": "production",
  "tagline": "한 문장 요약 — 사용자가 얻는 것",
  "context": "이 문서가 어느 범위를 다루는지 한두 문장",
  "audience": [{ "who": "처음 쓰는 분", "what": "할 일이 있는지 없는지 먼저" }],
  "highlights": [{
    "id": "recurring",                // 영문 kebab — 목차 링크·검수 화면 이름
    "short": "반복 지출",              // 목차에 보일 짧은 이름
    "badge": "새 기능",
    "badgeTone": "new",               // new | better | fix | safe
    "who": ["모든 사용자"],
    "layout": "side",                 // side(글 옆에 그림, 기본) | wide(그림이 넓게 — 영상·단계)
    "title": "…", "lead": "…",
    "points": ["…"],
    "howTitle": "이렇게 써 보세요",     // 기본값. 할 일이 아니라 알아 둘 점이면 "알아 두면 좋아요"
    "how": ["…"],
    "prs": ["412", "418"],
    "media": { "kind": "…" }          // 아래 표
  }],
  "minor": [{ "title": "…", "body": "…", "media": { … } }],   // 작은 카드 — 그림은 선택
  "notes": [{ "title": "…", "body": ["…"] }],               // 접힌 팀 참고 — 고객에게 안 갈 내부 맥락
  "downloadNote": "설치·업데이트 안내 한 문장 (비우면 파일 목록만)"
}
```

문자열 안의 작은 마크업: `**굵게**`, `` `화면 문구` ``(영문만이면 명령으로 보고 고정폭), `[글](https://…)`, `#123`(PR 링크).

### 그림 지정

그림 하나는 셋 중 하나로 가리킨다.

| 키 | 뜻 | 기본 ref |
|---|---|---|
| `golden` | config `goldensDir` 안의 파일 이름 | 이후는 `tag`, compare의 before는 `base` |
| `file` | 저장소 루트 기준 경로 | 같음 |
| `local` | story 폴더 기준 경로 (예: `.media/shot.png`) — 저장소에 없는 그림 | 없음 |

`ref`에 `tag`·`base` 또는 임의의 git ref를 줄 수 있다. `caption`은 그림 아래 설명, `showVersion: true`는 그림 위에 버전 표시.

### media 종류

| kind | 쓰임 | 필드 |
|---|---|---|
| `image` | 화면 한 장 | 그림 + `caption` |
| `row` | 여러 장 나란히 | `items: [그림…]` |
| `compare` | 이전·이후 비교 (나란히·한쪽 보기 토글) | `before`, `after`(각각 그림, `label`로 버전 표시를 바꿀 수 있음), `caption` |
| `steps` | 흐름을 단계별로 넘겨 보기 | `items: [{ label, title, caption, …그림 }]` |
| `tabs` | 같은 화면의 상태별 모습 | `items: [{ label, caption, …그림 }]` |
| `video` | 녹화 영상 + 챕터 | `clip`(clips.json id 또는 `.media/<id>.webm`), `poster`(그림) |
| `flow` | 이전·이후 절차 비교 흐름도 | `lanes: [{ title, tone: bad\|good, steps: [{ text, tone: pain\|win\|skip }] }]`, `caption` |
| `stack` | 위 블록 여러 개를 세로로 | `items: [media…]` |

고르는 법: 화면이 바뀜 → `compare` · 여러 화면을 거치는 새 흐름 → `video` + `steps`(stack) · 로딩·실패 같은 상태 → `tabs` · 사용자가 거치던 절차가 줄거나 바뀜 → `flow` · 화면 하나로 충분 → `image`.

## clips.json

```jsonc
[{
  "id": "add-recurring",
  "path": "settings/recurring",         // config record.url 기준 상대 경로 (선택)
  "query": { "fixture": "two-cards" },  // 주소 뒤에 붙일 쿼리 (선택) — 목 데이터 상태를 고를 때
  "ready": "main h1",                   // 이 앱의 record.ready 대신 쓸 선택자 (선택)
  "introCaption": "설정 홈", "intro": 1500,    // 첫 화면 챕터와 머무는 시간(ms)
  "steps": [
    { "role": "button", "name": "반복 지출 추가", "caption": "① 추가 누르기" },
    { "role": "textbox", "name": "이름", "action": "type", "value": "월세" },
    { "text": "매월", "pause": 1200 },
    { "role": "option", "name": "1일" },
    { "role": "button", "name": "저장", "dialog": "반복 지출" , "caption": "② 저장" },
    { "selector": "[data-test=toast]", "action": "hover" },
    { "press": "Escape" },
    { "wait": 1000 }
  ]
}]
```

단계 하나는 대상을 셋 중 하나로 찾는다.

- `text`: 화면 글자 정확 일치(`exact: false`면 포함).
- `role` + `name`: 접근성 역할과 이름 — `button`·`textbox`·`option`·`checkbox`·`link`·`tab` 등. `exact: false`면 이름 포함. `dialog`에 대화상자 이름(또는 `true`)을 주면 그 안에서만 찾는다.
- `selector`: CSS 선택자 — 이름이 없는 요소에만.

`action`: `click`(기본) · `type`(한 글자씩, 줄바꿈은 Shift+Enter) · `fill`(한 번에) · `hover` · `scroll`. 그 밖에 `{ "press": "키" }`, `{ "wait": ms }`. 모든 단계에 `caption`(이 단계부터 시작하는 챕터)과 `pause`(단계 뒤 머무는 ms, 기본 900)를 붙일 수 있다.

찾지 못하면 `.media/<id>.fail.png`에 그 순간 화면을 남기고 멈춘다.
