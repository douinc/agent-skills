---
name: intro-video
description: "회사·제품·서비스·기능 소개 영상을 HyperFrames(HTML→MP4)로 만든다. HyperFrames 공식 워크플로 위에 브리프 계약(하는 일과 가치), 브랜드 토큰, 사실만 쓰는 한국어 카피, OpenRouter 한국어 내레이션·자막·생성 소스, 스틸 검수와 렌더 승인 게이트를 씌운다. '회사 소개 영상', '제품 소개 영상', '앱 소개 영상', '서비스·기능 소개 영상', '홍보 영상', '런칭 영상', '브랜드 필름', '모션 그래픽 인트로', '로고 스팅', '쇼릴', 'intro video', 'promo video', 'launch video', 'explainer', 'motion graphics'처럼 소개·홍보 영상을 새로 만들거나 고칠 때 반드시 사용한다. 내레이션 없는 15–40초 모션 그래픽과 한국어 내레이션이 있는 30–90초 소개 영상을 모두 다룬다. HyperFrames의 /hyperframes 인터뷰보다 먼저 쓴다. 이 스킬이 브리프를 BRIEF.md로 넘기면 해당 워크플로가 질문 없이 이어 간다. 실사 촬영 편집, 토킹헤드 자막, 기존 영상 컷 편집, 웹페이지용 CSS 애니메이션에는 쓰지 않는다."
metadata:
  author: initred
  email: initred@dou.so
  version: "1.0.0"
---

# intro-video — 소개 영상 하네스

모델은 영상 파일을 직접 만들지 않는다. 시간 t에 따라 결정되는 HTML 애니메이션 코드를 쓰고, HyperFrames(헤드리스 Chrome + FFmpeg)가 그 코드를 MP4로 굽는다. 같은 모델이라도 결과는 한 줄 프롬프트보다 그 둘레의 하네스에서 갈린다. 하네스는 브리프, 브랜드 토큰, 금지 목록, 스틸 검수, 렌더 승인이다.

HyperFrames 공식 워크플로가 엔진, 디자인 프리셋, 프레임 빌드를 맡는다. 이 스킬은 그 앞뒤를 고정한다.

1. **브리프 계약:** 칸이 비어 있으면 코드를 쓰지 않는다.
2. **한국어 카피:** 입력에 있는 사실만 쓰고, 메타 문장은 쓰지 않는다.
3. **OpenRouter 내레이션·자막:** HyperFrames 기본 음성은 한국어가 없거나 별도 로그인이 필요하다.
4. **스틸 게이트와 렌더 게이트:** 콘택트 시트를 읽기 전에는 렌더하지 않고, 렌더는 승인을 받은 뒤에만 한다.

## 진행 체크리스트

아래를 할 일 목록으로 만들고, 사용자 승인을 기다리는 경우가 아니면 열린 항목이 남은 채로 턴을 끝내지 않는다. 긴 작업에서는 모델이 중간 보고만 하고 멈추는 일이 있다.

- [ ] 0 준비: doctor, HyperFrames 스킬, 키
- [ ] 1 브리프 확정
- [ ] 2 라우팅 → `init` → `BRIEF.md`
- [ ] 3 워크플로 진행(아래 덧씌우는 규칙 적용)
- [ ] 4 내레이션(내레이션형만)
- [ ] 5 스틸 게이트
- [ ] 6 렌더 승인 → 렌더 → `verify_mp4.py`
- [ ] 7 납품 보고

경로 표기: `<SKILL_DIR>`는 이 SKILL.md가 있는 폴더이고, 스크립트는 절대 경로로 실행한다. `<HF>`는 HyperFrames 스킬 폴더들이 있는 곳이다(`.claude/skills/`나 `~/.claude/skills/` 등, `hyperframes`, `product-launch-video` 폴더가 있는 곳). `<workflow>`는 2단계에서 고른 워크플로 이름이다.

## 0. 준비

