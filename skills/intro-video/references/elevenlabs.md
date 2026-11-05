# ElevenLabs로 효과음·배경음악 만들기

## 왜 이 경로를 쓰나

OpenRouter 계정에 ZDR(데이터 무보존)을 강제하면, 효과음·음악 모델은 ZDR 엔드포인트가 없어서 HTTP 404(`zdr-violation-by-account`)로 거절되는 일이 잦다. ZDR은 사용자의 정책이므로 바꾸지 않는다. 대신 ElevenLabs API를 직접 부르는 길을 하나 더 둔다.

- 효과음: `POST /v1/sound-generation`(`eleven_text_to_sound_v2`, 0.5–30초, 루프 가능)
- 배경음악: `POST /v1/music`(`music_v1`, 3–600초, 기본 연주곡)

내레이션·자막·이미지는 그대로 OpenRouter로 만든다. ElevenLabs 키는 효과음과 음악에만 쓴다.

## 사용자에게 먼저 묻는다

1단계 브리프에서 소리 칸이 "효과음 켬"이거나 "음악을 새로 만든다"이면, ElevenLabs 키를 쓸지 한 번 묻는다. 사용자가 음악 파일을 직접 주고 효과음을 끄면 묻지 않는다. 키가 이미 저장돼 있어도 묻는다. 데이터가 OpenRouter가 아닌 다른 회사로 가기 때문이다.

AskUserQuestion이 있으면 그것으로, 없으면 다른 브리프 질문과 함께 한 번에 묻는다.

> 효과음·배경음은 OpenRouter의 ZDR(데이터 무보존) 설정 때문에 막히는 경우가 많습니다. ElevenLabs API 키를 따로 써서 만들까요?
> - **ElevenLabs 키 사용(추천):** 효과음·음악을 설명문으로 생성합니다. 설명문(예: "짧고 깨끗한 UI 클릭음")이 ElevenLabs로 전송되고, ElevenLabs는 기본적으로 요청을 기록합니다(무보존 모드는 엔터프라이즈 전용). 키가 없으면 설정 방법을 안내합니다.
> - **쓰지 않음:** HyperFrames `media-use` 번들 효과음, 직접 주신 음원 파일, 또는 무음으로 갑니다.

- 답은 `BRIEF.md` `## Customizations`에 `효과음·음악: ElevenLabs(키 사용 승인 <날짜>)` 또는 `효과음·음악: ElevenLabs 안 씀 → <대안>`으로 적는다. 다음 수정 때 다시 묻지 않는다.
- "쓰지 않음"이면 이 문서의 나머지는 건너뛴다. OpenRouter로 효과음 생성을 다시 시도하지 않는다. ZDR 계정에서는 같은 이유로 또 막힌다.
- 설명문에는 공개 전 제품명, 고객명, 내부 정보를 넣지 않는다. 소리의 질감만 묘사한다.

## 키

키는 `elevenlabs_audio.py`가 직접 찾는다. OpenRouter 키와 규칙이 같다(`openrouter.md` "에이전트가 지킬 것"). 키를 셸에 불러오거나 출력하지 않고, 채팅으로 받지 않는다.

### 처음 한 번 준비하기

