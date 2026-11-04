# .release-showcase/config.json

저장소 루트의 `.release-showcase/config.json` 하나가 프로젝트마다 다른 것을 모두 담는다. 스크립트는 현재 폴더에서 git 루트를 찾아 이 파일을 읽는다. 파일이 없으면 앱 하나(`app`, 태그 접두사 `v`, 저장소 전체)로 본다.

```jsonc
{
  "repo": "owner/name",                 // GitHub 저장소 — PR 링크·릴리스 파일. 비우면 origin에서 읽는다
  "storiesDir": ".release-showcase/stories",
  "brandColor": "#1657b9",              // 강조색 — 밝은 변형은 자동으로 만든다
  "tone": "해요체",                     // 해요체 | 합니다체 | off — 문장 끝 검사
  "denyPattern": "vendor-a|vendor-b",   // 문서에 쓰지 않을 말(정규식, 대소문자 무시). 맞으면 오류
  "denyPatternFrom": {                  // 저장소에 이미 금칙 목록이 있으면 거기서 읽는다(denyPattern과 합침)
    "file": "app/scripts/lib/vendor-names.ts",
    "regex": "VENDOR_PATTERN =\\s*/(.+)/\\w*"   // 첫 그룹이 정규식 본문
  },
  "jargon": ["origin"],                 // 기본 내부 구현어 목록에 더할 말 — 맞으면 경고
  "includeDirectCommits": false,        // PR 없이 직접 push한 커밋도 변경 목록에 넣을지
  "notes": ["타이틀바의 `v0.0.0`은 테스트 고정 값이에요."],  // init이 팀 참고에 넣을 문장
  "apps": {
    "<앱 키>": {
      "label": "화면에 보일 앱 이름",
      "tagPrefix": "app-v",             // 이 앱의 정식 태그 접두사. 태그 = 접두사 + 버전
      "sourceDir": "app/",              // 변경 목록을 모을 경로 (비우면 저장소 전체)
      "goldensDir": "app/test/goldens", // 커밋된 스크린샷 폴더 — story의 `golden` 이름 기준
      "icon": "app/assets/icon.png",    // 머리말 아이콘 (태그 시점에서 꺼낸다, 선택)
      "uiDir": "app/src",               // 화면 문구 소스 — 글의 `문구`·**메뉴 › 경로**가 여기 있는지 본다
      "shipScopes": ["app", "ui"],      // conventional commit scope가 이 중 하나를 담아야 사용자 변경으로 본다
      "record": { … }                   // 녹화 (아래, 선택)
    }
  }
}
```

## 변경 목록이 읽는 커밋

- squash 머지: 제목 끝 `(#123)`이 PR 번호다.
- merge 커밋 머지: `Merge pull request #123 from …`과 본문 첫 줄(PR 제목)을 쓴다.
- 동기화·릴리스 PR을 squash로 넣은 커밋(`release…`): 본문의 `* 제목 (#N)` 줄을 각각 변경으로 본다.
- 분류: `feat` → 새 기능·바뀐 동작, `fix` → 고친 것, 나머지와 `shipScopes` 밖 scope → 내부 정비. 버전 올리기 커밋은 뺀다.
- conventional commit을 쓰지 않는 저장소는 전부 내부 정비로 모인다. 그럴 때는 하이라이트·minor 글이 변경 목록 역할을 한다.

## record — 태그 시점 코드로 녹화

`build --record`는 이렇게 돈다: 임시 `git worktree add --detach <태그>` → `cwd`에서 `install` → `serve`를 띄우고 `url`이 응답할 때까지 기다림 → `clips.json`의 흐름을 녹화 → 서버를 끄고 worktree를 지움.

```jsonc
"record": {
  "cwd": "app",                         // worktree 안에서 명령을 돌릴 폴더
  "install": "npm ci",                  // 의존성 설치 (선택)
  "serve": "npx vite --port {port} --strictPort",   // {port}는 빈 포트로 바뀐다
  "url": "http://127.0.0.1:{port}/",    // 녹화 기준 주소. clip의 path·query가 여기 붙는다
  "ready": "#root main",                // 이 선택자가 보이면 녹화 시작 (첫 로딩 구간은 잘라낸다)
  "viewport": { "width": 1280, "height": 800 },
  "scale": 1,                           // deviceScaleFactor — 작은 창은 2로 선명하게
  "browserArgs": []                     // 예: 마이크가 필요한 화면은 가짜 장치 플래그
}
```

### 앱 종류별 예

**웹앱 (dev 서버 + 목 데이터)**

```json
"record": {
  "cwd": "web", "install": "npm ci",
  "serve": "npm run dev -- --port {port} --strictPort",
  "url": "http://127.0.0.1:{port}/", "ready": "main",
  "viewport": { "width": 1280, "height": 800 }
}
```

백엔드가 필요하면 목 서버(MSW 등)를 켜는 dev 모드를 쓴다. 실제 서버·실데이터에 붙여 녹화하지 않는다.

**Storybook**

```json
"record": {
  "cwd": ".", "install": "npm ci",
  "serve": "npx storybook dev --ci --port {port}",
  "url": "http://127.0.0.1:{port}/iframe.html", "ready": "#storybook-root > *"
}
```

clip은 `"query": {"id": "settings--default", "viewMode": "story"}`처럼 스토리를 고른다.

**Electron 렌더러 (브라우저 캡처 하네스)**

렌더러를 일반 브라우저에 띄우는 vite 설정과 목 브리지가 있으면 그대로 쓴다.

```json
"record": {
  "cwd": "desktop", "install": "bun install --frozen-lockfile",
  "serve": "./node_modules/.bin/vite --config capture.vite.config.ts --host 127.0.0.1 --port {port} --strictPort",
  "url": "http://127.0.0.1:{port}/capture.html", "ready": ".app-root",
  "viewport": { "width": 380, "height": 560 }, "scale": 2,
  "browserArgs": ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]
}
```

**모바일 네이티브 (Flutter·iOS·Android)**

`record`를 두지 않는다. 시뮬레이터·에뮬레이터 화면 녹화(`xcrun simctl io booted recordVideo`, `adb shell screenrecord`)를 `.media/<id>.mp4`나 `.webm`으로 넣고, 필요하면 `.media/<id>.chapters.json`(`{"lead": 0, "chapters": [{"t": 0, "caption": "…"}]}`)을 손으로 적는다.

## 환경 변수

- `SHOWCASE_CHROMIUM`: 쓸 Chromium 실행 파일(기본: Playwright가 설치한 것).
- `SHOWCASE_PLAYWRIGHT_DIR`: playwright 패키지를 찾을 폴더. 보통은 스크립트가 정한다.