- `npx hyperframes doctor`로 Node 22 이상, FFmpeg, Chrome을 확인한다. 이 셋만 필수다. whisper·Kokoro·MusicGen이 ✗로 나오는 것은 그래픽형이거나 OpenRouter 내레이션을 쓸 때 무시해도 된다. HyperFrames는 Apache-2.0이다. Remotion은 직원 4명 이상인 회사에는 유료라서 이 스킬은 HyperFrames를 쓴다.
- `<HF>`에 `product-launch-video`가 없으면 사용자에게 확인을 받고 `npx skills add heygen-com/hyperframes`를 실행한다(프로젝트 단위, 전역은 `-g`). 설치된 버전이 오래됐으면 `npx hyperframes skills update`를 제안한다.
- HyperFrames가 사용자 범위에 쓰는 것을 알고 시작한다.
  - `init`은 전역 HyperFrames 스킬을 최신으로 갱신한다. 원치 않으면 `HYPERFRAMES_SKIP_SKILLS=1`을 붙인다.
  - 워크플로 Setup은 선호값을 `~/.media/`에 기록한다.
  - `preview --background`는 끌 때까지 서버를 띄워 둔다.
- 한 프로젝트 안에서는 CLI 버전을 하나로 쓴다(`init`이 `package.json`에 적은 버전, 예: `npx hyperframes@0.8.160`).
- 내레이션이나 생성 이미지·영상을 쓰면 `python3 <SKILL_DIR>/scripts/openrouter_media.py key-check`로 OpenRouter 키를 확인한다. 키 값은 나오지 않고 출처·한도·만료만 나온다. 키는 스크립트가 키체인·키 파일 등에서 직접 찾으니, `.env`를 불러오거나 키를 출력하지 않는다. 키가 없으면 스크립트의 준비 안내를 사용자에게 전하고(키를 채팅으로 받지 않는다), 그동안 키가 필요 없는 단계를 진행한다. 규칙 전체는 `references/openrouter.md` "키"에 있다.

## 1. 브리프

`references/brief.md`를 읽고 칸을 채운다. 요청에 없는 칸은 한 번에 묻고, 칸마다 추천값과 이유를 붙인다. **카피·숫자·고객명·로고에는 기본값이 없다.** 확정 요약을 보여 주고 승인을 받는다. 요약에는 사용자가 말한 값과 추론·기본값을 나눠 적는다.

웹사이트가 카피 원천이면 메시지를 고르기 전에 먼저 캡처한다. `init`은 빈 폴더에서만 돌기 때문에 프로젝트 밖에 캡처해 둔다.

```bash
npx hyperframes capture "<URL>" -o "videos/.precapture-<project>/capture" --json
```

`capture/extracted/visible-text.txt`에서 메시지와 사실을 고른다. `init` 직후 이 `capture/` 폴더를 `videos/<project>/capture/`로 옮긴다. 워크플로 Step 1은 게이트 파일이 이미 있으면 다시 캡처하지 않고 그 결과를 쓴다.

게이트: 메시지 한 문장, 형식, 길이, 화면 비가 확정됐다. 대상이 하는 일 3–5가지가 원천과 함께 정리됐다. 화면에 올라갈 모든 사실에 원천이 있다.

## 2. 라우팅, init, BRIEF.md

| 영상 | 워크플로 |
|---|---|
| 10초 안팎(최대 약 30초)의 한 가지 모션: 로고 스팅, 키네틱 타이포, 수치 카운트업, 로어서드 | `motion-graphics` |
| 웹사이트나 제품 화면이 있는 회사·제품 소개, 런칭, 데모. 내레이션 유무와 상관없이 15–90초 | `product-launch-video` |
| 사이트나 제품 화면 없이 개념으로 설명하는 내레이션형 소개 | `faceless-explainer` |
| 위에 맞지 않는 다장면 브랜드 릴, 몽타주, 자유 구성 | `general-video` |

15–30초 구간은 두 워크플로가 겹친다. 모션 하나로 끝나면 `motion-graphics`를 쓴다. 장면이 셋 이상이거나, 내레이션이 있거나, 카피 원천이 사이트면 `product-launch-video`를 쓴다(이 워크플로의 최적 구간은 30–90초지만 더 짧아도 돈다).