1. **이 스킬 전용 키를 새로 만든다.** ElevenLabs 웹 → 왼쪽 아래 프로필 → **Developers → API Keys**(https://elevenlabs.io/app/settings/api-keys) → **Create API Key**.
   - 이름: `intro-video`
   - **권한(Restrict key):** 켠다. **Sound Effects**와 **Music**만 허용한다. `key-check`로 플랜·사용량까지 보려면 **User**를 읽기(Read)로 둔다. 음성 복제·Voice Library·Workspace 관리 같은 권한은 끈다.
   - **크레딧 한도(Credit quota):** 건다. 예: 월 10,000 크레딧. 효과음은 초당, 음악은 길이에 비례해 크레딧이 든다.
   - 생성 직후 한 번만 키가 보인다. 바로 아래 2번으로 저장한다.
2. **키를 저장한다.** 위에서부터 권장한다.

   | 방법 | 명령 | 메모 |
   |---|---|---|
   | macOS 키체인 | `security add-generic-password -U -s elevenlabs -a intro-video -w` | 프롬프트에 붙여 넣는다. 화면·셸 기록에 남지 않는다 |
   | Linux 키 저장소 | `secret-tool store --label="ElevenLabs intro-video" service elevenlabs account intro-video` | 프롬프트에 붙여 넣는다 |
   | 키 파일 | `mkdir -p ~/.config/elevenlabs && (umask 077; read -rs k && printf '%s' "$k" > ~/.config/elevenlabs/key; unset k)` | 레포 밖, 권한 600. 다른 사용자가 읽을 수 있으면 스크립트가 거부한다 |
   | CI | 비밀 저장소에서 `ELEVENLABS_API_KEY` 또는 `ELEVENLABS_API_KEY_FILE`로 주입 | 사람이 쓰는 셸에는 두지 않는다 |

   Claude Code에서는 사용자가 프롬프트에 `! security add-generic-password -U -s elevenlabs -a intro-video -w`를 입력하면 그 자리에서 붙여넣기 프롬프트가 뜬다. 에이전트가 대신 실행하지 않는다(키가 대화에 들어온다).
3. **확인한다.**
   ```bash
   python3 <SKILL_DIR>/scripts/elevenlabs_audio.py key-check
   ```
   어디서 찾았는지, 키의 끝 4자리, 플랜, 이번 주기 크레딧 사용량·한도·초기화일이 나온다. User 권한을 끈 키면 "생성은 된다"는 메모만 나온다.

찾는 순서는 `ELEVENLABS_API_KEY` → `ELEVENLABS_API_KEY_FILE` → OS 키 저장소(service `elevenlabs`, account는 `ELEVENLABS_KEY_ACCOUNT`, 기본 `intro-video`) → `${XDG_CONFIG_HOME:-~/.config}/elevenlabs/key`다. 레포의 `.env`는 읽지 않는다.

키가 없으면 스크립트가 보여 주는 준비 안내를 사용자에게 그대로 전하고, 저장할 때까지 키가 필요 없는 단계(스토리보드, 프레임 빌드, 내레이션)를 먼저 진행한다. 키가 샜을 때는 대시보드에서 그 키를 지우고 새 키를 같은 방법으로 저장한다(키체인은 `-U`로 덮어쓴다).

## 라이선스

ElevenLabs 무료 플랜 결과물은 상업적 사용이 제한될 수 있다. 소개 영상은 대개 상업적 용도다. `key-check`의 `tier`가 `free`이면 납품 전에 사용자에게 플랜을 확인하고, 납품 보고에 플랜을 적는다. 음악 생성 API는 플랜에 따라 막힐 수 있다. 그러면 오류 안내대로 사용자에게 알리고 사용자 음원이나 무음으로 간다.

## 효과음

스토리보드의 `sfx:` 큐마다 하나씩 만든다. 같은 소리를 여러 번 쓰면 파일 하나를 여러 항목으로 등록한다.

```bash
python3 <SKILL_DIR>/scripts/elevenlabs_audio.py sfx "soft UI click, short, clean, dry, no reverb" \
  -o assets/audio/sfx-click.wav --duration 0.5 --project . --frame 2 --offset 0.85
```

- 설명문은 영어로, 질감·길이·공간감을 쓴다. 예: `airy whoosh, fast, subtle`, `low soft impact, warm, short tail`, `gentle sparkle chime, high, airy`. 음악적 요소(멜로디)는 넣지 않는다. 배경음악과 부딪힌다.
- `--duration`을 준다. 안 주면 모델이 길게 만들어 다음 컷까지 번진다. UI 소리 0.3–0.8초, 전환 0.6–1.2초, 로고 히트 1–2초가 출발점이다.
- `--project/--frame/--offset`을 주면 `audio_meta.json`의 `sfx`에 `{"frame", "file", "offset_s", "duration_s", "volume", "source": "host"}`로 추가된다. `source: host` 항목은 HyperFrames 오디오 패스(`fetch-sfx` 등)가 다시 돌아도 남고, 그 프레임에는 번들 효과음을 덧붙이지 않는다.
- 프레임 길이가 `sync-durations`로 바뀌었으면 `offset_s`를 다시 확인한다.
- 효과음은 내레이션보다 작게 둔다. 내레이션이 있는 구간은 `volume` 0.4–0.6에서 시작해 렌더 뒤 들어 보고 맞춘다.

## 배경음악

```bash
python3 <SKILL_DIR>/scripts/elevenlabs_audio.py music \
  "sophisticated upbeat minimal electronic, warm electric piano, soft sidechained pads, 112 bpm, clean ending" \
  -o assets/audio/bed.wav --length 32 --project .
```

- 길이는 조립된 영상 길이(`index.html` 루트의 `data-duration`)에 1–2초를 더한다. 끝은 렌더에서 페이드한다.
- 기본은 연주곡(`force_instrumental`)이다. 한국어 내레이션 영상에 보컬을 넣지 않는다. 브리프가 보컬을 원할 때만 `--vocals`를 쓴다.
- 설명문에 실존 아티스트·곡·브랜드 이름을 쓰지 않는다. 장르, 분위기, 악기, bpm, 구조("clean ending", "builds at 20s")로 쓴다.
- `--project`를 주면 `audio_meta.json`의 `bgm`이 `{"path", "volume", "source": "host"}`로 바뀌고 `bgm_pending`이 `false`가 된다. 스토리보드 frontmatter는 `music: none`으로 둔다(워크플로가 음악을 다시 찾지 않게).
- 음악이 생기면 `npx hyperframes beats assets/audio/bed.wav`로 비트를 뽑아 컷을 맞출 수 있다(`motion-rules.md` "소리"). 내레이션 아래는 `hyperframes-audio`의 보이스오버 카브로 누른다.
- 마음에 들지 않으면 한두 번만 다시 만든다. 매번 크레딧이 든다. 생성 전에 개수와 대략의 크레딧을 사용자에게 알린다.

## 기록

생성한 파일마다 `BRIEF.md` `## Assets`에 `경로 — ElevenLabs <모델>, 설명문 요약, 생성일`을 한 줄로 남긴다. 음악은 스크립트 출력의 `song_id`도 적는다. 납품 보고에는 ElevenLabs 플랜과 작업 전후 `key-check` 크레딧 사용량을 OpenRouter 사용액과 따로 적는다.