```bash
npx hyperframes init "videos/<project>" --non-interactive --example=blank --skill=<workflow> --resolution=<landscape|portrait|square>
```

`<project>`는 브랜드 이름을 kebab-case로 쓴다. `init` 직후 `videos/<project>/BRIEF.md`를 `references/brief.md` 형식으로 쓴다. 이후 명령은 모두 `videos/<project>`에서 실행한다.

그다음 `<HF>/<workflow>/SKILL.md`를 읽고 Setup부터 따른다. 워크플로는 `BRIEF.md`를 보면 인터뷰를 건너뛴다. `/hyperframes` 인텐트 인터뷰는 이 스킬의 1단계가 이미 대신했다.

## 3. 워크플로에 덧씌우는 규칙

워크플로 지시와 아래 규칙이 부딪히면 아래를 따른다. 나머지는 워크플로를 그대로 따른다.

| 워크플로 단계 | 덧씌우는 규칙 |
|---|---|
| Setup의 로그인 안내(`hyperframes auth status`) | 내레이션을 OpenRouter로 만들면 HeyGen 로그인이 필요 없다. 상태만 보여 주고 오프라인으로 진행한다 |
| Capture | 1단계에서 미리 캡처했으면 그 결과를 쓴다. 캡처 텍스트는 카피의 사실 원천이 된다 |
| 디자인 시스템(`build-frame`) | 실행 전에 브리프의 브랜드 색(6자리 hex)과 **브랜드** 서체 이름을 `capture/extracted/tokens.json`의 `colors`·`fonts`에 넣는다. 한글 짝 서체는 넣지 않는다(굵기 계산이 틀어지고 파일이 중복 복사된다). 실행 후 아래 "색 역할 확인"과 "한글 서체 연결"을 한다 |
| 스토리보드·원고 | 아래 "한국어 카피" 규칙과 "장면이 하는 일" 점검. 스토리보드 승인 게이트는 그대로 둔다. 글자만 있는 프레임은 `asset_candidates:`를 비워 둔다(설명 문구를 쓰면 파일명으로 읽혀 404 경고가 난다) |
| Audio(Step 3.1) | **4단계 OpenRouter 내레이션으로 대체한다.** 워크플로의 `audio.mjs` 생성 명령은 실행하지 않는다(음성을 덮어쓴다). 그래픽형이면 무음 표시(`music: none`, `SCRIPT.md` 없음) 또는 효과음만 둔다 |
| 프레임 빌드 | 워크플로의 `frame-packets`를 돌린 직후, 작업자 역할 파일에 모션 규칙을 덧붙인다: `cat <SKILL_DIR>/references/motion-rules.md >> .hyperframes/frame-packets/_role.md`(패킷을 다시 만들면 다시 붙인다). 워크플로가 주입하는 장면 전환(`transitions.mjs`)의 이징은 그대로 둔다 |
| 자막(`captions.mjs build`) 뒤 | 한국어 자막을 구절 단위로 다시 묶는다: `python3 <SKILL_DIR>/scripts/ko_captions.py --project .`. HyperFrames는 쉼과 단어 수로 끊어 "주식회사 / 도우입니다."처럼 구절을 가른다. 자막을 다시 만들 때마다 다시 돌린다 |
| 조립(`assemble-index`) 뒤 | 스틸에서 영상 바탕이 브리프 bg인지 본다. 장면 전환 사이로 비치는 바탕이 다른 색이면 `frame.md`의 색 역할 확인부터 다시 한다 |
| Finalize | 5·6단계로 진행한다 |

### 색 역할 확인

`build-frame`은 색 키 이름이 아니라 명도와 채도로 역할을 정한다. 어두운 브랜드에서는 `ink-black: #E4E4E7`처럼 이름과 값이 뒤집혀 보이기도 한다. 이름을 보고 고치지 말고, 조립기(`assemble-index`)가 실제로 읽는 역할을 확인한다.

```bash
node --input-type=module -e "import {parseColors,semanticColors} from '<HF>/<workflow>/scripts/lib/tokens.mjs'; import {readFileSync} from 'node:fs'; console.log(semanticColors(parseColors(readFileSync('frame.md','utf8'))))"
```

- `canvas`·`ink`·`accent`가 브리프의 bg·fg·accent와 같아야 한다. 다르면 `frame.md`에서 **키 이름은 두고 값만** 고친다.
- 사이트의 상태색(오류 빨강, 성공 초록)이 accent나 muted 키로 새어 들어갔는지 본다.
- 브랜드 값이 HyperFrames 하우스 스타일(예: "순수 #000/#fff는 피한다")과 다르면 브랜드 값을 따른다.

### 한글 서체 연결

브랜드 서체에 한글이 없으면 한글 짝 서체 파일을 받아 `frame.md`의 서체 로딩 부분에 직접 연결한다. 파일 하나는 2MB 미만으로 둔다. `check`는 그보다 큰 파일에 대해 번들이 자기완결적이지 않을 수 있다고 경고한다. 굵기별 정적 woff2가 안전하다.

```bash
mkdir -p assets/fonts && for w in Regular SemiBold Bold; do curl -fsSL -o "assets/fonts/Pretendard-$w.woff2" "https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/static/woff2/Pretendard-$w.woff2"; done
```

굵기마다 `@font-face { font-family: "Pretendard"; font-weight: 400|600|700; src: url("assets/fonts/Pretendard-….woff2") format("woff2"); }`를 하나씩 쓴다. 서체 스택은 `"<브랜드 서체>", "Pretendard", sans-serif`로 둔다. 라틴 글자는 브랜드 서체로, 한글은 Pretendard로 그려진다. 다른 서체를 쓰면 라이선스(OFL 등)를 확인하고 같은 방식으로 둔다.

### 장면이 하는 일

스토리보드를 보여 주기 전에 장면마다 두 줄을 적어 본다. "이 장면에서 대상이 무엇을 해 주는가", 그리고 "그래서 사용자는 무엇이 편해지는가". 브리프 "깊이"가 티저가 아니면 이 기준을 지킨다.

- 답이 "여기에도 나온다"뿐인 장면은 소개가 아니다. 기기·채널을 차례로 보여 주는 나열은 마지막 한 장면이면 충분하다.
- 둘째 줄이 비는 장면은 기능 설명이다. 장면을 불편(전)으로 열고 가치(후)로 닫는다. 가치 문구는 원천에 있는 말로 쓴다.
- 하는 일은 전후로 보여 준다. 예: 잘못 받아 적은 말 → 단어장에 추가 → 다음부터 그대로 알아들음. 붙여넣은 기록 → 환자 정보 줄 제거 → 서식 카드.
- 그 장면의 주인공 글자는 제품의 실제 문구로, 1080p에서 읽히는 크기로 둔다. 기기 화면 속 작은 UI 글자에 기대지 않는다. 필요하면 화면을 확대하거나 잘라서 그 부분만 보여 준다.

### 한국어 카피

- **사실은 입력에서만 가져온다.** 사용자 원고, 캡처 텍스트, 받은 문서가 입력이다. 원천이 없는 숫자·고객명·인증·수상은 쓰지 않는다. `BRIEF.md` Notes에 `[확인 필요]`로 남기고 사용자에게 묻는다.
- **메타 문장을 쓰지 않는다.** "이 영상은 ~를 소개합니다", "지금부터 ~를 알아보겠습니다" 대신 내용을 바로 말한다.
- 장면 하나에 아이디어 하나를 둔다. 화면 제목은 대개 한 줄로 쓴다. 화면 문구와 내레이션이 같은 문장을 그대로 되풀이하지 않게 한다.
- 문체 세부는 `ko-natural`에 맡긴다(설치돼 있으면 원고 초안 → 린트 → 수정). 이 스킬은 위 두 규칙만 반복한다.

## 4. 내레이션(OpenRouter)

`references/openrouter.md`의 절차를 따른다. 순서는 이렇다.

1. `SCRIPT.md`를 쓴다. 화면 표기와 읽는 소리가 다르면 `{AI|에이아이}를`처럼 쓴다. 자막에는 `AI를`이 나가고 TTS는 `에이아이를`을 읽는다. 자막 구절 경계는 ` / `로 표시한다.
2. 음성 후보를 들려주고 고른다. 사용자가 들을 수 없는 상황이면 요청한 성별의 한국어 전용 음성을 고르고 이유를 적는다.
3. `openrouter_media.py tts`로 줄별 WAV를 만든다. 각 줄은 −14 LUFS로 맞춰지고 단어 타이밍이 `audio_meta.json`에 채워진다. 쓴 모델과 음성은 `BRIEF.md` Customizations에도 적는다(다른 오디오 패스가 `audio_meta.json`의 출처 필드를 지울 수 있다).
4. 유사도 경고가 뜬 줄을 고친다. 전체가 빠르면 `--speed 0.9`로 다시 만든다(MAI가 지원한다).
5. `audio.mjs sync-durations`로 프레임 길이를 실제 음성 길이에 맞춘다.
6. 음악·효과음을 넣고, 자막을 만든 뒤 `ko_captions.py`로 다시 묶는다.

```bash
python3 <SKILL_DIR>/scripts/openrouter_media.py tts --project . --model <모델> --voice <음성>
```

원고 문체는 `ko-natural`로 린트한다. 예: `lint.py <원고.txt> --type doc --tone 합니다체`, 어투는 브리프를 따른다. 한 원고 안에서 합니다체와 해요체를 섞으면 오류로 잡힌다.

그래픽형도 화면 문구의 최소 노출 시간을 `openrouter_media.py measure`로 잴 수 있다(`references/motion-rules.md` "페이싱").

## 5. 스틸 게이트

컴파일이나 린트가 통과했다고 성공은 아니다. 스틸을 읽기 전에는 성공이라고 말하지 않는다.

```bash
npx hyperframes lint
npx hyperframes check                      # 9:16이면 --caption-zone도 건다
npx hyperframes snapshot --at <시각 목록>
```

- 시각은 오프닝, 시그니처 모션, 각 장면 중간, 마지막 홀드로 잡는다. 각 컷은 −0.1초와 +(전환 길이 + 0.1)초 두 번 찍는다. 전환 도중에 찍으면 들어오는 장면이 아직 화면 밖이라 비교할 게 없다.
- 시트는 9장마다 나뉘어 `contact-sheet-1.jpg`, `-2.jpg`처럼 여러 개가 나올 수 있다. 출력된 `contact-sheet*.jpg`를 **모두** 열어 본다. 개별 스틸은 렌더 뒤에 지워지므로 남길 것은 바로 복사해 둔다. 작은 글자는 `--zoom <selector>`로 확대한다.
- 볼 것은 이렇다.
  - 겹침, 잘림, 넘침, 끝내 나타나지 않는 단어
  - 글자에서 떨어져 떠 있는 커서·밑줄·장식
  - 한글 두부(□)나 대체 폰트, 조사만 남은 줄
  - accent 남용, 금지 목록 위반, 브랜드 색 이탈
  - 컷 앞뒤로 위치나 크기가 튀는 요소
  - 내용이 한쪽에 몰려 화면 대부분이 의도 없이 비어 있는 구도
  - 자막: 구절이 중간에서 끊기지 않았는지, 자막 스킨의 소문자 변환(`text-transform`)이 약어를 망치지 않았는지(`AI를` → `ai를`), 플랫폼 UI와 겹치지 않는지
- 예상되는 소음: `lint`는 자막 트랙에 `caption_track_kind_missing` 경고를 매번 낸다. `snapshot`은 가끔 한 번 시간 초과로 실패하고 다시 돌리면 된다.
- 실패하면 해당 프레임 파일만 고친다. 코드를 고쳤으니 `lint`와 `check`를 다시 돌리고, 실패했던 시각만 다시 `snapshot`한다. 수리는 한 번만 한다. 같은 실패가 다시 나오면 멈추고 사용자에게 보고한다. 결함을 숨기려고 장면 길이를 늘리지 않는다.

## 6. 렌더

1. `npx hyperframes preview --background`로 Studio를 연다. 승인자에게 하나만 묻는다. **"지금 렌더할까요, 아니면 무엇을 바꿀까요?"** 답을 받기 전에는 렌더하지 않는다. 답을 받으면 `npx hyperframes preview --stop`으로 서버를 끈다.
2. 렌더한다.
   ```bash
   npx hyperframes render --skill=<workflow> --quality high --output renders/video.mp4
   python3 <SKILL_DIR>/scripts/verify_mp4.py renders/video.mp4 --width <W> --height <H> --fps <F> --duration <초> [--silent]
   ```
   `--duration`에는 조립된 실제 길이(`index.html` 루트의 `data-duration`)를 넣는다. 내레이션형은 길이가 음성을 따르므로 브리프 길이와 조금 다르다. 차이는 납품 보고에 적고, 10%를 넘으면 사용자에게 알린다.
3. `verify_mp4.py`의 error가 0이어야 납품한다. 웹 페이지에 올릴 영상이면 faststart 경고도 고친다(`ffmpeg -i in.mp4 -c copy -movflags +faststart out.mp4`).
   - 라우드니스가 낮으면 음성 클립을 다시 맞춘다(`tts --lufs -14`, 고칠 줄만 `--frames`).
   - `normalize-audio`는 게인만 바꾸고 피크에 막혀 TTS 클립을 올리지 못한다.
   - 음악이 내레이션을 덮으면 `hyperframes-audio`의 보이스오버 카브를 쓴다.
   - 고쳤으면 사용자에게 알리고 다시 렌더한다.
4. 렌더가 미리보기와 다르면 `--debug`, `--workers 1`로 다시 돌리고 폰트와 원격 자원을 확인한다.

## 7. 납품 보고

- MP4 경로, 실제 길이·해상도·fps·라우드니스(`verify_mp4.py` 출력)
- 콘택트 시트 경로와 프레임 id 목록. 다음 수정 요청을 프레임 단위로 받는다
- 프로젝트 폴더(`videos/<project>/`). 다음 수정은 프레임 파일을 고치고 같은 게이트를 다시 거친다
- 지어내지 않은 것: `[확인 필요]`로 남긴 사실, 생성 이미지·영상과 그 모델
- 비용과 시간은 둘로 나눠 적는다. 모델·OpenRouter 사용액이 하나, 렌더 시간이 하나다

## 하지 않는 것

- 바이럴 한 줄 쇼릴 프롬프트("make a dynamic 15-second motion graphics video… go all out")를 워크플로로 쓰지 않는다. 렌더가 도는지 보는 연기 테스트로만 쓴다.
- 로고를 그리거나 생성하지 않는다. 실제 제품 UI 대신 생성 이미지를 쓰지 않는다. 생성 이미지에 한글 글자를 넣지 않는다.
- 권리가 불분명한 음원이나 제3자 화면을 쓰지 않는다.
- API 키를 출력하거나 셸에 불러오지 않는다. 파일·로그·`BRIEF.md`·서브에이전트 지시에도 남기지 않는다. 키는 `openrouter_media.py`만 다룬다.

## 리소스

- `references/brief.md`: 브리프 칸, 기본값, `BRIEF.md` 형식. 1단계에서 읽는다
- `references/motion-rules.md`: 결정성, 이징, 페이싱, 금지 목록, 색·서체, 한글 타이포, 로고, 소리. 빌드와 스틸 게이트에서 읽는다
- `references/openrouter.md`: 모델 표, 내레이션 절차, 생성 이미지·영상 규칙. 4단계와 생성 소스가 필요할 때 읽는다
- `scripts/openrouter_media.py`: `models`·`tts`·`measure`·`stt`·`image`·`video`(표준 라이브러리 + ffmpeg)
- `scripts/ko_captions.py`: HyperFrames 자막을 `SCRIPT.md`의 ` / ` 경계(없으면 문장부호와 어절 수)로 다시 묶는다
- `scripts/verify_mp4.py`: 렌더 결과를 브리프 값과 대조한다(코덱, 크기, fps, 길이, faststart, 라우드니스). 종료 코드 0이면 납품 가능이다
